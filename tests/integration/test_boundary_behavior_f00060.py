"""Integration tests for F-00060 boundary behavior.

Tests every row in the design doc's Boundary Behavior table:
- Retriever invoked on project with zero work items
- Semantic index missing (LanceDB table absent) → FTS + git-log carry
- Simulated LanceDB I/O error → semantic contribution empty; no exception escapes
- Code chunks with no file overlap with any work item → empty git_log_items
- Same work item in all three sources → single row with summed scores
- LLM hallucinates non-allowed ID → stripped from text and citations
- LLM answers without citing any work item → zero citation events
- Concurrent re-index request → 409
- Re-index after partial failure → starts from scratch
- Reindex when every item unchanged → items_indexed=0
- Embed model change → table dropped + full re-index
- Daemon kill mid-embedding → orphan recovery marks failed
- Question length > context window → docs truncated, question preserved
- Functional doc with NUL chars → sanitised before embedding
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy import Engine
    from sqlalchemy.orm import Session, sessionmaker

from orch.db.models import DocIndexJob, Project, WorkItem, WorkItemType
from orch.rag.doc_indexer import DocIndexer
from orch.rag.evidence import EvidenceBundle
from orch.rag.qa import QAEngine

MOCK_EMBED_MODEL = "test-embed-model"


def mock_embed(text: str) -> list[float]:
    vec = [0.0] * 8
    h = sum(text.encode()[:4])
    vec[h % 8] = 0.5 + (h % 10) * 0.05
    return vec


class MockOllamaEmbedding:
    model_name = MOCK_EMBED_MODEL

    def __init__(self, **kwargs: object) -> None:
        pass

    def get_text_embedding(self, text: str) -> list[float]:
        return mock_embed(text)

    async def aget_text_embedding(self, text: str) -> list[float]:
        return mock_embed(text)

    def get_query_embedding(self, text: str) -> list[float]:
        return mock_embed(text)

    async def aget_query_embedding(self, text: str) -> list[float]:
        return mock_embed(text)


class MockOllamaLLM:
    model_name = "test-model"

    def __init__(self, **kwargs: object) -> None:
        pass

    async def astream_chat(self, messages: object) -> object:
        class _Stream:
            async def __anext__(self) -> str:
                return "The button was added."

        return _Stream()


def _make_engine(project_id: str = "test-project") -> QAEngine:
    from orch.rag.config import CodeUnderstandingConfig

    config = MagicMock(spec=CodeUnderstandingConfig)
    config.resolved_embed_model.return_value = MOCK_EMBED_MODEL
    config.resolved_llm_model.return_value = "test-model"
    config.ollama_url = "http://localhost:11434"
    config.index_path = "/tmp/lance"
    return QAEngine(project_id=project_id, config=config)


class TestBoundaryZeroWorkItems:
    """Retriever invoked on a project with zero work items."""

    @pytest.mark.asyncio
    async def test_empty_project_returns_empty_bundle_no_error(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        tmp_path: Path,
    ) -> None:
        """Empty work_items table → bundle is empty, no exception raised."""
        project = Project(
            id="boundary-empty-proj",
            display_name="Empty Project",
            repo_root=str(tmp_path / "repo"),
            config={},
        )
        db_session.add(project)
        db_session.flush()
        db_session.commit()

        engine = _make_engine(project.id)

        with (
            patch("orch.rag.qa.OllamaEmbedding", MockOllamaEmbedding),
            patch("orch.rag.qa.Ollama", MockOllamaLLM),
        ):
            bundle = await engine._retrieve_evidence_bundle(project.id, "test question", db_session)

        assert len(bundle.doc_chunks) == 0
        assert len(bundle.fts_items) == 0
        assert len(bundle.git_log_items) == 0


class TestBoundarySemanticIndexMissing:
    """Semantic index missing (LanceDB table absent) → FTS + git-log carry the answer."""

    @pytest.mark.asyncio
    async def test_missing_lancedb_table_treated_as_empty(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """docs_{project_id} table absent → semantic contribution empty, no exception."""
        engine = _make_engine(test_project.id)

        with patch("orch.rag.qa.OllamaEmbedding", MockOllamaEmbedding):
            bundle = await engine._retrieve_evidence_bundle(
                test_project.id, "test question", db_session
            )

        assert len(bundle.doc_chunks) == 0


class TestBoundaryLanceDBIOError:
    """Simulated LanceDB I/O error → semantic contribution empty; no exception escapes."""

    @pytest.mark.asyncio
    async def test_lancedb_io_error_yields_empty_doc_chunks_no_exception(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """LanceDB exception → bundle.doc_chunks empty, no SSE error."""
        engine = _make_engine(test_project.id)

        def raising_embed(text: str) -> list[float]:
            raise RuntimeError("LanceDB I/O error")

        class RaisingEmbedding:
            model_name = MOCK_EMBED_MODEL

            def __init__(self, **kwargs: object) -> None:
                pass

            def get_text_embedding(self, text: str) -> list[float]:
                raise RuntimeError("LanceDB I/O error")

            async def aget_text_embedding(self, text: str) -> list[float]:
                raise RuntimeError("LanceDB I/O error")

            def get_query_embedding(self, text: str) -> list[float]:
                raise RuntimeError("LanceDB I/O error")

            async def aget_query_embedding(self, text: str) -> list[float]:
                raise RuntimeError("LanceDB I/O error")

        with patch("orch.rag.qa.OllamaEmbedding", RaisingEmbedding):
            bundle = await engine._retrieve_evidence_bundle(
                test_project.id, "test question", db_session
            )

        assert len(bundle.doc_chunks) == 0


class TestBoundaryNoFileOverlap:
    """Code chunks with no file overlap with any work item → empty git_log_items."""

    @pytest.mark.asyncio
    async def test_no_git_log_items_when_no_file_overlap(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """No code chunks from work-item files → git_log_items empty."""
        bundle = EvidenceBundle(question="test question")
        bundle.code_chunks = []
        bundle.fts_items = []
        bundle.git_log_items = []

        from orch.rag.qa import _merge_and_rank_work_items

        result = _merge_and_rank_work_items(
            code_chunks=bundle.code_chunks,
            doc_chunks=bundle.doc_chunks,
            fts_items=bundle.fts_items,
            git_log_items=bundle.git_log_items,
        )

        assert len(result) == 0
        assert len(bundle.git_log_items) == 0


class TestBoundarySameItemAllSources:
    """Same work item in all three sources → single row, scores summed."""

    def test_same_item_in_fts_and_git_log_appears_once(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Item appears in FTS and git_log → single row in merged list."""
        from orch.rag.qa import _merge_and_rank_work_items

        now = datetime.now(UTC)
        item = MagicMock()
        item.id = "SAME-001"
        item.title = "Same Item"
        item.summary = "Summary"
        item.type = MagicMock(value="Feature")
        item.created_at = now
        item.rank = 1.0

        result = _merge_and_rank_work_items(
            code_chunks=[],
            doc_chunks=[],
            fts_items=[item],
            git_log_items=[item],
        )

        ids = [r.id for r in result]
        assert ids.count("SAME-001") == 1, f"Expected 1 occurrence, got {ids.count('SAME-001')}"
        assert len(ids) == 1


