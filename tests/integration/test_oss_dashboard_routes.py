"""Integration tests for OSS compliance dashboard routes."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    Project,
    ProjectOssJob,
    ProjectOssJobKind,
    ProjectOssJobStatus,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session


# Override conftest's `db_session` for this file so SSE tests get a session
# that shares its connection with stream-factory sessions via SAVEPOINTs.
# That way `db_session.commit()` is visible to the stream's fresh sessions,
# and the whole outer transaction still rolls back at teardown.
@pytest.fixture
def oss_routes_connection(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


@pytest.fixture
def db_session(oss_routes_connection) -> Generator[Session, None, None]:
    from sqlalchemy.orm import Session as SASession

    session = SASession(
        bind=oss_routes_connection,
        autocommit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    yield session
    session.close()


@pytest.fixture
def client(
    db_session: Session,
    oss_routes_connection,
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    # Stream factory sessions share the test's connection so they see savepoint-
    # committed rows written by the test's session.
    from sqlalchemy.orm import Session as SASession

    def stream_factory() -> Session:
        return SASession(
            bind=oss_routes_connection,
            autocommit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )

    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        app.state.oss_session_factory = stream_factory

        with TestClient(app, raise_server_exceptions=True) as c:
            yield c

        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


@pytest.fixture
def project_with_oss_disabled(db_session: Session, tmp_path: Path) -> Project:
    repo = tmp_path / "oss-test"
    repo.mkdir()
    project = Project(
        id="test-oss-proj",
        display_name="OSS Test Project",
        repo_root=str(repo),
        config={},
        oss_enabled=False,
    )
    db_session.add(project)
    db_session.flush()
    return project


@pytest.fixture
def project_with_oss_enabled(db_session: Session, tmp_path: Path) -> Project:
    repo = tmp_path / "oss-enabled"
    repo.mkdir()
    project = Project(
        id="test-oss-enabled",
        display_name="OSS Enabled Project",
        repo_root=str(repo),
        config={},
        oss_enabled=True,
    )
    db_session.add(project)
    db_session.flush()
    return project


class TestOssPage:
    def test_oss_page_returns_200(
        self, client: TestClient, project_with_oss_disabled: Project
    ) -> None:
        resp = client.get(f"/project/{project_with_oss_disabled.id}/oss")
        assert resp.status_code == 200

    def test_oss_page_404_for_unknown_project(self, client: TestClient) -> None:
        resp = client.get("/project/nonexistent/oss")
        assert resp.status_code == 404


class TestOssStatusFrame:
    def test_status_frame_returns_200(
        self, client: TestClient, project_with_oss_disabled: Project
    ) -> None:
        resp = client.get(f"/project/{project_with_oss_disabled.id}/oss/status")
        assert resp.status_code == 200

    def test_status_frame_404_for_unknown_project(self, client: TestClient) -> None:
        resp = client.get("/project/nonexistent/oss/status")
        assert resp.status_code == 404


class TestOssTools:
    def test_tools_returns_200(
        self, client: TestClient, project_with_oss_disabled: Project
    ) -> None:
        resp = client.get(f"/project/{project_with_oss_disabled.id}/oss/tools")
        assert resp.status_code == 200

    def test_tools_404_for_unknown_project(self, client: TestClient) -> None:
        resp = client.get("/project/nonexistent/oss/tools")
        assert resp.status_code == 404


class TestOssInstall:
    def test_install_creates_job_with_install_kind(
        self,
        client: TestClient,
        project_with_oss_disabled: Project,
        db_session: Session,
    ) -> None:
        resp = client.post(f"/project/{project_with_oss_disabled.id}/oss/install")
        assert resp.status_code == 200

        data = resp.json()
        assert "job_id" in data
        assert "stream_url" in data
        assert f"/project/{project_with_oss_disabled.id}/oss/stream/" in data["stream_url"]

        job = (
            db_session.query(ProjectOssJob)
            .filter(ProjectOssJob.public_id == data["job_id"])
            .first()
        )
        assert job is not None
        assert job.kind == ProjectOssJobKind.install

    def test_install_returns_stream_url(
        self, client: TestClient, project_with_oss_disabled: Project
    ) -> None:
        resp = client.post(f"/project/{project_with_oss_disabled.id}/oss/install")
        assert resp.status_code == 200

        data = resp.json()
        assert "stream_url" in data
        assert data["stream_url"].startswith("/project/")
        assert "/oss/stream/" in data["stream_url"]

    def test_install_409_on_concurrent_install(
        self,
        client: TestClient,
        project_with_oss_disabled: Project,
        db_session: Session,
    ) -> None:
        existing = ProjectOssJob(
            project_id=project_with_oss_disabled.id,
            kind=ProjectOssJobKind.install,
            status=ProjectOssJobStatus.running,
        )
        db_session.add(existing)
        db_session.flush()

        resp = client.post(f"/project/{project_with_oss_disabled.id}/oss/install")
        assert resp.status_code == 409


class TestOssEnableDisable:
    def test_enable_flips_flag(
        self,
        client: TestClient,
        project_with_oss_disabled: Project,
        db_session: Session,
    ) -> None:
        resp = client.post(f"/project/{project_with_oss_disabled.id}/oss/enable")
        assert resp.status_code == 204

        db_session.expire(project_with_oss_disabled)
        assert project_with_oss_disabled.oss_enabled is True

    def test_enable_writes_toml_file(
        self,
        client: TestClient,
        project_with_oss_disabled: Project,
        db_session: Session,
    ) -> None:
        resp = client.post(f"/project/{project_with_oss_disabled.id}/oss/enable")
        assert resp.status_code == 204

        toml_path = Path(project_with_oss_disabled.repo_root) / ".iw" / "oss-publish.toml"
        assert toml_path.exists()

    def test_disable_flips_flag_off(
        self,
        client: TestClient,
        project_with_oss_enabled: Project,
        db_session: Session,
    ) -> None:
        resp = client.post(f"/project/{project_with_oss_enabled.id}/oss/disable")
        assert resp.status_code == 204

        db_session.expire(project_with_oss_enabled)
        assert project_with_oss_enabled.oss_enabled is False

    def test_disable_keeps_toml_on_disk(
        self,
        client: TestClient,
        project_with_oss_enabled: Project,
        db_session: Session,
    ) -> None:
        toml_path = Path(project_with_oss_enabled.repo_root) / ".iw" / "oss-publish.toml"
        toml_path.parent.mkdir(parents=True, exist_ok=True)
        toml_path.write_text("test content")

        resp = client.post(f"/project/{project_with_oss_enabled.id}/oss/disable")
        assert resp.status_code == 204
        assert toml_path.exists()


class TestOssScan:
    def test_scan_returns_job_id_and_stream_url(
        self, client: TestClient, project_with_oss_disabled: Project
    ) -> None:
        resp = client.post(f"/project/{project_with_oss_disabled.id}/oss/scan")
        assert resp.status_code == 200

        data = resp.json()
        assert "job_id" in data
        assert "stream_url" in data

    def test_scan_409_on_concurrent_scan(
        self,
        client: TestClient,
        project_with_oss_disabled: Project,
        db_session: Session,
    ) -> None:
        existing = ProjectOssJob(
            project_id=project_with_oss_disabled.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.running,
        )
        db_session.add(existing)
        db_session.flush()

        resp = client.post(f"/project/{project_with_oss_disabled.id}/oss/scan")
        assert resp.status_code == 409


class TestOssPrepare:
    def test_prepare_returns_404(
        self, client: TestClient, project_with_oss_disabled: Project
    ) -> None:
        """POST /oss/prepare is removed in CR-00022 (prepare/publish workflow deleted)."""
        resp = client.post(f"/project/{project_with_oss_disabled.id}/oss/prepare")
        assert resp.status_code == 404


class TestOssPublish:
    def test_publish_returns_404(
        self, client: TestClient, project_with_oss_disabled: Project
    ) -> None:
        """POST /oss/publish is removed in CR-00022 (prepare/publish workflow deleted)."""
        resp = client.post(f"/project/{project_with_oss_disabled.id}/oss/publish")
        assert resp.status_code == 404


class TestOssFix:
    def test_fix_preview_returns_200(
        self,
        client: TestClient,
        project_with_oss_disabled: Project,
    ) -> None:
        """POST /oss/fix/{check_id} with apply=False returns preview JSON."""
        resp = client.post(
            f"/project/{project_with_oss_disabled.id}/oss/fix/OSS-CH-01",
            json={"apply": False},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "target_files" in data or "check_id" in data

    def test_fix_apply_returns_job_id(
        self,
        client: TestClient,
        project_with_oss_disabled: Project,
    ) -> None:
        """POST /oss/fix/{check_id} with apply=True returns job_id + stream_url."""
        resp = client.post(
            f"/project/{project_with_oss_disabled.id}/oss/fix/OSS-CH-01",
            json={"apply": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data
        assert "stream_url" in data


class TestOssRecheck:
    def test_recheck_returns_200(
        self,
        client: TestClient,
        project_with_oss_disabled: Project,
    ) -> None:
        """POST /oss/recheck/{check_id} returns 200 and a job."""
        resp = client.post(f"/project/{project_with_oss_disabled.id}/oss/recheck/OSS-CH-01")
        assert resp.status_code == 200
        data = resp.json()
        assert "job_id" in data


class TestOssAccept:
    def test_accept_returns_204(
        self,
        client: TestClient,
        project_with_oss_disabled: Project,
    ) -> None:
        """POST /oss/accept/{check_id} with valid body returns 204."""
        resp = client.post(
            f"/project/{project_with_oss_disabled.id}/oss/accept/OSS-CH-01",
            json={"finding_hash": "abc123def456", "reason": "Test accepted"},
        )
        assert resp.status_code == 204

    def test_accept_rejects_empty_reason(
        self,
        client: TestClient,
        project_with_oss_disabled: Project,
    ) -> None:
        """POST /oss/accept/{check_id} with empty reason returns 422."""
        resp = client.post(
            f"/project/{project_with_oss_disabled.id}/oss/accept/OSS-CH-01",
            json={"finding_hash": "abc123def456", "reason": ""},
        )
        assert resp.status_code == 422


class TestOssApplyAllSafe:
    def test_apply_all_safe_preview_returns_200(
        self,
        client: TestClient,
        project_with_oss_enabled: Project,
    ) -> None:
        """POST /oss/apply-all-safe/preview returns 200 with array."""
        resp = client.post(f"/project/{project_with_oss_enabled.id}/oss/apply-all-safe/preview")
        assert resp.status_code == 200
        assert resp.json() is not None

    def test_apply_all_safe_rejects_unsafe(
        self,
        client: TestClient,
        project_with_oss_enabled: Project,
    ) -> None:
        """POST /oss/apply-all-safe with unsafe check_ids returns 422."""
        resp = client.post(
            f"/project/{project_with_oss_enabled.id}/oss/apply-all-safe",
            json={"check_ids": ["OSS-CH-99"]},
        )
        assert resp.status_code in (404, 422)


class TestOssStream:
    def test_stream_404_for_unknown_project(self, client: TestClient) -> None:
        resp = client.get("/project/nonexistent/oss/stream/99999")
        assert resp.status_code == 404

    def test_stream_404_for_nonexistent_job(
        self, client: TestClient, project_with_oss_disabled: Project
    ) -> None:
        resp = client.get(f"/project/{project_with_oss_disabled.id}/oss/stream/99999")
        assert resp.status_code == 404

    def test_stream_returns_sse_media_type(
        self,
        client: TestClient,
        project_with_oss_disabled: Project,
        db_session: Session,
    ) -> None:
        # Media-type check only — use a terminal-status job so the stream
        # finishes on its own. Whether status is running or complete, the
        # Content-Type header is set by StreamingResponse in the same way.
        job = ProjectOssJob(
            project_id=project_with_oss_disabled.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.complete,
            exit_code=0,
        )
        db_session.add(job)
        db_session.flush()

        resp = client.get(
            f"/project/{project_with_oss_disabled.id}/oss/stream/{job.public_id}",
            headers={"Accept": "text/event-stream"},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

    def test_stream_404_for_job_wrong_project(
        self,
        client: TestClient,
        project_with_oss_disabled: Project,
        db_session: Session,
        tmp_path: Path,
    ) -> None:
        other_repo = tmp_path / "other"
        other_repo.mkdir()
        other_project = Project(
            id="other-proj",
            display_name="Other",
            repo_root=str(other_repo),
            config={},
        )
        db_session.add(other_project)
        db_session.flush()

        job = ProjectOssJob(
            project_id=other_project.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.running,
        )
        db_session.add(job)
        db_session.flush()

        resp = client.get(f"/project/{project_with_oss_disabled.id}/oss/stream/{job.public_id}")
        assert resp.status_code == 404


class TestOssSseEventOrder:
    def test_stream_emits_status_and_complete_events(
        self,
        client: TestClient,
        project_with_oss_disabled: Project,
        db_session: Session,
    ) -> None:
        job = ProjectOssJob(
            project_id=project_with_oss_disabled.id,
            kind=ProjectOssJobKind.scan,
            status=ProjectOssJobStatus.complete,
            exit_code=0,
            completed_at=None,
        )
        db_session.add(job)
        db_session.flush()

        resp = client.get(
            f"/project/{project_with_oss_disabled.id}/oss/stream/{job.public_id}",
            headers={"Accept": "text/event-stream"},
            timeout=5,
        )
        assert resp.status_code == 200

        content = b"".join(resp.iter_bytes()).decode("utf-8", errors="replace")

        has_status_event = "event: status" in content or "event: complete" in content
        msg = f"Expected status or complete event in SSE stream, got: {content[:500]}"
        assert has_status_event, msg
