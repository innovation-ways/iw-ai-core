"""Integration tests for I-00062 — _launch_step env injection.

Exercises the full _launch_step path with a fake BatchItem that has all
four worktree_db_* columns populated, and asserts the spawned subprocess
sees IW_CORE_DB_PORT=<worktree-port> (not 5433).

The test patches subprocess.Popen so no real process is spawned. We capture
the env= argument and verify it contains the per-worktree DB values.

Uses a PostgreSQL testcontainer (via db_engine fixture) because the ORM
models use JSONB which SQLite does not support.

AC1: compose-stack path injects all five per-worktree DB vars
AC2: missing creds raises RuntimeError (not silent fallback)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from orch.daemon.batch_manager import (
    Batch,
    BatchItem,
    BatchItemStatus,
    StepType,
    WorkflowStep,
)
from orch.db.models import BatchStatus, WorkItem, WorkItemStatus


class TestLaunchStepInjectsWorktreeDBEnv:
    """I-00062 AC1: when a worktree has a compose stack, _launch_step
    must inject the per-worktree DB env vars from worktree_info, not
    leave them resolving to the daemon's 5433."""

    def test_compose_stack_injects_all_five_db_vars(
        self,
        monkeypatch: pytest.MonkeyPatch,
        db_session,
        test_project,
    ) -> None:
        """Canonical proof of AC1: the agent env has the per-worktree DB vars,
        not the daemon's 5433 values.

        Pre-fix: env["IW_CORE_DB_PORT"] == "5433" (leaked from daemon env).
        Post-fix: env["IW_CORE_DB_PORT"] == "36216" (from BatchItem columns).
        """
        # BatchItem requires a Batch row first (FK constraint)
        batch = Batch(
            project_id=test_project.id,
            id="I-00062-BATCH-00001",
            status=BatchStatus.planning,
        )
        db_session.add(batch)
        db_session.flush()

        # BatchItem also requires a WorkItem row (FK constraint)
        work_item = WorkItem(
            project_id=test_project.id,
            id="I-00062",
            type="Feature",
            title="I-00062 Test WorkItem",
            status=WorkItemStatus.approved,
            phase="active",
            design_doc_content="{}",
        )
        db_session.add(work_item)
        db_session.flush()

        item = BatchItem(
            project_id=test_project.id,
            batch_id="I-00062-BATCH-00001",
            work_item_id="I-00062",
            status=BatchItemStatus.executing,
            execution_group=1,
            worktree_compose_path="/tmp/worktree-i00062/ai-dev/iw-config/docker-compose.yml",
            worktree_info={"path": "/tmp/worktree-i00062"},
            # All four per-worktree DB credentials populated
            worktree_db_host="worktree-db-host",
            worktree_db_port=36216,
            worktree_db_name="iw_orch_worktree",
            worktree_db_user="worktree_user",
            worktree_db_password="worktree_password",  # noqa: S106
        )
        db_session.add(item)
        db_session.flush()

        step = WorkflowStep(
            project_id=test_project.id,
            work_item_id="I-00062",
            step_id="S01",
            step_number=1,
            agent_label="Implementation",
            step_type=StepType.implementation,
            status="pending",
        )
        db_session.add(step)
        db_session.commit()

        # Simulate daemon's env: IW_CORE_DB_PORT=5433 would be inherited
        # from the daemon process, but the fix strips it before injection.
        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_DB_HOST", "daemon-host")
        monkeypatch.setenv("IW_CORE_DB_NAME", "daemon_db")
        monkeypatch.setenv("IW_CORE_DB_USER", "daemon_user")
        monkeypatch.setenv("IW_CORE_DB_PASSWORD", "daemon_password")  # noqa: S106
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")

        # Patch subprocess.Popen to capture the env= argument
        captured_env: dict[str, str] = {}

        def fake_popen(*args: object, **kwargs: object) -> MagicMock:  # type: ignore[arg-type]
            env_dict = kwargs.get("env")
            if env_dict:
                captured_env.update(env_dict)
            proc = MagicMock()
            proc.pid = 12345
            return proc

        with (
            patch("subprocess.Popen", fake_popen),
            patch("orch.daemon.batch_manager._next_run_number", return_value=1),
        ):
            from orch.daemon.batch_manager import BatchManager

            bm = BatchManager.__new__(BatchManager)
            bm.project_id = test_project.id

            class FakeProjectConfig:
                cli_tool = "claude"
                repo_root = "/tmp/test-repo"
                config = {}

            bm.project_config = FakeProjectConfig()  # type: ignore[assignment]

            worktree_info = {
                "path": "/tmp/worktree-i00062",
                "batch_item_id": item.id,
                "worktree_compose_path": item.worktree_compose_path,
                "worktree_db_host": "worktree-db-host",
                "worktree_db_port": 36216,
                "worktree_db_name": "iw_orch_worktree",
                "worktree_db_user": "worktree_user",
                "worktree_db_password": "worktree_password",  # noqa: S106
            }

            fetched_step = (
                db_session.query(WorkflowStep).filter_by(project_id=test_project.id).first()
            )
            bm._launch_step(db_session, fetched_step, worktree_info)

        # AC1 assertions — ALL FIVE DB vars must be per-worktree, not daemon's
        assert captured_env.get("IW_CORE_DB_HOST") == "worktree-db-host", (
            f"Expected worktree-db-host, got {captured_env.get('IW_CORE_DB_HOST')}"
        )
        assert captured_env.get("IW_CORE_DB_PORT") == "36216", (
            f"Expected 36216 (per-worktree), not 5433 (daemon's orch). "
            f"Full DB vars: { {k: v for k, v in captured_env.items() if 'DB' in k} }"
        )
        assert captured_env.get("IW_CORE_DB_NAME") == "iw_orch_worktree"
        assert captured_env.get("IW_CORE_DB_USER") == "worktree_user"
        assert captured_env.get("IW_CORE_DB_PASSWORD") == "worktree_password"
        # IW_CORE_AGENT_CONTEXT must still be armed
        assert captured_env.get("IW_CORE_AGENT_CONTEXT") == "true"
        # IW_CORE_ORCH_DB_* must still be present (snapshot from Layer 1)
        assert captured_env.get("IW_CORE_ORCH_DB_PORT") == "5433"

    def test_missing_creds_raises_on_compose_stack(
        self,
        monkeypatch: pytest.MonkeyPatch,
        db_session,
        test_project,
    ) -> None:
        """Defensive: if compose_path is set but a credential is None/empty,
        _launch_step must raise RuntimeError naming I-00062 — never fall
        back to inherited env.

        Pre-fix: silently uses inherited daemon env (no guard in _launch_step).
        Post-fix: RuntimeError raised with I-00062 in the message.
        """
        batch = Batch(
            project_id=test_project.id,
            id="I-00062-BATCH-00002",
            status=BatchStatus.planning,
        )
        db_session.add(batch)
        db_session.flush()

        work_item = WorkItem(
            project_id=test_project.id,
            id="I-00062",
            type="Feature",
            title="I-00062 Test WorkItem",
            status=WorkItemStatus.approved,
            phase="active",
            design_doc_content="{}",
        )
        db_session.add(work_item)
        db_session.flush()

        item = BatchItem(
            project_id=test_project.id,
            batch_id="I-00062-BATCH-00002",
            work_item_id="I-00062",
            status=BatchItemStatus.executing,
            execution_group=1,
            worktree_compose_path="/tmp/worktree-i00062/ai-dev/iw-config/docker-compose.yml",
            worktree_info={"path": "/tmp/worktree-i00062"},
            worktree_db_host="worktree-db-host",
            worktree_db_port=36216,
            worktree_db_name="iw_orch_worktree",
            worktree_db_user="worktree_user",
            worktree_db_password="",  # empty — incomplete creds
        )
        db_session.add(item)
        db_session.flush()

        step = WorkflowStep(
            project_id=test_project.id,
            work_item_id="I-00062",
            step_id="S02",
            step_number=1,
            agent_label="Implementation",
            step_type=StepType.implementation,
            status="pending",
        )
        db_session.add(step)
        db_session.commit()

        monkeypatch.setenv("IW_CORE_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_ORCH_DB_PORT", "5433")
        monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")

        from orch.daemon.batch_manager import BatchManager

        bm = BatchManager.__new__(BatchManager)
        bm.project_id = test_project.id

        class FakeProjectConfig:
            cli_tool = "claude"
            repo_root = "/tmp/test-repo"
            config = {}

        bm.project_config = FakeProjectConfig()  # type: ignore[assignment]

        worktree_info = {
            "path": "/tmp/worktree-i00062",
            "batch_item_id": item.id,
            "worktree_compose_path": "/compose/path/docker-compose.yml",
            "worktree_db_host": "worktree-db-host",
            "worktree_db_port": 36216,
            "worktree_db_name": "iw_orch_worktree",
            "worktree_db_user": "worktree_user",
            "worktree_db_password": "",  # empty — incomplete creds
        }

        fetched_step = db_session.query(WorkflowStep).filter_by(project_id=test_project.id).first()

        with pytest.raises(RuntimeError, match="I-00062"):
            bm._launch_step(db_session, fetched_step, worktree_info)
