"""ModuleGenerator — Level 2 module doc generation via LanceDB RAG + Ollama."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import lancedb  # type: ignore[import-untyped]
from llama_index.embeddings.ollama import OllamaEmbedding
from sqlalchemy import select

from orch.db.models import DocTier, DocType, EditorialCategory, ProjectDoc
from orch.doc_service import DocService

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.rag.config import CodeUnderstandingConfig


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
        index_path = os.environ.get("IW_CORE_INDEX_PATH", "~/.iw-ai-core/indexes")
        store_path = Path(index_path).expanduser() / project_id / "vectors"
        table_name = f"code_{project_id.replace('-', '_')}"

        db = lancedb.connect(str(store_path))
        table = db.open_table(table_name)

        embed_model = config.resolved_embed_model()
        llm_model = config.resolved_llm_model()
        ollama_url = config.ollama_url

        embed = OllamaEmbedding(model_name=embed_model, base_url=ollama_url)

        answers: list[str] = []
        for question_template in self.MODULE_QUESTIONS:
            question = question_template.format(module=module_name)
            embedding = await embed.aget_text_embedding(question)

            results = (
                table.search(embedding).where(f"file_path LIKE '{module_path}%'").limit(5).to_list()
            )

            context_chunks = [r.get("text", "") for r in results if r.get("text")]
            context = "\n\n---\n\n".join(context_chunks)

            answer = await self._call_ollama(question, context, llm_model, ollama_url)
            answers.append(answer)

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
        return doc

    async def _call_ollama(self, question: str, context: str, model: str, ollama_url: str) -> str:
        prompt = f"""Context from the codebase:

{context}

Question: {question}

Provide a concise, informative answer based on the context above."""

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{ollama_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            data: dict[str, str] = response.json()
            result: str = data.get("response", "")
            return result

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