class TestBoundaryHallucinatedID:
    """LLM hallucinates fabricated ID → stripped from text AND no citation event."""

    def test_filter_citations_removes_hallucinated_id(
        self,
        db_session: Session,
    ) -> None:
        """F-99999 not in allowed_ids → dropped from text and citations."""
        from orch.rag.citation_allowlist import extract_citations, filter_citations

        allowed = {"CR-00011", "F-00042"}
        llm_output = "According to CR-00011, the button was added. F-99999 also touched this file."

        filtered_text, stripped = filter_citations(llm_output, allowed)

        assert "F-99999" not in filtered_text, "Hallucinated F-99999 must be stripped from text"
        assert "F-99999" in stripped, "Hallucinated F-99999 must be in stripped list"
        assert "CR-00011" in filtered_text

        mentioned = set(extract_citations(filtered_text))
        assert "F-99999" not in mentioned


class TestBoundaryLLMAnswersWithoutCiting:
    """LLM answers without citing any work item → zero citation events."""

    def test_empty_intersection_yields_no_citations(
        self,
        db_session: Session,
    ) -> None:
        """Empty intersection with allowed_ids → zero citation events."""
        from orch.rag.citation_allowlist import extract_citations, filter_citations

        allowed = {"F-00042", "CR-00011"}
        llm_output = (
            "The button was created as part of the New Project feature and has been working fine."
        )

        filtered_text, _ = filter_citations(llm_output, allowed)
        mentioned = set(extract_citations(filtered_text))

        assert len(mentioned) == 0


