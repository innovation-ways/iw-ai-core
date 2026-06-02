"""Unit tests for group_overlap_events (CR-00077 S01).

TDD: RED first — confirm the function does not exist yet, then implement.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import NamedTuple

from dashboard.routers.batches import group_overlap_events


class MockDaemonEvent(NamedTuple):
    """Minimal DaemonEvent stand-in for unit tests (no DB needed)."""

    id: int
    project_id: str
    event_type: str
    entity_id: str | None
    entity_type: str | None
    event_metadata: dict[str, object] | None
    created_at: datetime

    @property
    def message(self) -> str:
        """Return message."""
        return ""

    @property
    def metadata(self) -> dict | None:  # type: ignore
        """Return metadata."""
        return None


def _ev(
    event_id: int,
    entity_id: str,
    blocker_item_id: str,
    conflicting_globs: list[str],
    created_at_seconds_ago: float = 0.0,
) -> MockDaemonEvent:
    """Factory: create a mock DaemonEvent with the given overlap metadata."""
    created = datetime.now(UTC).replace(microsecond=0)
    return MockDaemonEvent(
        id=event_id,
        project_id="test-proj",
        event_type="item_held_for_scope",
        entity_id=entity_id,
        entity_type="work_item",
        event_metadata={
            "blocking_item_id": blocker_item_id,
            "conflicting_globs": conflicting_globs,
        },
        created_at=created,
    )


class TestGroupOverlapEventsEmpty:
    """Edge case: no events."""

    def test_empty_list_returns_empty_list(self) -> None:
        """Verifies that empty list returns empty list."""
        result = group_overlap_events([])
        assert result == []


class TestGroupOverlapEventsSingle:
    """Happy path: single event."""

    def test_single_event_returns_one_section(self) -> None:
        """Verifies that single event returns one section."""
        ev = _ev(
            event_id=1,
            entity_id="CR-00077",
            blocker_item_id="CR-00076",
            conflicting_globs=["docs/a.md", "docs/b.md"],
        )
        result = group_overlap_events([ev])  # type: ignore[list-item]
        assert result == [("CR-00076", ["docs/a.md", "docs/b.md"])]


class TestGroupOverlapEventsDuplicate:
    """Most-recent-wins on duplicate blocking_item_ids (events arrive newest first)."""

    def test_duplicate_blocking_item_keeps_first(self) -> None:
        """Verifies that duplicate blocking item keeps first."""
        # Newest first — all globs from ALL events for the same blocking_item_id
        # are accumulated (union), per the design doc "Accumulate ALL globs".
        ev_newer = _ev(
            event_id=2,
            entity_id="CR-00077",
            blocker_item_id="CR-00076",
            conflicting_globs=["new.md"],
        )
        ev_older = _ev(
            event_id=1,
            entity_id="CR-00077",
            blocker_item_id="CR-00076",
            conflicting_globs=["old.md"],
            created_at_seconds_ago=60.0,
        )
        result = group_overlap_events([ev_newer, ev_older])  # type: ignore[list-item]
        # Both globs are accumulated; blocking item id ordering from first occurrence
        assert result == [("CR-00076", ["new.md", "old.md"])]

    def test_duplicate_blocking_item_only_first_kept(self) -> None:
        """Verifies that duplicate blocking item only first kept."""
        # Events with the same blocking_item_id: all globs are accumulated (union).
        # The blocking_item_id ordering is from the FIRST occurrence of each id.
        ev_first = _ev(
            event_id=10, entity_id="A", blocker_item_id="BLOCK-1", conflicting_globs=["file-a.txt"]
        )
        ev_second = _ev(
            event_id=9, entity_id="B", blocker_item_id="BLOCK-1", conflicting_globs=["file-b.txt"]
        )
        ev_third = _ev(
            event_id=8, entity_id="C", blocker_item_id="BLOCK-1", conflicting_globs=["file-c.txt"]
        )
        result = group_overlap_events([ev_first, ev_second, ev_third])  # type: ignore[list-item]
        # All three globs are accumulated for BLOCK-1 (union of all events)
        assert result == [("BLOCK-1", ["file-a.txt", "file-b.txt", "file-c.txt"])]


class TestGroupOverlapEventsMultiple:
    """Two different blocking_item_ids — both preserved, original order."""

    def test_two_different_blocking_items_both_present(self) -> None:
        """Verifies that two different blocking items both present."""
        ev1 = _ev(
            event_id=1, entity_id="CR-00077", blocker_item_id="CR-00050", conflicting_globs=["x.py"]
        )
        ev2 = _ev(
            event_id=2, entity_id="CR-00077", blocker_item_id="CR-00060", conflicting_globs=["y.py"]
        )
        result = group_overlap_events([ev1, ev2])  # type: ignore[list-item]
        assert result == [
            ("CR-00050", ["x.py"]),
            ("CR-00060", ["y.py"]),
        ]

    def test_order_preserved_for_distinct_blocking_items(self) -> None:
        """Verifies that order preserved for distinct blocking items."""
        ev_a = _ev(event_id=3, entity_id="X", blocker_item_id="B-A", conflicting_globs=["a.txt"])
        ev_b = _ev(event_id=2, entity_id="Y", blocker_item_id="B-B", conflicting_globs=["b.txt"])
        ev_c = _ev(event_id=1, entity_id="Z", blocker_item_id="B-C", conflicting_globs=["c.txt"])
        result = group_overlap_events([ev_c, ev_b, ev_a])  # type: ignore[list-item]
        # Order of first appearance of each distinct blocking_item_id is preserved
        assert result[0][0] == "B-C"
        assert result[1][0] == "B-B"
        assert result[2][0] == "B-A"


class TestGroupOverlapEventsSkipsInvalid:
    """Events missing required keys are silently skipped."""

    def test_event_missing_blocking_item_id_skipped(self) -> None:
        """Verifies that event missing blocking item id skipped."""
        ev = _ev(event_id=1, entity_id="CR-00077", blocker_item_id="", conflicting_globs=["a.md"])
        result = group_overlap_events([ev])  # type: ignore[list-item]
        assert result == []

    def test_event_missing_conflicting_globs_skipped(self) -> None:
        """Verifies that event missing conflicting globs skipped."""
        created = datetime.now(UTC).replace(microsecond=0)
        ev = MockDaemonEvent(
            id=1,
            project_id="test-proj",
            event_type="item_held_for_scope",
            entity_id="CR-00077",
            entity_type="work_item",
            event_metadata={"blocking_item_id": "CR-00076"},  # no conflicting_globs
            created_at=created,
        )
        result = group_overlap_events([ev])  # type: ignore[list-item]
        assert result == []

    def test_event_with_none_metadata_skipped(self) -> None:
        """Verifies that event with none metadata skipped."""
        created = datetime.now(UTC).replace(microsecond=0)
        ev = MockDaemonEvent(
            id=1,
            project_id="test-proj",
            event_type="item_held_for_scope",
            entity_id="CR-00077",
            entity_type="work_item",
            event_metadata=None,
            created_at=created,
        )
        result = group_overlap_events([ev])  # type: ignore[list-item]
        assert result == []

    def test_event_missing_both_keys_skipped(self) -> None:
        """Verifies that event missing both keys skipped."""
        created = datetime.now(UTC).replace(microsecond=0)
        ev = MockDaemonEvent(
            id=1,
            project_id="test-proj",
            event_type="item_held_for_scope",
            entity_id="CR-00077",
            entity_type="work_item",
            event_metadata={"some": "other"},
            created_at=created,
        )
        result = group_overlap_events([ev])  # type: ignore[list-item]
        assert result == []
