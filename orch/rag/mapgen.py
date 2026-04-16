"""MapGenerator — Level 1 architecture map generation via RAG queries to Ollama."""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

from llama_index.core import VectorStoreIndex
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.lancedb import LanceDBVectorStore

from orch.db.models import Project, ProjectDoc
from orch.doc_service import DocService

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from orch.rag.config import CodeUnderstandingConfig


class MapGenerator:
    QUESTIONS: list[tuple[str, str]] = [
        ("purpose", "What is the overall purpose and main function of this system?"),
        (
            "components",
            "List the main components, services, or modules with a one-sentence "
            "description of each.",
        ),
        ("entry_points", "What are the main entry points of the application?"),
        ("databases", "What databases or data stores are used and what data do they store?"),
        (
            "external_services",
            "What external services, APIs, or integrations does this system use?",
        ),
        ("background_jobs", "What background jobs, workers, or async tasks exist?"),
        (
            "architecture_style",
            "What architectural pattern is used (e.g., microservices, monolith, event-driven)?",
        ),
        ("key_patterns", "What are the most important design patterns or technical patterns used?"),
    ]

    async def generate_level1(
        self,
        project_id: str,
        config: CodeUnderstandingConfig,
        cancel_check: Callable[[], bool] | None = None,
        db_session_factory: Any | None = None,
    ) -> ProjectDoc:
        store_path = f"~/.iw-ai-core/indexes/{project_id}/vectors"
        table_name = f"code_{project_id.replace('-', '_')}"

        embed = OllamaEmbedding(
            model_name=config.resolved_embed_model(),
            base_url=config.ollama_url,
        )

        vector_store = LanceDBVectorStore(
            uri=store_path,
            table_name=table_name,
        )

        index = VectorStoreIndex.from_vector_store(vector_store, embed_model=embed)
        query_engine = index.as_query_engine()

        answers: dict[str, str] = {}

        for key, question in self.QUESTIONS:
            if cancel_check and cancel_check():
                raise asyncio.CancelledError("map generation cancelled")
            response = query_engine.query(question)
            answers[key] = str(response)

        mermaid = self._build_mermaid(answers["components"])
        markdown = self._assemble_markdown(answers, mermaid)

        def do_upsert() -> ProjectDoc:
            from orch.db.session import SessionLocal as DefaultSessionLocal

            factory = db_session_factory or DefaultSessionLocal
            with factory() as session:
                project = session.get(Project, project_id)
                if project is None:
                    raise ValueError(f"Project {project_id} not found")

                doc_service = DocService(session)
                doc, _ = doc_service.upsert_doc(
                    project_id=project_id,
                    doc_id="architecture-map",
                    title=f"{project.display_name} — Architecture Map",
                    content=markdown,
                    generated_by="code-understanding:level1",
                )
                session.commit()
                return doc

        return await asyncio.to_thread(do_upsert)

    def _build_mermaid(self, components_answer: str) -> str:
        llm = Ollama(
            model="gemma4:e4b",
            base_url="http://localhost:11434",
        )
        prompt = (
            f"Given these components: {components_answer}\n"
            "Generate a Mermaid graph TD diagram showing the relationships between components.\n"
            "Output ONLY the Mermaid code block, no explanation.\n"
        )
        response = llm.complete(prompt)
        text = response.text

        match = re.search(r"```mermaid\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return "graph TD\n  A[System]"

    def _assemble_markdown(self, answers: dict[str, str], mermaid: str) -> str:
        section_keys = [k for k, _ in self.QUESTIONS]
        lines = ["# Architecture Map", ""]
        for key in section_keys:
            value = answers.get(key, "")
            label = key.replace("_", " ").title()
            lines.append(f"## {label}")
            lines.append(value)
            lines.append("")
        lines.append("## Architecture Diagram")
        lines.append("")
        lines.append("```mermaid")
        lines.append(mermaid)
        lines.append("```")
        return "\n".join(lines)
