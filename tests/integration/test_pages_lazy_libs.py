"""Integration tests for lazy-loaded libraries (E2)."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    Project,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Generator[Session, None, None]:
            yield db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


class TestPagesLazyLibs:
    def test_item_detail_has_mermaid(self, client: TestClient, db_session: Session) -> None:
        project = Project(
            id="test-lazy-proj",
            display_name="Test Lazy Project",
            repo_root="/repos/test-lazy",
            config={},
        )
        db_session.add(project)
        db_session.flush()

        item = WorkItem(
            project_id=project.id,
            id="I-LAZY-001",
            type=WorkItemType.Issue,
            title="Test Lazy Item",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(item)
        db_session.flush()

        step = WorkflowStep(
            project_id=project.id,
            work_item_id=item.id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.completed,
        )
        db_session.add(step)
        db_session.flush()

        response = client.get(f"/project/{project.id}/item/{item.id}")
        assert response.status_code == 200

        html = response.text
        assert "mermaid.min.js" in html, "item_detail page should include mermaid.min.js"

    def test_running_page_does_not_have_mermaid(
        self, client: TestClient, db_session: Session
    ) -> None:
        project = Project(
            id="test-running-lazy",
            display_name="Test Running Lazy",
            repo_root="/repos/test-running-lazy",
            config={},
        )
        db_session.add(project)
        db_session.flush()

        response = client.get("/system/running")
        assert response.status_code == 200

        html = response.text
        assert "mermaid.min.js" not in html, "running page should NOT include mermaid.min.js"

    def test_running_page_does_not_have_hljs(self, client: TestClient, db_session: Session) -> None:
        project = Project(
            id="test-running-lazy-2",
            display_name="Test Running Lazy 2",
            repo_root="/repos/test-running-lazy-2",
            config={},
        )
        db_session.add(project)
        db_session.flush()

        response = client.get("/system/running")
        assert response.status_code == 200

        html = response.text
        assert "highlight.js" not in html, "running page should NOT include highlight.js"
        assert "hljs" not in html, "running page should NOT include hljs"

    def test_project_dashboard_does_not_have_mermaid(
        self, client: TestClient, db_session: Session
    ) -> None:
        project = Project(
            id="test-dash-lazy",
            display_name="Test Dashboard Lazy",
            repo_root="/repos/test-dash-lazy",
            config={},
        )
        db_session.add(project)
        db_session.flush()

        response = client.get(f"/project/{project.id}/")
        assert response.status_code == 200

        html = response.text
        assert "mermaid.min.js" not in html, "project dashboard should NOT include mermaid.min.js"

    def test_base_html_comment_about_lazy_loading(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200

        html = response.text
        assert "loaded lazily per-page" in html or "{% block head %}" in html, (
            "base.html should mention lazy loading via block head"
        )
