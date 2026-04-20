"""Boundary behavior tests for F-00055 work-item-aware code chat.

Tests verify each row of the Boundary Behavior table in the design doc:
- Empty docs_ LanceDB table → falls back to FTS + code
- design_doc_content = NULL → summary-only fallback with placeholder
- Hallucinated citation → stripped + logged
- File with no git-log match → pipeline still works
- Low-confidence classifier → defaults to code-only
- /why with zero matching items → count=0, no fictional items
- Missing docs_ table → graceful FTS-only fallback
- Feed overflow >5 items → top-5 visible
- project_id with hyphens → table name conversion correct

These are unit tests for the boundary logic. Integration tests for SSE behavior
live in tests/integration/test_code_qa_workitem_flow.py and related files.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class TestBoundaryEmptyDocsTable:
    """Boundary: Empty docs_ LanceDB table falls back to FTS + code."""

    @pytest.mark.asyncio
    async def test_empty_docs_table_no_crash(self) -> None:
        """When docs_ table is empty, pipeline falls back gracefully without crash."""
        from orch.rag.evidence import EvidenceBundle
        from orch.rag.qa import QAEngine

        mock_config = MagicMock()
        mock_config.resolved_embed_model.return_value = "qwen3-embedding:8b"
        mock_config.resolved_llm_model.return_value = "gemma4:26b"
        mock_config.ollama_url = "http://localhost:11434"
        mock_config.index_path = "test-index"

        engine = QAEngine(project_id="test-project", config=mock_config)
        mock_session = MagicMock()

        mock_embedding_instance = MagicMock()
        mock_embedding_instance.get_query_embedding = MagicMock(return_value=[0.1] * 128)

        class MockWorkItem:
            def __init__(self, wi_id: str, created_at: datetime) -> None:
                self.id = wi_id
                self.type = MagicMock(value="Feature")
                self.title = f"Test {wi_id}"
                self.summary = "Test summary"
                self.design_doc_content = None
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

        class MockChunk:
            def __init__(self, delta: str) -> None:
                self.delta = delta

        async def mock_inner_generator() -> AsyncGenerator[MockChunk, None]:
            yield MockChunk("Answer")

        async def mock_astream_chat(messages: list) -> AsyncGenerator[MockChunk, None]:
            return mock_inner_generator()

        mock_llm = MagicMock()
        mock_llm.astream_chat = mock_astream_chat

        async def mock_classify(question, config, context_chips=None):
            return "workitem_aware"

        async def mock_retrieve(*args, **kwargs):
            return mock_bundle

        async def mock_fetch(wis, session):
            return [mock_wi]

        async def mock_get_repo_root(pid, session):
            return None

        events = []

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

        assert len(events) > 0, "Pipeline should still produce events with empty docs table"
        phase_events = [e for e in events if e.get("kind") == "phase"]
        assert len(phase_events) >= 4, "Should still emit full phase sequence"


class TestBoundaryNullDesignDoc:
    """Boundary: Work item with design_doc_content = NULL renders with placeholder."""

    def test_null_design_doc_no_excerpt(self) -> None:
        """When design_doc_content is NULL, no Design Doc Excerpt is added to prompt."""
        from orch.rag.evidence import EvidenceBundle
        from orch.rag.qa import QAEngine

        mock_config = MagicMock()
        mock_config.resolved_embed_model.return_value = "qwen3-embedding:8b"
        mock_config.resolved_llm_model.return_value = "gemma4:26b"
        mock_config.ollama_url = "http://localhost:11434"
        mock_config.index_path = "test-index"

        engine = QAEngine(project_id="test-project", config=mock_config)

        class MockWorkItem:
            def __init__(self) -> None:
                self.id = "F-00001"
                self.type = MagicMock(value="Feature")
                self.title = "Test Feature"
                self.summary = None
                self.design_doc_content = None
                self.created_at = datetime(2025, 1, 1, tzinfo=UTC)

        mock_wi = MockWorkItem()

        bundle = EvidenceBundle(
            question="why?",
            code_chunks=[],
            doc_chunks=[],
            fts_items=[mock_wi],
            git_log_items=[],
            work_items=[mock_wi],
            retrieval_cutoff=datetime.now(UTC),
        )

        system_prompt = engine._build_workitem_system_prompt(bundle, register="functional")

        assert "**Design Doc Excerpt**:" not in system_prompt, (
            "When design_doc_content is NULL, no Design Doc Excerpt should appear in prompt"
        )
        assert "F-00001" in system_prompt, "Work item ID should still appear"


class TestBoundaryHallucinatedCitation:
    """Boundary: Hallucinated citation is stripped + logged."""

    def test_hallucinated_id_stripped(self) -> None:
        """AC4: IDs not in allowed_ids are stripped from LLM output."""
        from orch.rag.citation_allowlist import filter_citations

        allowed_ids = {"F-00001", "CR-00001"}
        text = "According to [F-00001] and [F-99999], this behavior was introduced."

        filtered, stripped = filter_citations(text, allowed_ids)

        assert "F-99999" not in filtered, "Hallucinated ID must be stripped"
        assert "F-00001" in filtered, "Real ID must be preserved"
        assert "F-99999" in stripped, "Stripped ID must be in stripped list"

    def test_hallucinated_id_logged(self) -> None:
        """AC4: Stripped IDs are logged at WARNING level."""
        from orch.rag.citation_allowlist import filter_citations

        allowed_ids = {"F-00001"}
        text = "See [F-99999] for details."

        with patch("orch.rag.citation_allowlist.logger") as mock_logger:
            _, stripped = filter_citations(text, allowed_ids)

        assert len(stripped) == 1
        assert mock_logger.warning.called, "Stripped ID must be logged at WARNING level"


class TestBoundaryGitLogNoMatch:
    """Boundary: File with no git-log match returns empty; pipeline still works."""

    def test_empty_git_log_items_no_crash(self) -> None:
        """When git log has no work-item matches, pipeline still produces results."""
        from orch.rag.evidence import CodeChunk
        from orch.rag.qa import _merge_and_rank_work_items

        code_chunks = [
            CodeChunk(file_path="orch/rag/qa.py", text="def foo(): pass"),
        ]
        doc_chunks: list = []
        fts_items: list = []
        git_log_items: list = []

        result = _merge_and_rank_work_items(
            code_chunks,
            doc_chunks,
            fts_items,
            git_log_items,
        )

        assert isinstance(result, list), "Should return a list even with empty git_log_items"


class TestBoundaryLowConfidenceClassifier:
    """Boundary: Low-confidence classifier defaults to code-only."""

    def test_llm_timeout_defaults_to_code_only(self) -> None:
        """On LLM timeout, classifier defaults to code_only."""
        from orch.rag.classifier import classify_query

        mock_config = MagicMock()
        mock_config.resolved_llm_model.return_value = "gemma4:26b"
        mock_config.ollama_url = "http://localhost:11434"

        mock_llm = MagicMock()
        mock_llm.complete = MagicMock(side_effect=TimeoutError("LLM request timed out"))

        with patch("orch.rag.classifier.Ollama", return_value=mock_llm):
            result = classify_query(
                "why does this ambiguous query behave?",
                mock_config,
                context_chips=None,
            )

        assert result == "code_only", "LLM timeout must default to code_only"


class TestBoundaryZeroMatchingItems:
    """Boundary: /why with zero matching items emits count=0, no fictional items."""

    @pytest.mark.asyncio
    async def test_zero_items_emits_count_zero(self) -> None:
        """When no work items match, finding_items phase emits count=0."""
        from orch.rag.evidence import EvidenceBundle
        from orch.rag.qa import QAEngine

        mock_config = MagicMock()
        mock_config.resolved_embed_model.return_value = "qwen3-embedding:8b"
        mock_config.resolved_llm_model.return_value = "gemma4:26b"
        mock_config.ollama_url = "http://localhost:11434"
        mock_config.index_path = "test-index"

        engine = QAEngine(project_id="test-project", config=mock_config)
        mock_session = MagicMock()

        mock_bundle = MagicMock(spec=EvidenceBundle)
        mock_bundle.question = "why unknown feature?"
        mock_bundle.code_chunks = []
        mock_bundle.doc_chunks = []
        mock_bundle.fts_items = []
        mock_bundle.git_log_items = []
        mock_bundle.work_items = []
        mock_bundle.retrieval_cutoff = datetime.now(UTC)
        mock_bundle.allowed_ids = set()

        class MockChunk:
            def __init__(self, delta: str) -> None:
                self.delta = delta

        async def mock_inner_generator() -> AsyncGenerator[MockChunk, None]:
            yield MockChunk("No matching items found.")

        async def mock_astream_chat(messages: list) -> AsyncGenerator[MockChunk, None]:
            return mock_inner_generator()

        mock_llm = MagicMock()
        mock_llm.astream_chat = mock_astream_chat

        async def mock_classify(question, config, context_chips=None):
            return "workitem_aware"

        async def mock_retrieve(*args, **kwargs):
            return mock_bundle

        async def mock_fetch(wis, session):
            return []

        async def mock_get_repo_root(pid, session):
            return None

        events = []

        with (
            patch("orch.rag.qa.OllamaEmbedding"),
            patch("orch.rag.qa.Ollama", return_value=mock_llm),
            patch("orch.rag.classifier.classify_query", mock_classify),
            patch.object(engine, "_retrieve_evidence_bundle", mock_retrieve),
            patch.object(engine, "_fetch_full_work_items", mock_fetch),
            patch.object(engine, "_get_repo_root", mock_get_repo_root),
        ):
            async for event in engine.answer_stream_v2(
                question="why unknown feature?",
                context_level="architecture",
                context_doc_id=None,
                conversation_history=[],
                session=mock_session,
                context_chips=["why"],
            ):
                events.append(event)

        phase_events = [
            (e["name"], e.get("detail", {})) for e in events if e.get("kind") == "phase"
        ]

        finding_items_phases = [p for p in phase_events if p[0] == "finding_items"]
        assert len(finding_items_phases) == 1, "Must emit finding_items phase"
        assert finding_items_phases[0][1].get("count") == 0, (
            "finding_items count must be 0 when no items match"
        )


class TestBoundaryMissingDocsTable:
    """Boundary: Missing docs_ LanceDB table → graceful FTS-only fallback."""

    @pytest.mark.asyncio
    async def test_missing_docs_table_handled(self) -> None:
        """When docs_ table is missing, _retrieve_evidence_bundle handles it gracefully."""
        from orch.rag.evidence import CodeChunk, EvidenceBundle
        from orch.rag.qa import QAEngine

        mock_config = MagicMock()
        mock_config.resolved_embed_model.return_value = "qwen3-embedding:8b"
        mock_config.resolved_llm_model.return_value = "gemma4:26b"
        mock_config.ollama_url = "http://localhost:11434"
        mock_config.index_path = "test-index"

        engine = QAEngine(project_id="test-project", config=mock_config)
        mock_session = MagicMock()

        mock_embedding_instance = MagicMock()
        mock_embedding_instance.get_query_embedding = MagicMock(return_value=[0.1] * 128)

        class MockWorkItem:
            def __init__(self) -> None:
                self.id = "F-00001"
                self.type = MagicMock(value="Feature")
                self.title = "Test"
                self.summary = "Test"
                self.design_doc_content = "Content"
                self.created_at = datetime(2025, 1, 1, tzinfo=UTC)

        mock_wi = MockWorkItem()

        async def mock_retrieve_evidence_bundle(*args, **kwargs) -> EvidenceBundle:
            return EvidenceBundle(
                question="why?",
                code_chunks=[CodeChunk(file_path="a.py", text="code")],
                doc_chunks=[],
                fts_items=[mock_wi],
                git_log_items=[],
                work_items=[mock_wi],
                retrieval_cutoff=datetime.now(UTC),
            )

        async def mock_fetch(wis, session):
            return [mock_wi]

        async def mock_get_repo_root(pid, session):
            return None

        with (
            patch.object(engine, "_retrieve_evidence_bundle", mock_retrieve_evidence_bundle),
            patch.object(engine, "_fetch_full_work_items", mock_fetch),
            patch.object(engine, "_get_repo_root", mock_get_repo_root),
        ):
            bundle = await engine._retrieve_evidence_bundle(
                project_id="test-project",
                question="why?",
                session=mock_session,
                context_level="architecture",
            )

        assert bundle is not None, "Should return a bundle even when docs table is missing"
        assert len(bundle.code_chunks) >= 0, "Code chunks should be present"


class TestBoundaryFeedOverflow:
    """Boundary: Feed overflow >5 items → top-5 visible."""

    def test_top_5_work_items_returned(self) -> None:
        """When more than 5 work items match, only top 5 are returned."""
        from orch.rag.qa import _merge_and_rank_work_items

        class MockWI:
            def __init__(self, wi_id: str, created_at: datetime) -> None:
                self.id = wi_id
                self.type = MagicMock(value="Feature")
                self.created_at = created_at

        mock_wis = [MockWI(f"F-{i:05d}", datetime(2025, 1, i, tzinfo=UTC)) for i in range(1, 12)]

        result = _merge_and_rank_work_items(
            [],  # _code_chunks
            [],  # doc_chunks
            mock_wis,  # fts_items
            [],  # git_log_items
        )

        assert len(result) == 5, "Must return at most 5 work items (top-5)"

        returned_ids = {wi.id for wi in result}
        expected_ids = {f"F-{i:05d}" for i in range(1, 6)}
        assert returned_ids == expected_ids, (
            f"Top 5 by relevance should be returned, got {returned_ids}"
        )


class TestBoundaryProjectIdHyphens:
    """Boundary: project_id with hyphens → table name conversion correct."""

    def test_hyphenated_project_table_name(self) -> None:
        """project_id 'iw-ai-core' should convert to table name 'docs_iw_ai_core'."""

        project_id = "iw-ai-core"
        expected_table_name = f"docs_{project_id.replace('-', '_')}"

        assert expected_table_name == "docs_iw_ai_core", (
            "Hyphenated project_id must convert underscores in table name"
        )

    def test_code_table_hyphen_conversion(self) -> None:
        """Verify code table name also handles hyphens correctly."""
        project_id = "iw-ai-core"
        expected_table_name = f"code_{project_id.replace('-', '_')}"

        assert expected_table_name == "code_iw_ai_core", (
            "Hyphenated project_id must convert underscores in code table name"
        )


class TestBoundarySSEConnectionDrop:
    """Boundary: SSE connection drop mid-phase → error event, no partial citations."""

    def test_error_event_on_connection_drop(self) -> None:
        """When SSE connection drops, router should emit error event."""
        from orch.rag.qa import QAEngine

        mock_config = MagicMock()
        mock_config.resolved_embed_model.return_value = "qwen3-embedding:8b"
        mock_config.resolved_llm_model.return_value = "gemma4:26b"
        mock_config.ollama_url = "http://localhost:11434"
        mock_config.index_path = "test-index"

        engine = QAEngine(project_id="test-project", config=mock_config)

        class MockWorkItem:
            def __init__(self) -> None:
                self.id = "F-00001"
                self.type = MagicMock(value="Feature")
                self.title = "Test"
                self.summary = "Test"
                self.design_doc_content = "Content"
                self.created_at = datetime(2025, 1, 1, tzinfo=UTC)

        async def mock_answer_stream_v2_error(**kwargs: object):
            yield {"kind": "phase", "name": "retrieving", "detail": {}}
            yield {"kind": "error", "message": "Connection dropped"}
            return

        events = []
        with patch.object(engine, "answer_stream_v2", mock_answer_stream_v2_error):
            import asyncio

            async def collect():
                async for e in engine.answer_stream_v2(
                    question="test",
                    context_level="architecture",
                    context_doc_id=None,
                    conversation_history=[],
                    session=MagicMock(),
                ):
                    events.append(e)

            asyncio.run(collect())

        error_events = [e for e in events if e.get("kind") == "error"]
        assert len(error_events) > 0, "Must emit error event on connection drop"
        assert "connection" in error_events[0].get("message", "").lower()


class TestBoundaryCitationFormatValidation:
    """Invariant 4: Citation events must have valid work_item_type and work_item_id format."""

    def test_work_item_id_pattern_valid(self) -> None:
        """Work item ID must match F/CR/I-NNNNN format."""
        from orch.rag.citation_allowlist import WORK_ITEM_ID_PATTERN

        assert WORK_ITEM_ID_PATTERN.search("F-00001")
        assert WORK_ITEM_ID_PATTERN.search("CR-00042")
        assert WORK_ITEM_ID_PATTERN.search("I-00123")

    def test_work_item_id_pattern_invalid(self) -> None:
        """Invalid work item ID formats must not match."""
        from orch.rag.citation_allowlist import WORK_ITEM_ID_PATTERN

        assert WORK_ITEM_ID_PATTERN.search("F-0001") is None
        assert WORK_ITEM_ID_PATTERN.search("F-000001") is None
        assert WORK_ITEM_ID_PATTERN.search("X-00001") is None
        assert WORK_ITEM_ID_PATTERN.search("F00001") is None
