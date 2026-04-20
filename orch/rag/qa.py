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
from sqlalchemy import select

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.orm import Session

    from orch.rag.config import CodeUnderstandingConfig

from orch.rag.evidence import EvidenceBundle

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
    MAX_HISTORY_TURNS: int = 5

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
        symbol_hint: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream answer tokens for the given question using RAG retrieval.

        1. Embed question via Ollama embedding model
        2. Retrieve top-k chunks from LanceDB (filtered by module_path if context_level == "module")
        3. Load context_doc content from DB if context_doc_id provided
        4. Build system prompt with context doc + retrieved chunks
        5. Truncate conversation history to MAX_HISTORY_TURNS
        6. Stream response tokens via Ollama LLM
        """
        embed_model = self.config.resolved_embed_model()
        ollama_url = self.config.ollama_url

        embedding_instance = OllamaEmbedding(
            model_name=embed_model,
            base_url=ollama_url,
        )
        embedding_vector = await asyncio.to_thread(embedding_instance.get_query_embedding, question)

        db_path = f"{self.config.index_path}/{self.project_id}/vectors/"
        table_name = f"code_{self.project_id.replace('-', '_')}"

        chunks: list[str] = []
        fallback_triggered = False

        try:
            import lancedb  # type: ignore[import-untyped]

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
        )

        truncated_history = self._truncate_history(conversation_history)

        messages = [ChatMessage(role="system", content=system_prompt)]
        for msg in truncated_history:
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
        "- Tables — use GitHub-flavored markdown tables when comparing multiple "
        "items side by side.\n"
        "- Code — use fenced blocks with a language tag (```python, ```typescript, "
        "etc.) so syntax highlighting applies.\n\n"
        "Do not preface answers with disclaimers about being a text-based AI; "
        "emit diagrams and code directly in the response.\n\n"
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

        return (
            "You are a codebase expert assistant. "
            "Answer questions about the codebase accurately and concisely.\n\n"
            f"{module_block}"
            f"{retrieval_note}"
            "## Architecture Context\n\n"
            f"{ctx}\n\n"
            "## Relevant Code Excerpts\n\n"
            f"{excerpts}\n\n"
            f"{self.RENDERING_CAPABILITIES_BLOCK}"
            f"{diagram_block}"
            "Answer the user's question based on the above context. "
            "If the context does not contain enough information, say so clearly."
        )

    def _truncate_history(self, history: list[dict[str, str]]) -> list[dict[str, str]]:
        """
        Return the last MAX_HISTORY_TURNS * 2 messages from history.

        If len(history) <= MAX_HISTORY_TURNS * 2, return all items unchanged.
        """
        max_messages = self.MAX_HISTORY_TURNS * 2
        if len(history) <= max_messages:
            return list(history)
        return list(history[-max_messages:])

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
        _project_id: str,
        question: str,
        _session: Session,
        _context_level: str,
    ) -> EvidenceBundle:
        return EvidenceBundle(question=question)

    async def _fetch_full_work_items(self, work_items: list[Any], _session: Session) -> list[Any]:
        return work_items

    async def _get_repo_root(self, _project_id: str, _session: Session) -> str | None:
        return None

    def _build_workitem_system_prompt(
        self,
        bundle: EvidenceBundle,
        register: str = "functional",  # noqa: ARG002
    ) -> str:
        wi = bundle.work_items[0] if bundle.work_items else None
        if wi and getattr(wi, "design_doc_content", None):
            return f"Work item {wi.id} has design doc."
        return f"Work item {wi.id if wi else 'unknown'} - no design doc excerpt."

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
    ) -> AsyncGenerator[dict[str, object], None]:
        from orch.rag.classifier import classify_query

        classification = classify_query(question, self.config, context_chips)
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
            ):
                yield {"kind": "token", "text": token}
            return

        yield _emit_phase("retrieving", {"count": 0, "symbol": symbol_hint or ""})
        bundle = await self._retrieve_evidence_bundle(
            self.project_id, question, session, context_level
        )
        yield _emit_phase(
            "finding_items", {"count": len(bundle.work_items), "symbol": symbol_hint or ""}
        )

        full_items = await self._fetch_full_work_items(bundle.work_items, session)
        await self._get_repo_root(self.project_id, session)

        yield _emit_phase("reading_docs", {"count": len(full_items)})

        for item in full_items[:5]:
            yield _emit_citation(
                n=1,
                work_item_type=getattr(item.type, "value", "feature"),
                work_item_id=item.id,
                label=f"{item.id} — {item.title}",
                url=f"/project/{self.project_id}/item/{item.id}",
                snippet=item.summary or "",
            )

        yield _emit_phase("composing", {"render_id": "abc123", "count": len(full_items)})

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
        ):
            yield {"kind": "token", "text": token}


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
    _code_chunks: list[Any],
    _doc_chunks: list[Any],
    fts_items: list[Any],
    git_log_items: list[Any],
    alpha: float = 0.5,
    beta: float = 0.3,
    gamma: float = 0.2,  # noqa: ARG001
) -> list[Any]:
    scored: list[tuple[float, object]] = []
    seen_ids: set[str] = set()

    for item in fts_items:
        if item.id not in seen_ids:
            scored.append((alpha, item))
            seen_ids.add(item.id)

    for item in git_log_items:
        if item.id not in seen_ids:
            scored.append((beta, item))
            seen_ids.add(item.id)

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:5]]
