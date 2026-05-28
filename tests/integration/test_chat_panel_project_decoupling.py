from __future__ import annotations

import os
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import ChatTab, Project


@contextmanager
def _client(db_session):
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    app = create_app()
    app.state.opencode_runtime = MagicMock()
    app.state.opencode_runtime.health = AsyncMock(return_value=True)
    app.state.opencode_client = MagicMock()
    app.state.relay_manager = MagicMock()
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app, raise_server_exceptions=False) as tc:
            yield tc
    finally:
        app.dependency_overrides.clear()
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


def test_chat_tabs_are_isolated_per_project_and_projects_endpoint_lists_all(db_session) -> None:
    project_a = Project(
        id="proj-a",
        display_name="Alpha Project",
        repo_root="/repos/a",
        config={},
        enabled=True,
    )
    project_b = Project(
        id="proj-b",
        display_name="Beta Project",
        repo_root="/repos/b",
        config={},
        enabled=True,
    )
    db_session.add_all([project_a, project_b])
    db_session.flush()

    tabs_a = [
        ChatTab(project_id=project_a.id, runtime="opencode", model="prov-a/model-a", title="A-1"),
        ChatTab(project_id=project_a.id, runtime="opencode", model="prov-a/model-a", title="A-2"),
    ]
    tabs_b = [
        ChatTab(project_id=project_b.id, runtime="opencode", model="prov-a/model-a", title="B-1"),
        ChatTab(project_id=project_b.id, runtime="opencode", model="prov-a/model-a", title="B-2"),
    ]
    db_session.add_all([*tabs_a, *tabs_b])
    db_session.commit()

    with _client(db_session) as client:
        tabs_a_resp = client.get(f"/api/chat/tabs?project_id={project_a.id}")
        tabs_a_ids = {t["id"] for t in tabs_a_resp.json()["tabs"]}
        assert tabs_a_ids == {str(t.id) for t in tabs_a}

        tabs_b_resp = client.get(f"/api/chat/tabs?project_id={project_b.id}")
        tabs_b_ids = {t["id"] for t in tabs_b_resp.json()["tabs"]}
        assert tabs_b_ids == {str(t.id) for t in tabs_b}

        patch_resp = client.patch(f"/api/chat/tabs/{tabs_a[0].id}", json={"title": "A-1 renamed"})
        assert patch_resp.json()["tab"]["title"] == "A-1 renamed"

        tabs_b_after_patch = client.get(f"/api/chat/tabs?project_id={project_b.id}").json()["tabs"]
        assert {t["title"] for t in tabs_b_after_patch} == {"B-1", "B-2"}

        projects_resp = client.get("/api/chat/projects")
        assert projects_resp.json() == {
            "projects": [
                {"id": "proj-a", "display_name": "Alpha Project"},
                {"id": "proj-b", "display_name": "Beta Project"},
            ]
        }
