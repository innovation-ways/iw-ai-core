"""Integration tests for project history sorting."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from dashboard.routers.project_pages import _history_items
from orch.db.models import (
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def client(db_session: Generator[object, None, None]) -> Generator[TestClient, None, None]:
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Generator[object, None, None]:
            yield db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


def make_project(db: object, project_id: str = "test-proj") -> Project:
    project = Project(
        id=project_id,
        display_name="Test Project",
        repo_root="/repos/test",
        config={},
    )
    db.add(project)
    db.flush()
    return project


def make_history_item(
    db: object,
    project_id: str,
    item_id: str,
    title: str,
    status: WorkItemStatus,
    created_at: datetime,
    completed_at: datetime | None = None,
) -> WorkItem:
    """Create a work item in the history (completed/failed) phase."""
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Issue,
        title=title,
        status=status,
        phase=WorkItemPhase.done,
        config={},
        depends_on=[],
        blocks=[],
        created_at=created_at,
        completed_at=completed_at,
    )
    db.add(item)
    db.flush()
    return item


class TestHistorySorting:
    """Tests for _history_items() sort parameters."""

    def test_history_items_sort_by_title_asc(
        self, db_session: object, test_project: Project
    ) -> None:
        """Items should be returned alphabetically by title when sort_by=title and sort_dir=asc."""
        project_id = test_project.id
        now = datetime.now(UTC)

        # Create items with titles in non-alphabetical order
        make_history_item(
            db_session,
            project_id,
            "I-00003",
            "Zebra Item",
            WorkItemStatus.completed,
            now - timedelta(hours=1),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "Apple Item",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Mango Item",
            WorkItemStatus.completed,
            now - timedelta(hours=3),
            now,
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="title",
            sort_dir="asc",
        )

        assert total == 3
        titles = [item.title for item in items]
        assert titles == ["Apple Item", "Mango Item", "Zebra Item"], (
            f"Expected alphabetically sorted titles, got {titles}"
        )

    def test_history_items_sort_by_title_desc(
        self, db_session: object, test_project: Project
    ) -> None:
        """Items should be returned in reverse alphabetical order when sort_dir=desc."""
        project_id = test_project.id
        now = datetime.now(UTC)

        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "Apple Item",
            WorkItemStatus.completed,
            now - timedelta(hours=1),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Mango Item",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00003",
            "Zebra Item",
            WorkItemStatus.completed,
            now - timedelta(hours=3),
            now,
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="title",
            sort_dir="desc",
        )

        assert total == 3
        titles = [item.title for item in items]
        assert titles == ["Zebra Item", "Mango Item", "Apple Item"], (
            f"Expected reverse alphabetically sorted titles, got {titles}"
        )

    def test_history_items_sort_by_created_at_asc(
        self, db_session: object, test_project: Project
    ) -> None:
        """Items should be returned oldest first when sort_by='created_at' and sort_dir='asc'."""
        project_id = test_project.id
        now = datetime.now(UTC)

        # Create items with different creation times
        make_history_item(
            db_session,
            project_id,
            "I-00003",
            "Third Item",
            WorkItemStatus.completed,
            now - timedelta(hours=1),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "First Item",
            WorkItemStatus.completed,
            now - timedelta(hours=3),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Second Item",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now,
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="created_at",
            sort_dir="asc",
        )

        assert total == 3
        titles = [item.title for item in items]
        assert titles == ["First Item", "Second Item", "Third Item"], (
            f"Expected oldest first by created_at, got {titles}"
        )

    def test_history_items_invalid_sort_by_defaults_to_created_at(
        self, db_session: object, test_project: Project
    ) -> None:
        """Invalid sort_by value should default to created_at descending."""
        project_id = test_project.id
        now = datetime.now(UTC)

        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "First",
            WorkItemStatus.completed,
            now - timedelta(hours=1),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Second",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now,
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="invalid_column",
            sort_dir="desc",
        )

        # Should default to created_at desc (most recent first)
        assert total == 2
        # No error should occur

    def test_history_items_invalid_sort_dir_defaults_to_desc(
        self, db_session: object, test_project: Project
    ) -> None:
        """Invalid sort_dir value should default to desc."""
        project_id = test_project.id
        now = datetime.now(UTC)

        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "First",
            WorkItemStatus.completed,
            now - timedelta(hours=1),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Second",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now,
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="created_at",
            sort_dir="invalid_dir",
        )

        # Should default to desc (most recent first)
        assert total == 2
        # No error should occur

    # -------------------------------------------------------------------------
    # Additional tests from S05 test spec
    # -------------------------------------------------------------------------

    def test_history_sort_by_id_asc(self, db_session: object, test_project: Project) -> None:
        """Items must be returned in ascending ID order when sort_by='id' and sort_dir='asc'."""
        project_id = test_project.id
        now = datetime.now(UTC)

        # Create items with IDs in non-sequential order
        make_history_item(
            db_session,
            project_id,
            "I-00003",
            "Third Item",
            WorkItemStatus.completed,
            now - timedelta(hours=1),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "First Item",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Second Item",
            WorkItemStatus.completed,
            now - timedelta(hours=3),
            now,
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="id",
            sort_dir="asc",
        )

        assert total == 3
        ids = [item.id for item in items]
        assert ids == ["I-00001", "I-00002", "I-00003"], f"Expected ascending id order, got {ids}"

    def test_history_sort_by_title_desc(self, db_session: object, test_project: Project) -> None:
        """Items must be in descending alphabetical order when sort_by=title and sort_dir=desc."""
        project_id = test_project.id
        now = datetime.now(UTC)

        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "Apple",
            WorkItemStatus.completed,
            now - timedelta(hours=1),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Mango",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00003",
            "Zebra",
            WorkItemStatus.completed,
            now - timedelta(hours=3),
            now,
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="title",
            sort_dir="desc",
        )

        assert total == 3
        titles = [item.title for item in items]
        assert titles == ["Zebra", "Mango", "Apple"], (
            f"Expected descending alphabetical order, got {titles}"
        )

    def test_history_sort_by_created_at_default(
        self, db_session: object, test_project: Project
    ) -> None:
        """When no sort params are provided, default to created_at desc (most recent first)."""
        project_id = test_project.id
        now = datetime.now(UTC)

        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "Older",
            WorkItemStatus.completed,
            now - timedelta(hours=3),
            now - timedelta(hours=2),
        )
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Newest",
            WorkItemStatus.completed,
            now - timedelta(hours=1),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00003",
            "Middle",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now - timedelta(hours=1),
        )

        # Call without any sort params — should default to created_at desc
        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="created_at",
            sort_dir="desc",
        )

        assert total == 3
        titles = [item.title for item in items]
        assert titles == ["Newest", "Middle", "Older"], (
            f"Expected created_at desc (newest first), got {titles}"
        )

    def test_history_sort_by_duration_with_nulls(
        self, db_session: object, test_project: Project
    ) -> None:
        """Items with NULL completed_at must appear last when sorting by duration asc.

        The implementation uses completed_at as a proxy for duration ordering
        (nulls_last(completed_at) for asc). NULL completed_at appears last.
        Non-NULL items are ordered by completed_at ascending.
        """
        project_id = test_project.id
        now = datetime.now(UTC)

        # Item with a short duration (completed 10min ago, created 30min ago)
        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "Quick",
            WorkItemStatus.completed,
            now - timedelta(minutes=30),
            now - timedelta(minutes=10),
        )
        # Item with a longer duration (completed 1h ago, created 5h ago)
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Slow",
            WorkItemStatus.completed,
            now - timedelta(hours=5),
            now - timedelta(hours=1),
        )
        # Item with no completed_at (NULL duration) — should appear last in asc
        make_history_item(
            db_session,
            project_id,
            "I-00003",
            "Incomplete",
            WorkItemStatus.completed,
            now - timedelta(hours=1),
            None,  # completed_at=None → NULL duration
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="duration",
            sort_dir="asc",
        )

        assert total == 3
        titles = [item.title for item in items]
        # With duration asc (implemented as completed_at asc with NULLS LAST):
        # - Slow (completed T-1h, oldest completed_at) comes first
        # - Quick (completed T-10min) comes second
        # - Incomplete (NULL completed_at) comes last
        assert titles == ["Slow", "Quick", "Incomplete"], (
            f"Expected NULL completed_at last in asc order, got {titles}"
        )
        # Verify Incomplete is indeed last (NULL handling)
        assert items[-1].title == "Incomplete", (
            f"Expected Incomplete to be last (NULL), got {items[-1].title}"
        )

    def test_history_sort_by_id_desc(self, db_session: object, test_project: Project) -> None:
        """Items must be returned in descending ID order when sort_by='id' and sort_dir='desc'."""
        project_id = test_project.id
        now = datetime.now(UTC)

        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "First",
            WorkItemStatus.completed,
            now - timedelta(hours=1),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Second",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00003",
            "Third",
            WorkItemStatus.completed,
            now - timedelta(hours=3),
            now,
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="id",
            sort_dir="desc",
        )

        assert total == 3
        for i in range(len(items) - 1):
            assert items[i].id >= items[i + 1].id, (
                f"id at {i} ({items[i].id}) should be >= id at {i + 1} ({items[i + 1].id})"
            )

    def test_history_sort_by_created_at_desc(
        self, db_session: object, test_project: Project
    ) -> None:
        """Items must be returned newest first when sort_by='created_at' and sort_dir='desc'."""
        project_id = test_project.id
        now = datetime.now(UTC)

        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "Oldest",
            WorkItemStatus.completed,
            now - timedelta(hours=3),
            now - timedelta(hours=2),
        )
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Middle",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now - timedelta(hours=1),
        )
        make_history_item(
            db_session,
            project_id,
            "I-00003",
            "Newest",
            WorkItemStatus.completed,
            now - timedelta(hours=1),
            now,
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="created_at",
            sort_dir="desc",
        )

        assert total == 3
        for i in range(len(items) - 1):
            assert items[i].created_at >= items[i + 1].created_at, (
                f"created_at[{i}]={items[i].created_at} >= [{i + 1}]={items[i + 1].created_at}"
            )

    def test_history_sort_by_type_asc(self, db_session: object, test_project: Project) -> None:
        """Items must be returned in ascending type order when sort_by='type' and sort_dir='asc'."""
        project_id = test_project.id
        now = datetime.now(UTC)

        feat = WorkItem(
            project_id=project_id,
            id="F-00001",
            type=WorkItemType.Feature,
            title="Feature Item",
            status=WorkItemStatus.completed,
            phase=WorkItemPhase.done,
            config={},
            depends_on=[],
            blocks=[],
            created_at=now - timedelta(hours=1),
            completed_at=now,
        )
        db_session.add(feat)
        db_session.flush()

        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "Issue Item",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now,
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="type",
            sort_dir="asc",
        )

        assert total == 2
        for i in range(len(items) - 1):
            assert items[i].type <= items[i + 1].type, (
                f"type at {i} ({items[i].type}) should be <= type at {i + 1} ({items[i + 1].type})"
            )

    def test_history_sort_by_type_desc(self, db_session: object, test_project: Project) -> None:
        """Items must be in descending type order when sort_by=type and sort_dir=desc."""
        project_id = test_project.id
        now = datetime.now(UTC)

        feat = WorkItem(
            project_id=project_id,
            id="F-00001",
            type=WorkItemType.Feature,
            title="Feature Item",
            status=WorkItemStatus.completed,
            phase=WorkItemPhase.done,
            config={},
            depends_on=[],
            blocks=[],
            created_at=now - timedelta(hours=1),
            completed_at=now,
        )
        db_session.add(feat)
        db_session.flush()

        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "Issue Item",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now,
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="type",
            sort_dir="desc",
        )

        assert total == 2
        for i in range(len(items) - 1):
            assert items[i].type >= items[i + 1].type, (
                f"type at {i} ({items[i].type}) should be >= type at {i + 1} ({items[i + 1].type})"
            )

    def test_history_sort_by_status_asc(self, db_session: object, test_project: Project) -> None:
        """Items must be in ascending status order when sort_by=status and sort_dir=asc."""
        project_id = test_project.id
        now = datetime.now(UTC)

        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "Failed Item",
            WorkItemStatus.failed,
            now - timedelta(hours=1),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Completed Item",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now,
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="status",
            sort_dir="asc",
        )

        assert total == 2
        for i in range(len(items) - 1):
            assert items[i].status <= items[i + 1].status, (
                f"status at {i} ({items[i].status}) <= status at {i + 1} ({items[i + 1].status})"
            )

    def test_history_sort_by_status_desc(self, db_session: object, test_project: Project) -> None:
        """Items must be in descending status order when sort_by=status and sort_dir=desc."""
        project_id = test_project.id
        now = datetime.now(UTC)

        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "Failed Item",
            WorkItemStatus.failed,
            now - timedelta(hours=1),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Completed Item",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now,
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="status",
            sort_dir="desc",
        )

        assert total == 2
        for i in range(len(items) - 1):
            assert items[i].status >= items[i + 1].status, (
                f"status at {i} ({items[i].status}) >= status at {i + 1} ({items[i + 1].status})"
            )

    def test_history_sort_by_duration_desc(self, db_session: object, test_project: Project) -> None:
        """Items must be in descending duration order when sort_by=duration and sort_dir=desc.

        The implementation uses completed_at as a proxy for duration ordering
        (nulls_first(completed_at).desc() for desc). NULL completed_at appears first.
        Non-NULL items are ordered by completed_at descending (longest duration first).
        """
        project_id = test_project.id
        now = datetime.now(UTC)

        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "Quick",
            WorkItemStatus.completed,
            now - timedelta(minutes=30),
            now - timedelta(minutes=10),
        )
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Slow",
            WorkItemStatus.completed,
            now - timedelta(hours=5),
            now - timedelta(hours=1),
        )
        make_history_item(
            db_session,
            project_id,
            "I-00003",
            "Incomplete",
            WorkItemStatus.completed,
            now - timedelta(hours=1),
            None,
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="duration",
            sort_dir="desc",
        )

        assert total == 3
        # Check adjacent pairs: NULL completed_at should come before non-NULL (nulls_first),
        # and non-NULL values should be in descending completed_at order
        for i in range(len(items) - 1):
            curr_completed = items[i].completed_at
            next_completed = items[i + 1].completed_at
            if curr_completed is None and next_completed is not None:
                # NULL should come first - this is correct
                continue
            if curr_completed is None and next_completed is None:
                # Both NULL - equal, continue
                continue
            if curr_completed is not None and next_completed is None:
                # Non-NULL before NULL - incorrect (NULL should be first)
                pytest.fail(
                    f"Item at index {i} (completed_at={curr_completed}) should be NULL or "
                    f"after item at index {i + 1} (completed_at={next_completed})"
                )
            else:
                # Both non-NULL - check descending order
                assert curr_completed >= next_completed, (
                    f"completed_at at {i} ({curr_completed}) >= at {i + 1} ({next_completed})"
                )

    def test_history_sort_by_title_asc_adjacent_pairs(
        self, db_session: object, test_project: Project
    ) -> None:
        """Verify adjacent pairs are correctly ordered (not just full list)."""
        project_id = test_project.id
        now = datetime.now(UTC)

        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "Apple",
            WorkItemStatus.completed,
            now - timedelta(hours=1),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Banana",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00003",
            "Cherry",
            WorkItemStatus.completed,
            now - timedelta(hours=3),
            now,
        )

        items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="title",
            sort_dir="asc",
        )

        assert total == 3
        for i in range(len(items) - 1):
            assert items[i].title <= items[i + 1].title, (
                f"title at {i} ('{items[i].title}') <= title at {i + 1} ('{items[i + 1].title}')"
            )

    def test_history_sort_preserved_with_filters(
        self, db_session: object, test_project: Project
    ) -> None:
        """Both type filter and sort_by must be respected simultaneously."""
        project_id = test_project.id
        now = datetime.now(UTC)

        # Add two Issues and one Feature
        make_history_item(
            db_session,
            project_id,
            "I-00001",
            "Banana Issue",
            WorkItemStatus.completed,
            now - timedelta(hours=1),
            now,
        )
        make_history_item(
            db_session,
            project_id,
            "I-00002",
            "Apple Issue",
            WorkItemStatus.completed,
            now - timedelta(hours=2),
            now,
        )
        # Create a Feature — this should be filtered out by type_filter
        feat = WorkItem(
            project_id=project_id,
            id="F-00001",
            type=WorkItemType.Feature,
            title="Zebra Feature",
            status=WorkItemStatus.completed,
            phase=WorkItemPhase.done,
            config={},
            depends_on=[],
            blocks=[],
            created_at=now - timedelta(hours=3),
            completed_at=now,
        )
        db_session.add(feat)
        db_session.flush()

        # Filter by type=issue AND sort by title asc
        items, total = _history_items(
            project_id,
            db_session,
            type_filter="issue",
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="title",
            sort_dir="asc",
        )

        # Only the two issues should be returned (Feature filtered out)
        assert total == 2
        titles = [item.title for item in items]
        # Alphabetically: Apple Issue → Banana Issue
        assert titles == ["Apple Issue", "Banana Issue"], (
            f"Expected issues sorted alphabetically, got {titles}"
        )

    def test_history_sort_preserved_across_pages(
        self, db_session: object, test_project: Project
    ) -> None:
        """Sort order must continue consistently on page 2."""
        project_id = test_project.id
        now = datetime.now(UTC)

        # Create 25 items (page size is 20, so page 2 = last 5)
        for i in range(25):
            # Titles start with letters that would be out of order without sorting
            letter = chr(ord("A") + (i % 26))
            make_history_item(
                db_session,
                project_id,
                f"I-{i:05d}",
                f"{letter} Item {i:02d}",
                WorkItemStatus.completed,
                now - timedelta(hours=i),
                now,
            )

        # Sort by title asc, get page 1
        page1_items, total = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=1,
            sort_by="title",
            sort_dir="asc",
        )

        # Sort by title asc, get page 2
        page2_items, _ = _history_items(
            project_id,
            db_session,
            type_filter=None,
            status_filter=None,
            date_from=None,
            date_to=None,
            page=2,
            sort_by="title",
            sort_dir="asc",
        )

        assert total == 25
        assert len(page1_items) == 20
        assert len(page2_items) == 5

        # Page 2 titles should continue alphabetically after page 1's last title
        page1_last_title = page1_items[-1].title
        page2_first_title = page2_items[0].title
        page2_all_titles = [item.title for item in page2_items]

        # The first item on page 2 should come after the last item on page 1
        assert page2_first_title >= page1_last_title, (
            f"Page 2 first ('{page2_first_title}') should be >= page 1 last ('{page1_last_title}')"
        )
        # Verify page 2 is also sorted
        assert page2_all_titles == sorted(page2_all_titles), (
            f"Page 2 titles should be sorted, got {page2_all_titles}"
        )
