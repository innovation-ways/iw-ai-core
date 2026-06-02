"""Tests for the /api/chat/projects endpoint — returns enabled projects in alpha order."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import Project


@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    """Provide a TestClient with get_db overridden to the test db_session."""
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        app = create_app()
        app.dependency_overrides[get_db] = lambda: db_session
        with TestClient(app, raise_server_exceptions=False) as tc:
            yield tc
        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


def test_lists_enabled_projects_alpha(client: TestClient, db_session) -> None:
    """Verifies that enabled projects are returned sorted alphabetically by display_name."""
    db_session.add_all(
        [
            Project(
                id="iw-ai-core",
                display_name="IW AI Core Platform",
                repo_root="/repos/a",
                config={},
                enabled=True,
            ),
            Project(
                id="innoforge",
                display_name="InnoForge Document Platform",
                repo_root="/repos/b",
                config={},
                enabled=True,
            ),
            Project(
                id="disabled-proj",
                display_name="ZZ Disabled",
                repo_root="/repos/c",
                config={},
                enabled=False,
            ),
        ]
    )
    db_session.commit()

    response = client.get("/api/chat/projects")

    assert response.status_code == 200
    assert response.json() == {
        "projects": [
            {"id": "innoforge", "display_name": "InnoForge Document Platform"},
            {"id": "iw-ai-core", "display_name": "IW AI Core Platform"},
        ]
    }


def test_lists_empty_when_no_enabled_projects(client: TestClient) -> None:
    """Verifies that an empty projects list is returned when no enabled projects exist."""
    response = client.get("/api/chat/projects")

    assert response.status_code == 200
    assert response.json() == {"projects": []}
