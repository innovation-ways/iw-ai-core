"""QAEngine — context-aware RAG Q&A engine with streaming response and conversation history."""

from __future__ import annotations

import asyncio
import threading
from collections import OrderedDict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import httpx
from llama_index.core.llms import ChatMessage
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from sqlalchemy import func, select, text

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.orm import Session

    from orch.rag.config import CodeUnderstandingConfig

from orch.rag.chat_repo import truncate_messages_to_budget as _truncate_messages_to_budget
from orch.rag.condense import condense_query as _condense_query
from orch.rag.evidence import EvidenceBundle

# Memory / token-budget constants
HISTORY_SOFT_BUDGET_TOKENS: int = 3000
HISTORY_HARD_BUDGET_TOKENS: int = 6000

SYSTEM_PROMPT_HARDENING: str = (
    "On contradictions in the user's statements, trust the most recent one. "
    "Do not claim to remember anything not present in the provided "
    "conversation history."
)

RENDER_CACHE_MAX: int = 64
RENDER_CACHE_TTL: timedelta = timedelta(minutes=10)


def _module_path_to_file_prefix(module_path: str) -> str:
    """Normalize a module path (dotted Python name or filesystem path) to a filesystem
    prefix suitable for a LanceDB ``file_path LIKE '<prefix>/%'`` filter.

    Examples:
        ``orch.daemon``   -> ``orch/daemon``
        ``orch/daemon/``  -> ``orch/daemon``
        ``orch.rag.qa``   -> ``orch/rag/qa``
        ``dashboard``     -> ``dashboard``

    Leading/trailing slashes are stripped. If the path already contains ``/`` it is
    assumed to be a filesystem path and dots are preserved (e.g. ``docs/readme.md``).
    """
    p = module_path.strip().strip("/")
    if not p:
        return ""
    if "/" not in p and "." in p:
        p = p.replace(".", "/")
    return p


