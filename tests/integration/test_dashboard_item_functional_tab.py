"""Integration tests for the functional-doc tab route and fragment."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import Project, WorkItem, WorkItemPhase, WorkItemStatus, WorkItemType

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session


@pytest.fixture
def app_with_session(db_engine):
    """Create app with session override, no stream factory."""
    from sqlalchemy.orm import Session as SASession

    connection = db_engine.connect()
    transaction = connection.begin()

    session = SASession(
        bind=connection,
        autocommit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )

    def override_get_db() -> Generator[SASession, None, None]:
        yield session

    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c, session, connection

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original
        transaction.rollback()
        connection.close()


@pytest.fixture
def client_with_proj(
    app_with_session,
) -> tuple[TestClient, Project, Session]:
    """Return (client, test_project, session)."""
    client, session, connection = app_with_session

    project = Project(
        id="test-proj-func",
        display_name="Func Tab Test",
        repo_root="/repos/test",
        config={},
    )
    session.add(project)
    session.flush()
    return client, project, session


class TestItemTabFunctionalDoc:
    """Test GET /project/{project_id}/item/{item_id}/tab/functional-doc."""

    def test_returns_200_with_content_populated(
        self,
        client_with_proj,
    ) -> None:
        """200 when content is populated; fragment contains rendered markdown."""
        client, project, session = client_with_proj

        item = WorkItem(
            project_id=project.id,
            id="F-FUNC-001",
            type=WorkItemType.Feature,
            title="Functional Doc Test",
            status=WorkItemStatus.draft,
            phase=WorkItemPhase.active,
            functional_doc_content="# Functional Design\n\n## Why\nTest content here.",
        )
        session.add(item)
        session.commit()

        resp = client.get(f"/project/{project.id}/item/{item.id}/tab/functional-doc")
        assert resp.status_code == 200
        assert "Functional Design" in resp.text
        assert "Test content here" in resp.text

    def test_returns_200_with_null_content_shows_empty_state(
        self,
        client_with_proj,
    ) -> None:
        """200 when content is NULL; fragment shows empty-state copy."""
        client, project, session = client_with_proj

        item = WorkItem(
            project_id=project.id,
            id="F-FUNC-002",
            type=WorkItemType.Feature,
            title="No Functional Doc",
            status=WorkItemStatus.draft,
            phase=WorkItemPhase.active,
            functional_doc_content=None,
            functional_doc_path=None,
        )
        session.add(item)
        session.commit()

        resp = client.get(f"/project/{project.id}/item/{item.id}/tab/functional-doc")
        assert resp.status_code == 200
        assert "No functional design document has been loaded" in resp.text

    def test_returns_404_for_unknown_item_id(
        self,
        client_with_proj,
    ) -> None:
        """Request for unknown item ID -> 404."""
        client, project, session = client_with_proj

        resp = client.get(f"/project/{project.id}/item/F-DOES-NOT-EXIST/tab/functional-doc")
        assert resp.status_code == 404

    def test_returns_200_with_null_content_falls_back_to_disk_path(
        self,
        client_with_proj,
        tmp_path: Path,
    ) -> None:
        """200 when content is NULL but path is set; file content rendered."""
        client, project, session = client_with_proj

        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        func_dir = repo_root / "ai-dev" / "active" / "F-FUNC-003"
        func_dir.mkdir(parents=True)
        func_file = func_dir / "F-FUNC-003_Functional.md"
        func_file.write_text(
            "# F-FUNC-003 Functional Design\n\n## Why\nDisk content here.\n",
            encoding="utf-8",
        )

        project.repo_root = str(repo_root)
        session.commit()

        item = WorkItem(
            project_id=project.id,
            id="F-FUNC-003",
            type=WorkItemType.Feature,
            title="Disk Fallback Test",
            status=WorkItemStatus.draft,
            phase=WorkItemPhase.active,
            functional_doc_content=None,
            functional_doc_path="ai-dev/active/F-FUNC-003/F-FUNC-003_Functional.md",
        )
        session.add(item)
        session.commit()

        resp = client.get(f"/project/{project.id}/item/{item.id}/tab/functional-doc")
        assert resp.status_code == 200
        assert "Disk content here" in resp.text

    def test_returns_404_cross_project_leakage(
        self,
        client_with_proj,
    ) -> None:
        """Request with wrong project in URL -> 404; cross-project leakage prevented."""
        client, project, session = client_with_proj

        item = WorkItem(
            project_id=project.id,
            id="F-FUNC-004",
            type=WorkItemType.Feature,
            title="Cross Project Leak",
            status=WorkItemStatus.draft,
            phase=WorkItemPhase.active,
            functional_doc_content="Some content",
        )
        session.add(item)
        session.commit()

        resp = client.get(f"/project/wrong-project/item/{item.id}/tab/functional-doc")
        assert resp.status_code == 404
