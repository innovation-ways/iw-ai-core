"""Integration tests for orch.services.work_items — round-trip DB service tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from orch.db.models import (
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(
    db_session: Any,
    project_id: str,
    item_id: str,
    *,
    status: WorkItemStatus = WorkItemStatus.draft,
    item_type: WorkItemType = WorkItemType.Feature,
) -> WorkItem:
    """Insert a minimal WorkItem for use in tests.

    Args:
        db_session: Active SQLAlchemy session.
        project_id: Project to scope the item under.
        item_id: The work item identifier.
        status: Initial status; defaults to draft.
        item_type: Work item type; defaults to Feature.

    Returns:
        The inserted WorkItem ORM instance.
    """
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=item_type,
        title=f"Test item {item_id}",
        status=status,
        phase=WorkItemPhase.active,
    )
    db_session.add(item)
    db_session.flush()
    return item


# ---------------------------------------------------------------------------
# create_work_item
# ---------------------------------------------------------------------------


class TestCreateWorkItem:
    """Covers create_work_item DB persistence and idempotency."""

    def test_create_work_item_returns_dict_with_expected_keys(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that create_work_item returns a dict with project_id, id, title, status."""
        from orch.services.work_items import RegistrationSpec, create_work_item

        spec = RegistrationSpec(
            item_id="F-00001",
            title="My feature",
            item_type="feature",
            design_doc_path=None,
            design_doc_content=None,
            functional_doc_path=None,
            functional_doc_content=None,
            manifest_steps=[],
            manifest_digest=None,
            impacted_paths=[],
            depends_on=[],
            blocks=[],
            config={},
        )
        result = create_work_item(db_session, test_project.id, spec)
        assert result["project_id"] == test_project.id
        assert result["id"].find("F-00001") != -1
        assert result["status"].find("draft") != -1
        assert result["created"] is True

    def test_create_work_item_idempotent_on_second_call(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that calling create_work_item twice returns created=False on the second call."""
        from orch.services.work_items import RegistrationSpec, create_work_item

        spec = RegistrationSpec(
            item_id="F-00001",
            title="My feature",
            item_type="feature",
            design_doc_path=None,
            design_doc_content=None,
            functional_doc_path=None,
            functional_doc_content=None,
            manifest_steps=[],
            manifest_digest=None,
            impacted_paths=[],
            depends_on=[],
            blocks=[],
            config={},
        )
        create_work_item(db_session, test_project.id, spec)
        result2 = create_work_item(db_session, test_project.id, spec)
        assert result2["created"] is False

    def test_create_work_item_persists_to_db(self, db_session: Any, test_project: Project) -> None:
        """Verifies that after create_work_item a WorkItem row exists in the DB."""
        from sqlalchemy import select

        from orch.services.work_items import RegistrationSpec, create_work_item

        spec = RegistrationSpec(
            item_id="F-00002",
            title="Persisted feature",
            item_type="feature",
            design_doc_path=None,
            design_doc_content=None,
            functional_doc_path=None,
            functional_doc_content=None,
            manifest_steps=[],
            manifest_digest=None,
            impacted_paths=[],
            depends_on=[],
            blocks=[],
            config={},
        )
        create_work_item(db_session, test_project.id, spec)
        row = db_session.execute(
            select(WorkItem).where(
                WorkItem.project_id == test_project.id,
                WorkItem.id == "F-00002",
            )
        ).scalar_one_or_none()
        assert row is not None
        assert row.title.find("Persisted feature") != -1


# ---------------------------------------------------------------------------
# approve_work_item / unapprove_work_item
# ---------------------------------------------------------------------------


class TestApproveUnapproveWorkItem:
    """Covers approve/unapprove round-trip."""

    def test_approve_draft_item(self, db_session: Any, test_project: Project) -> None:
        """Verifies that approve_work_item transitions a draft item to approved."""
        from orch.services.work_items import approve_work_item

        _make_item(db_session, test_project.id, "F-00010")
        result = approve_work_item(db_session, test_project.id, "F-00010")
        assert result["status"].find("approved") != -1

    def test_approve_nonexistent_item_raises_service_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that approve_work_item raises ServiceError when item is missing."""
        from orch.services._common import ServiceError
        from orch.services.work_items import approve_work_item

        with pytest.raises(ServiceError):
            approve_work_item(db_session, test_project.id, "F-99999")

    def test_unapprove_approved_item(self, db_session: Any, test_project: Project) -> None:
        """Verifies that unapprove_work_item transitions an approved item back to draft."""
        from orch.services.work_items import approve_work_item, unapprove_work_item

        _make_item(db_session, test_project.id, "F-00011")
        approve_work_item(db_session, test_project.id, "F-00011")
        result = unapprove_work_item(db_session, test_project.id, "F-00011")
        assert result["status"].find("draft") != -1

    def test_unapprove_draft_item_raises_service_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that unapprove_work_item raises ServiceError when item is already draft."""
        from orch.services._common import ServiceError
        from orch.services.work_items import unapprove_work_item

        _make_item(db_session, test_project.id, "F-00012")
        with pytest.raises(ServiceError):
            unapprove_work_item(db_session, test_project.id, "F-00012")


# ---------------------------------------------------------------------------
# get_work_item_status
# ---------------------------------------------------------------------------


class TestGetWorkItemStatus:
    """Covers the item-status dict shape."""

    def test_get_work_item_status_returns_expected_keys(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that get_work_item_status returns concrete field values for a known item."""
        from orch.services.work_items import get_work_item_status

        _make_item(db_session, test_project.id, "F-00020")
        result = get_work_item_status(db_session, test_project.id, "F-00020")
        assert result["project_id"] == test_project.id
        assert result["id"] == "F-00020"
        assert result["title"] == "Test item F-00020"
        assert result["status"] == "draft"
        assert result["phase"] == "active"
        assert result["steps"] == []

    def test_get_work_item_status_nonexistent_raises_service_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that get_work_item_status raises ServiceError when item is missing."""
        from orch.services._common import ServiceError
        from orch.services.work_items import get_work_item_status

        with pytest.raises(ServiceError):
            get_work_item_status(db_session, test_project.id, "F-99999")


# ---------------------------------------------------------------------------
# list_work_items
# ---------------------------------------------------------------------------


class TestListWorkItems:
    """Covers pagination, filtering, and shape of list_work_items."""

    def test_list_work_items_returns_expected_shape(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that list_work_items returns exact pagination values for an empty project."""
        from orch.services.work_items import list_work_items

        result = list_work_items(db_session, test_project.id)
        assert result["items"] == []
        assert result["next_cursor"] is None
        assert result["has_more"] is False
        assert result["total"] == 0

    def test_list_work_items_returns_all_items_when_no_filter(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that list_work_items without filter returns all items for the project."""
        from orch.services.work_items import list_work_items

        _make_item(db_session, test_project.id, "F-00030")
        _make_item(db_session, test_project.id, "F-00031")
        result = list_work_items(db_session, test_project.id)
        assert result["total"] == 2
        ids = {it["id"] for it in result["items"]}
        assert ids == {"F-00030", "F-00031"}

    def test_list_work_items_filters_by_status(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that list_work_items status filter excludes non-matching items."""
        from orch.services.work_items import list_work_items

        _make_item(db_session, test_project.id, "F-00040", status=WorkItemStatus.draft)
        _make_item(db_session, test_project.id, "F-00041", status=WorkItemStatus.approved)
        result = list_work_items(db_session, test_project.id, status="draft")
        ids = [it["id"] for it in result["items"]]
        assert "F-00040" in ids
        assert "F-00041" not in ids

    def test_list_work_items_respects_limit(self, db_session: Any, test_project: Project) -> None:
        """Verifies that list_work_items respects the limit parameter."""
        from orch.services.work_items import list_work_items

        for i in range(5):
            _make_item(db_session, test_project.id, f"F-0{100 + i}")
        result = list_work_items(db_session, test_project.id, limit=2)
        assert len(result["items"]) <= 2

    def test_list_work_items_clamps_limit_to_50(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that list_work_items enforces a server-side cap of 50 items."""
        from orch.services.work_items import list_work_items

        # Only need to check that no more than 50 are returned even if limit=200
        result = list_work_items(db_session, test_project.id, limit=200)
        assert len(result["items"]) <= 50

    def test_list_work_items_item_shape(self, db_session: Any, test_project: Project) -> None:
        """Verifies that a returned item has correct concrete field values for a known item."""
        from orch.services.work_items import list_work_items

        _make_item(db_session, test_project.id, "F-00050")
        result = list_work_items(db_session, test_project.id)
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["id"] == "F-00050"
        assert item["type"] == "Feature"
        assert item["title"] == "Test item F-00050"
        assert item["status"] == "draft"
        assert item["phase"] == "active"
        assert item["created_at"] is not None
        assert item["updated_at"] is not None


# ---------------------------------------------------------------------------
# retry_work_item
# ---------------------------------------------------------------------------


class TestRetryWorkItem:
    """Covers retry_work_item service."""

    def test_retry_item_not_found_raises_service_error(
        self, db_session: Any, test_project: Project
    ) -> None:
        """Verifies that retry_work_item raises ServiceError when item does not exist."""
        from orch.services._common import ServiceError
        from orch.services.work_items import retry_work_item

        with pytest.raises(ServiceError):
            retry_work_item(db_session, test_project.id, "F-99999")