class QAEngine:
    """
    Context-aware RAG Q&A engine with streaming response and conversation history.

    Conversation history is passed in on each call — this class is stateless.
    """

    TOP_K: int = 8

    WORKITEM_RELEVANCE_FILTER = (
        "## Work Item Context\n\n"
        "The following work items may be related to the user's question. Decide\n"
        "which ones actually address it. Cite only the items whose reasoning answers\n"
        "the question. If an item touched related code but does not address the\n"
        "question (for example, it changed shape while the user asked about\n"
        "colour), omit it from your citations.\n\n"
    )

    def __init__(self, project_id: str, config: CodeUnderstandingConfig) -> None:
        self.project_id = project_id
        self.config = config
        self._render_cache: OrderedDict[str, tuple[datetime, object, str]] = OrderedDict()
        self._render_cache_lock = threading.RLock()

    async def answer_stream(
        self,
        question: str,
        context_level: str,
        context_doc_id: str | None,
        conversation_history: list[dict[str, str]],
        session: Session,
        module_path: str | None = None,
        module_name: str | None = None,
        context_chips: list[str] | None = None,
        symbol_hint: str | None = None,  # noqa: ARG002
        workitem_section: str = "",
        conversation_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream answer tokens for the given question using RAG retrieval.

        1. Condense the question using conversation history (if len >= 2 turns)
           — only used for embedding/retrieval; original question used in answer turn.
        2. Embed condensed query via Ollama embedding model
        3. Retrieve top-k chunks from LanceDB (filtered by module_path if context_level == "module")
        4. Load context_doc content from DB if context_doc_id provided
        5. Build system prompt with context doc + retrieved chunks + hardening lines
        6. Load conversation history from DB (if conversation_id) using token-budget truncation
        7. Prepend rolling_summary as synthetic system note if present
        8. Stream response tokens via Ollama LLM

        When conversation_id is provided, history is loaded from DB and the
        conversation_history argument is ignored (server is source of truth).
        When conversation_id is None, falls back to conversation_history for
        backwards compatibility with existing tests.
        """
        embed_model = self.config.resolved_embed_model()
        ollama_url = self.config.ollama_url

        # Determine history for condense step
        if conversation_id is not None:
            from orch.rag import chat_repo

            history_for_condense, rolling_summary = chat_repo.list_messages_for_context(
                session,
                conversation_id=conversation_id,
                soft_budget_tokens=HISTORY_SOFT_BUDGET_TOKENS,
            )
        else:
            history_for_condense = conversation_history  # type: ignore[assignment]
            rolling_summary = None

        # Condense query before embedding (only used for retrieval; original question
        # goes to the LLM in the final user turn)
        condensed_question = _condense_query(
            history_for_condense,  # type: ignore[arg-type]
            question,
            self._make_llm(ollama_url),
            db_session=session,
            conversation_id=conversation_id,
        )

        embedding_instance = OllamaEmbedding(
            model_name=embed_model,
            base_url=ollama_url,
        )
        embedding_vector = await asyncio.to_thread(
            embedding_instance.get_query_embedding, condensed_question
        )

        db_path = f"{self.config.index_path}/{self.project_id}/vectors/"
        table_name = f"code_{self.project_id.replace('-', '_')}"

        chunks: list[str] = []
        fallback_triggered = False

        try:
            import lancedb

            db = lancedb.connect(db_path)
            table = db.open_table(table_name)

            seed_filter = "file_path != '__iwcore_seed__'"
            if context_level == "module" and module_path:
                prefix = _module_path_to_file_prefix(module_path)
                safe_prefix = prefix.replace("'", "''")
                query = (
                    table.search(embedding_vector)
                    .where(f"file_path LIKE '{safe_prefix}/%' AND {seed_filter}")
                    .limit(self.TOP_K)
                )
            else:
                query = table.search(embedding_vector).where(seed_filter).limit(self.TOP_K)

            results = query.to_pandas()
            chunks = list(results["text"].tolist())

            if context_level == "module" and module_path and not chunks:
                fallback_triggered = True
                fallback_query = table.search(embedding_vector).where(seed_filter).limit(self.TOP_K)
                fallback_results = fallback_query.to_pandas()
                chunks = list(fallback_results["text"].tolist())
        except Exception:
            import logging

            logging.warning("LanceDB unavailable, skipping retrieval")

        context_doc_content = ""
        if context_doc_id:
            from orch.db.models import ProjectDoc

            result = await asyncio.to_thread(
                session.execute,
                select(ProjectDoc).where(ProjectDoc.id == context_doc_id),
            )
            doc = result.scalar_one_or_none()
            if doc:
                context_doc_content = doc.content or ""

        system_prompt = self._build_system_prompt(
            context_doc_content,
            chunks,
            module_path,
            module_name,
            fallback_triggered,
            context_chips,
            workitem_section,
        )

        # Build message stack: system prompt + optional rolling_summary
        # note + truncated history + original question
        messages = [ChatMessage(role="system", content=system_prompt)]

        # Prepend rolling_summary as synthetic system note if present
        if rolling_summary:
            messages.append(
                ChatMessage(
                    role="system",
                    content=f"Earlier in this conversation:\n{rolling_summary}",
                )
            )

        # history_for_condense is already token-budget truncated
        for msg in history_for_condense:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            messages.append(ChatMessage(role=role, content=content))

        messages.append(ChatMessage(role="user", content=question))

        llm = Ollama(
            model=self.config.resolved_llm_model(),
            base_url=ollama_url,
        )

        try:
            stream = await llm.astream_chat(messages)
            async for chunk in stream:
                yield chunk.delta
        except (httpx.ConnectError, ConnectionRefusedError):
            yield "__ERROR__:Local AI unavailable. Check that Ollama is running."

    RENDERING_CAPABILITIES_BLOCK: str = (
        "## Rendering Capabilities\n\n"
        "The chat UI renders your markdown response inline. Use these features "
        "directly when they help — never tell the user to paste code into an "
        "external editor or live-preview site:\n"
        "- Mermaid diagrams — emit a fenced ```mermaid block. The UI renders it "
        "as an interactive SVG with expand and retry controls. Supported types: "
        "flowchart, sequenceDiagram, classDiagram, erDiagram, stateDiagram-v2, gantt.\n"
        "- D2 diagrams — emit a fenced ```d2 block. D2 excels at architecture, "
        "network topology, and multi-container system diagrams (rendered server-side "
        "as SVG; falls back to source if the d2 binary is absent).\n"
        "- Tables — use GitHub-flavored markdown tables when comparing multiple "
        "items side by side.\n"
        "- Code — use fenced blocks with a language tag (```python, ```typescript, "
        "etc.) so syntax highlighting applies.\n\n"
        "- Callouts — use GitHub-style blockquote callouts for special content:\n"
        "  > [!NOTE] supplementary context or background that doesn't interrupt main flow\n"
        "  > [!TIP] best practice, shortcut, or recommended approach\n"
        "  > [!WARNING] non-obvious behavior, footgun, or constraint the reader must not miss\n"
        "  > [!DANGER] destructive or irreversible action — use very sparingly\n"
        "  The UI renders these as colored admonition blocks. Use [!WARNING] when describing "
        "  a non-obvious gotcha. Reserve [!DANGER] for operations that cannot be undone. "
        "  Do NOT use [!DANGER] for normal informational notes.\n\n"
        "- Structure — format multi-topic answers with H2 (##) headings. Use bullet lists "
        "  for enumerations of 3 or more items. Avoid dense paragraphs when a list would be "
        "  clearer. Do not start every answer with a heading — only use headings when the "
        "  response covers 2 or more distinct sections.\n\n"
        "Do not preface answers with disclaimers about being a text-based AI; "
        "emit diagrams and code directly in the response. If a diagram would make "
        "an architectural relationship clearer than prose, include it proactively.\n\n"
    )

    DIAGRAM_DIRECTIVE_BLOCK: str = (
        "## Respond With a Diagram\n\n"
        "The user invoked /diagram. Make the primary content of your answer a "
        "Mermaid diagram in a fenced ```mermaid code block. Choose the type that "
        "best fits the question:\n"
        "- sequenceDiagram — for request/response flows, interactions over time\n"
        "- classDiagram — for class/interface hierarchies and relationships\n"
        "- erDiagram — for database schema / table relationships\n"
        "- stateDiagram-v2 — for state machines / status transitions\n"
        "- flowchart — for architecture, component wiring, control flow (default)\n"
        "Keep accompanying prose to one short paragraph before and a brief caption "
        "after. Do not apologize or suggest external tools.\n\n"
    )

    def _build_system_prompt(
        self,
        context_doc_content: str,
        chunks: list[str],
        module_path: str | None = None,
        module_name: str | None = None,
        fallback_triggered: bool = False,
        context_chips: list[str] | None = None,
        workitem_section: str = "",
    ) -> str:
        """
        Build the system prompt with optional module-focus block, optional retrieval-note block,
        architecture context, relevant code excerpts, and UI rendering capabilities.

        The module block is emitted only when module_path is non-empty.
        The retrieval-note block is emitted only when fallback_triggered is True.
        The diagram directive block is emitted only when "diagram" appears in context_chips.
        """
        module_block = ""
        if module_path:
            if module_name:
                module_block = f"""## Current Focus — Module

The user is currently viewing the `{module_path}` module (\"{module_name}\").
Prioritize this module in your answer. If the question is clearly about this module,
ground your answer in the excerpts below and the module's role in the architecture.

"""
            else:
                module_block = f"""## Current Focus — Module

The user is currently viewing the `{module_path}` module.
Prioritize this module in your answer. If the question is clearly about this module,
ground your answer in the excerpts below and the module's role in the architecture.

"""

        retrieval_note = ""
        if fallback_triggered:
            retrieval_note = """## Retrieval Note

No indexed content matched the current module on the first retrieval pass.
The excerpts below come from a project-wide fallback search. If the excerpts do not
cover the module directly, say so explicitly in your answer.

"""

        ctx = context_doc_content if context_doc_content else "(No architecture document available)"

        excerpts = ""
        for chunk in chunks:
            excerpts += f"---\n{chunk}\n"

        diagram_block = ""
        if context_chips and "diagram" in context_chips:
            diagram_block = self.DIAGRAM_DIRECTIVE_BLOCK

        workitem_block = f"{workitem_section}\n\n" if workitem_section else ""

        return (
            "You are a codebase expert assistant. "
            "Answer questions about the codebase accurately and concisely.\n\n"
            f"{module_block}"
            f"{retrieval_note}"
            "## Architecture Context\n\n"
            f"{ctx}\n\n"
            f"{workitem_block}"
            "## Relevant Code Excerpts\n\n"
            f"{excerpts}\n\n"
            f"{self.RENDERING_CAPABILITIES_BLOCK}"
            f"{diagram_block}"
            "Answer the user's question based on the above context. "
            "If the context does not contain enough information, say so clearly.\n\n"
            f"{SYSTEM_PROMPT_HARDENING}"
        )

    def _truncate_history(self, history: list[dict[str, str]]) -> list[dict[str, str]]:
        """Token-budget truncation — drops oldest messages until within HISTORY_SOFT_BUDGET_TOKENS.

        Always preserves the last 2 messages (correctness over budget).
        Kept for backwards compatibility with call sites that pass dict messages.
        For DB-backed path, use chat_repo.list_messages_for_context() directly.
        """
        return _truncate_messages_to_budget(history, HISTORY_SOFT_BUDGET_TOKENS)  # type: ignore[arg-type,return-value]

    def _make_llm(self, ollama_url: str) -> Ollama:
        return Ollama(
            model=self.config.resolved_llm_model(),
            base_url=ollama_url,
        )

    def _cache_get(self, render_id: str) -> object | None:
        with self._render_cache_lock:
            if render_id not in self._render_cache:
                return None
            timestamp, bundle, question = self._render_cache[render_id]
            if datetime.now(UTC) - timestamp > RENDER_CACHE_TTL:
                del self._render_cache[render_id]
                return None
            self._render_cache.move_to_end(render_id)
            return bundle

    def _cache_put(self, render_id: str, bundle: object, question: str) -> None:
        with self._render_cache_lock:
            self._evict_expired_locked()
            if len(self._render_cache) >= RENDER_CACHE_MAX:
                self._render_cache.popitem(last=False)
            self._render_cache[render_id] = (datetime.now(UTC), bundle, question)

    def _evict_expired_locked(self) -> None:
        now = datetime.now(UTC)
        expired = [
            rid for rid, (ts, _, _) in self._render_cache.items() if now - ts > RENDER_CACHE_TTL
        ]
        for rid in expired:
            del self._render_cache[rid]

    async def _retrieve_evidence_bundle(
        self,
        project_id: str,
        question: str,
        session: Session,
        _context_level: str = "",
    ) -> EvidenceBundle:
        from orch.db.models import WorkItem
        from orch.rag.evidence import DocChunk

        now = datetime.now(UTC)
        bundle = EvidenceBundle(question=question, retrieval_cutoff=now)

        embed_model = self.config.resolved_embed_model()
        ollama_url = self.config.ollama_url

        db_path = f"{self.config.index_path}/{project_id}/vectors/"
        table_name = f"docs_{project_id.replace('-', '_')}"

        try:
            embedding_instance = OllamaEmbedding(model_name=embed_model, base_url=ollama_url)
            embedding_vector = await asyncio.to_thread(
                embedding_instance.get_query_embedding, question
            )

            import lancedb

            ldb = lancedb.connect(db_path)
            if table_name in ldb.table_names():
                tbl = ldb.open_table(table_name)
                results = tbl.search(embedding_vector).limit(20).to_pandas()
                for _, row in results.iterrows():
                    score = row.get("score", 0.0)
                    bundle.doc_chunks.append(
                        DocChunk(
                            work_item_id=str(row.get("work_item_id", "")),
                            work_item_type=str(row.get("work_item_type", "")),
                            work_item_title=str(row.get("work_item_title", "")),
                            text=str(row.get("text", "")),
                            score=1 - score if score is not None else 0.0,
                        )
                    )
        except Exception:
            import logging

            logging.warning("LanceDB doc index unavailable, skipping semantic retrieval")

        tsq = func.plainto_tsquery("english", question)
        stmt = (
            select(
                WorkItem,
                func.ts_rank(WorkItem.functional_doc_search, tsq).label("rank"),
            )
            .where(WorkItem.project_id == project_id)
            .where(WorkItem.functional_doc_search.isnot(None))
            .where(WorkItem.functional_doc_search.op("@@")(tsq))
            .order_by(text("rank DESC"))
            .limit(20)
        )
        fts_result = session.execute(stmt)
        for row in fts_result.all():
            bundle.fts_items.append(row[0])

        return bundle

    async def _fetch_full_work_items(self, work_items: list[Any], session: Session) -> list[Any]:
        from orch.db.models import WorkItem

        if not work_items:
            return work_items

        ids_to_load: list[str] = []
        for wi in work_items:
            has_content = (
                hasattr(wi, "functional_doc_content") and wi.functional_doc_content is not None
            )
            has_summary = hasattr(wi, "summary") and wi.summary is not None
            has_title = hasattr(wi, "title") and getattr(wi, "title", None) is not None
            has_type = hasattr(wi, "type") and getattr(wi, "type", None) is not None
            if not (has_content and has_summary and has_title and has_type):
                ids_to_load.append(wi.id)

        if not ids_to_load:
            return work_items

        project_ids = {wi.project_id for wi in work_items}
        if len(project_ids) != 1:
            return work_items

        project_id = next(iter(project_ids))

        stmt = (
            select(WorkItem)
            .where(WorkItem.project_id == project_id)
            .where(WorkItem.id.in_(ids_to_load))
        )
        result = session.execute(stmt)
        full_rows = {row[0].id: row[0] for row in result.all()}

        merged: list[Any] = []
        for wi in work_items:
            full = full_rows.get(wi.id)
            if full is not None:
                merged.append(full)
            else:
                merged.append(wi)
        return merged

    async def _get_repo_root(self, _project_id: str, _session: Session) -> str | None:
        return None

    def _build_workitem_system_prompt(
        self,
        bundle: EvidenceBundle,
        full_items: list[Any] | None = None,
        register: str = "functional",  # noqa: ARG002
    ) -> str:
        items = full_items if full_items is not None else bundle.work_items
        if not items:
            return ""

        full_doc_items: list[Any] = []
        compact_items: list[Any] = []

        for item in items[:8]:
            has_func_doc = (
                hasattr(item, "functional_doc_content") and item.functional_doc_content is not None
            )
            if has_func_doc:
                full_doc_items.append(item)
            else:
                compact_items.append(item)

        top_3_full = full_doc_items[:3]
        remaining_compact = (full_doc_items[3:] + compact_items)[:5]

        result = self.WORKITEM_RELEVANCE_FILTER

        for i, item in enumerate(top_3_full, start=1):
            content = item.functional_doc_content or ""
            truncated = content[:12000] + ("…" if len(content) > 12000 else "")
            type_val = getattr(item.type, "value", "feature")
            result += f"### Candidate {i}: {item.id} — {item.title} ({type_val})\n{truncated}\n\n"

        for i, item in enumerate(remaining_compact, start=len(top_3_full) + 1):
            has_func_doc = (
                hasattr(item, "functional_doc_content") and item.functional_doc_content is not None
            )
            if has_func_doc:
                excerpt = (item.functional_doc_content or "")[:200]
            else:
                excerpt = (item.summary or "")[:200]
            type_val = getattr(item.type, "value", "feature")
            result += f"### Candidate {i}: {item.id} — {item.title} ({type_val})\n{excerpt}\n\n"

        if len(result) > 56000:
            chars_to_remove = len(result) - 56000
            while chars_to_remove > 0 and remaining_compact:
                removed = remaining_compact.pop()
                removed_excerpt = (
                    removed.summary
                    if (
                        removed.summary and getattr(removed, "functional_doc_content", None) is None
                    )
                    else (getattr(removed, "functional_doc_content", None) or removed.summary or "")
                )
                removed_text = f"### Candidate (removed): {removed.id} — {removed.title}\n"
                chars_to_remove -= len(removed_text)
                chars_to_remove -= len(removed_excerpt)

            if chars_to_remove > 0 and top_3_full:
                top_3_full.pop()

        return result

    async def answer_stream_v2(
        self,
        question: str,
        context_level: str,
        context_doc_id: str | None,
        conversation_history: list[dict[str, str]],
        session: Session,
        module_path: str | None = None,
        module_name: str | None = None,
        context_chips: list[str] | None = None,
        symbol_hint: str | None = None,
        conversation_id: str | None = None,
    ) -> AsyncGenerator[dict[str, object], None]:
        from orch.rag.citation_allowlist import extract_citations, filter_citations
        from orch.rag.classifier import classify_query
        from orch.rag.git_log_resolver import resolve_work_items_for_files

        classification = await classify_query(question, self.config, context_chips)
        if classification == "code_only":
            async for token in self.answer_stream(
                question=question,
                context_level=context_level,
                context_doc_id=context_doc_id,
                conversation_history=conversation_history,
                session=session,
                module_path=module_path,
                module_name=module_name,
                context_chips=context_chips,
                symbol_hint=symbol_hint,
                conversation_id=conversation_id,
            ):
                yield {"kind": "token", "text": token}
            return

        yield _emit_phase("retrieving", {"count": 0, "symbol": symbol_hint or ""})
        bundle = await self._retrieve_evidence_bundle(
            self.project_id, question, session, context_level
        )

        repo_root = await self._get_repo_root(self.project_id, session)

        if repo_root and bundle.code_chunks:
            from pathlib import Path

            from orch.db.models import WorkItem

            file_paths = [chunk.file_path for chunk in bundle.code_chunks]
            resolved = resolve_work_items_for_files(file_paths, repo_root=Path(repo_root))
            project_ids = {wi.project_id for wi in bundle.work_items}
            if project_ids:
                project_id = next(iter(project_ids))
                for _file_path, wi_ids in resolved.items():
                    for wi_id in wi_ids:
                        if wi_id.startswith(project_id.split("-")[0].upper()):
                            stmt = select(WorkItem).where(
                                WorkItem.project_id == project_id,
                                WorkItem.id == wi_id,
                            )
                            result = session.execute(stmt)
                            row = result.scalar_one_or_none()
                            if row and row not in bundle.git_log_items:
                                bundle.git_log_items.append(row)

        merged_items = _merge_and_rank_work_items(
            code_chunks=bundle.code_chunks,
            doc_chunks=bundle.doc_chunks,
            fts_items=bundle.fts_items,
            git_log_items=bundle.git_log_items,
            alpha=0.45,
            beta=0.20,
            gamma=0.35,
        )
        bundle.work_items = merged_items

        full_items = await self._fetch_full_work_items(merged_items, session)

        yield _emit_phase("finding_items", {"count": len(full_items), "symbol": symbol_hint or ""})
        yield _emit_phase("reading_docs", {"count": len(full_items)})

        workitem_prompt = self._build_workitem_system_prompt(bundle, full_items)
        workitem_section = workitem_prompt if workitem_prompt else ""

        yield _emit_phase("composing", {"render_id": "abc123", "count": len(full_items)})

        accumulated_text = ""
        async for token in self.answer_stream(
            question=question,
            context_level=context_level,
            context_doc_id=context_doc_id,
            conversation_history=conversation_history,
            session=session,
            module_path=module_path,
            module_name=module_name,
            context_chips=context_chips,
            symbol_hint=symbol_hint,
            workitem_section=workitem_section,
            conversation_id=conversation_id,
        ):
            accumulated_text += token
            yield {"kind": "token", "text": token}

        filtered_text, _ = filter_citations(accumulated_text, bundle.allowed_ids)
        mentioned_ids = set(extract_citations(filtered_text))

        for i, item in enumerate(full_items[:8], start=1):
            item_id = item.id
            if item_id in mentioned_ids and item_id in bundle.allowed_ids:
                snippet = (item.functional_doc_content or "")[:300].strip() or (item.summary or "")
                yield _emit_citation(
                    n=i,
                    work_item_type=getattr(item.type, "value", "feature"),
                    work_item_id=item.id,
                    label=f"{item.id} — {item.title}",
                    url=f"/project/{self.project_id}/item/{item.id}",
                    snippet=snippet,
                )


def _emit_citation(
    n: int,
    work_item_type: str,
    work_item_id: str,
    label: str,
    url: str,
    snippet: str,
) -> dict[str, object]:
    return {
        "kind": "citation",
        "n": n,
        "work_item_type": work_item_type,
        "work_item_id": work_item_id,
        "label": label,
        "url": url,
        "snippet": snippet,
    }


def _emit_phase(name: str, detail: dict[str, object] | None) -> dict[str, object]:
    return {
        "kind": "phase",
        "name": name,
        "detail": detail or {},
    }


def _emit_token(text: str) -> dict[str, object]:
    return {
        "kind": "token",
        "text": text,
    }


def _merge_and_rank_work_items(
    code_chunks: list[Any],  # noqa: ARG001
    doc_chunks: list[Any],
    fts_items: list[Any],
    git_log_items: list[Any],
    alpha: float = 0.45,
    beta: float = 0.20,
    gamma: float = 0.35,
) -> list[Any]:
    if not fts_items and not git_log_items and not doc_chunks:
        return []

    scored: dict[str, tuple[float, Any]] = {}

    fts_max = max((item.rank if hasattr(item, "rank") else 1.0 for item in fts_items), default=1.0)
    fts_scores: dict[str, float] = {}
    for item in fts_items:
        if item.id not in fts_scores:
            raw_rank = getattr(item, "rank", 1.0) if fts_items else 0.0
            fts_scores[item.id] = raw_rank / fts_max if fts_max > 0 else 0.0

    doc_max = max(
        (
            chunk.score
            for chunk in doc_chunks
            if hasattr(chunk, "score") and chunk.score is not None
        ),
        default=1.0,
    )
    semantic_scores: dict[str, float] = {}
    for chunk in doc_chunks:
        wid = getattr(chunk, "work_item_id", None)
        if wid is None:
            continue
        if wid not in semantic_scores:
            semantic_scores[wid] = 0.0
        chunk_score = getattr(chunk, "score", None)
        if chunk_score is not None:
            semantic_scores[wid] = max(
                semantic_scores[wid], chunk_score / doc_max if doc_max > 0 else 0.0
            )

    git_max = max((1.0 for _ in git_log_items), default=1.0)
    git_scores: dict[str, float] = {}
    for item in git_log_items:
        if item.id not in git_scores:
            git_scores[item.id] = 1.0 / git_max if git_max > 0 else 0.0

    seen_ids: list[str] = []
    for item in fts_items:
        if item.id not in seen_ids:
            seen_ids.append(item.id)
    for item in git_log_items:
        if item.id not in seen_ids:
            seen_ids.append(item.id)
    for chunk in doc_chunks:
        wid = getattr(chunk, "work_item_id", None)
        if wid is not None and wid not in seen_ids:
            seen_ids.append(wid)

    all_ids = seen_ids

    for wi_id in all_ids:
        fts_s = fts_scores.get(wi_id, 0.0)
        sem_s = semantic_scores.get(wi_id, 0.0)
        git_s = git_scores.get(wi_id, 0.0)
        combined = alpha * fts_s + gamma * sem_s + beta * git_s
        for item in fts_items:
            if item.id == wi_id:
                scored[wi_id] = (combined, item)
                break
        else:
            for item in git_log_items:
                if item.id == wi_id:
                    scored[wi_id] = (combined, item)
                    break
            else:
                for chunk in doc_chunks:
                    if chunk.work_item_id == wi_id:
                        mock_item = type(
                            "MockWI",
                            (),
                            {
                                "id": wi_id,
                                "title": chunk.work_item_title,
                                "type": type("T", (), {"value": chunk.work_item_type})(),
                                "project_id": "",
                                "summary": chunk.work_item_title,
                                "functional_doc_content": None,
                                "design_doc_content": None,
                            },
                        )()
                        scored[wi_id] = (combined, mock_item)
                        break

    sorted_items = sorted(scored.values(), key=lambda x: x[0], reverse=True)
    return [item for _, item in sorted_items[:5]]
