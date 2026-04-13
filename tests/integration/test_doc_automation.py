"""Integration tests for F-00013: Documentation Automation.

Tests cover:
- Post-merge hook: merge triggers doc regeneration jobs
- Staleness detection: git mtime-based stale doc detection
- Lint gate: editorial lint warnings on job completion
- Config panel: auto-trigger and forbidden phrases settings
- Concurrent job limit enforcement
- Boundary cases: archived docs, glob matching, high volume

CRITICAL: All tests use testcontainers — NEVER connect to live DB.
"""

from __future__ import annotations

import subprocess
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.daemon.batch_merge_hooks import trigger_doc_regeneration_on_merge
from orch.db.models import (
    DocGenerationJob,
    DocStatus,
    DocTier,
    DocType,
    EditorialCategory,
    JobStatus,
    Project,
    ProjectDoc,
)
from orch.doc_service import DocService

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# FastAPI TestClient fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app, raise_server_exceptions=True) as c:
        yield c

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_project(
    db: Session,
    project_id: str = "test-proj",
    repo_root: str = "/repos/test",
    config: dict[str, Any] | None = None,
) -> Project:
    project = Project(
        id=project_id,
        display_name="Test Project",
        repo_root=repo_root,
        config=config or {},
    )
    db.add(project)
    db.flush()
    return project


def _make_doc(
    db: Session,
    project_id: str = "test-proj",
    doc_id: str = "module-auth",
    title: str = "Auth Module",
    editorial_category: EditorialCategory = EditorialCategory.technical,
    source_paths: list[str] | None = None,
    content: str | None = "# Content\n",
    status: DocStatus = DocStatus.draft,
    generated_at: datetime | None = None,
) -> ProjectDoc:
    doc = ProjectDoc(
        id=f"{project_id}:{doc_id}",
        project_id=project_id,
        doc_id=doc_id,
        title=title,
        slug=doc_id.replace("_", "-"),
        doc_type=DocType.module,
        tier=DocTier.semi_automated,
        editorial_category=editorial_category,
        status=status,
        audience=["developers"],
        source_paths=source_paths or ["src/auth/mod.rs"],
        content=content,
        generated_at=generated_at or datetime.now(UTC),
    )
    db.add(doc)
    db.flush()
    return doc


def _git_commit(repo: Path, path: Path, message: str = "commit") -> None:

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(uuid.uuid4()), encoding="utf-8")
    subprocess.run(["git", "add", str(path)], cwd=repo, check=True, capture_output=True)  # noqa: S603
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        check=True,
        capture_output=True,
        env={
            **__import__("os").environ,
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
        },
    )  # noqa: S603


# ---------------------------------------------------------------------------
# Post-Merge Hook Tests
# ---------------------------------------------------------------------------


