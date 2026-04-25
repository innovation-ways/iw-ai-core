"""Integration tests for DocIndexer (orch/rag/doc_indexer.py).

Uses the same testcontainer + tmp_path pattern as test_code_index_pipeline.py.
All Ollama HTTP calls are mocked.
All LanceDB files live under tmp_path for test isolation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

if TYPE_CHECKING:
    from pathlib import Path

    from sqlalchemy import Engine
    from sqlalchemy.orm import Session, sessionmaker

from orch.db.models import Project, WorkItem, WorkItemType
from orch.rag.config import CodeUnderstandingConfig
from orch.rag.doc_indexer import DocIndexer

MOCK_EMBED_MODEL = "test-embed-model"


def mock_embed(text: str) -> list[float]:
    """Deterministic mock embedding — a vector of zeros with a unique
    non-zero element per distinct input so collision probability is negligible.
    """
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


def create_doc_indexer(
    project_id: str,
    index_path: str,
    db_session_factory: sessionmaker,
) -> DocIndexer:
    config = CodeUnderstandingConfig(
        provider="local",
        embed_model=MOCK_EMBED_MODEL,
        ollama_url="http://localhost:11434",
        index_path=index_path,
    )
    return DocIndexer(
        project_id=project_id,
        config=config,
        index_path=index_path,
        db_session_factory=db_session_factory,
    )


class TestDocIndexerBasic:
    def test_index_three_items_creates_chunks_in_lancedb(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        tmp_path: Path,
    ) -> None:
        """Index 3 items with distinct content → 3 work_item_ids in the table."""
        test_session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

        project_id = "test-proj-doc-basic"
        index_path = str(tmp_path / "index")

        with test_session_factory() as setup_session:
            project = Project(
                id=project_id,
                display_name="Test Project Doc Basic",
                repo_root=str(tmp_path / "repo"),
                config={},
            )
            setup_session.add(project)

            now = datetime.now(UTC).replace(tzinfo=None)
            items = [
                WorkItem(
                    project_id=project_id,
                    id="WI-001",
                    title="First item",
                    type=WorkItemType.Feature,
                    functional_doc_content="This is the content for the first item about widgets.",
                    updated_at=now,
                ),
                WorkItem(
                    project_id=project_id,
                    id="WI-002",
                    title="Second item",
                    type=WorkItemType.ChangeRequest,
                    functional_doc_content="This is the content for the second item about gadgets.",
                    updated_at=now,
                ),
                WorkItem(
                    project_id=project_id,
                    id="WI-003",
                    title="Third item",
                    type=WorkItemType.Issue,
                    functional_doc_content="This is the content for the third item about doohickeys.",
                    updated_at=now,
                ),
            ]
            for item in items:
                setup_session.add(item)
            setup_session.flush()
            setup_session.commit()

        indexer = create_doc_indexer(project_id, index_path, test_session_factory)

        with patch(
            "llama_index.embeddings.ollama.OllamaEmbedding",
            MockOllamaEmbedding,
        ):
            result = indexer.index_all()

        assert result.items_discovered == 3, f"Expected 3, got {result.items_discovered}"
        assert result.items_indexed == 3, f"Expected 3, got {result.items_indexed}"
        assert result.chunks_created > 0, "Expected chunks created"
        assert result.errors == [], f"Expected no errors, got {result.errors}"

        import lancedb

        uri = f"{index_path}/{project_id}/vectors/"
        db = lancedb.connect(uri)
        table_name = f"docs_{project_id.replace('-', '_')}"
        assert table_name in db.table_names(), f"Expected table {table_name} in {db.table_names()}"

        tbl = db.open_table(table_name)
        df = tbl.to_pandas()
        assert set(df["work_item_id"].tolist()) == {"WI-001", "WI-002", "WI-003"}, (
            f"Expected 3 work item IDs, got {df['work_item_id'].tolist()}"
        )
        assert len(df) == result.chunks_created

    def test_reindex_changed_updates_chunks(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        tmp_path: Path,
    ) -> None:
        """Update one item's functional_doc_content + bump updated_at → old chunks removed."""
        test_session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

        project_id = "test-proj-doc-reindex"
        index_path = str(tmp_path / "index")
        item_id = "WI-REINDEX-001"

        with test_session_factory() as setup_session:
            project = Project(
                id=project_id,
                display_name="Test Project Doc Reindex",
                repo_root=str(tmp_path / "repo"),
                config={},
            )
            setup_session.add(project)

            now = datetime.now(UTC).replace(tzinfo=None)
            item = WorkItem(
                project_id=project_id,
                id=item_id,
                title="Reindex test item",
                type=WorkItemType.Feature,
                functional_doc_content="Original content for the reindex test.",
                updated_at=now,
            )
            setup_session.add(item)
            setup_session.flush()
            setup_session.commit()

        indexer = create_doc_indexer(project_id, index_path, test_session_factory)

        with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
            result1 = indexer.index_all()

        assert result1.items_indexed == 1

        import lancedb

        uri = f"{index_path}/{project_id}/vectors/"
        db = lancedb.connect(uri)
        table_name = f"docs_{project_id.replace('-', '_')}"
        tbl = db.open_table(table_name)
        df_before = tbl.to_pandas()
        original_chunk_count = len(df_before)

        new_timestamp = datetime.now(UTC).replace(tzinfo=None)

        with test_session_factory() as update_session:
            # WorkItem PK order is (project_id, id)
            item = update_session.get(WorkItem, (project_id, item_id))
            assert item is not None, f"Could not load WorkItem ({project_id}, {item_id})"
            item.functional_doc_content = "Updated content for the reindex test with more text."
            item.updated_at = new_timestamp
            update_session.commit()

        with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
            result2 = indexer.reindex_changed(watermark=now)

        assert result2.items_indexed == 1
        tbl = db.open_table(table_name)
        df_after = tbl.to_pandas()
        assert set(df_after["work_item_id"].tolist()) == {"WI-REINDEX-001"}
        assert len(df_after) >= original_chunk_count

    def test_skip_null_functional_doc_content(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        tmp_path: Path,
    ) -> None:
        """Items with NULL functional_doc_content are skipped, not deleted."""
        test_session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

        project_id = "test-proj-doc-null"
        index_path = str(tmp_path / "index")

        with test_session_factory() as setup_session:
            project = Project(
                id=project_id,
                display_name="Test Project Doc Null",
                repo_root=str(tmp_path / "repo"),
                config={},
            )
            setup_session.add(project)

            now = datetime.now(UTC).replace(tzinfo=None)
            items = [
                WorkItem(
                    project_id=project_id,
                    id="WI-NULL-001",
                    title="Has content",
                    type=WorkItemType.Feature,
                    functional_doc_content="This item has content.",
                    updated_at=now,
                ),
                WorkItem(
                    project_id=project_id,
                    id="WI-NULL-002",
                    title="No content",
                    type=WorkItemType.Feature,
                    functional_doc_content=None,
                    updated_at=now,
                ),
            ]
            for item in items:
                setup_session.add(item)
            setup_session.flush()
            setup_session.commit()

        indexer = create_doc_indexer(project_id, index_path, test_session_factory)

        with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
            result = indexer.index_all()

        assert result.items_indexed == 1, f"Expected 1 indexed, got {result.items_indexed}"
        assert result.errors == []

        import lancedb

        uri = f"{index_path}/{project_id}/vectors/"
        db = lancedb.connect(uri)
        table_name = f"docs_{project_id.replace('-', '_')}"
        if table_name in db.table_names():
            tbl = db.open_table(table_name)
            df = tbl.to_pandas()
            assert "WI-NULL-001" in df["work_item_id"].tolist()
            assert "WI-NULL-002" not in df["work_item_id"].tolist()

    def test_embed_model_change_drops_and_reindexes(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        tmp_path: Path,
    ) -> None:
        """Embed-model change → table dropped + full re-index."""
        test_session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

        project_id = "test-proj-doc-embed-change"
        index_path = str(tmp_path / "index")

        with test_session_factory() as setup_session:
            project = Project(
                id=project_id,
                display_name="Test Project Doc Embed Change",
                repo_root=str(tmp_path / "repo"),
                config={},
            )
            setup_session.add(project)

            now = datetime.now(UTC).replace(tzinfo=None)
            item = WorkItem(
                project_id=project_id,
                id="WI-EMBED-CHANGE",
                title="Embed change test",
                type=WorkItemType.Feature,
                functional_doc_content="Content for embed change test.",
                updated_at=now,
            )
            setup_session.add(item)
            setup_session.flush()
            setup_session.commit()

        config1 = CodeUnderstandingConfig(
            provider="local",
            embed_model="model-v1",
            ollama_url="http://localhost:11434",
            index_path=index_path,
        )
        indexer1 = DocIndexer(
            project_id=project_id,
            config=config1,
            index_path=index_path,
            db_session_factory=test_session_factory,
        )
        with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
            result1 = indexer1.index_all()
        assert result1.items_indexed == 1

        import lancedb

        uri = f"{index_path}/{project_id}/vectors/"
        db = lancedb.connect(uri)
        table_name = f"docs_{project_id.replace('-', '_')}"
        assert table_name in db.table_names()

        config2 = CodeUnderstandingConfig(
            provider="local",
            embed_model="model-v2",
            ollama_url="http://localhost:11434",
            index_path=index_path,
        )
        indexer2 = DocIndexer(
            project_id=project_id,
            config=config2,
            index_path=index_path,
            db_session_factory=test_session_factory,
        )
        with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
            result2 = indexer2.index_all()

        assert result2.items_indexed == 1
        db = lancedb.connect(uri)
        assert table_name in db.table_names()


