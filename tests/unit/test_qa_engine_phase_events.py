"""Unit tests for QAEngine phase events in answer_stream_v2."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class TestPhaseEventSequence:
    """Tests for phase event emission in answer_stream_v2."""

    @pytest.fixture
    def mock_config(self) -> MagicMock:
        """Create a mock CodeUnderstandingConfig."""
        config = MagicMock()
        config.resolved_embed_model.return_value = "qwen3-embedding:8b"
        config.resolved_llm_model.return_value = "gemma4:26b"
        config.ollama_url = "http://localhost:11434"
        config.index_path = "test-index"
        return config

    @pytest.mark.asyncio
    async def test_code_only_emits_no_phase_events(self, mock_config: MagicMock) -> None:
        """AC9/Invariant 3: code_only pipeline emits no phase events."""
        from orch.rag.qa import QAEngine

        engine = QAEngine(project_id="test-project", config=mock_config)

        mock_session = MagicMock()
        mock_embedding_instance = MagicMock()
        mock_embedding_instance.get_query_embedding = MagicMock(return_value=[0.1] * 128)

        class MockChunk:
            def __init__(self, delta: str) -> None:
                self.delta = delta

        async def mock_inner_generator() -> AsyncGenerator[MockChunk, None]:
            yield MockChunk("Answer")

        async def mock_astream_chat(messages: list) -> AsyncGenerator[MockChunk, None]:
            return mock_inner_generator()

        mock_llm = MagicMock()
        mock_llm.astream_chat = mock_astream_chat

        events = []

        async def mock_classify(question, config, context_chips):
            return "code_only"

        with (
            patch("orch.rag.qa.OllamaEmbedding", return_value=mock_embedding_instance),
            patch("orch.rag.qa.Ollama", return_value=mock_llm),
            patch("orch.rag.classifier.classify_query", mock_classify),
        ):
            async for event in engine.answer_stream_v2(
                question="show me the signature of parse_id",
                context_level="architecture",
                context_doc_id=None,
                conversation_history=[],
                session=mock_session,
            ):
                events.append(event)

        phase_events = [e for e in events if e.get("kind") == "phase"]
        assert len(phase_events) == 0, "code_only pipeline should emit no phase events"

    @pytest.mark.asyncio
    async def test_workitem_aware_emits_correct_phase_sequence(
        self, mock_config: MagicMock
    ) -> None:
        """Invariant 2: phase events follow correct sequence."""
        from orch.rag.evidence import EvidenceBundle
        from orch.rag.qa import QAEngine

        engine = QAEngine(project_id="test-project", config=mock_config)

        mock_session = MagicMock()

        class MockWorkItem:
            def __init__(self, wi_id: str, created_at: datetime) -> None:
                self.id = wi_id
                self.type = MagicMock(value="Feature")
                self.title = f"Test {wi_id}"
                self.summary = "Test summary"
                self.design_doc_content = "Test content"
                self.created_at = created_at

        mock_wi = MockWorkItem("F-00001", datetime(2025, 1, 1, tzinfo=UTC))

        mock_bundle = MagicMock(spec=EvidenceBundle)
        mock_bundle.question = "why does it work?"
        mock_bundle.code_chunks = []
        mock_bundle.doc_chunks = []
        mock_bundle.fts_items = []
        mock_bundle.git_log_items = []
        mock_bundle.work_items = [mock_wi]
        mock_bundle.retrieval_cutoff = datetime.now(UTC)
        mock_bundle.allowed_ids = {"F-00001"}

        mock_embedding_instance = MagicMock()
        mock_embedding_instance.get_query_embedding = MagicMock(return_value=[0.1] * 128)

        class MockChunk:
            def __init__(self, delta: str) -> None:
                self.delta = delta

        async def mock_inner_generator() -> AsyncGenerator[MockChunk, None]:
            yield MockChunk("Answer")

        async def mock_astream_chat(messages: list) -> AsyncGenerator[MockChunk, None]:
            return mock_inner_generator()

        mock_llm = MagicMock()
        mock_llm.astream_chat = mock_astream_chat

        events = []

        async def mock_classify(question, config, context_chips):
            return "workitem_aware"

        async def mock_retrieve(*args, **kwargs):
            return mock_bundle

        async def mock_fetch(wis, session):
            return [mock_wi]

        async def mock_get_repo_root(pid, session):
            return None

        with (
            patch("orch.rag.qa.OllamaEmbedding", return_value=mock_embedding_instance),
            patch("orch.rag.qa.Ollama", return_value=mock_llm),
            patch("orch.rag.classifier.classify_query", mock_classify),
            patch.object(engine, "_retrieve_evidence_bundle", mock_retrieve),
            patch.object(engine, "_fetch_full_work_items", mock_fetch),
            patch.object(engine, "_get_repo_root", mock_get_repo_root),
        ):
            async for event in engine.answer_stream_v2(
                question="why does it work?",
                context_level="architecture",
                context_doc_id=None,
                conversation_history=[],
                session=mock_session,
            ):
                events.append(event)

        phase_events = [
            (e["name"], e.get("detail", {})) for e in events if e.get("kind") == "phase"
        ]

        assert len(phase_events) >= 4, f"Expected at least 4 phase events, got {len(phase_events)}"
        phase_names = [p[0] for p in phase_events]

        expected_sequence = ["retrieving", "finding_items", "reading_docs", "composing"]
        assert phase_names[:4] == expected_sequence, (
            f"Phase sequence should be {expected_sequence}, got {phase_names[:4]}"
        )

    @pytest.mark.asyncio
    async def test_citation_events_emitted_after_reading_docs(self, mock_config: MagicMock) -> None:
        """Citation events are emitted after reading_docs phase."""
        from orch.rag.evidence import EvidenceBundle
        from orch.rag.qa import QAEngine

        engine = QAEngine(project_id="test-project", config=mock_config)

        mock_session = MagicMock()

        class MockWorkItem:
            def __init__(self, wi_id: str, created_at: datetime) -> None:
                self.id = wi_id
                self.type = MagicMock(value="Feature")
                self.title = f"Test {wi_id}"
                self.summary = "Test summary"
                self.design_doc_content = "Test content"
                self.functional_doc_content = "Test functional content"
                self.created_at = created_at

        mock_wi = MockWorkItem("F-00001", datetime(2025, 1, 1, tzinfo=UTC))

        mock_bundle = MagicMock(spec=EvidenceBundle)
        mock_bundle.question = "why does it work?"
        mock_bundle.code_chunks = []
        mock_bundle.doc_chunks = []
        mock_bundle.fts_items = [mock_wi]
        mock_bundle.git_log_items = []
        mock_bundle.work_items = [mock_wi]
        mock_bundle.retrieval_cutoff = datetime.now(UTC)
        mock_bundle.allowed_ids = {"F-00001"}

        mock_embedding_instance = MagicMock()
        mock_embedding_instance.get_query_embedding = MagicMock(return_value=[0.1] * 128)

        class MockChunk:
            def __init__(self, delta: str) -> None:
                self.delta = delta

        async def mock_inner_generator() -> AsyncGenerator[MockChunk, None]:
            yield MockChunk("Based on F-00001")

        async def mock_astream_chat(messages: list) -> AsyncGenerator[MockChunk, None]:
            return mock_inner_generator()

        mock_llm = MagicMock()
        mock_llm.astream_chat = mock_astream_chat

        events = []

        async def mock_classify(question, config, context_chips):
            return "workitem_aware"

        async def mock_retrieve(*args, **kwargs):
            return mock_bundle

        async def mock_fetch(wis, session):
            return [mock_wi]

        async def mock_get_repo_root(pid, session):
            return None

        with (
            patch("orch.rag.qa.OllamaEmbedding", return_value=mock_embedding_instance),
            patch("orch.rag.qa.Ollama", return_value=mock_llm),
            patch("orch.rag.classifier.classify_query", mock_classify),
            patch.object(engine, "_retrieve_evidence_bundle", mock_retrieve),
            patch.object(engine, "_fetch_full_work_items", mock_fetch),
            patch.object(engine, "_get_repo_root", mock_get_repo_root),
        ):
            async for event in engine.answer_stream_v2(
                question="why does it work?",
                context_level="architecture",
                context_doc_id=None,
                conversation_history=[],
                session=mock_session,
            ):
                events.append(event)

        citation_events = [e for e in events if e.get("kind") == "citation"]
        phase_events = [e for e in events if e.get("kind") == "phase"]

        assert len(citation_events) > 0, "Should emit citation events"

        reading_docs_idx = next(
            i for i, e in enumerate(phase_events) if e["name"] == "reading_docs"
        )
        first_citation_idx = events.index(citation_events[0])

        assert first_citation_idx > reading_docs_idx, (
            "Citation events should come after reading_docs phase"
        )

    @pytest.mark.asyncio
    async def test_composing_phase_contains_render_id(self, mock_config: MagicMock) -> None:
        """AC5: composing phase detail contains render_id."""
        from orch.rag.evidence import EvidenceBundle
        from orch.rag.qa import QAEngine

        engine = QAEngine(project_id="test-project", config=mock_config)

        mock_session = MagicMock()

        class MockWorkItem:
            def __init__(self, wi_id: str, created_at: datetime) -> None:
                self.id = wi_id
                self.type = MagicMock(value="Feature")
                self.title = f"Test {wi_id}"
                self.summary = "Test summary"
                self.design_doc_content = "Test content"
                self.created_at = created_at

        mock_wi = MockWorkItem("F-00001", datetime(2025, 1, 1, tzinfo=UTC))

        mock_bundle = MagicMock(spec=EvidenceBundle)
        mock_bundle.question = "why does it work?"
        mock_bundle.code_chunks = []
        mock_bundle.doc_chunks = []
        mock_bundle.fts_items = []
        mock_bundle.git_log_items = []
        mock_bundle.work_items = [mock_wi]
        mock_bundle.retrieval_cutoff = datetime.now(UTC)
        mock_bundle.allowed_ids = {"F-00001"}

        mock_embedding_instance = MagicMock()
        mock_embedding_instance.get_query_embedding = MagicMock(return_value=[0.1] * 128)

        class MockChunk:
            def __init__(self, delta: str) -> None:
                self.delta = delta

        async def mock_inner_generator() -> AsyncGenerator[MockChunk, None]:
            yield MockChunk("Answer")

        async def mock_astream_chat(messages: list) -> AsyncGenerator[MockChunk, None]:
            return mock_inner_generator()

        mock_llm = MagicMock()
        mock_llm.astream_chat = mock_astream_chat

        events = []

        async def mock_classify(question, config, context_chips):
            return "workitem_aware"

        async def mock_retrieve(*args, **kwargs):
            return mock_bundle

        async def mock_fetch(wis, session):
            return [mock_wi]

        async def mock_get_repo_root(pid, session):
            return None

        with (
            patch("orch.rag.qa.OllamaEmbedding", return_value=mock_embedding_instance),
            patch("orch.rag.qa.Ollama", return_value=mock_llm),
            patch("orch.rag.classifier.classify_query", mock_classify),
            patch.object(engine, "_retrieve_evidence_bundle", mock_retrieve),
            patch.object(engine, "_fetch_full_work_items", mock_fetch),
            patch.object(engine, "_get_repo_root", mock_get_repo_root),
        ):
            async for event in engine.answer_stream_v2(
                question="why does it work?",
                context_level="architecture",
                context_doc_id=None,
                conversation_history=[],
                session=mock_session,
            ):
                events.append(event)

        composing_events = [
            e for e in events if e.get("kind") == "phase" and e["name"] == "composing"
        ]

        assert len(composing_events) > 0, "Should emit composing phase"
        assert "render_id" in composing_events[0].get("detail", {}), (
            "composing phase should contain render_id"
        )
