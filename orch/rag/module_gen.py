"""ModuleGenerator — Level 2 module doc generation via LanceDB RAG + Ollama."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import lancedb
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from sqlalchemy import select

from orch.db.models import DocTier, DocType, EditorialCategory, ProjectDoc
from orch.doc_service import DocService
from orch.rag.module_progress import start_progress, update_progress

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.rag.config import CodeUnderstandingConfig


_ELK_FRONTMATTER = """\
---
config:
  layout: elk
---
"""


_MERMAID_CLASSDEF = """\
After the graph declaration, add this classDef block verbatim:
  classDef api fill:#DBEAFE,stroke:#3B82F6,color:#1E3A5F
  classDef data fill:#D1FAE5,stroke:#10B981,color:#065F46
  classDef worker fill:#FEF3C7,stroke:#F59E0B,color:#78350F
  classDef external fill:#F3F4F6,stroke:#9CA3AF,color:#374151
  classDef ui fill:#EDE9FE,stroke:#8B5CF6,color:#3B0764
  classDef core fill:#FEE2E2,stroke:#EF4444,color:#7F1D1D
"""

_MERMAID_CLASSDEF_BLOCK = """\
  classDef api fill:#DBEAFE,stroke:#3B82F6,color:#1E3A5F
  classDef data fill:#D1FAE5,stroke:#10B981,color:#065F46
  classDef worker fill:#FEF3C7,stroke:#F59E0B,color:#78350F
  classDef external fill:#F3F4F6,stroke:#9CA3AF,color:#374151
  classDef ui fill:#EDE9FE,stroke:#8B5CF6,color:#3B0764
  classDef core fill:#FEE2E2,stroke:#EF4444,color:#7F1D1D
"""

_ELK_FRONTMATTER = """\
---
config:
  layout: elk
---
"""

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


_ELK_FRONTMATTER = """\
---
config:
  layout: elk