class TestMergeHookCreatesJobs:
    """Tests for trigger_doc_regeneration_on_merge()."""

    def test_merge_hook_creates_jobs_for_matching_docs(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """Merge changes docs/auth.md -> DocGenerationJob created with trigger_reason."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "test"],
            cwd=repo,
            check=True,
            capture_output=True,
        )

        auth_md = repo / "docs" / "auth.md"
        _git_commit(repo, auth_md, "base commit")

        _git_commit(repo, auth_md, "change commit")

        _make_project(
            db_session,
            repo_root=str(repo),
            config={"doc_generation": {"auto_trigger_on_merge": True}},
        )
        _make_doc(
            db_session,
            source_paths=["docs/auth.md"],
            content="# Auth Doc\n",
        )
        db_session.flush()

        mock_batch_item = MagicMock()
        mock_batch_item.batch_id = "B-00042"
        mock_batch_item.work_item_id = "F-00013"

        project = db_session.get(Project, "test-proj")
        assert project is not None

        jobs = trigger_doc_regeneration_on_merge(db_session, mock_batch_item, project)

        assert len(jobs) == 1
        assert jobs[0].trigger_reason == "batch-merge:B-00042:F-00013"
        assert jobs[0].status == JobStatus.queued

    def test_merge_hook_no_jobs_when_auto_trigger_disabled(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """auto_trigger_on_merge=False -> no jobs created."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True
        )

        auth_md = repo / "docs" / "auth.md"
        _git_commit(repo, auth_md, "base commit")
        _git_commit(repo, auth_md, "change commit")

        _make_project(
            db_session,
            repo_root=str(repo),
            config={"doc_generation": {"auto_trigger_on_merge": False}},
        )
        _make_doc(db_session, source_paths=["docs/auth.md"])
        db_session.flush()

        mock_batch_item = MagicMock()
        mock_batch_item.batch_id = "B-00042"
        mock_batch_item.work_item_id = "F-00013"

        project = db_session.get(Project, "test-proj")
        assert project is not None

        jobs = trigger_doc_regeneration_on_merge(db_session, mock_batch_item, project)
        assert len(jobs) == 0

    def test_merge_hook_no_jobs_when_source_not_changed(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """HEAD commit changed only README.md -> no job for docs/auth.md."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True
        )

        auth_md = repo / "docs" / "auth.md"
        readme = repo / "README.md"
        _git_commit(repo, auth_md, "base commit")
        _git_commit(repo, readme, "change readme only")

        _make_project(
            db_session,
            repo_root=str(repo),
            config={"doc_generation": {"auto_trigger_on_merge": True}},
        )
        _make_doc(db_session, source_paths=["docs/auth.md"])
        db_session.flush()

        mock_batch_item = MagicMock()
        mock_batch_item.batch_id = "B-00042"
        mock_batch_item.work_item_id = "F-00013"

        project = db_session.get(Project, "test-proj")
        assert project is not None

        jobs = trigger_doc_regeneration_on_merge(db_session, mock_batch_item, project)
        assert len(jobs) == 0

    def test_merge_hook_glob_path_matching(self, db_session: Session, tmp_path: Path) -> None:
        """Glob pattern docs/auth/**/*.py matches changed file docs/auth/middleware/token.py."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True
        )

        token_py = repo / "docs" / "auth" / "middleware" / "token.py"
        _git_commit(repo, token_py, "base")
        _git_commit(repo, token_py, "change")

        _make_project(
            db_session,
            repo_root=str(repo),
            config={"doc_generation": {"auto_trigger_on_merge": True}},
        )
        _make_doc(db_session, doc_id="module-auth", source_paths=["docs/auth/**/*.py"])
        db_session.flush()

        mock_batch_item = MagicMock()
        mock_batch_item.batch_id = "B-00042"
        mock_batch_item.work_item_id = "F-00013"

        project = db_session.get(Project, "test-proj")
        assert project is not None

        jobs = trigger_doc_regeneration_on_merge(db_session, mock_batch_item, project)
        assert len(jobs) == 1


# ---------------------------------------------------------------------------
# Staleness Tests
# ---------------------------------------------------------------------------


class TestGetStaleDocs:
    """Tests for DocService.get_stale_docs() with real git mtime."""

    def test_get_stale_docs_detects_changed_source(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """Doc is stale when source file has newer commit than generated_at."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True
        )

        auth_md = repo / "src" / "auth" / "mod.rs"
        _git_commit(repo, auth_md, "initial")

        import time

        time.sleep(0.1)

        _git_commit(repo, auth_md, "updated")

        _make_project(db_session, repo_root=str(repo))
        _make_doc(
            db_session,
            doc_id="module-auth",
            source_paths=["src/auth/mod.rs"],
            generated_at=datetime.now(UTC) - timedelta(days=1),
        )
        db_session.flush()

        svc = DocService(db_session)
        stale = svc.get_stale_docs("test-proj", str(repo))

        assert len(stale) == 1
        assert stale[0][0].doc_id == "module-auth"

    def test_get_stale_docs_returns_empty_for_current(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """No stale docs when source file is older than generated_at."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True
        )

        auth_md = repo / "src" / "auth" / "mod.rs"
        _git_commit(repo, auth_md, "initial")

        _make_project(db_session, repo_root=str(repo))
        _make_doc(
            db_session,
            doc_id="module-auth",
            source_paths=["src/auth/mod.rs"],
            generated_at=datetime.now(UTC) + timedelta(days=1),
        )
        db_session.flush()

        svc = DocService(db_session)
        stale = svc.get_stale_docs("test-proj", str(repo))
        assert len(stale) == 0


