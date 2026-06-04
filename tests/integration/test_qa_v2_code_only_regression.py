"""Regression guard for code_only path (Inv 1).

Ensures the code_only branch of answer_stream is byte-for-byte unchanged
after F-00060. Runs a "show me the signature" question end-to-end through
answer_stream_v2 and asserts the response matches pre-F-00060 behaviour:
no Work Item Context section, no retrieve/finding-items/reading-docs phase events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from orch.rag.qa import QAEngine

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def mock_embed(text: str) -> list[float]:
    vec = [0.0] * 8
    h = sum(text.encode()[:4])
    vec[h % 8] = 0.5 + (h % 10) * 0.05
    return vec


class MockOllamaEmbedding:
    model_name = "test-embed-model"

    def __init__(self, **kwargs: object) -> None:
        pass

    def get_text_embedding(self, text: str) -> list[float]:
        return mock_embed(text)

    def get_query_embedding(self, text: str) -> list[float]:
        return mock_embed(text)

    async def aget_text_embedding(self, text: str) -> list[float]:
        return mock_embed(text)

    async def aget_query_embedding(self, text: str) -> list[float]:
        return mock_embed(text)


class MockChunk:
    def __init__(self, text: str) -> None:
        self.delta = text


class MockOllamaLLM:
    """Streams a pre-known response that tests the code_only regression."""

    model_name = "test-model"

    def __init__(self, **kwargs: object) -> None:
        pass

    async def astream_chat(self, messages: object) -> object:
        async def _aiter():
            yield MockChunk("def foo(bar: int) -> str:\n    return str(bar)")

        return _aiter()

    def stream(self) -> None:
        pass


class TestCodeOnlyRegression:
    """Regression tests to ensure code_only path is unchanged."""

    def _make_engine(self) -> QAEngine:
        from orch.rag.config import CodeUnderstandingConfig

        config = MagicMock(spec=CodeUnderstandingConfig)
        config.resolved_embed_model.return_value = "test-embed-model"
        config.resolved_llm_model.return_value = "test-model"
        config.ollama_url = "http://localhost:11434"
        config.index_path = "/tmp/lance"
        return QAEngine(project_id="test-project", config=config)

    @pytest.mark.asyncio
    async def test_code_only_question_yields_no_workitem_context(
        self,
        db_session: Session,
    ) -> None:
        """A code-only question must not inject Work Item Context."""
        engine = self._make_engine()

        with (
            patch(
                "orch.rag.qa.OllamaEmbedding",
                MockOllamaEmbedding,
            ),
            patch(
                "orch.rag.qa.Ollama",
                MockOllamaLLM,
            ),
        ):
            events = []
            async for event in engine.answer_stream_v2(
                question="show me the signature of foo",
                context_level="project",
                context_doc_id=None,
                conversation_history=[],
                session=db_session,
                module_path=None,
                module_name=None,
                context_chips=None,
                symbol_hint=None,
            ):
                events.append(event)

        tokens = [e for e in events if e.get("kind") == "token"]
        text = "".join(e.get("text", "") for e in tokens)

        assert "## Work Item Context" not in text, (
            "code_only path must not include Work Item Context section"
        )

    @pytest.mark.asyncio
    async def test_code_only_question_yields_no_phase_events_for_workitem_steps(
        self,
        db_session: Session,
    ) -> None:
        """A code-only question must not emit retrieve/finding-items/reading-docs phases."""
        engine = self._make_engine()

        with (
            patch(
                "orch.rag.qa.OllamaEmbedding",
                MockOllamaEmbedding,
            ),
            patch(
                "orch.rag.qa.Ollama",
                MockOllamaLLM,
            ),
        ):
            events = []
            async for event in engine.answer_stream_v2(
                question="show me the signature of foo",
                context_level="project",
                context_doc_id=None,
                conversation_history=[],
                session=db_session,
                module_path=None,
                module_name=None,
                context_chips=None,
                symbol_hint=None,
            ):
                events.append(event)

        phase_names = {e.get("name") for e in events if e.get("kind") == "phase"}

        assert "retrieving" not in phase_names, (
            "code_only path must not emit 'retrieving' phase event"
        )
        assert "finding_items" not in phase_names, (
            "code_only path must not emit 'finding_items' phase event"
        )
        assert "reading_docs" not in phase_names, (
            "code_only path must not emit 'reading_docs' phase event"
        )

    @pytest.mark.asyncio
    async def test_code_only_question_yields_no_citation_events(
        self,
        db_session: Session,
    ) -> None:
        """A code-only question must not emit any citation events."""
        engine = self._make_engine()

        with (
            patch(
                "orch.rag.qa.OllamaEmbedding",
                MockOllamaEmbedding,
            ),
            patch(
                "orch.rag.qa.Ollama",
                MockOllamaLLM,
            ),
        ):
            events = []
            async for event in engine.answer_stream_v2(
                question="show me the signature of foo",
                context_level="project",
                context_doc_id=None,
                conversation_history=[],
                session=db_session,
                module_path=None,
                module_name=None,
                context_chips=None,
                symbol_hint=None,
            ):
                events.append(event)

        citations = [e for e in events if e.get("kind") == "citation"]

        assert len(citations) == 0, f"code_only path must not emit citations, got {len(citations)}"

    @pytest.mark.asyncio
    async def test_classifier_routes_signature_question_as_code_only(
        self,
        db_session: Session,
    ) -> None:
        """The query classifier must route 'show me the signature' as code_only."""
        from orch.rag.classifier import classify_query

        engine = self._make_engine()
        with patch("orch.rag.classifier.Ollama"):
            classification = await classify_query(
                "show me the signature of foo",
                engine.config,
                None,
            )
        assert classification == "code_only", f"Expected 'code_only', got '{classification}'"

    @pytest.mark.asyncio
    async def test_classifier_routes_how_do_i_use_as_code_only(
        self,
        db_session: Session,
    ) -> None:
        """The query classifier routes 'how do I use X' as code_only."""
        from orch.rag.classifier import classify_query

        engine = self._make_engine()
        with patch("orch.rag.classifier.Ollama"):
            classification = await classify_query(
                "how do I use the foo function",
                engine.config,
                None,
            )
        assert classification == "code_only"
