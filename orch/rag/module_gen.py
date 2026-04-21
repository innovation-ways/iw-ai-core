"""ModuleGenerator — Level 2 module doc generation via LanceDB RAG + Ollama."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import lancedb  # type: ignore[import-untyped]
from llama_index.embeddings.ollama import OllamaEmbedding
from sqlalchemy import select

from orch.db.models import DocTier, DocType, EditorialCategory, ProjectDoc
from orch.doc_service import DocService
from orch.rag.module_progress import start_progress, update_progress

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.rag.config import CodeUnderstandingConfig


_STEP_LABELS: list[str] = [
    "Primary responsibility",
    "Key files",
    "Dependencies",
    "Design patterns",
    "Entry points",
]


_FILLER_PREAMBLE_RE = re.compile(
    r"^(?:"
    r"based on|according to|from|looking at|as (?:per|shown|indicated) (?:by|in)|referring to"
    r")\s+(?:the\s+|this\s+|these\s+)?"
    r"(?:provided\s+|given\s+|above\s+|following\s+)?"
    r"(?:code|context|excerpts?|information|snippets?|sources?|documentation)"
    r"[^.:\n]*?:\s*\n?",
    re.IGNORECASE,
)


def _strip_filler_preamble(text: str) -> str:
    """Remove a leading list-intro preamble like 'Based on the provided code, X are:'.

    Conservative: only strips when the filler phrase ends with a colon (i.e. it
    introduces a list or section), which is the dominant pattern emitted by
    smaller instruction-tuned LLMs. Prose openings that end with a period are
    left alone to avoid deleting real content.
    """
    if not text:
        return text
    out = text.lstrip()
    for _ in range(2):
        new = _FILLER_PREAMBLE_RE.sub("", out, count=1)
        if new == out:
            break
        out = new.lstrip()
    return out


def _normalize_module_path_for_filter(module_path: str) -> str:
    """Normalize a module_path for use as a `metadata.file_path LIKE '%X%'` filter.

    The Level 1 architecture doc is LLM-generated and occasionally emits Python
    import notation (`orch.daemon`) instead of filesystem notation (`orch/daemon`).
    LanceDB stores `metadata.file_path` as a filesystem path, so a LIKE filter
    built from the dotted form silently matches zero chunks.

    Rule: if the path contains no slash, assume dots are directory separators
    and convert them to slashes. Paths that already contain a slash are left
    alone (they are already filesystem-shaped, and `foo/bar.py` must keep its
    dot for the extension).
    """
    if not module_path or "/" in module_path:
        return module_path
    return module_path.replace(".", "/")


class ModuleGenerator:
    MODULE_QUESTIONS: list[str] = [
        "What is the primary responsibility of the {module} component?",
        "What are the most important files in {module} and what does each do?",
        "What external components or services does {module} depend on?",
        "What design patterns or architectural approaches are used in {module}?",
        "What are the key entry points or public interfaces of {module}?",
    ]

    def _make_slug(self, project_id: str, module_path: str) -> str:
        return f"{project_id}-module-{module_path.strip('/').replace('/', '-')}"

    async def get_or_generate(
        self,
        project_id: str,
        module_path: str,
        module_name: str,
        config: CodeUnderstandingConfig,
        session: Session,
    ) -> tuple[ProjectDoc, bool]:
        slug = self._make_slug(project_id, module_path)

        existing = self._get_by_slug(slug, session)
        if existing is not None:
            return existing, True

        doc = await self.generate_level2(project_id, module_path, module_name, config, session)
        return doc, False

    def _get_by_slug(self, slug: str, session: Session) -> ProjectDoc | None:
        result = session.execute(select(ProjectDoc).where(ProjectDoc.slug == slug))
        return result.scalars().first()

    async def generate_level2(
        self,
        project_id: str,
        module_path: str,
        module_name: str,
        config: CodeUnderstandingConfig,
        session: Session,
    ) -> ProjectDoc:
        store_path = Path(config.index_path).expanduser() / project_id / "vectors"
        table_name = f"code_{project_id.replace('-', '_')}"

        db = lancedb.connect(str(store_path))
        table = db.open_table(table_name)

        embed_model = config.resolved_embed_model()
        llm_model = config.resolved_llm_model()
        ollama_url = config.ollama_url

        embed = OllamaEmbedding(model_name=embed_model, base_url=ollama_url)

        filter_path = _normalize_module_path_for_filter(module_path)
        safe_path = filter_path.replace("'", "''")
        path_filter = f"metadata.file_path LIKE '%{safe_path}%'"

        start_progress(project_id, module_path, module_name, llm_model)

        answers: list[str] = []
        for idx, (question_template, label) in enumerate(
            zip(self.MODULE_QUESTIONS, _STEP_LABELS, strict=True), start=1
        ):
            update_progress(project_id, module_path, step=idx, step_label=label)

            question = question_template.format(module=module_name)
            embedding = await embed.aget_text_embedding(question)

            results = table.search(embedding).where(path_filter).limit(5).to_list()

            context_chunks = [r.get("text", "") for r in results if r.get("text")]
            context = "\n\n---\n\n".join(context_chunks)

            answer = await self._call_ollama(question, context, llm_model, ollama_url)
            answers.append(answer)

        update_progress(project_id, module_path, step=5, step_label="writing doc")
        content = self._assemble_markdown(module_name, module_path, answers)

        slug = self._make_slug(project_id, module_path)
        title = f"Module: {module_name} ({module_path})"

        doc_service = DocService(session)
        doc = doc_service.create_doc(
            project_id=project_id,
            doc_id=slug,
            title=title,
            doc_type=DocType.code_components,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            slug=slug,
            content=content,
            generated_by="code-understanding:level2",
        )
        session.flush()
        update_progress(project_id, module_path, step=5, step_label="complete", done=True)
        return doc

    async def _call_ollama(self, question: str, context: str, model: str, ollama_url: str) -> str:
        prompt = f"""You are documenting one module of a real codebase.

