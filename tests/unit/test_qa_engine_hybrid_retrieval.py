"""Unit tests for hybrid retrieval merge-and-rank logic."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock


class MockWorkItem:
    """Mock WorkItem for testing."""

    def __init__(
        self,
        wi_id: str,
        created_at: datetime,
        title: str = "Test",
        summary: str = "Summary",
    ) -> None:
        self.id = wi_id
        self.work_item_id = wi_id
        self.type = MagicMock(value="Feature")
        self.title = title
        self.summary = summary
        self.design_doc_content = "Content"
        self.created_at = created_at


class TestMergeAndRankWorkItems:
    """Tests for _merge_and_rank_work_items function."""

    def test_empty_inputs(self) -> None:
        """Empty inputs return empty list."""
        from orch.rag.qa import _merge_and_rank_work_items

        result = _merge_and_rank_work_items([], [], [], [])
        assert result == []

    def test_single_source(self) -> None:
        """Single source returns items sorted by score."""
        from orch.rag.qa import _merge_and_rank_work_items

        wis = [
            MockWorkItem("F-00001", datetime(2025, 1, 1, tzinfo=UTC)),
            MockWorkItem("F-00002", datetime(2025, 2, 1, tzinfo=UTC)),
        ]

        result = _merge_and_rank_work_items([], [], wis, [])

        assert len(result) == 2
        assert result[0].id == "F-00001"
        assert result[1].id == "F-00002"

    def test_fts_ranks_higher_than_git_log(self) -> None:
        """FTS items get higher weight than git_log items."""
        from orch.rag.qa import _merge_and_rank_work_items

        fts_items = [MockWorkItem("F-00001", datetime(2025, 1, 1, tzinfo=UTC))]
        git_log_items = [MockWorkItem("F-00002", datetime(2025, 2, 1, tzinfo=UTC))]

        result = _merge_and_rank_work_items(
            [],
            fts_items,
            fts_items,
            git_log_items,
            alpha=0.5,
            beta=0.3,
            gamma=0.2,
        )

        assert result[0].id == "F-00001"

    def test_top_5_cap(self) -> None:
        """Result is capped at 5 items."""
        from orch.rag.qa import _merge_and_rank_work_items

        wis = [MockWorkItem(f"F-{i:05d}", datetime(2025, 1, i, tzinfo=UTC)) for i in range(1, 11)]

        result = _merge_and_rank_work_items([], [], wis, [])

        assert len(result) <= 5

    def test_deduplication_by_id(self) -> None:
        """Same ID appearing in multiple sources appears once."""
        from orch.rag.qa import _merge_and_rank_work_items

        wi = MockWorkItem("F-00001", datetime(2025, 1, 1, tzinfo=UTC))
        fts_items = [wi]
        git_log_items = [wi]

        result = _merge_and_rank_work_items([], [], fts_items, git_log_items)

        ids = [item.id for item in result]
        assert ids.count("F-00001") == 1

    def test_weighted_scoring(self) -> None:
        """Items from fts and git_log are ranked and combined."""
        from orch.rag.qa import _merge_and_rank_work_items

        now = datetime.now(UTC)

        fts_wi = MockWorkItem("F-00001", now - timedelta(days=10))
        git_wi = MockWorkItem("F-00002", now - timedelta(days=20))

        result = _merge_and_rank_work_items(
            [],
            [],
            [fts_wi],
            [git_wi],
            alpha=0.5,
            beta=0.3,
            gamma=0.2,
        )

        result_ids = [item.id for item in result]
        assert "F-00001" in result_ids
        assert "F-00002" in result_ids
        assert len(result_ids) == 2


class MockCodeChunk:
    """Mock code chunk for testing."""

    def __init__(self, file_path: str, text: str = "code") -> None:
        self.file_path = file_path
        self.text = text


class MockDocChunk:
    """Mock doc chunk for testing."""

    def __init__(self, work_item_id: str, text: str = "doc") -> None:
        self.work_item_id = work_item_id
        self.work_item_type = "feature"
        self.work_item_title = "Title"
        self.text = text


class TestEvidenceBundleCodeFilePaths:
    """Tests for EvidenceBundle.code_file_paths property."""

    def test_deduplicates_file_paths(self) -> None:
        """Same file path appearing multiple times is deduplicated."""
        from orch.rag.evidence import CodeChunk, EvidenceBundle

        chunks = [
            CodeChunk("file1.py", "code1"),
            CodeChunk("file1.py", "code2"),
            CodeChunk("file2.py", "code3"),
        ]

        bundle = EvidenceBundle(question="test", code_chunks=chunks)

        paths = bundle.code_file_paths

        assert len(paths) == 2
        assert "file1.py" in paths
        assert "file2.py" in paths


class TestEvidenceBundleAllowedIds:
    """Tests for EvidenceBundle.allowed_ids property."""

    def test_returns_set_of_ids(self) -> None:
        """Returns set of all work-item IDs in bundle."""
        from orch.rag.evidence import EvidenceBundle

        wi1 = MockWorkItem("F-00001", datetime(2025, 1, 1, tzinfo=UTC))
        wi2 = MockWorkItem("CR-00002", datetime(2025, 2, 1, tzinfo=UTC))

        bundle = EvidenceBundle(question="test", work_items=[wi1, wi2])

        allowed = bundle.allowed_ids

        assert allowed == {"F-00001", "CR-00002"}
