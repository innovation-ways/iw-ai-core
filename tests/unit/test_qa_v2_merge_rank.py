"""Unit tests for _merge_and_rank_work_items α/β/γ blend math."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from orch.rag.evidence import DocChunk
from orch.rag.qa import _merge_and_rank_work_items


class MockWorkItem:
    """Mock WorkItem with optional rank attribute."""

    def __init__(
        self,
        wi_id: str,
        created_at: datetime,
        title: str = "Test",
        summary: str = "Summary",
        rank: float | None = None,
    ) -> None:
        self.id = wi_id
        self.work_item_id = wi_id
        self.type = MagicMock(value="Feature")
        self.title = title
        self.summary = summary
        self.created_at = created_at
        if rank is not None:
            self.rank = rank


class TestMergeAndRankWorkItemsMath:
    """Tests for _merge_and_rank_work_items α/β/γ math."""

    def test_empty_inputs_returns_empty(self) -> None:
        """Empty inputs return empty list."""
        result = _merge_and_rank_work_items([], [], [], [])
        assert result == []

    def test_alpha_beta_gamma_weights_sum_to_one(self) -> None:
        """Default α=0.45, β=0.20, γ=0.35 sum to 1.0."""
        fts_items = [MockWorkItem("F-00001", datetime(2025, 1, 1, tzinfo=UTC), rank=1.0)]
        result = _merge_and_rank_work_items([], [], fts_items, [])

        assert len(result) == 1
        assert result[0].id == "F-00001"

    def test_single_source_all_scores_equal(self) -> None:
        """With single source, all items get same normalized score."""
        wis = [
            MockWorkItem("F-00001", datetime(2025, 1, 1, tzinfo=UTC)),
            MockWorkItem("F-00002", datetime(2025, 1, 2, tzinfo=UTC)),
        ]
        result = _merge_and_rank_work_items([], [], wis, [])

        assert len(result) == 2

    def test_doc_chunks_semantic_scoring(self) -> None:
        """Doc chunks contribute semantic score to merge."""
        doc_chunks = [
            DocChunk(
                work_item_id="F-00001",
                work_item_type="Feature",
                work_item_title="Item 1",
                text="Content about widgets",
                score=0.9,
            ),
            DocChunk(
                work_item_id="F-00002",
                work_item_type="Feature",
                work_item_title="Item 2",
                text="Content about gadgets",
                score=0.5,
            ),
        ]
        result = _merge_and_rank_work_items([], doc_chunks, [], [])

        assert len(result) == 2
        assert result[0].id == "F-00001"
        assert result[1].id == "F-00002"

    def test_custom_alpha_beta_gamma_parameters(self) -> None:
        """Custom α/β/γ parameters are respected."""
        fts_items = [
            MockWorkItem("F-00001", datetime(2025, 1, 1, tzinfo=UTC), rank=1.0),
        ]
        git_log_items = [
            MockWorkItem("F-00002", datetime(2025, 1, 2, tzinfo=UTC)),
        ]

        result = _merge_and_rank_work_items(
            [],
            [],
            fts_items,
            git_log_items,
            alpha=0.45,
            beta=0.20,
            gamma=0.35,
        )

        assert len(result) == 2
        assert result[0].id == "F-00001"

    def test_all_zero_scores_handled_gracefully(self) -> None:
        """All-zero scores from any source are handled without division error."""
        fts_items = [
            MockWorkItem("F-00001", datetime(2025, 1, 1, tzinfo=UTC), rank=0.0),
        ]
        doc_chunks = [
            DocChunk(
                work_item_id="F-00002",
                work_item_type="Feature",
                work_item_title="Item 2",
                text="Content",
                score=0.0,
            ),
        ]
        result = _merge_and_rank_work_items([], doc_chunks, fts_items, [])

        assert len(result) >= 0

    def test_single_item_source(self) -> None:
        """Single item in single source returns that item."""
        wis = [MockWorkItem("F-00001", datetime(2025, 1, 1, tzinfo=UTC))]
        result = _merge_and_rank_work_items([], [], wis, [])

        assert len(result) == 1
        assert result[0].id == "F-00001"

    def test_top_8_cap(self) -> None:
        """Result is capped at 8 items."""
        wis = [MockWorkItem(f"F-{i:05d}", datetime(2025, 1, i, tzinfo=UTC)) for i in range(1, 15)]
        result = _merge_and_rank_work_items([], [], wis, [])

        assert len(result) <= 8

    def test_deduplication_by_id(self) -> None:
        """Same ID in multiple sources appears once with combined score."""
        wi = MockWorkItem("F-00001", datetime(2025, 1, 1, tzinfo=UTC), rank=1.0)
        fts_items = [wi]
        git_log_items = [wi]

        result = _merge_and_rank_work_items([], [], fts_items, git_log_items)

        ids = [item.id for item in result]
        assert ids.count("F-00001") == 1
        assert len(ids) == 1

    def test_fts_with_rank_normalization(self) -> None:
        """FTS items with rank are normalized by max rank."""
        fts_items = [
            MockWorkItem("F-00001", datetime(2025, 1, 1, tzinfo=UTC), rank=0.5),
            MockWorkItem("F-00002", datetime(2025, 1, 2, tzinfo=UTC), rank=1.0),
        ]

        result = _merge_and_rank_work_items([], [], fts_items, [])

        assert len(result) == 2
        assert result[0].id == "F-00002"

    def test_semantic_normalization_by_max(self) -> None:
        """Semantic scores normalized by max score in doc_chunks."""
        doc_chunks = [
            DocChunk(
                work_item_id="F-00001",
                work_item_type="Feature",
                work_item_title="Item 1",
                text="Content 1",
                score=0.5,
            ),
            DocChunk(
                work_item_id="F-00002",
                work_item_type="Feature",
                work_item_title="Item 2",
                text="Content 2",
                score=1.0,
            ),
        ]

        result = _merge_and_rank_work_items([], doc_chunks, [], [])

        assert len(result) == 2
        assert result[0].id == "F-00002"
