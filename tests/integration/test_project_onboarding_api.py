"""Integration tests for /api/projects/* routes (CR-00011 new-project onboarding).

Uses testcontainers PostgreSQL + FastAPI TestClient.
"""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import Project

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path


@pytest.fixture
def client(db_session: Any, tmp_path: Path) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Any, None, None]:
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    original_browse_root = None
    try:
        from dashboard.routers import projects as projects_module

        original_browse_root = projects_module._browse_root
        projects_module._browse_root = lambda: tmp_path
    except Exception as exc:
        logging.warning("Could not override _browse_root: %s", exc)

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    try:
        if original_browse_root is not None:
            projects_module._browse_root = original_browse_root
    except Exception as exc:
        logging.warning("Could not restore _browse_root: %s", exc)

    app.dependency_overrides.clear()


def make_git_repo(tmp_path: Path, name: str = "my-repo") -> Path:
    """Create a real git repo in tmp_path and return its path."""
    repo_root = tmp_path / name
    repo_root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    return repo_root


class TestNewProjectModalRoute:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/projects/new")
        assert resp.status_code == 200

    def test_has_form(self, client: TestClient) -> None:
        resp = client.get("/api/projects/new")
        assert 'hx-post="/api/projects/create"' in resp.text

    def test_has_project_id_input(self, client: TestClient) -> None:
        resp = client.get("/api/projects/new")
        assert 'id="project_id"' in resp.text

    def test_has_display_name_input(self, client: TestClient) -> None:
        resp = client.get("/api/projects/new")
        assert 'id="display_name"' in resp.text

    def test_has_repo_root_input(self, client: TestClient) -> None:
        resp = client.get("/api/projects/new")
        assert 'id="repo_root"' in resp.text

    def test_has_browse_button(self, client: TestClient) -> None:
        resp = client.get("/api/projects/new")
        assert "Browse" in resp.text

    def test_renders_with_empty_form_values(self, client: TestClient) -> None:
        resp = client.get("/api/projects/new")
        assert 'value=""' in resp.text


class TestProjectSlugRoute:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/projects/slug?path=/some/path")
        assert resp.status_code == 200

    def test_slugifies_simple_name(self, client: TestClient, tmp_path: Path) -> None:
        test_file = tmp_path / "my-project"
        test_file.mkdir()
        resp = client.get(f"/api/projects/slug?path={test_file}")
        assert resp.text.strip() == "my-project"

    def test_slugifies_with_spaces(self, client: TestClient, tmp_path: Path) -> None:
        test_dir = tmp_path / "My Test Project"
        test_dir.mkdir()
        resp = client.get(f"/api/projects/slug?path={test_dir}")
        assert resp.text.strip() == "my-test-project"

    def test_returns_empty_for_missing_path(self, client: TestClient) -> None:
        resp = client.get("/api/projects/slug")
        assert resp.text.strip() == ""

    def test_returns_empty_for_path_outside_safe_root(self, client: TestClient) -> None:
        resp = client.get("/api/projects/slug?path=/nonexistent/../etc")
        assert resp.text.strip() == ""


class TestBrowseDirectoryRoute:
    def test_returns_200(self, client: TestClient) -> None:
        resp = client.get("/api/projects/browse")
        assert resp.status_code == 200

    def test_has_breadcrumbs(self, client: TestClient) -> None:
        resp = client.get("/api/projects/browse")
        assert "Home" in resp.text

    def test_has_directory_entries_section(self, client: TestClient) -> None:
        resp = client.get("/api/projects/browse")
        assert "No subdirectories found" in resp.text or "<li>" in resp.text

    def test_show_hidden_param_accepted(self, client: TestClient) -> None:
        resp = client.get("/api/projects/browse?show_hidden=true")
        assert resp.status_code == 200

    def test_path_param_filters_entries(self, client: TestClient) -> None:
        resp = client.get("/api/projects/browse?path=")
        assert resp.status_code == 200

    def test_navigates_to_subdirectory(self, client: TestClient, tmp_path: Path) -> None:
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        resp = client.get(f"/api/projects/browse?path={subdir}")
        assert resp.status_code == 200
        assert "subdir" in resp.text


class TestCreateProjectRoute:
    def test_missing_project_id_returns_modal_with_error(
        self, client: TestClient, db_session: Any
    ) -> None:
        resp = client.post(
            "/api/projects/create",
            data={"project_id": "", "display_name": "My Project", "repo_root": "/tmp"},
        )
        assert resp.status_code == 200
        assert "Project ID is required" in resp.text

    def test_invalid_project_id_returns_modal_with_error(
        self, client: TestClient, db_session: Any
    ) -> None:
        resp = client.post(
            "/api/projects/create",
            data={"project_id": "Invalid ID!", "display_name": "My Project", "repo_root": "/tmp"},
        )
        assert resp.status_code == 200
        assert "must be lowercase" in resp.text

    def test_duplicate_project_id_returns_error(
        self, client: TestClient, db_session: Any, test_project: Project
    ) -> None:
        resp = client.post(
            "/api/projects/create",
            data={
                "project_id": test_project.id,
                "display_name": "Duplicate",
                "repo_root": "/tmp/nonexistent",
            },
        )
        assert resp.status_code == 200
        assert "already in use" in resp.text

    def test_missing_display_name_returns_error(self, client: TestClient, db_session: Any) -> None:
        resp = client.post(
            "/api/projects/create",
            data={"project_id": "valid-id", "display_name": "", "repo_root": "/tmp"},
        )
        assert resp.status_code == 200
        assert "Display name is required" in resp.text

    def test_nonexistent_repo_root_returns_error(self, client: TestClient, db_session: Any) -> None:
        resp = client.post(
            "/api/projects/create",
            data={
                "project_id": "valid-id",
                "display_name": "Valid",
                "repo_root": "/nonexistent/path/12345",
            },
        )
        assert resp.status_code == 200
        assert "does not exist" in resp.text or "outside the allowed directory" in resp.text

    def test_valid_repo_without_git_returns_error(
        self, client: TestClient, db_session: Any, tmp_path: Path
    ) -> None:
        empty_dir = tmp_path / "no-git"
        empty_dir.mkdir()
        resp = client.post(
            "/api/projects/create",
            data={
                "project_id": "valid-id",
                "display_name": "Valid",
                "repo_root": str(empty_dir),
            },
        )
        assert resp.status_code == 200
        assert "not a git repository" in resp.text

    def test_valid_creation_redirects(
        self,
        client: TestClient,
        db_session: Any,
        tmp_path: Path,
    ) -> None:
        repo = make_git_repo(tmp_path)
        resp = client.post(
            "/api/projects/create",
            data={
                "project_id": "test-create-project",
                "display_name": "Test Create Project",
                "repo_root": str(repo),
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("HX-Redirect") == "/"
        db_session.rollback()

    def test_project_created_in_db(
        self,
        client: TestClient,
        db_session: Any,
        tmp_path: Path,
    ) -> None:
        repo = make_git_repo(tmp_path)
        resp = client.post(
            "/api/projects/create",
            data={
                "project_id": "test-db-project",
                "display_name": "Test DB Project",
                "repo_root": str(repo),
            },
        )
        assert resp.status_code == 200
        project_row = db_session.scalars(
            select(Project).where(Project.id == "test-db-project")
        ).first()
        assert project_row is not None
        assert project_row.display_name == "Test DB Project"
        db_session.rollback()