Code excerpts from the module:
---
{context}
---

Task: {question}

Rules:
- Answer directly. Do NOT restate the task, do NOT describe the excerpts.
- Forbidden openers (do not begin your answer with these or anything similar):
  "Based on the provided code", "According to the code", "The provided code shows",
  "Looking at the excerpts", "From the context", "As shown in the code", "Here is".
- Start with the substantive content itself — a concrete file path, class name,
  function name, or claim drawn from the excerpts.
- Cite specific identifiers (file paths, class/function names, imports) from the
  excerpts. No speculation beyond what the excerpts show.
- Use GitHub-flavored Markdown. Prefer short paragraphs and bullet lists over prose."""

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ollama_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            data: dict[str, str] = response.json()
            result: str = data.get("response", "")
            return _strip_filler_preamble(result)

    async def run_standalone(
        self,
        project_id: str,
        module_path: str,
        module_name: str,
        config: CodeUnderstandingConfig,
    ) -> None:
        """Run generate_level2 with a dedicated DB session.

        Intended for background execution: the HTTP request's session closes as
        soon as the response is returned, so we cannot reuse it for a 2-4-minute
        Ollama-bound generation. Opens its own session, commits on success.
        """
        from orch.db.session import SessionLocal

        with SessionLocal() as session:
            await self.generate_level2(project_id, module_path, module_name, config, session)
            session.commit()

    def _assemble_markdown(self, module_name: str, module_path: str, answers: list[str]) -> str:
        lines = [
            f"# {module_name}",
            "",
            f"**Path:** `{module_path}`",
            "",
        ]

        question_labels = [
            "Primary Responsibility",
            "Key Files",
            "Dependencies",
            "Design Patterns",
            "Entry Points",
        ]

        for label, answer in zip(question_labels, answers, strict=True):
            lines.append(f"## {label}")
            lines.append("")
            lines.append(answer)
            lines.append("")

        return "\n".join(lines)
