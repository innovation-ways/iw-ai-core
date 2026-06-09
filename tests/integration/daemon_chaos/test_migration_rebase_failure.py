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
    """Provide a fully-seeded migration rebase failure scenario context.

    Creates a fake worktree with a conflicting Alembic revision file, a
    completed WorkItem with a Batch and BatchItem in the test DB, and a
    ProjectConfig pointing at the temporary repo root.

    Yields:
        dict: Context with keys ``item_id``, ``repo_root``, ``worktree_path``,
            ``throwaway_revision``, and ``project_config``.
    """
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
        # This exercises the orch-DB pre-merge rebase, which only runs for the
        # orch-DB-owning project — opt this synthetic project in (see I-00131).
        owns_orch_db=True,
    )

    return {
        "item_id": item_id,
        "repo_root": repo_root,
        "worktree_path": worktree_path,
        "throwaway_revision": throwaway_revision,
        "project_config": project_config,
    }


def _current_alembic_version(db_session) -> str | None:
    """Query the current Alembic version from the test DB.

    Args:
        db_session: The SQLAlchemy session for the testcontainer DB.

    Returns:
        The current ``version_num`` string, or None if the table is empty.
    """
    row = db_session.execute(text("SELECT version_num FROM alembic_version")).fetchone()
    return row[0] if row else None


def _run_rebase_failure(db_session, chaos_daemon, migration_rebase_ctx):
    """Execute a simulated migration rebase failure and return the updated BatchItem.

    Args:
        db_session: The SQLAlchemy session for the testcontainer DB.
        chaos_daemon: The ChaosDaemonHarness instance with the rebase failure hook armed.
        migration_rebase_ctx: Fixture context dict from ``migration_rebase_ctx``.

    Returns:
        The refreshed BatchItem after _merge_item has processed the failed rebase.
    """
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
    """Verifies that a failed rebase does not alter the Alembic version in the database."""
    before = _current_alembic_version(db_session)
    _run_rebase_failure(db_session, chaos_daemon, migration_rebase_ctx)
    after = _current_alembic_version(db_session)

    assert before == after


@pytest.mark.integration
def test_migration_rebase_failure_is_detected(
    db_session, test_project, chaos_daemon, migration_rebase_ctx, caplog
):
    """Verifies that a RebaseChainError is logged and the BatchItem is marked
    migration_rebase_failed.
    """
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
    """Verifies that both BatchItem and WorkItem are marked failed after a rebase failure."""
    batch_item = _run_rebase_failure(db_session, chaos_daemon, migration_rebase_ctx)
    work_item = db_session.get(WorkItem, ("test-proj", migration_rebase_ctx["item_id"]))

    assert batch_item.status == BatchItemStatus.migration_rebase_failed
    assert work_item is not None
    assert work_item.status == WorkItemStatus.failed


@pytest.mark.integration
def test_worktree_directory_preserved_for_inspection(
    db_session, test_project, chaos_daemon, migration_rebase_ctx
):
    """Verifies that the worktree directory is left intact after a rebase failure for operator
    inspection.
    """
    _run_rebase_failure(db_session, chaos_daemon, migration_rebase_ctx)

    worktree_path = migration_rebase_ctx["worktree_path"]
    assert worktree_path.exists()


@pytest.mark.integration
def test_no_alembic_revision_skips_scenario(tmp_path):
    """Verifies that the test is skipped when no new Alembic revision file exists in the."""
    worktree_path = tmp_path / "repo" / ".worktrees" / "I-NO-REV"
    revisions = list((worktree_path / "orch" / "db" / "migrations" / "versions").glob("*.py"))
    assert revisions == []
    pytest.skip("no rebase to fail: worktree carries no new alembic revision file")


@pytest.mark.integration
def test_throwaway_revision_written_outside_host_repo(
    migration_rebase_ctx,
):
    """Verifies that the throwaway revision file is written inside tmp_path and not the host."""
    throwaway_revision = migration_rebase_ctx["throwaway_revision"].resolve()
    host_versions = (Path.cwd() / "orch" / "db" / "migrations" / "versions").resolve()

    assert throwaway_revision.exists()
    assert host_versions not in throwaway_revision.parents