class TestDocsCheckStaleCli:
    """Tests for iw docs-check-stale CLI exit codes."""

    def test_docs_check_stale_cli_exits_1(
        self, db_session: Session, tmp_path: Path, cli_get_session: Any
    ) -> None:
        """docs-check-stale exits 1 when stale docs exist (via CliRunner)."""
        from click.testing import CliRunner

        from orch.cli.doc_commands import docs_check_stale

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True
        )

        auth_md = repo / "src" / "auth" / "mod.rs"
        _git_commit(repo, auth_md, "initial")
        _git_commit(repo, auth_md, "updated")

        _make_project(db_session, repo_root=str(repo))
        _make_doc(
            db_session,
            doc_id="module-auth",
            source_paths=["src/auth/mod.rs"],
            generated_at=datetime.now(UTC) - timedelta(days=1),
        )
        db_session.flush()

        fake_get_session = MagicMock()
        fake_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
        fake_get_session.return_value.__exit__ = MagicMock(return_value=False)

        runner = CliRunner()
        result = runner.invoke(
            docs_check_stale,
            ["test-proj"],
            obj={"get_session": fake_get_session},
        )
        assert result.exit_code == 1

    def test_docs_check_stale_cli_exits_0(
        self, db_session: Session, tmp_path: Path, cli_get_session: Any
    ) -> None:
        """docs-check-stale exits 0 when no stale docs."""
        from click.testing import CliRunner

        from orch.cli.doc_commands import docs_check_stale

        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True
        )

        auth_md = repo / "src" / "auth" / "mod.rs"
        _git_commit(repo, auth_md, "initial")

        _make_project(db_session, repo_root=str(repo))
        _make_doc(
            db_session,
            doc_id="module-auth",
            source_paths=["src/auth/mod.rs"],
            generated_at=datetime.now(UTC) + timedelta(days=1),
        )
        db_session.flush()

        fake_get_session = MagicMock()
        fake_get_session.return_value.__enter__ = MagicMock(return_value=db_session)
        fake_get_session.return_value.__exit__ = MagicMock(return_value=False)

        runner = CliRunner()
        result = runner.invoke(
            docs_check_stale,
            ["test-proj"],
            obj={"get_session": fake_get_session},
        )
        assert result.exit_code == 0
        assert "All docs are current" in result.output


# ---------------------------------------------------------------------------
# Lint Gate Tests
# ---------------------------------------------------------------------------


