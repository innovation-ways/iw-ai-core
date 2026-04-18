"""QAEngine — context-aware RAG Q&A engine with streaming response and conversation history."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import httpx
from llama_index.core.llms import ChatMessage
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from sqlalchemy import select

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from sqlalchemy.ext.asyncio import AsyncSession

    from orch.rag.config import CodeUnderstandingConfig


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

    async def answer_stream(
        self,
        question: str,
        context_level: str,
        context_doc_id: str | None,
        conversation_history: list[dict[str, str]],
        session: AsyncSession,
        module_path: str | None = None,
        module_name: str | None = None,
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
                query = (
                    table.search(embedding_vector)
                    .where(f"file_path LIKE '{module_path}%' AND {seed_filter}")
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
        if context_doc_id is not None:
            from orch.db.models import ProjectDoc

            result = await session.execute(
                select(ProjectDoc).where(ProjectDoc.id == context_doc_id)
            )
            doc = result.scalar_one_or_none()
            if doc:
                context_doc_content = doc.content or ""

        system_prompt = self._build_system_prompt(
            context_doc_content, chunks, module_path, module_name, fallback_triggered
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

    def _build_system_prompt(
        self,
        context_doc_content: str,
        chunks: list[str],
        module_path: str | None = None,
        module_name: str | None = None,
        fallback_triggered: bool = False,
    ) -> str:
        """
        Build the system prompt with optional module-focus block, optional retrieval-note block,
        architecture context, and relevant code excerpts.

        The module block is emitted only when module_path is non-empty.
        The retrieval-note block is emitted only when fallback_triggered is True.
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

        return (
            "You are a codebase expert assistant. "
            "Answer questions about the codebase accurately and concisely.\n\n"
            f"{module_block}"
            f"{retrieval_note}"
            "## Architecture Context\n\n"
            f"{ctx}\n\n"
            "## Relevant Code Excerpts\n\n"
            f"{excerpts}\n\n"
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
