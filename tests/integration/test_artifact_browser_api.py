"""Integration tests for /artifact-raw endpoint against a real PostgreSQL testcontainer."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def client(db_session: Generator) -> Generator[TestClient, None, None]:
    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Generator:
            yield db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


def make_project_and_item(
    db_session: Generator,
    project_id: str = "test-proj",
    item_id: str = "F-00010",
    worktree_root: Path | None = None,
) -> tuple[Project, WorkItem, BatchItem]:
    """Create a project + work item + batch_item.

    worktree_root is the actual worktree root (contains ai-dev/ directory).
    The artifact directory is worktree_root / "ai-dev" / "design" / "active" / {item_id}.
    """
    if worktree_root is None:
        repo_root = "/repos/test"
        design_doc_path = None
        worktree_info = None
    else:
        repo_root = str(worktree_root)
        design_doc_path = f"ai-dev/design/active/{item_id}/design.md"
        worktree_info = {"path": str(worktree_root)}

    project = Project(
        id=project_id,
        display_name="Test Project",
        repo_root=repo_root,
        config={},
    )
    db_session.add(project)
    db_session.flush()

    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Feature,
        title="Test item",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        design_doc_path=design_doc_path,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)
    db_session.flush()

    batch = Batch(
        id="BATCH-TEST",
        project_id=project_id,
        status=BatchStatus.executing,
        created_at=item.created_at,
    )
    db_session.add(batch)
    db_session.flush()

    batch_item = BatchItem(
        batch_id="BATCH-TEST",
        project_id=project_id,
        work_item_id=item_id,
        status=BatchItemStatus.executing,
        worktree_info=worktree_info,
    )
    db_session.add(batch_item)
    db_session.flush()

    return project, item, batch_item


def artifact_dir(worktree_root: Path, item_id: str) -> Path:
    """Return the artifact directory for an item."""
    return worktree_root / "ai-dev" / "design" / "active" / item_id


class TestArtifactRaw:
    """Tests for GET /project/{project_id}/item/{item_id}/artifact-raw."""

    def test_path_traversal_rejected(
        self, client: TestClient, db_session: Generator, tmp_path: Path
    ) -> None:
        """Path traversal attempt returns HTTP 403."""
        worktree_root = tmp_path
        artifact = artifact_dir(worktree_root, "F-00010")
        artifact.mkdir(parents=True)
        (artifact / "design.md").write_text("# Design")

        make_project_and_item(db_session, worktree_root=worktree_root)

        resp = client.get(
            "/project/test-proj/item/F-00010/artifact-raw",
            params={"path": "../../etc/passwd"},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    def test_simple_dotdot_rejected(
        self, client: TestClient, db_session: Generator, tmp_path: Path
    ) -> None:
        """Simple ../secret path returns HTTP 403."""
        worktree_root = tmp_path
        artifact = artifact_dir(worktree_root, "F-00010")
        artifact.mkdir(parents=True)
        (artifact / "design.md").write_text("# Design")

        make_project_and_item(db_session, worktree_root=worktree_root)

        resp = client.get(
            "/project/test-proj/item/F-00010/artifact-raw",
            params={"path": "../secret"},
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"

    def test_valid_file_returns_200(
        self, client: TestClient, db_session: Generator, tmp_path: Path
    ) -> None:
        """A valid file path returns HTTP 200 with correct content."""
        worktree_root = tmp_path
        artifact = artifact_dir(worktree_root, "F-00010")
        artifact.mkdir(parents=True)
        (artifact / "design.md").write_text("# Design\n\nSome content.")

        make_project_and_item(db_session, worktree_root=worktree_root)

        resp = client.get(
            "/project/test-proj/item/F-00010/artifact-raw",
            params={"path": "design.md"},
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert b"# Design" in resp.content

    def test_missing_file_returns_404(
        self, client: TestClient, db_session: Generator, tmp_path: Path
    ) -> None:
        """Requesting a nonexistent file returns HTTP 404."""
        worktree_root = tmp_path
        artifact = artifact_dir(worktree_root, "F-00010")
        artifact.mkdir(parents=True)
        (artifact / "existing.md").write_text("# Existing")

        make_project_and_item(db_session, worktree_root=worktree_root)

        resp = client.get(
            "/project/test-proj/item/F-00010/artifact-raw",
            params={"path": "nonexistent.md"},
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"

    def test_directory_path_returns_404(
        self, client: TestClient, db_session: Generator, tmp_path: Path
    ) -> None:
        """Requesting a directory path (not a file) returns HTTP 404."""
        worktree_root = tmp_path
        artifact = artifact_dir(worktree_root, "F-00010")
        artifact.mkdir(parents=True)
        subdir = artifact / "subdir"
        subdir.mkdir()
        (subdir / "file.md").write_text("# File")

        make_project_and_item(db_session, worktree_root=worktree_root)

        resp = client.get(
            "/project/test-proj/item/F-00010/artifact-raw",
            params={"path": "subdir"},
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"

    def test_no_artifact_root_returns_404(self, client: TestClient, db_session: Generator) -> None:
        """When design_doc_path is None, returns HTTP 404."""
        make_project_and_item(db_session, worktree_root=None)

        resp = client.get(
            "/project/test-proj/item/F-00010/artifact-raw",
            params={"path": "design.md"},
        )
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text}"

    def test_worktree_preferred_over_repo_root(
        self, client: TestClient, db_session: Generator, tmp_path: Path
    ) -> None:
        """When BOTH exist, worktree is preferred."""
        worktree_root = tmp_path
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        worktree_artifact = artifact_dir(worktree_root, "F-00010")
        worktree_artifact.mkdir(parents=True)
        (worktree_artifact / "design.md").write_text("# Worktree Version")

        repo_artifact = repo_root / "ai-dev" / "design" / "active" / "F-00010"
        repo_artifact.mkdir(parents=True)
        (repo_artifact / "design.md").write_text("# Repo Version")

        make_project_and_item(db_session, worktree_root=worktree_root)

        resp = client.get(
            "/project/test-proj/item/F-00010/artifact-raw",
            params={"path": "design.md"},
        )
        assert resp.status_code == 200
        assert b"Worktree Version" in resp.content
        assert b"Repo Version" not in resp.content

    def test_image_file_returns_correct_content_type(
        self, client: TestClient, db_session: Generator, tmp_path: Path
    ) -> None:
        """Image files are served with correct MIME type."""
        worktree_root = tmp_path
        artifact = artifact_dir(worktree_root, "F-00010")
        artifact.mkdir(parents=True)
        png_content = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
            b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
        )
        (artifact / "image.png").write_bytes(png_content)

        make_project_and_item(db_session, worktree_root=worktree_root)

        resp = client.get(
            "/project/test-proj/item/F-00010/artifact-raw",
            params={"path": "image.png"},
        )
        assert resp.status_code == 200
        assert "image/png" in resp.headers["content-type"]