class TestLintGate:
    """Tests for editorial lint gate on job completion."""

    def test_lint_gate_runs_after_job_completion(self, db_session: Session) -> None:
        """Job completes with missing Purpose section: lint_warnings populated, status unchanged."""
        _make_project(db_session)
        _make_doc(
            db_session,
            editorial_category=EditorialCategory.technical,
            content="# Auth Module\n\nNo Purpose section here.",
        )
        svc = DocService(db_session)
        job = svc.create_doc_job("test-proj", "module-auth")
        svc.start_doc_job(job.id)
        db_session.flush()

        svc.complete_doc_job(job.id)
        db_session.flush()

        job = svc.get_doc_job(job.id)
        assert job is not None
        assert job.lint_warnings is not None
        assert len(job.lint_warnings) > 0
        purpose_warnings = [w for w in job.lint_warnings if w["rule"] == "required_section_purpose"]
        assert len(purpose_warnings) == 1

        doc = svc.get_doc("test-proj", "module-auth")
        assert doc is not None
        assert doc.status == DocStatus.draft

    def test_lint_gate_passes_valid_content(self, db_session: Session) -> None:
        """Valid technical doc content -> empty lint_warnings."""
        _make_project(db_session)
        valid_content = """---
title: Auth Module
---
## Purpose
Handles authentication.

## Architecture
JWT-based auth.

```
def foo():
    pass
```
"""
        _make_doc(db_session, editorial_category=EditorialCategory.technical, content=valid_content)
        svc = DocService(db_session)
        job = svc.create_doc_job("test-proj", "module-auth")
        svc.start_doc_job(job.id)
        db_session.flush()

        svc.complete_doc_job(job.id)
        db_session.flush()

        job = svc.get_doc_job(job.id)
        assert job is not None
        assert job.lint_warnings is None or len(job.lint_warnings) == 0

    def test_lint_gate_forbidden_phrase(self, db_session: Session) -> None:
        """Content with 'cutting-edge' -> forbidden phrase warning."""
        _make_project(db_session)
        _make_doc(
            db_session,
            editorial_category=EditorialCategory.technical,
            content="---\ntitle: Auth\n---\n## Purpose\nThis is cutting-edge.\n",
        )
        svc = DocService(db_session)
        job = svc.create_doc_job("test-proj", "module-auth")
        svc.start_doc_job(job.id)
        db_session.flush()

        svc.complete_doc_job(job.id)
        db_session.flush()

        job = svc.get_doc_job(job.id)
        assert job is not None
        assert job.lint_warnings is not None
        phrase_warnings = [w for w in job.lint_warnings if w["rule"] == "forbidden_phrase"]
        assert len(phrase_warnings) == 1
        assert "cutting-edge" in phrase_warnings[0]["message"]

    def test_lint_warnings_route(self, client: TestClient, db_session: Session) -> None:
        """GET /api/project/{id}/docs/{doc_id}/lint-warnings returns warnings HTML."""
        _make_project(db_session)
        _make_doc(
            db_session,
            editorial_category=EditorialCategory.technical,
            content="# No Purpose\n",
        )
        svc = DocService(db_session)
        job = svc.create_doc_job("test-proj", "module-auth")
        svc.start_doc_job(job.id)
        db_session.flush()
        svc.complete_doc_job(job.id)
        db_session.flush()

        response = client.get(
            "/project/test-proj/api/project/test-proj/docs/module-auth/lint-warnings"
        )
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Config Panel Tests
# ---------------------------------------------------------------------------


class TestConfigPanel:
    """Tests for doc config panel routes."""

    def test_config_panel_saves_auto_trigger_setting(
        self, client: TestClient, db_session: Session
    ) -> None:
        """POST /api/project/{id}/docs/config saves auto_trigger_on_merge=true."""
        _make_project(db_session, config={})
        db_session.flush()

        response = client.post(
            "/project/test-proj/api/project/test-proj/docs/config",
            json={"auto_trigger_on_merge": True},
        )
        assert response.status_code == 200

        response = client.get("/project/test-proj/api/project/test-proj/docs/config")
        assert response.status_code == 200
        assert "auto_trigger_on_merge" in response.text
        assert "true" in response.text.lower()

    def test_config_panel_saves_forbidden_phrases(
        self, client: TestClient, db_session: Session
    ) -> None:
        """POST saves forbidden_phrases list."""
        _make_project(db_session, config={})
        db_session.flush()

        response = client.post(
            "/project/test-proj/api/project/test-proj/docs/config",
            json={"forbidden_phrases": "foo,bar,baz"},
        )
        assert response.status_code == 200

        response = client.get("/project/test-proj/api/project/test-proj/docs/config")
        assert response.status_code == 200

    def test_regenerate_stale_creates_jobs(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """POST /api/project/{id}/docs/regenerate-stale creates jobs for stale docs."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True
        )

        auth_md = repo / "src" / "auth" / "mod.rs"
        _git_commit(repo, auth_md, "initial")
        _git_commit(repo, auth_md, "updated")

        _make_project(db_session, repo_root=str(repo))
        _make_doc(
            db_session,
            doc_id="module-auth",
            source_paths=["src/auth/mod.rs"],
            generated_at=datetime.now(UTC) - timedelta(days=1),
        )
        _make_doc(
            db_session,
            doc_id="module-users",
            source_paths=["src/users/mod.rs"],
            generated_at=datetime.now(UTC) - timedelta(days=1),
        )
        db_session.flush()

        response = client.post("/project/test-proj/api/project/test-proj/docs/regenerate-stale")
        assert response.status_code == 200

        svc = DocService(db_session)
        jobs = svc.get_queued_jobs("test-proj")
        assert len(jobs) >= 1

    def test_stale_summary_route(
        self, client: TestClient, db_session: Session, tmp_path: Path
    ) -> None:
        """GET /api/project/{id}/docs/stale returns 200 with banner HTML."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True
        )

        auth_md = repo / "src" / "auth" / "mod.rs"
        _git_commit(repo, auth_md, "initial")
        _git_commit(repo, auth_md, "updated")

        _make_project(db_session, repo_root=str(repo))
        _make_doc(
            db_session,
            doc_id="module-auth",
            source_paths=["src/auth/mod.rs"],
            generated_at=datetime.now(UTC) - timedelta(days=1),
        )
        db_session.flush()

        response = client.get("/project/test-proj/api/project/test-proj/docs/stale")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Boundary Tests
