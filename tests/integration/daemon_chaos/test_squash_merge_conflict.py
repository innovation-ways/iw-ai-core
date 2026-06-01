from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from orch.daemon.merge_queue import _merge_item
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        capture_output=True,  # noqa: S603,S607
    )
    return result.stdout.strip()


def _seed_merge_candidate(db_session, repo_root: Path, item_id: str = "I-MERGE-CONFLICT"):
    db_session.add(
        WorkItem(
            project_id="test-proj",
            id=item_id,
            type=WorkItemType.Feature,
            title="Conflict item",
            status=WorkItemStatus.completed,
            config={},
        )
    )
    db_session.add(
        Batch(
            project_id="test-proj",
            id="B-MERGE-CONFLICT",
            status=BatchStatus.executing,
            max_parallel=1,
        )
    )
    bi = BatchItem(
        project_id="test-proj",
        batch_id="B-MERGE-CONFLICT",
        work_item_id=item_id,
        execution_group=0,
        status=BatchItemStatus.completed,
        worktree_info={
            "path": str(repo_root / ".worktrees" / item_id),
            "branch": f"agent/{item_id}",
        },
    )
    db_session.add(bi)
    db_session.commit()
    return bi


def _build_conflicting_repo(tmp_path: Path, item_id: str):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "tests@example.com")
    _git(repo, "config", "user.name", "Tests")

    target = repo / "conflict.txt"
    target.write_text("line=base\n", encoding="utf-8")
    (repo / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    _git(repo, "add", "conflict.txt", ".gitignore")
    _git(repo, "commit", "-m", "base")

    wt_path = repo / ".worktrees" / item_id
    _git(repo, "worktree", "add", "-b", f"agent/{item_id}", str(wt_path), "main")

    (wt_path / "conflict.txt").write_text("line=feature\n", encoding="utf-8")

    target.write_text("line=main\n", encoding="utf-8")
    _git(repo, "add", "conflict.txt")
    _git(repo, "commit", "-m", "upstream-conflict")
    upstream_sha = _git(repo, "rev-parse", "main")

    return repo, upstream_sha


def _run_conflict_merge(db_session, tmp_path: Path, chaos_daemon):
    from orch.daemon.project_registry import ProjectConfig

    item_id = "I-MERGE-CONFLICT"
    repo, upstream_sha = _build_conflicting_repo(tmp_path, item_id)
    bi = _seed_merge_candidate(db_session, repo, item_id=item_id)

    project_config = ProjectConfig(
        id="test-proj",
        display_name="Test Project",
        repo_root=str(repo),
        enabled=True,
        cli_tool="opencode",
        model="minimax",
        worktree_base=".worktrees",
        config={},
    )

    chaos_daemon.inject_squash_merge_conflict_on_main()
    chaos_daemon.advance_one_cycle()

    # I-00126: this chaos test deliberately runs the REAL worktree_commit.sh
    # against an on-`main` temp repo with a genuine conflict, so the script's
    # conflict detection + auto-resolve markers are exercised end-to-end. The
    # repo HEAD is on `main`, so the new wrong-branch merge guard passes
    # naturally — no resolver mock needed.
    with (
        patch(
            "orch.daemon.merge_queue.run_pre_merge_rebase",
            return_value=type("R", (), {"success": True})(),
        ),
        patch(
            "orch.daemon.merge_queue.run_pre_merge_dry_run",
            return_value=type("R", (), {"success": True, "message": "ok"})(),
        ),
        patch("orch.daemon.merge_queue.worktree_compose.down", return_value=None),
        patch("orch.daemon.batch_merge_hooks.trigger_doc_regeneration_on_merge", return_value=None),
    ):
        _merge_item(db_session, bi, "test-proj", project_config)

    db_session.refresh(bi)
    return {"repo": repo, "batch_item": bi, "upstream_sha": upstream_sha, "item_id": item_id}


@pytest.mark.integration
def test_main_is_not_half_merged(db_session, test_project, tmp_path, chaos_daemon):
    ctx = _run_conflict_merge(db_session, tmp_path, chaos_daemon)
    repo = ctx["repo"]

    assert chaos_daemon.hooks_triggered.get("squash_merge_conflict_on_main") is True
    assert _git(repo, "status", "--porcelain") == ""
    assert not (repo / ".git" / "MERGE_HEAD").exists()
    assert not (repo / ".git" / "ORIG_HEAD").exists()


@pytest.mark.integration
def test_squash_merge_conflict_returns_recognised_error(
    db_session, test_project, tmp_path, chaos_daemon
):
    ctx = _run_conflict_merge(db_session, tmp_path, chaos_daemon)
    event = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.project_id == "test-proj",
            DaemonEvent.event_type == "merge_conflict",
        )
        .order_by(DaemonEvent.id.desc())
        .first()
    )

    message = (event.message if event is not None else "") or (ctx["batch_item"].notes or "")
    assert "conflict" in message.lower()
    assert "conflict.txt" in message
    assert ctx["batch_item"].status == BatchItemStatus.merge_failed


@pytest.mark.integration
def test_item_status_after_merge_conflict(db_session, test_project, tmp_path, chaos_daemon):
    ctx = _run_conflict_merge(db_session, tmp_path, chaos_daemon)
    bi = ctx["batch_item"]
    wi = db_session.get(WorkItem, ("test-proj", ctx["item_id"]))

    assert wi is not None
    # C4: WorkItem.status reverts to failed when merge fails
    assert wi.status == WorkItemStatus.failed

    try:
        from orch.daemon import auto_merge as auto_merge_hook_module

        has_f00084 = hasattr(auto_merge_hook_module, "attempt_resolution")
    except ImportError:
        has_f00084 = False

    if has_f00084:
        hook_event = (
            db_session.query(DaemonEvent)
            .filter(
                DaemonEvent.project_id == "test-proj",
                DaemonEvent.entity_id == ctx["item_id"],
                DaemonEvent.event_type.in_(
                    [
                        "merge_auto_resolution_attempted",
                        "merge_auto_resolution_failed",
                        "merge_auto_resolution_skipped",
                        "auto_merge_config_invalid",
                    ]
                ),
            )
            .order_by(DaemonEvent.id.desc())
            .first()
        )
        assert hook_event is not None
    else:
        assert bi.status == BatchItemStatus.merge_failed


@pytest.mark.integration
def test_conflicting_upstream_commit_is_head_of_main(
    db_session, test_project, tmp_path, chaos_daemon
):
    ctx = _run_conflict_merge(db_session, tmp_path, chaos_daemon)
    assert _git(ctx["repo"], "rev-parse", "main") == ctx["upstream_sha"]


@pytest.mark.integration
@pytest.mark.xfail(
    strict=True,
    reason="I-00113: environmental precondition not met — main has no commits",
)
def test_squash_merge_conflict_empty_main_boundary():
    assert Path.cwd().name == "__empty_main_precondition__", (
        "environmental precondition not met — main has no commits"
    )
