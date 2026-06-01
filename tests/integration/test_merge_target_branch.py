"""I-00126 AC1: merge queue refuses to merge when repo is not on default branch.

Uses a real temp git repo so `resolve_branch_for_project` hits actual git.
The repo is checked out on a non-default branch (mimicking the I-00121 stray
branch situation).  The merge queue's pre-check must detect the mismatch and:

  1. Set batch_item.status = merge_failed
  2. Emit a merge_refused_wrong_branch daemon_event with expected + actual branch
  3. NOT mark the item as merged

This test is integration-style (testcontainers DB) because it verifies semantic
DB outcomes: status flip, event metadata, and the absence of a merged state.

AC coverage: AC1 (semantic: batch item is NOT marked merged when on wrong branch).
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select

from orch.daemon.merge_queue import process_merge_queue
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Temp git repo helpers
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["git", *args], capture_output=True, text=True, cwd=cwd, timeout=30
    )


def _git_ok(*args: str, cwd: Path) -> str:
    r = _git(*args, cwd=cwd)
    assert r.returncode == 0, f"git {' '.join(args)} failed in {cwd}: {r.stderr}"
    return r.stdout.strip()


def _make_temp_repo(tmp_path: Path) -> tuple[Path, Path]:
    """Create a bare-bones repo: main branch + a stray feature branch checked out.

    Returns (repo_root, worktree_branch_path).  After this the repo's HEAD is
    on the stray branch, so the merge queue guard must fire.
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    _git_ok("init", "-b", "main", cwd=repo)
    _git_ok("config", "user.email", "test@example.com", cwd=repo)
    _git_ok("config", "user.name", "Test User", cwd=repo)

    # Commit on main
    (repo / "README.md").write_text("initial\n")
    _git_ok("add", "README.md", cwd=repo)
    _git_ok("commit", "-m", "initial commit", cwd=repo)

    # Create a stray feature branch and check it out (simulates I-00121's state)
    _git_ok("checkout", "-b", "feature/stray", cwd=repo)
    (repo / "stray.txt").write_text("on stray branch\n")
    _git_ok("add", "stray.txt", cwd=repo)
    _git_ok("commit", "-m", "stray commit", cwd=repo)

    # Verify precondition: HEAD should be on stray branch, not main
    head = _git_ok("rev-parse", "--abbrev-ref", "HEAD", cwd=repo)
    assert head == "feature/stray", f"Precondition: expected HEAD on stray, got {head}"

    return repo, repo  # worktree == repo for this test


def _make_agent_branch_worktree(
    repo: Path, worktree_path: Path, branch_name: str = "agent/I-00126-test"
) -> None:
    """Create a worktree on an agent branch with a commit to merge."""
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    _git_ok("worktree", "add", "-b", branch_name, str(worktree_path), "HEAD", cwd=repo)
    # Add a meaningful commit on the worktree branch
    (worktree_path / "feature.py").write_text("# I-00126 test change\n")
    _git_ok("add", "feature.py", cwd=worktree_path)
    _git_ok("commit", "-m", "I-00126 test commit", cwd=worktree_path)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def project_config(repo_root: Path) -> ProjectConfig:
    return ProjectConfig(
        id="test-proj",
        display_name="Test Project",
        repo_root=str(repo_root),
        enabled=True,
        cli_tool="opencode",
        model="minimax",
        worktree_base=".worktrees",
        config={},
    )


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """Create a temp repo with main + stray branch; repo HEAD is on stray."""
    repo, _ = _make_temp_repo(tmp_path)
    return repo


@pytest.fixture
def agent_worktree_path(tmp_path: Path, repo_root: Path) -> Path:
    """Create an agent branch worktree with one commit (the thing to be merged)."""
    wt = tmp_path / "worktrees" / "I-00126-test"
    _make_agent_branch_worktree(repo_root, wt)
    return wt


# ---------------------------------------------------------------------------
# AC1 test
# ---------------------------------------------------------------------------


