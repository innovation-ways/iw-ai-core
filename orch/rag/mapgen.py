"""MapGenerator — Level 1 architecture map generation via RAG queries to Ollama."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import TYPE_CHECKING

from llama_index.core import PromptTemplate, VectorStoreIndex
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.lancedb import LanceDBVectorStore

from orch.db.models import Project, ProjectDoc
from orch.doc_service import DocService

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from orch.rag.config import CodeUnderstandingConfig


_SIMILARITY_TOP_K = 20


_SECTION_TITLES: dict[str, str] = {
    "purpose": "Purpose",
    "components": "Components",
    "entry_points": "Entry Points",
    "databases": "Databases",
    "external_services": "External Services",
    "background_jobs": "Background Jobs",
    "architecture_style": "Architecture Style",
    "key_patterns": "Key Patterns",
}


_GROUNDING_TEMPLATE = PromptTemplate(
    "You are a senior software architect documenting the architecture of a real "
    "codebase. Below are code excerpts retrieved from that codebase.\n"
    "-----------------\n"
    "{context_str}\n"
    "-----------------\n"
    "Task: {query_str}\n\n"
    "Rules:\n"
    "- Ground your answer ONLY in concrete evidence from the code excerpts "
    "(class names, function names, file paths, imports, SQL/ORM models, routes, "
    "framework usage).\n"
    "- Do NOT describe the prompt or the questions being asked. Do NOT mention "
    "'context', 'excerpt', 'provided text', 'RAG', or 'MapGenerator'. Describe "
    "the system itself.\n"
    "- Write 2–5 concise sentences (or a short bulleted list where natural).\n"
    "- If the excerpts are genuinely insufficient, answer with the strongest "
    "observations you can make from what IS present — never refuse.\n\n"
    "Answer:"
)


class MapGenerator:
    """Tuple items are (section_key, human_question, retrieval_query_text).

    retrieval_query_text is a keyword/topical phrase used for vector search; it
    deliberately avoids the verbatim interrogative form of the question so the
    embedding does not collide with the QUESTIONS list inside this very module.
    """

    QUESTIONS: list[tuple[str, str, str]] = [
        (
            "purpose",
            "Describe the overall purpose and main function of this codebase.",
            "project mission high-level goals primary responsibilities README "
            "package entry CLI daemon dashboard orchestration",
        ),
        (
            "components",
            "List the main components, services, modules, or subpackages that "
            "make up this codebase, with a short description of each. "
            "Format each entry as a Markdown bullet of the form "
            "`- **Component Name (`path/`)**: description.`, where the path "
            "is the FILESYSTEM path to the directory (forward slashes, "
            "trailing slash — e.g. `orch/daemon/`, `dashboard/`, `orch/rag/`). "
            "Never emit Python dotted import paths like `orch.daemon`; the "
            "path must be something that could be passed to `cd` from the "
            "repository root.",
            "top-level packages modules subpackages CLI commands routers "
            "services daemon workers engines managers",
        ),
        (
            "entry_points",
            "Identify the real entry points of the application: CLI commands, "
            "server endpoints, scripts, or background workers.",
            "main function __main__ FastAPI app uvicorn Click Typer entry point "
            "console_scripts pyproject scripts run",
        ),
        (
            "databases",
            "What databases or data stores does the system use, what tables or "
            "collections exist, and what domain data is stored?",
            "PostgreSQL SQLAlchemy ORM models tables columns migrations Alembic "
            "JSONB vector store LanceDB schema",
        ),
        (
            "external_services",
            "Which external services, APIs, or third-party integrations does this system talk to?",
            "HTTP client requests httpx OpenAI Anthropic Ollama LLM API "
            "webhook external service integration subprocess git",
        ),
        (
            "background_jobs",
            "What background jobs, workers, polling loops, or async tasks run in this system?",
            "background task asyncio loop daemon poll worker queue job runner "
            "scheduler FastAPI BackgroundTasks",
        ),
        (
            "architecture_style",
            "Describe the overall architectural style and runtime topology of this codebase.",
            "monolith single process service layered architecture CLI daemon "
            "web server event driven polling state machine",
        ),
        (
            "key_patterns",
            "Identify the most important technical patterns and conventions "
            "used across this codebase.",
            "repository pattern dependency injection session factory ORM "
            "migrations state machine fix cycle retry audit append-only",
        ),
    ]

    async def generate_level1(
        self,
        project_id: str,
        config: CodeUnderstandingConfig,
        cancel_check: Callable[[], bool] | None = None,
        db_session_factory: Any | None = None,
    ) -> ProjectDoc:
        store_path = str(Path(config.index_path) / project_id / "vectors")
        table_name = f"code_{project_id.replace('-', '_')}"

        llm = Ollama(
            model=config.resolved_llm_model(),
            base_url=config.ollama_url,
            request_timeout=300.0,
        )

        embed = OllamaEmbedding(
            model_name=config.resolved_embed_model(),
            base_url=config.ollama_url,
        )

        vector_store = LanceDBVectorStore(
            uri=store_path,
            table_name=table_name,
        )

        index = VectorStoreIndex.from_vector_store(vector_store, embed_model=embed)
        retriever = index.as_retriever(similarity_top_k=_SIMILARITY_TOP_K)

        answers: dict[str, str] = {}

        for key, question, retrieval_query in self.QUESTIONS:
            if cancel_check and cancel_check():
                raise asyncio.CancelledError("map generation cancelled")
            nodes = await asyncio.to_thread(retriever.retrieve, retrieval_query)
            context_str = self._build_context_str(nodes)
            prompt = _GROUNDING_TEMPLATE.format(context_str=context_str, query_str=question)
            response = await asyncio.to_thread(llm.complete, prompt)
            answers[key] = str(response).strip()

        mermaid = await asyncio.to_thread(self._build_mermaid, answers["components"], config)
        markdown = self._assemble_markdown(answers, mermaid)

        def store_arch_diagram(dsl: str) -> None:
            from orch.db.models import DocTier, DocType, EditorialCategory, Project
            from orch.db.session import SessionLocal as DefaultSessionLocal

            factory = db_session_factory or DefaultSessionLocal
            with factory() as session:
                project = session.get(Project, project_id)
                if project is None:
                    return
                doc_service = DocService(session)
                existing = doc_service.get_doc(project_id, "diagram-architecture")
                if existing is None:
                    doc_service.create_doc(
                        project_id=project_id,
                        doc_id="diagram-architecture",
                        title=f"{project.display_name} — Architecture Diagram",
                        doc_type=DocType.diagram,
                        tier=DocTier.fully_automated,
                        editorial_category=EditorialCategory.technical,
                        content=dsl,
                        generated_by="code-understanding:mapgen",
                        source_paths=["*"],
                    )
                else:
                    doc_service.update_doc(
                        project_id=project_id,
                        doc_id="diagram-architecture",
                        title=f"{project.display_name} — Architecture Diagram",
                        content=dsl,
                        generated_by="code-understanding:mapgen",
                        source_paths=["*"],
                    )
                session.commit()

        try:
            await asyncio.to_thread(store_arch_diagram, mermaid)
        except Exception as exc:
            import logging

            logging.warning("Architecture diagram storage failed for %s: %s", project_id, exc)

        def do_upsert() -> ProjectDoc:
            from orch.db.models import DocTier, DocType, EditorialCategory
            from orch.db.session import SessionLocal as DefaultSessionLocal

            factory = db_session_factory or DefaultSessionLocal
            with factory() as session:
                project = session.get(Project, project_id)
                if project is None:
                    raise ValueError(f"Project {project_id} not found")

                doc_service = DocService(session)
                existing = doc_service.get_doc(project_id, "architecture-map")
                if existing is None:
                    doc = doc_service.create_doc(
                        project_id=project_id,
                        doc_id="architecture-map",
                        title=f"{project.display_name} — Architecture Map",
                        doc_type=DocType.architecture,
                        tier=DocTier.fully_automated,
                        editorial_category=EditorialCategory.technical,
                        content=markdown,
                        generated_by="code-understanding:level1",
                    )
                else:
                    doc = doc_service.update_doc(
                        project_id=project_id,
                        doc_id="architecture-map",
                        title=f"{project.display_name} — Architecture Map",
                        tier=DocTier.fully_automated,
                        editorial_category=EditorialCategory.technical,
                        content=markdown,
                        generated_by="code-understanding:level1",
                    )
                session.commit()
                session.refresh(doc)
                session.expunge(doc)
                return doc

        return await asyncio.to_thread(do_upsert)

    @staticmethod
    def _build_context_str(nodes: Any) -> str:
        parts: list[str] = []
        for n in nodes:
            text = getattr(n.node, "get_content", lambda: "")()
            if not text:
                text = getattr(n.node, "text", "") or ""
            meta = getattr(n.node, "metadata", {}) or {}
            path = meta.get("file_path", "<unknown>")
            lang = meta.get("language", "")
            parts.append(f"// {path}  ({lang})\n{text}")
        return "\n\n---\n\n".join(parts)

    def _build_mermaid(self, components_answer: str, config: CodeUnderstandingConfig) -> str:
        llm = Ollama(
            model=config.resolved_llm_model(),
            base_url=config.ollama_url,
            request_timeout=300.0,
        )
        prompt = (
            "You are generating a Mermaid component diagram for a software system.\n"
            f"Components and their descriptions:\n{components_answer}\n\n"
            "The diagram MUST start with this exact YAML frontmatter block:\n"
            "---\n"
            "config:\n"
            "  layout: elk\n"
            "---\n\n"
            "Produce ONLY a valid Mermaid `graph TD` diagram showing the "
            "relationships between these components. Use short alphanumeric "
            "node IDs and put the human label in brackets, e.g. `CLI[iw CLI]`. "
            "Wrap the diagram in a ```mermaid ... ``` fenced code block. "
            "No prose, no explanation.\n"
            "Maximum 15 nodes. If the system has more components, group minor ones.\n"
        )
        response = llm.complete(prompt)
        text = response.text

        match = re.search(r"```mermaid\s*(.*?)\s*```", text, re.DOTALL)
        mermaid_dsl = match.group(1).strip() if match else "graph TD\n  A[System]"

        elk_frontmatter = "---\nconfig:\n  layout: elk\n---\n"
        if "layout: elk" not in mermaid_dsl:
            mermaid_dsl = elk_frontmatter + mermaid_dsl
        return mermaid_dsl

    def _assemble_markdown(self, answers: dict[str, str], mermaid: str) -> str:
        lines = ["# Architecture Map", ""]
        for key, _question, _retrieval in self.QUESTIONS:
            value = answers.get(key, "").strip()
            label = _SECTION_TITLES.get(key, key.replace("_", " ").title())
            lines.append(f"## {label}")
            lines.append(value if value else "_(no answer)_")
            lines.append("")
        lines.append("## Architecture Diagram")
        lines.append("")
        lines.append("```mermaid")
        lines.append(mermaid)
        lines.append("```")
        return "\n".join(lines)