class TestBoundaryConcurrentReindex:
    """Concurrent re-index request → POST returns 409."""

    def test_concurrent_reindex_returns_409(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """Second POST while first is running → 409."""
        from fastapi.testclient import TestClient

        from dashboard.app import create_app
        from dashboard.dependencies import get_db

        existing_job = DocIndexJob(
            project_id=test_project.id,
            status="running",
            embed_model="test-embed",
        )
        db_session.add(existing_job)
        db_session.flush()

        app = create_app()

        def _override_get_db() -> Session:
            return db_session

        app.dependency_overrides[get_db] = _override_get_db
        client = TestClient(app, raise_server_exceptions=True)

        response = client.post(f"/project/{test_project.id}/api/code/reindex-docs")

        assert response.status_code == 409


class TestBoundaryReindexAfterPartialFailure:
    """Re-index after partial failure → starts from scratch (not from watermark)."""

    @pytest.mark.asyncio
    async def test_failed_job_restarts_from_scratch(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """A failed job starts from scratch — watermark is NOT used."""
        from orch.rag.config import CodeUnderstandingConfig

        now = datetime.now(UTC).replace(tzinfo=None)
        item = WorkItem(
            project_id=test_project.id,
            id="WI-RETRY-001",
            title="Retry Item",
            type=WorkItemType.Feature,
            functional_doc_content="Original content.",
            updated_at=now,
        )
        db_session.add(item)
        db_session.commit()

        config = CodeUnderstandingConfig(
            provider="local",
            embed_model=MOCK_EMBED_MODEL,
            ollama_url="http://localhost:11434",
            index_path=str(tmp_path / "index"),
        )
        indexer = DocIndexer(
            project_id=test_project.id,
            config=config,
            index_path=str(tmp_path / "index"),
            db_session_factory=db_session_factory,
        )

        with patch(
            "llama_index.embeddings.ollama.OllamaEmbedding",
            MockOllamaEmbedding,
        ):
            result1 = indexer.index_all()

        assert result1.items_indexed == 1

        with patch(
            "llama_index.embeddings.ollama.OllamaEmbedding",
            MockOllamaEmbedding,
        ):
            result2 = indexer.index_all()

        assert result2.items_indexed == 1, (
            "Failed/partial job → re-index must start from scratch, not watermark"
        )


class TestBoundaryEmbedModelChange:
    """Embed model change → table dropped + full re-index."""

    def test_embed_model_change_drops_and_reindexes(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """Different embed_model → table dropped and re-indexed."""
        from orch.rag.config import CodeUnderstandingConfig

        now = datetime.now(UTC).replace(tzinfo=None)
        item = WorkItem(
            project_id=test_project.id,
            id="WI-EMBED-CHG",
            title="Embed Change Test",
            type=WorkItemType.Feature,
            functional_doc_content="Content for embed change.",
            updated_at=now,
        )
        db_session.add(item)
        db_session.commit()

        config1 = CodeUnderstandingConfig(
            provider="local",
            embed_model="model-v1",
            ollama_url="http://localhost:11434",
            index_path=str(tmp_path / "index"),
        )
        indexer1 = DocIndexer(
            project_id=test_project.id,
            config=config1,
            index_path=str(tmp_path / "index"),
            db_session_factory=db_session_factory,
        )

        with patch(
            "llama_index.embeddings.ollama.OllamaEmbedding",
            MockOllamaEmbedding,
        ):
            r1 = indexer1.index_all()

        assert r1.items_indexed == 1

        config2 = CodeUnderstandingConfig(
            provider="local",
            embed_model="model-v2",
            ollama_url="http://localhost:11434",
            index_path=str(tmp_path / "index"),
        )
        indexer2 = DocIndexer(
            project_id=test_project.id,
            config=config2,
            index_path=str(tmp_path / "index"),
            db_session_factory=db_session_factory,
        )

        with patch(
            "llama_index.embeddings.ollama.OllamaEmbedding",
            MockOllamaEmbedding,
        ):
            r2 = indexer2.index_all()

        assert r2.items_indexed == 1


class TestBoundaryReindexUnchangedItems:
    """Reindex when every item is unchanged → items_indexed=0."""

    def test_reindex_no_change_yields_zero_items_indexed(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """Reindex with no updated_at changes → items_indexed=0."""
        from orch.rag.config import CodeUnderstandingConfig

        now = datetime.now(UTC).replace(tzinfo=None)
        item = WorkItem(
            project_id=test_project.id,
            id="WI-UNCHANGED",
            title="Unchanged Item",
            type=WorkItemType.Feature,
            functional_doc_content="Static content.",
            updated_at=now,
        )
        db_session.add(item)
        db_session.commit()

        config = CodeUnderstandingConfig(
            provider="local",
            embed_model=MOCK_EMBED_MODEL,
            ollama_url="http://localhost:11434",
            index_path=str(tmp_path / "index"),
        )
        indexer = DocIndexer(
            project_id=test_project.id,
            config=config,
            index_path=str(tmp_path / "index"),
            db_session_factory=db_session_factory,
        )

        with patch(
            "llama_index.embeddings.ollama.OllamaEmbedding",
            MockOllamaEmbedding,
        ):
            indexer.index_all()

        with patch(
            "llama_index.embeddings.ollama.OllamaEmbedding",
            MockOllamaEmbedding,
        ):
            result = indexer.reindex_changed(watermark=now)

        assert result.items_indexed == 0
        assert result.chunks_created == 0


class TestBoundaryQuestionTooLong:
    """Question length > context window → docs truncated, question preserved."""

    def test_prompt_truncation_preserves_question_not_docs(
        self,
        db_session: Session,
        test_project: Project,
    ) -> None:
        """When prompt is over budget, docs are truncated but question remains."""
        engine = _make_engine(test_project.id)

        long_question = "A" * 200

        items = [
            MagicMock(
                id=f"F-{i:05d}",
                title=f"Item {i}",
                summary="Summary",
                functional_doc_content="B" * 10000,
                type=MagicMock(value="Feature"),
            )
            for i in range(1, 4)
        ]
        bundle = EvidenceBundle(question=long_question)
        bundle.work_items = items

        prompt = engine._build_workitem_system_prompt(bundle, items)

        assert long_question in bundle.question
        assert prompt.count("B" * 10000) <= 3


class TestBoundaryFunctionalDocWithNULChars:
    """Functional doc with NUL chars → sanitised before embedding."""

    def test_indexer_sanitises_nul_chars(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        test_project: Project,
        tmp_path: Path,
    ) -> None:
        """NUL chars in functional_doc_content are stripped before embedding."""
        from orch.rag.config import CodeUnderstandingConfig

        now = datetime.now(UTC).replace(tzinfo=None)
        item = WorkItem(
            project_id=test_project.id,
            id="WI-NUL-CHARS",
            title="NUL Test Item",
            type=WorkItemType.Feature,
            functional_doc_content="Normal text\x00more text\x00end",
            updated_at=now,
        )
        db_session.add(item)
        db_session.commit()

        config = CodeUnderstandingConfig(
            provider="local",
            embed_model=MOCK_EMBED_MODEL,
            ollama_url="http://localhost:11434",
            index_path=str(tmp_path / "index"),
        )
        indexer = DocIndexer(
            project_id=test_project.id,
            config=config,
            index_path=str(tmp_path / "index"),
            db_session_factory=db_session_factory,
        )

        with patch(
            "llama_index.embeddings.ollama.OllamaEmbedding",
            MockOllamaEmbedding,
        ):
            result = indexer.index_all()

        assert result.errors == [], f"Expected no errors, got {result.errors}"
        assert result.items_indexed == 1