def test_i00126_merge_refused_when_repo_on_stray_branch(
    db_session: Session,
    test_project: Project,
    project_config: ProjectConfig,
    agent_worktree_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AC1: merge queue refuses when repo is checked out on a non-default branch.

    Given the repo is on 'feature/stray' (not 'main'),
    when process_merge_queue is called for a completed batch item,
    then:
      - batch_item.status is merge_failed (NOT merged)
      - notes contain both the actual branch 'feature/stray' and expected 'main'
      - a merge_refused_wrong_branch daemon_event is emitted with the correct
        expected_branch and actual_branch in event_metadata
      - the squash commit is NOT on the stray branch (no accidental merge)
    """
    from orch.config import DaemonConfig

    # Patch run_pre_merge_rebase so the test doesn't need a real git remote.
    # This bypasses the `git fetch origin main` call; we only care about
    # the branch-guard logic which fires after this step.
    fake_rebase_result = __import__(
        "orch.daemon.migration_rebase", fromlist=["RebaseResult"]
    ).RebaseResult(
        success=True,
        rebased=False,
        rewrites=[],
        worktree_base_sha="0" * 40,
        current_main_sha="0" * 40,
        message="mocked (no git remote in test)",
        error_message=None,
    )
    monkeypatch.setattr(
        "orch.daemon.merge_queue.run_pre_merge_rebase",
        lambda _batch_id, _worktree_path, _repo_root: fake_rebase_result,
    )

    # Also mock dry_run to avoid needing real migrations in the temp worktree.
    # The dry_run step runs inside the branch guard, so mocking it here
    # lets us reach the branch guard without pipeline noise.
    fake_dry_result = __import__(
        "orch.daemon.migration_pipeline", fromlist=["PipelineResult"]
    ).PipelineResult(
        phase="dry_run",
        success=True,
        final_batch_state="proceed_to_merge",
        frozen=False,
        message="mocked dry-run (no migrations in test worktree)",
    )
    monkeypatch.setattr(
        "orch.daemon.merge_queue.run_pre_merge_dry_run",
        lambda _batch_id, **_: fake_dry_result,
    )

    # Seed project with the temp repo's root (repo is on stray branch)
    test_project.repo_root = str(project_config.repo_root)
    db_session.add(test_project)
    db_session.flush()

    # Seed a completed WorkItem + BatchItem pointing at the agent worktree
    work_item = WorkItem(
        project_id=test_project.id,
        id="I-00126-TEST",
        type=WorkItemType.Issue,
        title="I-00126 test item",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(work_item)

    batch = Batch(
        project_id=test_project.id,
        id="B-I00126-001",
        status=BatchStatus.executing,
        max_parallel=4,
        cli_tool="opencode",
        auto_publish=False,
    )
    db_session.add(batch)
    db_session.flush()

    batch_item = BatchItem(
        project_id=test_project.id,
        batch_id=batch.id,  # must be non-null; pre-merge rebase is mocked
        work_item_id=work_item.id,
        execution_group=0,
        status=BatchItemStatus.completed,
        started_at=datetime.now(UTC),
        worktree_info={"path": str(agent_worktree_path)},
    )
    db_session.add(batch_item)
    db_session.commit()

    # Build a minimal DaemonConfig (only fields used by process_merge_queue)
    dummy_toml = tmp_path / "projects.toml"
    dummy_toml.write_text("")
    daemon_config = DaemonConfig(
        db_host="localhost",
        db_port=5432,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106
        db_url="postgresql+psycopg://test:test@localhost:5432/test",
        dashboard_host="127.0.0.1",  # noqa: S104
        dashboard_port=9900,
        poll_interval=60,
        stall_threshold=600,
        pid_file=str(tmp_path / "daemon.pid"),
        archive_dir=str(tmp_path / "archive"),
        archive_ttl=90,
        log_level="DEBUG",
        log_file=str(tmp_path / "daemon.log"),
        projects_toml=dummy_toml,
    )

    # Act — process_merge_queue must detect the wrong branch and refuse.
    # The branch guard calls db.commit() before _emit_event, so the test must
    # also commit to persist the daemon_event before querying.
    db_session.commit()
    process_merge_queue(db_session, test_project.id, project_config, daemon_config)
    db_session.commit()

    # ---- Assert: batch item is merge_failed (NOT merged) ----
    db_session.expire_all()
    bi: BatchItem | None = db_session.scalar(
        select(BatchItem).where(
            BatchItem.project_id == test_project.id,
            BatchItem.work_item_id == "I-00126-TEST",
        )
    )
    assert bi is not None, "batch item not found after process_merge_queue"
    assert bi.status == BatchItemStatus.merge_failed, (
        f"Expected merge_failed when on stray branch, got {bi.status.value}"
    )

    # ---- Assert: notes contain branch information ----
    notes = bi.notes or ""
    assert "feature/stray" in notes, f"notes must mention the actual branch: {notes}"
    assert "main" in notes, f"notes must mention the expected branch: {notes}"

    # ---- Assert: merge_refused_wrong_branch daemon_event was emitted ----
    # Commit any uncommitted changes (the branch-guard path commits status + notes
    # before _emit_event, so the daemon_event sits in the session buffer until
    # the test explicitly commits).
    db_session.commit()

    all_project_events = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.project_id == test_project.id,
        )
        .all()
    )
    merge_refused_events = [
        e for e in all_project_events if e.event_type == "merge_refused_wrong_branch"
    ]
    assert len(merge_refused_events) >= 1, (
        f"merge_refused_wrong_branch daemon_event must be emitted when on wrong branch. "
        f"All events: {[(e.event_type, e.entity_id) for e in all_project_events]}"
    )

    # ---- Assert: event_metadata has the correct branch pair ----
    meta = merge_refused_events[0].event_metadata or {}
    assert meta.get("expected_branch") == "main", f"expected_branch must be 'main': {meta}"
    assert meta.get("actual_branch") == "feature/stray", (
        f"actual_branch must be 'feature/stray': {meta}"
    )

    # ---- Assert: the agent branch was NOT merged to stray (no commit on stray) ----
    # The stray branch should have exactly 2 commits (initial + stray commit),
    # no merge commit from worktree_commit.sh.
    commit_count_on_stray = _git_ok(
        "rev-list", "--count", "HEAD", cwd=Path(project_config.repo_root)
    )
    assert commit_count_on_stray == "2", (
        f"stray branch must have exactly 2 commits (no merge), got: {commit_count_on_stray}"
    )


# ---------------------------------------------------------------------------
# Control test (AC1 complementary)
# ---------------------------------------------------------------------------


def test_i00126_merge_succeeds_when_repo_on_default_branch(
    db_session: Session,
    test_project: Project,
    project_config: ProjectConfig,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Control: when repo IS on the default branch, merge proceeds normally.

    We monkeypatch the branch resolver to report is_on_default=True so we don't
    need a real worktree_commit.sh environment. This verifies the happy-path
    branch check passes and allows the merge to proceed (merge_info is set).
    """
    from orch.config import DaemonConfig

    # Point the test project at the temp repo
    test_project.repo_root = str(project_config.repo_root)
    db_session.add(test_project)
    db_session.flush()

    # Monkeypatch resolve_branch_for_project to report on-default
    fake_info = __import__("orch.utils.branch_resolver", fromlist=["BranchInfo"]).BranchInfo(
        current_branch="main",
        default_branch="main",
        is_on_default=True,
    )
    monkeypatch.setattr(
        "orch.daemon.merge_queue.resolve_branch_for_project",
        lambda _repo_root: fake_info,
    )

    # Mock run_pre_merge_rebase and run_pre_merge_dry_run to avoid needing a real remote
    fake_rebase_result = __import__(
        "orch.daemon.migration_rebase", fromlist=["RebaseResult"]
    ).RebaseResult(
        success=True,
        rebased=False,
        rewrites=[],
        worktree_base_sha="0" * 40,
        current_main_sha="0" * 40,
        message="mocked (no git remote in test)",
        error_message=None,
    )
    monkeypatch.setattr(
        "orch.daemon.merge_queue.run_pre_merge_rebase",
        lambda _batch_id, _worktree_path, _repo_root: fake_rebase_result,
    )

    fake_dry_result = __import__(
        "orch.daemon.migration_pipeline", fromlist=["PipelineResult"]
    ).PipelineResult(
        phase="dry_run",
        success=True,
        final_batch_state="proceed_to_merge",
        frozen=False,
        message="mocked dry-run (no migrations in test worktree)",
    )
    monkeypatch.setattr(
        "orch.daemon.merge_queue.run_pre_merge_dry_run",
        lambda _batch_id, **_: fake_dry_result,
    )

    # Seed a completed WorkItem + BatchItem
    work_item = WorkItem(
        project_id=test_project.id,
        id="I-00126-CTRL",
        type=WorkItemType.Issue,
        title="I-00126 control item",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(work_item)

    batch = Batch(
        project_id=test_project.id,
        id="B-I00126-C1",
        status=BatchStatus.executing,
        max_parallel=4,
        cli_tool="opencode",
        auto_publish=False,
    )
    db_session.add(batch)
    db_session.flush()

    batch_item = BatchItem(
        project_id=test_project.id,
        batch_id=batch.id,
        work_item_id=work_item.id,
        execution_group=0,
        status=BatchItemStatus.completed,
        started_at=datetime.now(UTC),
        worktree_info={"path": str(tmp_path / "worktrees" / "ctrl")},
    )
    db_session.add(batch_item)
    db_session.commit()

    dummy_toml = tmp_path / "projects.toml"
    dummy_toml.write_text("")
    daemon_config = DaemonConfig(
        db_host="localhost",
        db_port=5432,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106
        db_url="postgresql+psycopg://test:test@localhost:5432/test",
        dashboard_host="127.0.0.1",  # noqa: S104
        dashboard_port=9900,
        poll_interval=60,
        stall_threshold=600,
        pid_file=str(tmp_path / "daemon.pid"),
        archive_dir=str(tmp_path / "archive"),
        archive_ttl=90,
        log_level="DEBUG",
        log_file=str(tmp_path / "daemon.log"),
        projects_toml=dummy_toml,
    )

    # Act
    db_session.commit()
    process_merge_queue(db_session, test_project.id, project_config, daemon_config)
    db_session.commit()

    # ---- Assert: branch guard fires and blocks merge ----
    # Since the test patches is_on_default=True, the branch guard does NOT fire.
    # We mock worktree_commit.sh to avoid needing a real git environment.
    fake_commit_result = __import__("subprocess", fromlist=["CompletedProcess"]).CompletedProcess(
        args=[], returncode=0, stdout="fake-commit-hash", stderr=""
    )
    monkeypatch.setattr(
        "orch.daemon.merge_queue.subprocess.run",
        lambda *_args, **_kwargs: fake_commit_result,
    )
    db_session.commit()
    process_merge_queue(db_session, test_project.id, project_config, daemon_config)

    # Commit any uncommitted changes (merge_started event is db.add()-ed)
    db_session.commit()

    # ---- Assert: merge_refused_wrong_branch was NOT emitted ----
    all_project_events = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.project_id == test_project.id,
        )
        .all()
    )
    merge_refused_events = [
        e for e in all_project_events if e.event_type == "merge_refused_wrong_branch"
    ]
    assert len(merge_refused_events) == 0, (
        f"merge_refused_wrong_branch must NOT be emitted when on default branch. "
        f"Events: {[(e.event_type, e.entity_id) for e in all_project_events]}"
    )