class TestDocIndexerReindex:
    def test_reindex_none_changed(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        tmp_path: Path,
    ) -> None:
        """Reindex with no changes yields items_indexed=0."""
        test_session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

        project_id = "test-proj-doc-no-change"
        index_path = str(tmp_path / "index")

        with test_session_factory() as setup_session:
            project = Project(
                id=project_id,
                display_name="Test Project No Change",
                repo_root=str(tmp_path / "repo"),
                config={},
            )
            setup_session.add(project)

            now = datetime.now(UTC).replace(tzinfo=None)
            item = WorkItem(
                project_id=project_id,
                id="WI-NO-CHANGE",
                title="No change test",
                type=WorkItemType.Feature,
                functional_doc_content="Static content that never changes.",
                updated_at=now,
            )
            setup_session.add(item)
            setup_session.flush()
            setup_session.commit()

        indexer = create_doc_indexer(project_id, index_path, test_session_factory)

        with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
            indexer.index_all()

        with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
            result = indexer.reindex_changed(watermark=now)

        assert result.items_indexed == 0
        assert result.chunks_created == 0

    def test_watermark_none_indexes_all(
        self,
        db_session: Session,
        db_engine: Engine,
        db_session_factory: sessionmaker,
        tmp_path: Path,
    ) -> None:
        """reindex_changed with watermark=None indexes everything."""
        test_session_factory = sessionmaker(bind=db_engine, autocommit=False, autoflush=False)

        project_id = "test-proj-doc-wm-none"
        index_path = str(tmp_path / "index")

        with test_session_factory() as setup_session:
            project = Project(
                id=project_id,
                display_name="Test Project WM None",
                repo_root=str(tmp_path / "repo"),
                config={},
            )
            setup_session.add(project)

            now = datetime.now(UTC).replace(tzinfo=None)
            items = [
                WorkItem(
                    project_id=project_id,
                    id="WI-WM-NONE-1",
                    title="Item 1",
                    type=WorkItemType.Feature,
                    functional_doc_content="Content for item 1.",
                    updated_at=now,
                ),
                WorkItem(
                    project_id=project_id,
                    id="WI-WM-NONE-2",
                    title="Item 2",
                    type=WorkItemType.Issue,
                    functional_doc_content="Content for item 2.",
                    updated_at=now,
                ),
            ]
            for item in items:
                setup_session.add(item)
            setup_session.flush()
            setup_session.commit()

        indexer = create_doc_indexer(project_id, index_path, test_session_factory)

        with patch("llama_index.embeddings.ollama.OllamaEmbedding", MockOllamaEmbedding):
            result = indexer.reindex_changed(watermark=None)

        assert result.items_indexed == 2
