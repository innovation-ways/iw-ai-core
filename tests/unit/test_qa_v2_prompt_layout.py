"""Unit tests for _build_workitem_system_prompt layout."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

from orch.rag.evidence import EvidenceBundle
from orch.rag.qa import QAEngine


class MockWorkItem:
    """Mock WorkItem for testing."""

    def __init__(
        self,
        wi_id: str,
        created_at: datetime,
        title: str = "Test",
        summary: str = "Summary",
        functional_doc_content: str | None = None,
        work_item_type: str = "Feature",
    ) -> None:
        self.id = wi_id
        self.work_item_id = wi_id
        self.type = MagicMock(value=work_item_type)
        self.title = title
        self.summary = summary
        self.functional_doc_content = functional_doc_content
        self.created_at = created_at


class TestWorkItemPromptLayout:
    """Tests for _build_workitem_system_prompt layout."""

    def _make_engine(self) -> QAEngine:
        from orch.rag.config import CodeUnderstandingConfig

        config = MagicMock(spec=CodeUnderstandingConfig)
        return QAEngine(project_id="test-project", config=config)

    def test_eight_candidates_top_3_full_doc(self) -> None:
        """Given 8 candidates, top 3 get full doc, 4-8 get compact."""
        engine = self._make_engine()
        items = [
            MockWorkItem(
                f"F-{i:05d}",
                datetime(2025, 1, i, tzinfo=UTC),
                title=f"Item {i}",
                summary=f"Summary {i}",
                functional_doc_content=f"Content for item {i}",
            )
            for i in range(1, 9)
        ]
        bundle = EvidenceBundle(question="test")
        result = engine._build_workitem_system_prompt(bundle, items)

        assert "## Work Item Context" in result
        assert "Candidate 1: F-00001" in result
        assert "Candidate 3: F-00003" in result
        assert "Candidate 4: F-00004" in result
        assert "Candidate 8: F-00008" in result
        assert result.count("Content for item 1") == 1
        assert result.count("Content for item 2") == 1
        assert result.count("Content for item 3") == 1
        assert result.count("Content for item 4") == 1

    def test_three_candidates_all_full_doc(self) -> None:
        """Given 3 candidates, all get full doc."""
        engine = self._make_engine()
        items = [
            MockWorkItem(
                f"F-{i:05d}",
                datetime(2025, 1, i, tzinfo=UTC),
                title=f"Item {i}",
                summary=f"Summary {i}",
                functional_doc_content=f"Full doc {i}",
            )
            for i in range(1, 4)
        ]
        bundle = EvidenceBundle(question="test")
        result = engine._build_workitem_system_prompt(bundle, items)

        for i in range(1, 4):
            assert f"Candidate {i}: F-{i:05d}" in result
            assert f"Full doc {i}" in result

    def test_null_functional_doc_demoted_to_compact(self) -> None:
        """Items with NULL functional_doc_content are demoted to compact form."""
        engine = self._make_engine()
        items = [
            MockWorkItem(
                "F-00001",
                datetime(2025, 1, 1, tzinfo=UTC),
                title="Has Full Doc",
                summary="Summary 1",
                functional_doc_content="This has a full doc",
            ),
            MockWorkItem(
                "F-00002",
                datetime(2025, 1, 2, tzinfo=UTC),
                title="No Full Doc",
                summary="Summary 2",
                functional_doc_content=None,
            ),
        ]
        bundle = EvidenceBundle(question="test")
        result = engine._build_workitem_system_prompt(bundle, items)

        assert "Candidate 1: F-00001" in result
        assert "Candidate 2: F-00002" in result
        assert "This has a full doc" in result
        assert "Summary 2" in result
        assert (
            "Summary 2"
            not in result.split("Candidate 1: F-00001")[1].split("Candidate 2: F-00002")[0]
        )

    def test_over_budget_truncation(self) -> None:
        """Over 56K chars drops candidates from position 8 backward."""
        engine = self._make_engine()
        long_content = "x" * 10000
        items = [
            MockWorkItem(
                f"F-{i:05d}",
                datetime(2025, 1, i, tzinfo=UTC),
                title=f"Item {i}",
                summary="Summary",
                functional_doc_content=long_content,
            )
            for i in range(1, 9)
        ]
        bundle = EvidenceBundle(question="test")
        result = engine._build_workitem_system_prompt(bundle, items)

        assert len(result) <= 56000
        assert "Candidate 1: F-00001" in result

    def test_relevance_filter_instruction_present(self) -> None:
        """Relevance filter instruction is present verbatim at top."""
        engine = self._make_engine()
        items = [
            MockWorkItem(
                "F-00001",
                datetime(2025, 1, 1, tzinfo=UTC),
                title="Item 1",
                summary="Summary 1",
                functional_doc_content="Content 1",
            ),
        ]
        bundle = EvidenceBundle(question="test")
        result = engine._build_workitem_system_prompt(bundle, items)

        assert "## Work Item Context" in result
        assert "Cite only the items whose reasoning answers" in result

    def test_empty_items_returns_empty_string(self) -> None:
        """Empty items list returns empty string."""
        engine = self._make_engine()
        bundle = EvidenceBundle(question="test")
        result = engine._build_workitem_system_prompt(bundle, [])
        assert result == ""

    def test_prompt_budget_at_most_3_full_docs_plus_5_snippets(self) -> None:
        """Prompt contains at most 3 full doc bodies + 5 chunk snippets (Inv 7)."""
        engine = self._make_engine()
        items = [
            MockWorkItem(
                f"F-{i:05d}",
                datetime(2025, 1, i, tzinfo=UTC),
                title=f"Item {i}",
                summary=f"Summary {i}",
                functional_doc_content=f"Content for item {i}" * 500,
            )
            for i in range(1, 10)
        ]
        bundle = EvidenceBundle(question="test question")
        result = engine._build_workitem_system_prompt(bundle, items)

        candidate_sections = result.split("### Candidate")[1:]
        full_doc_count = 0
        compact_count = 0
        for section in candidate_sections:
            if "Content for item" in section:
                stripped = section.strip()
                lines = stripped.split("\n")
                body = "\n".join(lines[1:]) if len(lines) > 1 else ""
                if len(body) > 500:
                    full_doc_count += 1
                else:
                    compact_count += 1

        assert full_doc_count <= 3, f"Expected at most 3 full-doc candidates, got {full_doc_count}"
        assert compact_count <= 5, f"Expected at most 5 compact candidates, got {compact_count}"

    def test_truncation_at_12000_chars(self) -> None:
        """Full doc content is truncated at 12,000 chars."""
        engine = self._make_engine()
        items = [
            MockWorkItem(
                "F-00001",
                datetime(2025, 1, 1, tzinfo=UTC),
                title="Item 1",
                summary="Summary 1",
                functional_doc_content="x" * 20000,
            ),
        ]
        bundle = EvidenceBundle(question="test")
        result = engine._build_workitem_system_prompt(bundle, items)

        content_len = len(items[0].functional_doc_content or "")
        assert content_len == 20000
        assert "x" * 12000 in result
        assert "x" * 20000 not in result
        assert "…" in result
