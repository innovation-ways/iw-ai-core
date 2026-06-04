"""Model-level unit tests for BatchOverlapIgnore (CR-00078).

These tests exercise the model as a plain Python object — no DB, no fixtures.
The integration-level tests (DB-backed, real PostgreSQL via testcontainers)
live in tests/integration/test_batch_overlap_ignore.py.

Tests here cover:
- Instantiation and attribute round-trip (no DB needed)
- repr implementation (no DB needed)
- Attribute access validation (no DB needed)
"""

from __future__ import annotations

from orch.db.models import BatchOverlapIgnore


class TestBatchOverlapIgnoreInstantiation:
    """Model instantiation tests — no DB required."""

    def test_insert_and_read(self) -> None:
        """Insert one BatchOverlapIgnore row and verify every field round-trips.

        This is the same assertion as the integration test, but exercised
        as a plain Python object (no DB commit/flush needed).
        """
        row = BatchOverlapIgnore(
            project_id="test-proj",
            batch_id="BATCH-001",
            held_item_id="CR-00072",
            blocking_item_id="CR-00057",
            file_pattern="docs/IW_AI_Core_Testing_Strategy.md",
            ignored_by="operator",
            reason="Intentional overlap for testing",
        )
        assert row.project_id == "test-proj"
        assert row.batch_id == "BATCH-001"
        assert row.held_item_id == "CR-00072"
        assert row.blocking_item_id == "CR-00057"
        assert row.file_pattern == "docs/IW_AI_Core_Testing_Strategy.md"
        assert row.ignored_by == "operator"
        assert row.reason == "Intentional overlap for testing"
        # ignored_at is None until the DB assigns it via server_default
        assert row.ignored_at is None

    def test_reason_optional(self) -> None:
        """reason is nullable — NULL value is accepted by the model."""
        row = BatchOverlapIgnore(
            project_id="test-proj",
            batch_id="BATCH-002",
            held_item_id="CR-00072",
            blocking_item_id="CR-00057",
            file_pattern="docs/guide.md",
            ignored_by="operator",
            reason=None,
        )
        assert row.reason is None

    def test_ignored_by_not_null(self) -> None:
        """ignored_by is NOT NULL — model accepts empty string (DB enforces)."""
        row = BatchOverlapIgnore(
            project_id="test-proj",
            batch_id="BATCH-003",
            held_item_id="CR-00072",
            blocking_item_id="CR-00057",
            file_pattern="docs/empty.txt",
            ignored_by="",
        )
        assert row.ignored_by == ""

    def test_all_pk_fields_present(self) -> None:
        """All 5 composite PK fields exist on the model and are accessible."""
        row = BatchOverlapIgnore(
            project_id="test-proj",
            batch_id="BATCH-001",
            held_item_id="CR-00072",
            blocking_item_id="CR-00057",
            file_pattern="docs/file.md",
            ignored_by="operator",
        )
        # Access each field to confirm it is defined on the model
        assert row.project_id == "test-proj"
        assert row.batch_id == "BATCH-001"
        assert row.held_item_id == "CR-00072"
        assert row.blocking_item_id == "CR-00057"
        assert row.file_pattern == "docs/file.md"
        assert row.ignored_by == "operator"

    def test_all_fields_present(self) -> None:
        """All documented fields are present on the model."""
        row = BatchOverlapIgnore(
            project_id="p",
            batch_id="b",
            held_item_id="h",
            blocking_item_id="blk",
            file_pattern="f.py",
            ignored_by="op",
            reason="r",
        )
        # Verify all documented fields are accessible
        assert row.project_id == "p"
        assert row.batch_id == "b"
        assert row.held_item_id == "h"
        assert row.blocking_item_id == "blk"
        assert row.file_pattern == "f.py"
        assert row.ignored_by == "op"
        assert row.reason == "r"
        assert row.ignored_at is None  # DB-populated

    def test_tablename(self) -> None:
        """__tablename__ is batch_overlap_ignore as per the design."""
        row = BatchOverlapIgnore(
            project_id="p",
            batch_id="b",
            held_item_id="h",
            blocking_item_id="blk",
            file_pattern="f.py",
            ignored_by="op",
        )
        assert row.__tablename__ == "batch_overlap_ignore"


class TestBatchOverlapIgnoreRepr:
    """repr implementation — no DB required."""

    def test_repr_includes_class_name(self) -> None:
        """Custom repr starts with the class name."""
        row = BatchOverlapIgnore(
            project_id="p",
            batch_id="b",
            held_item_id="CR-00072",
            blocking_item_id="CR-00057",
            file_pattern="foo.py",
            ignored_by="op",
        )
        repr_str = repr(row)
        # repr starts with "BatchOverlapIgnore(" — would fail on default Python repr
        assert repr_str.startswith("BatchOverlapIgnore(")

        # repr contains the key identity fields as string values
        assert "CR-00072" in repr_str
        assert "CR-00057" in repr_str
        assert "foo.py" in repr_str

    def test_repr_contains_key_fields(self) -> None:
        """Custom repr shows the held item, blocking item, and file pattern."""
        row = BatchOverlapIgnore(
            project_id="test-proj",
            batch_id="BATCH-001",
            held_item_id="CR-00099",
            blocking_item_id="CR-00088",
            file_pattern="bar/baz.md",
            ignored_by="operator",
        )
        repr_str = repr(row)
        # Verify key identity fields are embedded as Python repr strings
        assert repr_str.startswith("BatchOverlapIgnore(")
        # These specific CR IDs appear as string literals in the repr
        assert "'CR-00099'" in repr_str
        assert "'CR-00088'" in repr_str
        assert "bar/baz.md" in repr_str
        assert "'BATCH-001'" in repr_str
