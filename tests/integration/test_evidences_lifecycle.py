"""Integration tests for evidence ingestion lifecycle via CLI commands.

Tests AC1 (approve ingests pre), AC2 (step-done ingests post for browser_verification),
AC4 (oversize rolls back), and AC5 (post-archive visibility regression guard).

Uses real PostgreSQL testcontainer + real CLI invocation via CliRunner.
No DB mocking; ON CONFLICT upsert is exercised against a real Postgres.
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest
from click.testing import CliRunner

from dashboard.routers.items import _list_evidences
from orch.archive.archiver import archive_work_item
from orch.cli.main import cli
from orch.db.models import (
    EvidencePhase,
    Project,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemEvidence,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if __name__ == "__main__":
    pytest.main([__file__, "-v"])

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _invoke(
    runner: CliRunner,
    args: list[str],
    get_session: Any,
    project_id: str = "test-proj",
    **ctx_obj_extra: Any,
) -> Any:
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": get_session, **ctx_obj_extra},
        catch_exceptions=False,
    )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _make_git_repo_with_active_dir(work_item_dir: Path, item_id: str) -> Path:
    """Create a git repo and stage + commit the ai-dev/active/<item_id>/ directory."""
    import subprocess

    work_item_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=work_item_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.test"],
        cwd=work_item_dir,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=work_item_dir, check=True, capture_output=True
    )
    active_dir = work_item_dir / "ai-dev" / "active" / item_id
    active_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "add", "ai-dev"], cwd=work_item_dir, check=True, capture_output=True)
    result = subprocess.run(
        ["git", "commit", "-m", f"init {item_id}"],
        cwd=work_item_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and "nothing to commit" not in result.stdout:
        raise RuntimeError(f"git commit failed: {result.stderr}")
    return work_item_dir


def _git_add_and_commit(work_item_dir: Path, item_id: str, msg: str = "update") -> None:
    """Stage and commit any new/modified files in the worktree."""
    import subprocess

    subprocess.run(
        ["git", "-C", str(work_item_dir), "add", "ai-dev"],
        cwd=work_item_dir,
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["git", "-C", str(work_item_dir), "commit", "-m", msg],
        cwd=work_item_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and "nothing to commit" not in result.stdout:
        raise RuntimeError(f"git commit failed: {result.stderr}")


class TestApproveIngestsPreEvidences:
    def test_approve_ingests_pre_2_files_png_and_yaml(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
    ) -> None:
        """AC1: iw approve ingests pre evidences from ai-dev/active/<id>/evidences/pre/."""
        runner = CliRunner()

        item_id = "X-99911"
        work_item_dir = _make_git_repo_with_active_dir(
            Path(tempfile.mkdtemp()) / "repo_root", item_id
        )
        pre_dir = work_item_dir / "ai-dev" / "active" / item_id / "evidences" / "pre"
        pre_dir.mkdir(parents=True)

        (pre_dir / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
        (pre_dir / "b.yaml").write_bytes(b"key: value\n")
        _git_add_and_commit(work_item_dir, item_id)

        db_session.add(
            WorkItem(
                project_id="test-proj",
                id=item_id,
                type=WorkItemType.Feature,
                title="Test AC1",
                status=WorkItemStatus.draft,
                phase=WorkItemPhase.active,
                config={},
                depends_on=[],
                blocks=[],
            )
        )
        db_session.flush()

        result = _invoke(
            runner,
            ["approve", item_id],
            cli_get_session,
            repo_root=str(work_item_dir),
        )
        assert result.exit_code == 0, f"approve failed: {result.output}"

        db_session.refresh(db_session.get(WorkItem, ("test-proj", item_id)))
        item = db_session.get(WorkItem, ("test-proj", item_id))
        assert item is not None, "WorkItem should exist after approve"
        assert item.status == WorkItemStatus.approved

        rows = (
            db_session.query(WorkItemEvidence)
            .filter_by(
                project_id="test-proj",
                work_item_id=item_id,
                phase=EvidencePhase.pre,
            )
            .all()
        )
        assert len(rows) == 2, f"expected 2 rows, got {len(rows)}"

        filenames = {r.filename for r in rows}
        assert "a.png" in filenames
        assert "b.yaml" in filenames

        for row in rows:
            disk_file = pre_dir / row.filename
            assert disk_file.read_bytes() == row.content, f"content mismatch for {row.filename}"
            assert row.size_bytes == disk_file.stat().st_size
            assert _sha256(disk_file.read_bytes()) == _sha256(row.content)

        content_types = {r.filename: r.content_type for r in rows}
        assert content_types["a.png"] == "image/png"
        assert content_types["b.yaml"] == "application/yaml"

        shutil.rmtree(work_item_dir.parent)


class TestStepDoneIngestsPostEvidences:
    def test_step_done_browser_verification_ingests_post(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC2 positive: step-done for browser_verification ingests post evidences."""
        runner = CliRunner()

        item_id = "X-99912"
        work_item_dir = Path(tempfile.mkdtemp())
        post_dir = work_item_dir / "ai-dev" / "active" / item_id / "evidences" / "post"
        post_dir.mkdir(parents=True)

        screenshot_path = post_dir / "screenshot.png"
        screenshot_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 30)

        item = WorkItem(
            project_id="test-proj",
            id=item_id,
            type=WorkItemType.Feature,
            title="Test AC2 browser_verification",
            status=WorkItemStatus.approved,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(item)
        step = WorkflowStep(
            project_id="test-proj",
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Browser",
            step_type=StepType.browser_verification,
            status=StepStatus.in_progress,
        )
        db_session.add(step)
        db_session.flush()

        monkeypatch.chdir(work_item_dir)

        result = _invoke(
            runner,
            ["step-done", item_id, "--step", "S01"],
            cli_get_session,
        )
        assert result.exit_code == 0, f"step-done failed: {result.output}"

        db_session.refresh(step)
        assert step.status == StepStatus.completed

        rows = (
            db_session.query(WorkItemEvidence)
            .filter_by(
                project_id="test-proj",
                work_item_id=item_id,
                phase=EvidencePhase.post,
            )
            .all()
        )
        assert len(rows) == 1, f"expected 1 post row, got {len(rows)}"
        assert rows[0].filename == "screenshot.png"
        assert rows[0].content == screenshot_path.read_bytes()
        assert rows[0].step_id == "S01"

        shutil.rmtree(work_item_dir)

    def test_step_done_implementation_does_not_ingest(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC2 negative: step-done for non-browser_verification does NOT ingest post."""
        runner = CliRunner()

        item_id = "X-99913"
        work_item_dir = Path(tempfile.mkdtemp())
        post_dir = work_item_dir / "ai-dev" / "active" / item_id / "evidences" / "post"
        post_dir.mkdir(parents=True)

        (post_dir / "screenshot.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 30)

        item = WorkItem(
            project_id="test-proj",
            id=item_id,
            type=WorkItemType.Feature,
            title="Test AC2 implementation",
            status=WorkItemStatus.approved,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(item)
        step = WorkflowStep(
            project_id="test-proj",
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Backend",
            step_type=StepType.implementation,
            status=StepStatus.in_progress,
        )
        db_session.add(step)
        db_session.flush()

        monkeypatch.chdir(work_item_dir)

        result = _invoke(
            runner,
            ["step-done", item_id, "--step", "S01"],
            cli_get_session,
        )
        assert result.exit_code == 0, f"step-done failed: {result.output}"

        rows = (
            db_session.query(WorkItemEvidence)
            .filter_by(
                project_id="test-proj",
                work_item_id=item_id,
                phase=EvidencePhase.post,
            )
            .all()
        )
        assert len(rows) == 0, f"expected 0 post rows for implementation step, got {len(rows)}"

        shutil.rmtree(work_item_dir)


class TestApproveOversizeRollback:
    def test_approve_oversize_keeps_status_draft_no_rows(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC4: oversize evidence during approve rolls back status flip to draft."""
        runner = CliRunner()

        item_id = "X-99914"
        work_item_dir = _make_git_repo_with_active_dir(
            Path(tempfile.mkdtemp()) / "repo_root", item_id
        )
        pre_dir = work_item_dir / "ai-dev" / "active" / item_id / "evidences" / "pre"
        pre_dir.mkdir(parents=True)

        (pre_dir / "large.png").write_bytes(b"\x00" * 201)
        _git_add_and_commit(work_item_dir, item_id)

        monkeypatch.setenv("IW_CORE_EVIDENCE_MAX_BYTES", "100")

        db_session.add(
            WorkItem(
                project_id="test-proj",
                id=item_id,
                type=WorkItemType.Feature,
                title="Test AC4",
                status=WorkItemStatus.draft,
                phase=WorkItemPhase.active,
                config={},
                depends_on=[],
                blocks=[],
            )
        )
        db_session.flush()

        result = _invoke(
            runner,
            ["approve", item_id],
            cli_get_session,
            repo_root=str(work_item_dir),
        )
        assert result.exit_code != 0, "approve should have failed for oversize"

        item = db_session.get(WorkItem, ("test-proj", item_id))
        assert item is not None
        assert item.status == WorkItemStatus.draft, f"status should remain draft, got {item.status}"

        rows = db_session.query(WorkItemEvidence).filter_by(work_item_id=item_id).all()
        assert len(rows) == 0, f"expected 0 evidence rows after rollback, got {len(rows)}"

        shutil.rmtree(work_item_dir.parent)


class TestPostArchiveVisibilityRegression:
    def test_evidences_visible_after_archive_cleanup(
        self,
        db_session: Session,
        test_project: Project,
        cli_get_session: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AC5 regression guard: evidences visible after archive + cleanup.

        This test would have caught the CR-00020 gap where the Evidences tab
        went blank after archiving because the ingestion pipeline had not been
        wired. If this test ever fails, the ingestion pipeline has regressed
        and the bug from CR-00020 has reopened.
        """
        runner = CliRunner()

        item_id = "X-99915"
        work_item_dir = _make_git_repo_with_active_dir(
            Path(tempfile.mkdtemp()) / "repo_root", item_id
        )
        pre_dir = work_item_dir / "ai-dev" / "active" / item_id / "evidences" / "pre"
        post_dir = work_item_dir / "ai-dev" / "active" / item_id / "evidences" / "post"
        pre_dir.mkdir(parents=True)
        post_dir.mkdir(parents=True)

        pre_file = pre_dir / "pre_screenshot.png"
        post_file = post_dir / "post_screenshot.png"
        pre_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 30)
        post_file.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x01" * 40)
        _git_add_and_commit(work_item_dir, item_id)

        pre_content_before_archive = pre_file.read_bytes()
        post_content_before_archive = post_file.read_bytes()

        item = WorkItem(
            project_id="test-proj",
            id=item_id,
            type=WorkItemType.Feature,
            title="Test AC5 post-archive visibility",
            status=WorkItemStatus.draft,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db_session.add(item)
        step = WorkflowStep(
            project_id="test-proj",
            work_item_id=item_id,
            step_number=1,
            step_id="S01",
            agent_label="Browser",
            step_type=StepType.browser_verification,
            status=StepStatus.in_progress,
        )
        db_session.add(step)
        db_session.flush()

        monkeypatch.chdir(work_item_dir)

        result = _invoke(
            runner,
            ["approve", item_id],
            cli_get_session,
            repo_root=str(work_item_dir),
        )
        assert result.exit_code == 0, f"approve failed: {result.output}"

        result = _invoke(
            runner,
            ["step-done", item_id, "--step", "S01"],
            cli_get_session,
        )
        assert result.exit_code == 0, f"step-done failed: {result.output}"

        item_obj = db_session.get(WorkItem, ("test-proj", item_id))
        assert item_obj is not None, "WorkItem should exist before archive"
        item_obj.status = WorkItemStatus.completed

        test_project.repo_root = str(work_item_dir)
        db_session.flush()

        archive_dir = Path(tempfile.mkdtemp())
        try:
            archive_work_item(
                db=db_session,
                project_id="test-proj",
                item_id=item_id,
                archive_dir=archive_dir,
                cleanup=True,
            )
            db_session.commit()

            assert not pre_dir.exists(), (
                "ai-dev/active/<id>/ should be deleted after archive cleanup"
            )

            db_session.expire_all()

            project_obj = db_session.get(Project, "test-proj")
            assert project_obj is not None, "Project should exist"

            item_obj = db_session.get(WorkItem, ("test-proj", item_id))
            assert item_obj is not None

            evidences = _list_evidences(
                item=item_obj,
                project=project_obj,
                db=db_session,
                worktree_path=None,
            )

            assert len(evidences) == 2, (
                f"expected 2 EvidenceFile rows from DB after archive, got {len(evidences)}"
            )

            found_pre = False
            found_post = False
            for ev in evidences:
                if ev.phase == "pre" and ev.filename == "pre_screenshot.png":
                    found_pre = True
                    assert ev.content is not None, "pre content should not be None in DB"
                    assert ev.content == pre_content_before_archive, (
                        "pre content must be byte-identical after archive"
                    )
                if ev.phase == "post" and ev.filename == "post_screenshot.png":
                    found_post = True
                    assert ev.content is not None, "post content should not be None in DB"
                    assert ev.content == post_content_before_archive, (
                        "post content must be byte-identical after archive"
                    )

            assert found_pre, "pre_screenshot.png must be in DB after archive"
            assert found_post, "post_screenshot.png must be in DB after archive"

            pre_row = (
                db_session.query(WorkItemEvidence)
                .filter_by(
                    project_id="test-proj",
                    work_item_id=item_id,
                    phase=EvidencePhase.pre,
                    filename="pre_screenshot.png",
                )
                .one()
            )
            assert pre_row.content == pre_content_before_archive
            assert _sha256(pre_row.content) == _sha256(pre_content_before_archive)

            post_row = (
                db_session.query(WorkItemEvidence)
                .filter_by(
                    project_id="test-proj",
                    work_item_id=item_id,
                    phase=EvidencePhase.post,
                    filename="post_screenshot.png",
                )
                .one()
            )
            assert post_row.content == post_content_before_archive
            assert _sha256(post_row.content) == _sha256(post_content_before_archive)

        finally:
            shutil.rmtree(archive_dir, ignore_errors=True)
            shutil.rmtree(work_item_dir.parent, ignore_errors=True)
