"""Scenario 5 mirrors I-00075 / I-00076 migration-rebase failure mode."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import text

from orch.daemon.migration_rebase import RebaseResult
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)


@pytest.fixture
def migration_rebase_ctx(db_session, tmp_path, chaos_daemon):
    from orch.daemon.project_registry import ProjectConfig

    item_id = "I-MIGRATION-REBASE-FAIL"
    repo_root = tmp_path / "repo"
    worktree_path = repo_root / ".worktrees" / item_id
    versions_dir = worktree_path / "orch" / "db" / "migrations" / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)

    throwaway_revision = versions_dir / "zzz_throwaway_conflict.py"
    throwaway_revision.write_text(
        '"""throwaway"""\n'
        "revision = 'zzz_throwaway_conflict'\n"
        "down_revision = 'bogus_parent_revision'\n\n"
        "def upgrade() -> None:\n"
        "    pass\n\n"
        "def downgrade() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )

    db_session.add(
        WorkItem(
            project_id="test-proj",
            id=item_id,
            type=WorkItemType.Feature,
            title="Migration rebase fail",
            status=WorkItemStatus.completed,
            config={},
        )
    )
    db_session.add(
        Batch(
            project_id="test-proj",
            id="B-MIGRATION-REBASE-FAIL",
            status=BatchStatus.executing,
            max_parallel=1,
        )
    )
    db_session.add(
        BatchItem(
            project_id="test-proj",
            batch_id="B-MIGRATION-REBASE-FAIL",
            work_item_id=item_id,
            execution_group=0,
            status=BatchItemStatus.completed,
            worktree_info={"path": str(worktree_path), "branch": f"agent/{item_id}"},
        )
    )
    db_session.commit()

    project_config = ProjectConfig(
        id="test-proj",
        display_name="Test Project",
        repo_root=str(repo_root),
        enabled=True,
        cli_tool="opencode",
        model="minimax",
        worktree_base=".worktrees",
        config={},
    )

    return {
        "item_id": item_id,
        "repo_root": repo_root,
        "worktree_path": worktree_path,
        "throwaway_revision": throwaway_revision,
        "project_config": project_config,
    }


def _current_alembic_version(db_session) -> str | None:
    row = db_session.execute(text("SELECT version_num FROM alembic_version")).fetchone()
    return row[0] if row else None


def _run_rebase_failure(db_session, chaos_daemon, migration_rebase_ctx):
    from orch.daemon.merge_queue import _merge_item

    chaos_daemon.inject_migration_rebase_conflict_revision()
    chaos_daemon.advance_one_cycle()

    batch_item = (
        db_session.query(BatchItem)
        .filter(
            BatchItem.project_id == "test-proj",
            BatchItem.batch_id == "B-MIGRATION-REBASE-FAIL",
            BatchItem.work_item_id == migration_rebase_ctx["item_id"],
        )
        .one()
    )

    failed_rebase = RebaseResult(
        success=False,
        rebased=False,
        rewrites=[],
        worktree_base_sha="oldsha",
        current_main_sha="newsha",
        message="Rebase failed and aborted",
        error_message=(
            "Traceback (most recent call last):\n"
            "  File 'migration_rebase.py', line 1, in run_pre_merge_rebase\n"
            "RebaseChainError: conflicting down_revision in throwaway migration"
        ),
    )

    with (
        patch("orch.daemon.merge_queue.run_pre_merge_rebase", return_value=failed_rebase),
        patch("orch.daemon.merge_queue.worktree_compose.down", return_value=None),
    ):
        _merge_item(db_session, batch_item, "test-proj", migration_rebase_ctx["project_config"])

    db_session.refresh(batch_item)
    return batch_item


@pytest.mark.integration
def test_alembic_version_unchanged_after_failed_rebase(
    db_session, test_project, chaos_daemon, migration_rebase_ctx
):
    before = _current_alembic_version(db_session)
    _run_rebase_failure(db_session, chaos_daemon, migration_rebase_ctx)
    after = _current_alembic_version(db_session)

    assert before == after


@pytest.mark.integration
def test_migration_rebase_failure_is_detected(
    db_session, test_project, chaos_daemon, migration_rebase_ctx, caplog
):
    batch_item = _run_rebase_failure(db_session, chaos_daemon, migration_rebase_ctx)

    log_text = "\n".join(record.getMessage() for record in caplog.records)
    assert "Pre-merge rebase failed" in log_text
    assert "Traceback" in log_text
    assert "RebaseChainError" in log_text
    assert batch_item.status == BatchItemStatus.migration_rebase_failed


@pytest.mark.integration
def test_item_marked_migration_rebase_failed(
    db_session, test_project, chaos_daemon, migration_rebase_ctx
):
    batch_item = _run_rebase_failure(db_session, chaos_daemon, migration_rebase_ctx)
    work_item = db_session.get(WorkItem, ("test-proj", migration_rebase_ctx["item_id"]))

    assert batch_item.status == BatchItemStatus.migration_rebase_failed
    assert work_item is not None
    assert work_item.status == WorkItemStatus.failed


@pytest.mark.integration
def test_worktree_directory_preserved_for_inspection(
    db_session, test_project, chaos_daemon, migration_rebase_ctx
):
    _run_rebase_failure(db_session, chaos_daemon, migration_rebase_ctx)

    worktree_path = migration_rebase_ctx["worktree_path"]
    assert worktree_path.exists()


@pytest.mark.integration
def test_no_alembic_revision_skips_scenario(tmp_path):
    worktree_path = tmp_path / "repo" / ".worktrees" / "I-NO-REV"
    revisions = list((worktree_path / "orch" / "db" / "migrations" / "versions").glob("*.py"))
    assert revisions == []
    pytest.skip("no rebase to fail: worktree carries no new alembic revision file")


@pytest.mark.integration
def test_throwaway_revision_written_outside_host_repo(
    migration_rebase_ctx,
):
    throwaway_revision = migration_rebase_ctx["throwaway_revision"].resolve()
    host_versions = (Path.cwd() / "orch" / "db" / "migrations" / "versions").resolve()

    assert throwaway_revision.exists()
    assert host_versions not in throwaway_revision.parents