---
"""


def _strip_yaml_frontmatter(dsl: str) -> str:
    """Strip YAML frontmatter (---...---) from a Mermaid DSL string.

    LLMs sometimes emit frontmatter even when not instructed to. Mermaid
    versions without ELK plugin support fail with a parse error when they
    encounter layout directives. Stripping prevents that regression.
    """
    stripped = dsl.lstrip()
    if not stripped.startswith("---"):
        return dsl
    end = stripped.find("\n---", 3)
    if end == -1:
        return dsl
    return stripped[end + 4 :].lstrip()


def _extract_frontmatter(dsl: str) -> tuple[str, str]:
    """Extract YAML frontmatter from a Mermaid DSL string.

    Returns (frontmatter, stripped_dsl) where frontmatter includes the --- markers,
    or ('', dsl) if no frontmatter found.
    """
    stripped = dsl.lstrip()
    if not stripped.startswith("---"):
        return "", dsl
    end = stripped.find("\n---", 3)
    if end == -1:
        return "", dsl
    frontmatter = stripped[: end + 4]
    return frontmatter, stripped[end + 4 :].lstrip()


def _inject_elk_frontmatter(dsl: str) -> str:
    """Prepend ELK layout frontmatter to a Mermaid DSL string if not already present."""
    if "layout: elk" in dsl:
        return dsl
    dsl = _strip_yaml_frontmatter(dsl)
    return _ELK_FRONTMATTER + dsl


def _ensure_classdef_in_dsl(dsl: str) -> str:
    """Ensure the classDef block and ELK frontmatter are present in the Mermaid DSL.

    The LLM often uses individual 'class NodeID api' assignments instead of
    including the 'classDef' color definitions. This function post-processes
    the DSL to inject the classDef block right after the diagram-type line
    (e.g. 'graph TD').

    ELK frontmatter (layout: elk) is also injected to ensure proper layout
    of the diagram.
    """
    if "layout: elk" in dsl:
        if "classDef api" in dsl:
            return dsl
        lines = dsl.split("\n")
        insert_idx = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("graph ") or line.strip().startswith("flowchart "):
                insert_idx = i + 1
                break
        new_lines = lines[:insert_idx] + [_MERMAID_CLASSDEF_BLOCK, ""] + lines[insert_idx:]
        return "\n".join(new_lines)

    dsl = _strip_yaml_frontmatter(dsl)
    has_classdef = "classDef api" in dsl

    lines = dsl.split("\n")
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.strip().startswith("graph ") or line.strip().startswith("flowchart "):
            insert_idx = i + 1
            break

    new_lines = lines[:insert_idx]
    if not has_classdef:
        new_lines += [_MERMAID_CLASSDEF_BLOCK, ""]
    new_lines += lines[insert_idx:]

    result = "\n".join(new_lines)
    if "layout: elk" not in result:
        result = _ELK_FRONTMATTER + result
    return result


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
    """Generates Level 2 per-module documentation using LanceDB RAG retrieval and Ollama.

    Produces structured markdown covering primary responsibility, key files,
    dependencies, design patterns, and entry points for a given module path.
    Also generates a Mermaid component diagram stored as a separate ProjectDoc.
    """

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
        """Return the existing module doc if one exists, otherwise generate it.

        Args:
            project_id: Project the module belongs to.
            module_path: Filesystem path of the module (e.g. "orch/daemon/").
            module_name: Human-readable module name for display and prompts.
            config: LLM model, embedding model, and Ollama connection settings.
            session: Active SQLAlchemy session for DB reads and writes.

        Returns:
            Tuple of (ProjectDoc, was_cached) where was_cached is True when the
            doc already existed and generation was skipped.
        """
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
        """Generate a Level 2 module documentation page and store it as a ProjectDoc.

        Retrieves relevant code chunks from LanceDB filtered to the module path,
        calls Ollama for each of the MODULE_QUESTIONS, assembles the markdown, and
        persists it. Also triggers module diagram generation (non-fatal on failure).

        Args:
            project_id: Project the module belongs to.
            module_path: Filesystem path used for LanceDB filter and doc slug.
            module_name: Human-readable module name used in prompts and titles.
            config: LLM model, embedding model, and Ollama connection settings.
            session: Active SQLAlchemy session; caller is responsible for commit.

        Returns:
            The newly created ProjectDoc for the module.
        """
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
        last_context_chunks: list[str] = []
        for idx, (question_template, label) in enumerate(
            zip(self.MODULE_QUESTIONS, _STEP_LABELS, strict=True), start=1
        ):
            update_progress(project_id, module_path, step=idx, step_label=label)

            question = question_template.format(module=module_name)
            embedding = await embed.aget_text_embedding(question)

            results = table.search(embedding).where(path_filter).limit(5).to_list()

            context_chunks = [r.get("text", "") for r in results if r.get("text")]
            context = "\n\n---\n\n".join(context_chunks)
            last_context_chunks = context_chunks

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
            doc_type=DocType.research,
            tier=DocTier.fully_automated,
            editorial_category=EditorialCategory.technical,
            slug=slug,
            content=content,
            generated_by="code-understanding:level2",
        )
        session.flush()

        try:
            await self._generate_and_store_module_diagram(
                project_id=project_id,
                module_path=module_path,
                module_name=module_name,
                config=config,
                session=session,
                retrieved_nodes=last_context_chunks,
            )
        except Exception as exc:
            import logging

            logging.warning(
                "Module diagram generation failed for %s/%s: %s", project_id, module_path, exc
            )

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

    async def _generate_and_store_module_diagram(
        self,
        project_id: str,
        module_path: str,
        module_name: str,
        config: CodeUnderstandingConfig,
        session: Session,
        retrieved_nodes: list[str],
    ) -> None:
        context_str = "\n\n---\n\n".join(retrieved_nodes)

        llm = Ollama(
            model=config.resolved_llm_model(),
            base_url=config.ollama_url,
            request_timeout=300.0,
        )
        prompt = (
            f"You are generating a Mermaid component diagram for the '{module_name}' module.\n\n"
            f"Code context:\n{context_str}\n\n"
            "Rules:\n"
            "- Output ONLY a fenced ```mermaid block. No prose, no explanation.\n"
            "- The diagram block MUST start with a YAML frontmatter:\n"
            "  ```mermaid\n"
            "  ---\n"
            "  config:\n"
            "    layout: elk\n"
            "  ---\n"
            "  graph LR\n"
            "  ...\n"
            "  ```\n"
            "- Use 'graph LR' direction (left-to-right).\n"
            "- Maximum 12 nodes. Group minor items if needed.\n"
            "- Node IDs: short alphanumeric (e.g., QA, IDX, CFG). Labels in [brackets].\n"
            "- Show the main internal components and their key dependencies.\n"
            "- The diagram MUST include ELK layout frontmatter: 'layout: elk' inside\n"
            "  a '---' YAML block right after the opening ```mermaid line.\n\n"
            + _MERMAID_CLASSDEF
            + "\n"
            "Class assignment rules:\n"
            "- API handlers, controllers, routers → `class NodeID api`\n"
            "- Database models, repositories, data access layers → `class NodeID data`\n"
            "- Background jobs, daemon workers, pipeline stages → `class NodeID worker`\n"
            "- External API clients, third-party integrations → `class NodeID external`\n"
            "- Dashboard/UI components, frontend adapters → `class NodeID ui`\n"
            "- Core domain models, business logic services → `class NodeID core`\n\n"
            "Structural-elements-only instruction:\n"
            "Show only: controllers, API handlers, services, repositories, data access layers, "
            "integration adapters, core domain models.\n"
            "Do NOT show: utility classes, helpers, DTOs, config objects.\n\n"
            "After the diagram block, output a second fenced block:\n"
            "```purpose\n"
            "[One or two sentences describing what this diagram shows and when to refer to it.]\n"
            "```\n"
        )
        response = await asyncio.to_thread(llm.complete, prompt)
        text = response.text

        match = re.search(r"```mermaid\s*(.*?)\s*```", text, re.DOTALL)
        mermaid_dsl = match.group(1).strip() if match else f"graph LR\n  A[{module_name}]"

        purpose_match = re.search(r"```purpose\s*(.*?)\s*```", text, re.DOTALL)
        if purpose_match:
            purpose = purpose_match.group(1).strip().replace("\n", " ")
        else:
            purpose = (
                f"This diagram shows the internal component structure of the {module_name} module."
            )

        mermaid_dsl = _ensure_classdef_in_dsl(mermaid_dsl)
        mermaid_dsl = _inject_elk_frontmatter(mermaid_dsl)
        content = f"<!-- purpose: {purpose} -->\n{mermaid_dsl}"

        slug = self._make_slug(project_id, module_path)
        doc_id = f"diagram-module-{slug}"

        doc_service = DocService(session)
        existing = doc_service.get_doc(project_id, doc_id)
        if existing is None:
            doc_service.create_doc(
                project_id=project_id,
                doc_id=doc_id,
                title=f"Module Diagram: {module_name} ({module_path})",
                doc_type=DocType.diagram,
                tier=DocTier.fully_automated,
                editorial_category=EditorialCategory.technical,
                content=content,
                generated_by="code-understanding:module_gen",
                source_paths=[module_path],
            )
        else:
            doc_service.update_doc(
                project_id=project_id,
                doc_id=doc_id,
                title=f"Module Diagram: {module_name} ({module_path})",
                content=content,
                generated_by="code-understanding:module_gen",
                source_paths=[module_path],
            )
        session.flush()

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
        """Assemble the final module documentation markdown from per-question answers.

        Args:
            module_name: Human-readable module name used as the H1 heading.
            module_path: Filesystem path displayed as the Path metadata line.
            answers: List of LLM answer strings in MODULE_QUESTIONS order.

        Returns:
            Markdown string with H1 title, path annotation, and one H2 section per answer.
        """
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