# ---------------------------------------------------------------------------


class TestMergeHookHighVolume:
    """High-volume merge -> concurrent limit enforced."""

    def test_merge_hook_high_volume_queues_within_limit(
        self, db_session: Session, tmp_path: Path
    ) -> None:
        """10 matching docs -> max 2 running, 8 remain queued."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True
        )

        changed = repo / "docs" / "changed.py"
        _git_commit(repo, changed, "base")
        _git_commit(repo, changed, "change")

        _make_project(
            db_session,
            repo_root=str(repo),
            config={"doc_generation": {"auto_trigger_on_merge": True}},
        )

        for i in range(10):
            _make_doc(db_session, doc_id=f"module-{i}", source_paths=["docs/changed.py"])
        db_session.flush()

        mock_batch_item = MagicMock()
        mock_batch_item.batch_id = "B-00042"
        mock_batch_item.work_item_id = "F-00013"

        project = db_session.get(Project, "test-proj")
        assert project is not None

        result = trigger_doc_regeneration_on_merge(db_session, mock_batch_item, project)
        db_session.flush()
        assert len(result) == 10

        running_count = (
            db_session.query(DocGenerationJob)
            .filter(
                DocGenerationJob.project_id == "test-proj",
                DocGenerationJob.status == JobStatus.running,
            )
            .count()
        )
        queued_count = (
            db_session.query(DocGenerationJob)
            .filter(
                DocGenerationJob.project_id == "test-proj",
                DocGenerationJob.status == JobStatus.queued,
            )
            .count()
        )
        assert running_count <= 2
        assert queued_count == 10 - running_count


class TestGetStaleDocsSkipsArchived:
    """Archived docs are not returned as stale."""

    def test_get_stale_docs_skips_archived(self, db_session: Session, tmp_path: Path) -> None:
        """Archived doc with stale source is NOT returned."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=repo,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "test"], cwd=repo, check=True, capture_output=True
        )

        auth_md = repo / "src" / "auth" / "mod.rs"
        _git_commit(repo, auth_md, "initial")
        _git_commit(repo, auth_md, "updated")

        _make_project(db_session, repo_root=str(repo))
        _make_doc(
            db_session,
            doc_id="module-auth",
            source_paths=["src/auth/mod.rs"],
            generated_at=datetime.now(UTC) - timedelta(days=1),
            status=DocStatus.archived,
        )
        db_session.flush()

        svc = DocService(db_session)
        stale = svc.get_stale_docs("test-proj", str(repo))
        assert len(stale) == 0


class TestLintDocNoContentSkipped:
    """Doc with null content -> lint not called."""

    def test_lint_doc_no_content_skipped(self, db_session: Session) -> None:
        """Doc with content=None -> complete_doc_job does not call lint gate."""
        _make_project(db_session)
        _make_doc(db_session, content=None)
        svc = DocService(db_session)
        job = svc.create_doc_job("test-proj", "module-auth")
        svc.start_doc_job(job.id)
        db_session.flush()

        svc.complete_doc_job(job.id)
        db_session.flush()

        job = svc.get_doc_job(job.id)
        assert job is not None
        assert job.lint_warnings is None


class TestConfigDefaultsWhenNotSet:
    """No doc_generation key in config -> defaults apply."""

    def test_config_defaults_when_not_set(self, client: TestClient, db_session: Session) -> None:
        """Project.config without doc_generation key -> defaults apply."""
        _make_project(db_session, config={})
        db_session.flush()

        response = client.get("/project/test-proj/api/project/test-proj/docs/config")
        assert response.status_code == 200
