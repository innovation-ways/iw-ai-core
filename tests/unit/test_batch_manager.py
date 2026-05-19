"""Unit tests for batch_manager — no DB, no subprocess.

All database interaction and subprocess calls are mocked.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from orch.config import DaemonConfig

if TYPE_CHECKING:
    from pathlib import Path
from orch.daemon.batch_manager import (
    _BLOCKING_TERMINAL_STATUSES,
    BatchManager,
    WorktreeSetupError,
    _current_execution_group,
    _next_run_number,
)
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    RunStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def make_config(tmp_path: Path) -> DaemonConfig:
    projects_toml = tmp_path / "projects.toml"
    projects_toml.write_text("")
    return DaemonConfig(
        db_host="localhost",
        db_port=5433,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106
        db_url="postgresql+psycopg://test:test@localhost:5433/test",
        dashboard_host="0.0.0.0",  # noqa: S104
        dashboard_port=9900,
        poll_interval=60,
        stall_threshold=600,
        pid_file=str(tmp_path / "daemon.pid"),
        archive_dir=str(tmp_path / "archive"),
        archive_ttl=90,
        log_level="DEBUG",
        log_file=str(tmp_path / "daemon.log"),
        projects_toml=projects_toml,
    )


def make_project_config(cli_tool: str = "opencode") -> ProjectConfig:
    return ProjectConfig(
        id="test-proj",
        display_name="Test Project",
        repo_root="/repos/test",
        enabled=True,
        cli_tool=cli_tool,
        model="minimax",
        worktree_base=".worktrees",
        config={},
    )


def make_batch_item(
    work_item_id: str,
    execution_group: int = 0,
    status: BatchItemStatus = BatchItemStatus.pending,
    started_at: datetime | None = None,
    worktree_info: dict[str, Any] | None = None,
) -> MagicMock:
    item = MagicMock(spec=BatchItem)
    item.work_item_id = work_item_id
    item.execution_group = execution_group
    item.status = status
    item.started_at = started_at or datetime(2024, 1, 1, tzinfo=UTC)
    item.worktree_info = worktree_info or {}
    item.id = hash(work_item_id) % 1000
    return item


def make_manager(tmp_path: Path, db: MagicMock, cli_tool: str = "opencode") -> BatchManager:
    """Return a BatchManager whose session factory yields `db`."""

    @contextmanager
    def fake_factory():
        yield db

    return BatchManager(
        project_id="test-proj",
        project_config=make_project_config(cli_tool),
        session_factory=fake_factory,
        config=make_config(tmp_path),
    )


# ---------------------------------------------------------------------------
# _current_execution_group
# ---------------------------------------------------------------------------


class TestCurrentExecutionGroup:
    def test_all_pending_returns_group_0(self):
        items = [
            make_batch_item("F-00001", execution_group=0, status=BatchItemStatus.pending),
            make_batch_item("F-00002", execution_group=0, status=BatchItemStatus.pending),
        ]
        assert _current_execution_group(items) == 0

    def test_group_0_executing_returns_group_0(self):
        items = [
            make_batch_item("F-00001", execution_group=0, status=BatchItemStatus.executing),
            make_batch_item("F-00002", execution_group=1, status=BatchItemStatus.pending),
        ]
        assert _current_execution_group(items) == 0

    def test_group_0_merged_advances_to_group_1(self):
        items = [
            make_batch_item("F-00001", execution_group=0, status=BatchItemStatus.merged),
            make_batch_item("F-00002", execution_group=1, status=BatchItemStatus.pending),
        ]
        assert _current_execution_group(items) == 1

    def test_all_terminal_returns_none(self):
        items = [
            make_batch_item("F-00001", execution_group=0, status=BatchItemStatus.merged),
            make_batch_item("F-00002", execution_group=0, status=BatchItemStatus.failed),
            make_batch_item("F-00003", execution_group=1, status=BatchItemStatus.skipped),
        ]
        assert _current_execution_group(items) is None

    def test_completed_item_keeps_group_active(self):
        # 'completed' means waiting for merge — still non-terminal
        items = [
            make_batch_item("F-00001", execution_group=0, status=BatchItemStatus.completed),
            make_batch_item("F-00002", execution_group=1, status=BatchItemStatus.pending),
        ]
        assert _current_execution_group(items) == 0

    def test_merging_item_keeps_group_active(self):
        # 'merging' means squash-merge subprocess is running — dependent group must not launch yet
        items = [
            make_batch_item("F-00001", execution_group=0, status=BatchItemStatus.merging),
            make_batch_item("F-00002", execution_group=1, status=BatchItemStatus.pending),
        ]
        assert _current_execution_group(items) == 0

    def test_mixed_groups_returns_lowest_non_terminal(self):
        items = [
            make_batch_item("F-00001", execution_group=0, status=BatchItemStatus.merged),
            make_batch_item("F-00002", execution_group=1, status=BatchItemStatus.executing),
            make_batch_item("F-00003", execution_group=2, status=BatchItemStatus.pending),
        ]
        assert _current_execution_group(items) == 1

    def test_empty_returns_none(self):
        assert _current_execution_group([]) is None

    def test_merge_failed_item_keeps_group_active(self):
        # CR-00028: merge_failed is non-terminal — group stays open
        items = [
            make_batch_item("F-00001", execution_group=0, status=BatchItemStatus.merge_failed),
            make_batch_item("F-00002", execution_group=1, status=BatchItemStatus.pending),
        ]
        assert _current_execution_group(items) == 0

    def test_migration_invalid_item_keeps_group_active(self):
        # CR-00028: operator-recoverable — group stays open
        items = [
            make_batch_item("F-00001", execution_group=0, status=BatchItemStatus.migration_invalid),
            make_batch_item("F-00002", execution_group=1, status=BatchItemStatus.pending),
        ]
        assert _current_execution_group(items) == 0

    def test_migration_rebase_failed_item_keeps_group_active(self):
        # CR-00028: operator-recoverable — group stays open
        items = [
            make_batch_item(
                "F-00001",
                execution_group=0,
                status=BatchItemStatus.migration_rebase_failed,
            ),
            make_batch_item("F-00002", execution_group=1, status=BatchItemStatus.pending),
        ]
        assert _current_execution_group(items) == 0


# ---------------------------------------------------------------------------
# Parallelism limit
# ---------------------------------------------------------------------------


class TestParallelismLimit:
    def _make_db_with_items(self, items: list[MagicMock]) -> MagicMock:
        db = MagicMock()
        batch_query = MagicMock()
        batch_query.filter.return_value.order_by.return_value.all.return_value = items
        # Executing items check
        step_query = MagicMock()
        step_query.filter.return_value.first.return_value = None
        db.query.side_effect = lambda model: {
            BatchItem: batch_query,
            WorkflowStep: step_query,
        }.get(model, MagicMock())
        return db

    def test_respects_max_parallel(self, tmp_path):
        items = [
            make_batch_item("F-00001", execution_group=0, status=BatchItemStatus.pending),
            make_batch_item("F-00002", execution_group=0, status=BatchItemStatus.pending),
            make_batch_item("F-00003", execution_group=0, status=BatchItemStatus.pending),
        ]
        db = MagicMock()
        batch = MagicMock(spec=Batch)
        batch.id = "B001"
        batch.max_parallel = 2
        batch.status = BatchStatus.executing

        launched: list[str] = []

        def fake_launch(db_, item_):
            launched.append(item_.work_item_id)
            # Mark as executing so count increases
            item_.status = BatchItemStatus.executing

        manager = make_manager(tmp_path, db)
        manager._launch_item = fake_launch  # type: ignore[method-assign]

        # Wire db to return our items
        q = MagicMock()
        q.filter.return_value.order_by.return_value.all.return_value = items
        step_q = MagicMock()
        step_q.filter.return_value.first.return_value = None  # no active/failed steps
        # No pending steps → _check_executing_item → _complete_item (not _launch_step)
        step_q.filter.return_value.order_by.return_value.first.return_value = None
        work_item_q = MagicMock()
        work_item_q.join.return_value.filter.return_value.all.return_value = []
        db.query.side_effect = lambda model, *_args, **_kwargs: {
            BatchItem: q,
            WorkflowStep: step_q,
            WorkItem: work_item_q,
        }.get(model, MagicMock())

        manager._process_batch(db, batch)

        assert len(launched) == 2, f"Expected 2 launched, got {launched}"
        assert "F-00003" not in launched

    def test_already_executing_counts_against_limit(self, tmp_path):
        items = [
            make_batch_item("F-00001", execution_group=0, status=BatchItemStatus.executing),
            make_batch_item("F-00002", execution_group=0, status=BatchItemStatus.pending),
            make_batch_item("F-00003", execution_group=0, status=BatchItemStatus.pending),
        ]
        db = MagicMock()
        batch = MagicMock(spec=Batch)
        batch.id = "B001"
        batch.max_parallel = 2
        batch.status = BatchStatus.executing

        launched: list[str] = []

        def fake_launch(db_, item_):
            launched.append(item_.work_item_id)
            item_.status = BatchItemStatus.executing

        manager = make_manager(tmp_path, db)
        manager._launch_item = fake_launch  # type: ignore[method-assign]

        q = MagicMock()
        q.filter.return_value.order_by.return_value.all.return_value = items
        step_q = MagicMock()
        step_q.filter.return_value.first.return_value = None
        # No pending steps → _check_executing_item → _complete_item (not _launch_step)
        step_q.filter.return_value.order_by.return_value.first.return_value = None
        work_item_q = MagicMock()
        work_item_q.join.return_value.filter.return_value.all.return_value = []
        db.query.side_effect = lambda model, *_args, **_kwargs: {
            BatchItem: q,
            WorkflowStep: step_q,
            WorkItem: work_item_q,
        }.get(model, MagicMock())

        manager._process_batch(db, batch)

        # 1 already executing + 1 launched = 2 (limit)
        assert len(launched) == 1
        assert launched[0] == "F-00002"


# ---------------------------------------------------------------------------
# Batch completion detection
# ---------------------------------------------------------------------------


class TestCheckBatchCompletion:
    def test_all_merged_completes(self, tmp_path):
        db = MagicMock()
        batch = MagicMock(spec=Batch)
        batch.id = "B001"
        batch.status = BatchStatus.executing
        items = [
            make_batch_item("F-00001", status=BatchItemStatus.merged),
            make_batch_item("F-00002", status=BatchItemStatus.merged),
        ]
        manager = make_manager(tmp_path, db)
        manager._check_batch_completion(db, batch, items)
        assert batch.status == BatchStatus.completed

    def test_mixed_merged_failed_gives_completed_with_errors(self, tmp_path):
        db = MagicMock()
        batch = MagicMock(spec=Batch)
        batch.id = "B001"
        batch.status = BatchStatus.executing
        items = [
            make_batch_item("F-00001", status=BatchItemStatus.merged),
            make_batch_item("F-00002", status=BatchItemStatus.failed),
        ]
        manager = make_manager(tmp_path, db)
        manager._check_batch_completion(db, batch, items)
        assert batch.status == BatchStatus.completed_with_errors

    def test_all_skipped_gives_completed_with_errors(self, tmp_path):
        db = MagicMock()
        batch = MagicMock(spec=Batch)
        batch.id = "B001"
        batch.status = BatchStatus.executing
        items = [
            make_batch_item("F-00001", status=BatchItemStatus.skipped),
            make_batch_item("F-00002", status=BatchItemStatus.merged),
        ]
        manager = make_manager(tmp_path, db)
        manager._check_batch_completion(db, batch, items)
        assert batch.status == BatchStatus.completed_with_errors

    def test_not_done_if_still_executing(self, tmp_path):
        db = MagicMock()
        batch = MagicMock(spec=Batch)
        batch.id = "B001"
        batch.status = BatchStatus.executing
        items = [
            make_batch_item("F-00001", status=BatchItemStatus.merged),
            make_batch_item("F-00002", status=BatchItemStatus.executing),
        ]
        manager = make_manager(tmp_path, db)
        manager._check_batch_completion(db, batch, items)
        # Status should be unchanged
        assert batch.status == BatchStatus.executing


# ---------------------------------------------------------------------------
# Command building
# ---------------------------------------------------------------------------


class TestCommandBuilding:
    def test_opencode_command(self, tmp_path):
        db = MagicMock()
        step = MagicMock(spec=WorkflowStep)
        step.work_item_id = "F-00001"
        step.step_id = "S01"
        step.step_type = StepType.implementation
        step.id = 1
        step.started_at = None
        step.agent_runtime_option_id = None

        worktree_info = {"path": "/wt/F-00001"}

        with (
            patch("orch.daemon.batch_manager.subprocess.Popen") as mock_popen,
            patch("orch.agent_runtime.resolver.resolve_runtime") as mock_resolve,
            patch("pathlib.Path.open", MagicMock()),
            patch("pathlib.Path.mkdir"),
        ):
            mock_proc = MagicMock()
            mock_proc.pid = 12345
            mock_popen.return_value = mock_proc
            mock_option = MagicMock()
            mock_option.cli_tool = "opencode"
            mock_option.model = "minimax"
            mock_option.id = 1
            mock_resolve.return_value = mock_option
            manager = make_manager(tmp_path, db, cli_tool="opencode")
            db.query.return_value.filter.return_value.count.return_value = 0
            manager._launch_step(db, step, worktree_info)

        cmd = mock_popen.call_args[0][0]
        assert "opencode run" in cmd
        assert "F-00001" in cmd
        assert "S01" in cmd

    def test_claude_command(self, tmp_path):
        db = MagicMock()
        step = MagicMock(spec=WorkflowStep)
        step.work_item_id = "F-00002"
        step.step_id = "S02"
        step.step_type = StepType.code_review
        step.id = 2
        step.started_at = None
        step.agent_runtime_option_id = None

        worktree_info = {"path": "/wt/F-00002"}

        with (
            patch("orch.daemon.batch_manager.subprocess.Popen") as mock_popen,
            patch("orch.agent_runtime.resolver.resolve_runtime") as mock_resolve,
            patch("pathlib.Path.open", MagicMock()),
            patch("pathlib.Path.mkdir"),
        ):
            mock_proc = MagicMock()
            mock_proc.pid = 99999
            mock_popen.return_value = mock_proc
            mock_option = MagicMock()
            mock_option.cli_tool = "claude"
            mock_option.model = "claude-sonnet-4-6"
            mock_option.id = 4
            mock_resolve.return_value = mock_option
            manager = make_manager(tmp_path, db, cli_tool="claude")
            db.query.return_value.filter.return_value.count.return_value = 0
            manager._launch_step(db, step, worktree_info)

        cmd = mock_popen.call_args[0][0]
        assert "claude -p" in cmd
        assert "F-00002" in cmd
        assert "S02" in cmd


# ---------------------------------------------------------------------------
# Step launch records all fields
# ---------------------------------------------------------------------------


class TestStepLaunchFields:
    def test_step_run_records_pid_command_and_timeout(self, tmp_path):
        db = MagicMock()
        step = MagicMock(spec=WorkflowStep)
        step.work_item_id = "F-00003"
        step.step_id = "S01"
        step.step_type = StepType.implementation
        step.id = 3
        step.started_at = None
        step.agent_runtime_option_id = None

        worktree_info = {"path": "/wt/F-00003"}

        with (
            patch("orch.daemon.batch_manager.subprocess.Popen") as mock_popen,
            patch("orch.agent_runtime.resolver.resolve_runtime") as mock_resolve,
            patch("pathlib.Path.open", MagicMock()),
            patch("pathlib.Path.mkdir"),
        ):
            mock_proc = MagicMock()
            mock_proc.pid = 55555
            mock_popen.return_value = mock_proc
            mock_option = MagicMock()
            mock_option.cli_tool = "opencode"
            mock_option.model = "minimax"
            mock_option.id = 1
            mock_resolve.return_value = mock_option
            manager = make_manager(tmp_path, db, cli_tool="opencode")
            db.query.return_value.filter.return_value.count.return_value = 0
            manager._launch_step(db, step, worktree_info)

        # Verify StepRun was added with expected fields
        added_runs = [
            call.args[0] for call in db.add.call_args_list if hasattr(call.args[0], "pid")
        ]
        assert len(added_runs) == 1
        run = added_runs[0]
        assert run.pid == 55555
        assert run.status == RunStatus.running
        assert run.pid_alive is True
        assert run.cli_tool == "opencode"
        assert run.worktree_path == "/wt/F-00003"
        assert run.timeout_secs is not None
        assert run.started_at is not None
        assert run.last_heartbeat is not None
        assert "opencode run" in run.command
        assert run.log_file is not None

    def test_start_new_session_true(self, tmp_path):
        """Agents must be detached from the daemon's process group."""
        db = MagicMock()
        step = MagicMock(spec=WorkflowStep)
        step.work_item_id = "F-00004"
        step.step_id = "S01"
        step.step_type = StepType.implementation
        step.id = 4
        step.started_at = None

        with (
            patch("orch.daemon.batch_manager.subprocess.Popen") as mock_popen,
            patch("orch.agent_runtime.resolver.resolve_runtime") as mock_resolve,
            patch("pathlib.Path.open", MagicMock()),
            patch("pathlib.Path.mkdir"),
        ):
            # CR-00062: _build_initial_command raises on unknown cli_tool, so the
            # runtime resolver must return a concrete cli_tool string (not a MagicMock).
            mock_option = MagicMock()
            mock_option.cli_tool = "opencode"
            mock_option.model = "minimax/MiniMax-M2.7"
            mock_option.id = 1
            mock_resolve.return_value = mock_option
            mock_popen.return_value = MagicMock(pid=1)
            manager = make_manager(tmp_path, db)
            db.query.return_value.filter.return_value.count.return_value = 0
            manager._launch_step(db, step, {"path": "/wt/F-00004"})

        kwargs = mock_popen.call_args[1]
        assert kwargs.get("start_new_session") is True


# ---------------------------------------------------------------------------
# QV direct-exec (no LLM) for quality_validation steps
# ---------------------------------------------------------------------------


class TestQvDirectExec:
    """Quality-validation steps with a populated `step.command` are run via a
    self-contained bash wrapper — no LLM CLI is launched. Legacy QV steps
    (no `step.command`) still fall through to the LLM path.
    """

    def _make_qv_step(self, *, item_id: str, step_id: str, command: str | None) -> MagicMock:
        step = MagicMock(spec=WorkflowStep)
        step.work_item_id = item_id
        step.step_id = step_id
        step.step_type = StepType.quality_validation
        step.id = 42
        step.started_at = None
        step.command = command
        step.gate = "lint"
        step.agent_label = "QvGate"
        step.opencode_agent = "qv-gate"
        step.timeout_secs = 120
        return step

    def test_qv_step_with_command_runs_directly_without_llm(self, tmp_path):
        db = MagicMock()
        step = self._make_qv_step(item_id="F-00010", step_id="S06", command="make lint")
        worktree_info = {"path": str(tmp_path)}

        with patch("orch.daemon.batch_manager.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=4242)
            manager = make_manager(tmp_path, db, cli_tool="claude")
            db.query.return_value.filter.return_value.count.return_value = 0
            manager._launch_step(db, step, worktree_info)

        cmd = mock_popen.call_args[0][0]
        assert cmd.startswith("bash ")
        assert ".qv-wrap.sh" in cmd
        # No LLM in the launch command.
        assert "claude -p" not in cmd
        assert "opencode run" not in cmd

        # Wrapper + gate scripts are written under the worktree.
        wrap_script = tmp_path / ".tmp" / "F-00010_S06.qv-wrap.sh"
        gate_script = tmp_path / ".tmp" / "F-00010_S06.qv-gate.sh"
        assert wrap_script.exists()
        assert gate_script.exists()
        wrapper_text = wrap_script.read_text()
        assert "iw step-done" in wrapper_text
        assert "iw step-fail" in wrapper_text
        assert "QvGate Report" in wrapper_text
        assert gate_script.read_text().strip().endswith("make lint")

    def test_qv_step_records_bash_wrapper_in_step_run(self, tmp_path):
        """StepRun.command must reflect the bash wrapper, not an LLM invocation."""
        db = MagicMock()
        step = self._make_qv_step(item_id="F-00011", step_id="S07", command="make test-unit")
        worktree_info = {"path": str(tmp_path)}

        with patch("orch.daemon.batch_manager.subprocess.Popen") as mock_popen:
            mock_popen.return_value = MagicMock(pid=4343)
            manager = make_manager(tmp_path, db, cli_tool="claude")
            db.query.return_value.filter.return_value.count.return_value = 0
            manager._launch_step(db, step, worktree_info)

        added_runs = [
            call.args[0] for call in db.add.call_args_list if hasattr(call.args[0], "pid")
        ]
        assert len(added_runs) == 1
        run = added_runs[0]
        assert run.command.startswith("bash ")
        assert "claude" not in run.command
        assert "opencode" not in run.command

    def test_qv_step_without_command_falls_back_to_llm(self, tmp_path):
        """Legacy items registered before CR-00023 (NULL step.command) still use the LLM path."""
        db = MagicMock()
        step = self._make_qv_step(item_id="F-00012", step_id="S08", command=None)
        worktree_info = {"path": "/wt/F-00012"}

        with (
            patch("orch.daemon.batch_manager.subprocess.Popen") as mock_popen,
            patch("orch.agent_runtime.resolver.resolve_runtime") as mock_resolve,
            patch("pathlib.Path.open", MagicMock()),
            patch("pathlib.Path.mkdir"),
            patch("pathlib.Path.exists", return_value=False),
            patch("pathlib.Path.write_text"),
        ):
            # CR-00062: _build_initial_command raises on unknown cli_tool.
            mock_option = MagicMock()
            mock_option.cli_tool = "claude"
            mock_option.model = "anthropic/claude-sonnet-4-6"
            mock_option.id = 2
            mock_resolve.return_value = mock_option
            mock_popen.return_value = MagicMock(pid=4444)
            manager = make_manager(tmp_path, db, cli_tool="claude")
            db.query.return_value.filter.return_value.count.return_value = 0
            manager._launch_step(db, step, worktree_info)

        cmd = mock_popen.call_args[0][0]
        assert "claude -p" in cmd  # LLM fallback
        assert "bash " not in cmd.split(" ")[0:1]  # not the bash wrapper


class TestBuildQvDirectCommand:
    """Pure unit tests for the wrapper-script builder."""

    def test_returns_bash_invocation_of_wrap_script(self, tmp_path):
        from orch.daemon.batch_manager import _build_qv_direct_command

        cmd = _build_qv_direct_command(
            item_id="F-00020",
            step_id="S06",
            gate_name="lint",
            gate_command="make lint",
            agent_label="QvGate",
            worktree_path=str(tmp_path),
        )
        assert cmd == "bash .tmp/F-00020_S06.qv-wrap.sh"

    def test_writes_gate_and_wrap_scripts(self, tmp_path):
        from orch.daemon.batch_manager import _build_qv_direct_command

        _build_qv_direct_command(
            item_id="F-00021",
            step_id="S07",
            gate_name="format",
            gate_command="ruff format --check .",
            agent_label="QvGate",
            worktree_path=str(tmp_path),
        )
        gate_script = tmp_path / ".tmp" / "F-00021_S07.qv-gate.sh"
        wrap_script = tmp_path / ".tmp" / "F-00021_S07.qv-wrap.sh"
        assert gate_script.read_text().strip().endswith("ruff format --check .")
        wrapper = wrap_script.read_text()
        # Both branches are present
        assert "iw step-done" in wrapper
        assert "iw step-fail" in wrapper
        # Report path uses the agent_label
        assert "F-00021_S07_QvGate_report.md" in wrapper
        # Gate name appears in the report
        assert "format" in wrapper

    def test_gate_command_with_special_chars_is_preserved(self, tmp_path):
        from orch.daemon.batch_manager import _build_qv_direct_command

        gate_cmd = "pytest -k 'parser or schema' --maxfail=1"
        _build_qv_direct_command(
            item_id="F-00022",
            step_id="S08",
            gate_name="unit-tests",
            gate_command=gate_cmd,
            agent_label="QvGate",
            worktree_path=str(tmp_path),
        )
        gate_script = tmp_path / ".tmp" / "F-00022_S08.qv-gate.sh"
        # The gate script body is the gate command verbatim — quotes preserved.
        assert gate_cmd in gate_script.read_text()

    def test_scripts_are_executable(self, tmp_path):
        import stat

        from orch.daemon.batch_manager import _build_qv_direct_command

        _build_qv_direct_command(
            item_id="F-00023",
            step_id="S09",
            gate_name="typecheck",
            gate_command="mypy orch",
            agent_label="QvGate",
            worktree_path=str(tmp_path),
        )
        for name in ("F-00023_S09.qv-gate.sh", "F-00023_S09.qv-wrap.sh"):
            mode = (tmp_path / ".tmp" / name).stat().st_mode
            assert mode & stat.S_IXUSR


# ---------------------------------------------------------------------------
# Worktree setup error handling
# ---------------------------------------------------------------------------


class TestWorktreeSetup:
    @pytest.fixture(autouse=True)
    def _alembic_guard_ok(self):
        """Mock the I-00040 check_db_at_head() pre-flight at the top of _launch_item.

        Without this, _launch_item's first action is a real DB probe that fails
        under the conftest env-hijack (port 1 unreachable). These tests target
        worktree setup error handling, not the alembic guard.
        """
        from orch.db.alembic_guard import GuardStatus

        ok = GuardStatus(current_rev="abc", head_rev="abc", pending=[], multiple_heads=[], ok=True)
        with patch("orch.daemon.batch_manager.check_db_at_head", return_value=ok):
            yield

    def test_failed_setup_marks_item_failed(self, tmp_path):
        db = MagicMock()
        batch_item = MagicMock(spec=BatchItem)
        batch_item.work_item_id = "F-00001"
        batch_item.status = BatchItemStatus.pending

        # Set up a mock work item that db.query(WorkItem).filter_by(...).one() returns
        mock_work_item = MagicMock()
        db.query.return_value.filter_by.return_value.one.return_value = mock_work_item

        manager = make_manager(tmp_path, db)

        with patch.object(manager, "_setup_worktree", side_effect=WorktreeSetupError("disk full")):
            manager._launch_item(db, batch_item)

        assert batch_item.status == BatchItemStatus.setup_failed
        assert "disk full" in batch_item.notes
        # Work item must also be marked failed so the UI shows a Restart button
        assert mock_work_item.status == WorkItemStatus.failed

    def test_successful_setup_transitions_to_executing(self, tmp_path):
        db = MagicMock()
        batch_item = MagicMock(spec=BatchItem)
        batch_item.work_item_id = "F-00001"
        batch_item.status = BatchItemStatus.pending

        manager = make_manager(tmp_path, db)
        fake_info = {"path": "/wt/F-00001", "branch": "agent/F-00001", "created_at": "now"}

        with (
            patch.object(manager, "_setup_worktree", return_value=fake_info),
            patch.object(manager, "_launch_next_step"),
        ):
            manager._launch_item(db, batch_item)

        assert batch_item.status == BatchItemStatus.executing
        assert batch_item.worktree_info == fake_info


# ---------------------------------------------------------------------------
# _next_run_number
# ---------------------------------------------------------------------------


class TestNextRunNumber:
    def test_first_run_is_1(self):
        db = MagicMock()
        step = MagicMock(spec=WorkflowStep)
        step.id = 1
        db.query.return_value.filter.return_value.count.return_value = 0
        assert _next_run_number(db, step) == 1

    def test_second_run_is_2(self):
        db = MagicMock()
        step = MagicMock(spec=WorkflowStep)
        step.id = 1
        db.query.return_value.filter.return_value.count.return_value = 1
        assert _next_run_number(db, step) == 2


# ---------------------------------------------------------------------------
# H1: _BLOCKING_TERMINAL_STATUSES and execution-group dependency check
# ---------------------------------------------------------------------------


class TestBlockingTerminalStatuses:
    """Unit tests for the H1 fix: _BLOCKING_TERMINAL_STATUSES set."""

    def test_merged_is_not_blocking(self):
        assert BatchItemStatus.merged not in _BLOCKING_TERMINAL_STATUSES

    def test_failed_is_blocking(self):
        assert BatchItemStatus.failed in _BLOCKING_TERMINAL_STATUSES

    def test_setup_failed_is_blocking(self):
        assert BatchItemStatus.setup_failed in _BLOCKING_TERMINAL_STATUSES

    def test_migration_invalid_not_blocking(self):
        # CR-00028: operator-recoverable merge failure — excluded from cascade
        assert BatchItemStatus.migration_invalid not in _BLOCKING_TERMINAL_STATUSES

    def test_migration_rolled_back_is_blocking(self):
        assert BatchItemStatus.migration_rolled_back in _BLOCKING_TERMINAL_STATUSES

    def test_stalled_is_blocking(self):
        assert BatchItemStatus.stalled in _BLOCKING_TERMINAL_STATUSES

    def test_skipped_is_blocking(self):
        assert BatchItemStatus.skipped in _BLOCKING_TERMINAL_STATUSES

    def test_merge_failed_not_blocking(self):
        # CR-00028: operator-recoverable merge failure — excluded from cascade
        assert BatchItemStatus.merge_failed not in _BLOCKING_TERMINAL_STATUSES


class TestExecutionGroupDependencyCheck:
    """Unit tests for H1: process_batch blocks on all terminal-failure statuses."""

    def _make_db_for_items(self, items: list[MagicMock]) -> MagicMock:
        db = MagicMock()
        q = MagicMock()
        q.filter.return_value.order_by.return_value.all.return_value = items
        step_q = MagicMock()
        step_q.filter.return_value.first.return_value = None
        step_q.filter.return_value.order_by.return_value.first.return_value = None
        work_item_q = MagicMock()
        work_item_q.join.return_value.filter.return_value.all.return_value = []
        db.query.side_effect = lambda model, *_args, **_kwargs: {
            BatchItem: q,
            WorkflowStep: step_q,
            WorkItem: work_item_q,
        }.get(model, MagicMock())
        return db

    def _make_batch(self) -> MagicMock:
        batch = MagicMock(spec=Batch)
        batch.id = "B001"
        batch.max_parallel = 4
        batch.status = BatchStatus.executing
        return batch

    @pytest.mark.parametrize(
        "blocking_status",
        [
            BatchItemStatus.setup_failed,
            # CR-00028: migration_invalid, migration_rebase_failed, merge_failed are
            # operator-recoverable — excluded from cascade
            BatchItemStatus.migration_rolled_back,
            BatchItemStatus.stalled,
            BatchItemStatus.skipped,
        ],
    )
    def test_blocking_status_in_group_0_cascades_to_group_1(self, tmp_path, blocking_status):
        """Non-'failed' terminal statuses in group 0 must block group 1."""
        item_a = make_batch_item("F-00001", execution_group=0, status=blocking_status)
        item_b = make_batch_item("F-00002", execution_group=1, status=BatchItemStatus.pending)

        db = self._make_db_for_items([item_a, item_b])
        batch = self._make_batch()

        launched: list[str] = []
        manager = make_manager(tmp_path, db)
        manager._launch_item = lambda _db, item_: launched.append(item_.work_item_id)  # type: ignore[method-assign]  # noqa: ARG005

        manager._process_batch(db, batch)

        assert item_b.status == BatchItemStatus.failed
        assert "F-00002" not in launched

    def test_merged_in_group_0_does_not_block_group_1(self, tmp_path):
        """merged is the success terminal — group 1 must NOT be blocked."""
        item_a = make_batch_item("F-00001", execution_group=0, status=BatchItemStatus.merged)
        item_b = make_batch_item("F-00002", execution_group=1, status=BatchItemStatus.pending)

        db = self._make_db_for_items([item_a, item_b])
        batch = self._make_batch()

        launched: list[str] = []
        manager = make_manager(tmp_path, db)
        manager._launch_item = lambda _db, item_: launched.append(item_.work_item_id)  # type: ignore[method-assign]  # noqa: ARG005

        manager._process_batch(db, batch)

        # item_b should have been launched, not failed
        assert item_b.status != BatchItemStatus.failed
        assert "F-00002" in launched

    def test_setup_failed_cascades_to_groups_1_and_2(self, tmp_path):
        """setup_failed in group 0 blocks BOTH group 1 and group 2."""
        item_a = make_batch_item("F-00001", execution_group=0, status=BatchItemStatus.setup_failed)
        item_b = make_batch_item("F-00002", execution_group=1, status=BatchItemStatus.pending)
        item_c = make_batch_item("F-00003", execution_group=2, status=BatchItemStatus.pending)

        db = self._make_db_for_items([item_a, item_b, item_c])
        batch = self._make_batch()

        manager = make_manager(tmp_path, db)
        manager._launch_item = MagicMock()  # type: ignore[method-assign]

        manager._process_batch(db, batch)

        assert item_b.status == BatchItemStatus.failed
        assert item_c.status == BatchItemStatus.failed
        manager._launch_item.assert_not_called()


# ---------------------------------------------------------------------------
# H11: browser env-up failure triggers env-down teardown
# ---------------------------------------------------------------------------


class TestBrowserEnvUpFailureTeardown:
    """Unit test for H11: run_env_down_hook called when run_env_up_hook returns False."""

    @pytest.fixture(autouse=True)
    def _alembic_guard_ok(self):
        from orch.db.alembic_guard import GuardStatus

        ok = GuardStatus(current_rev="abc", head_rev="abc", pending=[], multiple_heads=[], ok=True)
        with patch("orch.daemon.batch_manager.check_db_at_head", return_value=ok):
            yield

    def test_env_down_called_when_env_up_fails(self, tmp_path):
        """When run_env_up_hook returns False, run_env_down_hook must be called."""
        from orch.daemon.step_monitor import get_timeout  # noqa: F401

        db = MagicMock()
        step = MagicMock(spec=WorkflowStep)
        step.work_item_id = "F-00001"
        step.step_id = "S01"
        step.step_type = MagicMock()
        step.id = 1
        step.started_at = None
        step.command = None
        step.prompt_file = None
        step.timeout_secs = None
        step.opencode_agent = None
        step.agent_label = "test-agent"

        worktree_info = {"path": "/wt/F-00001"}
        bv_env = {"E2E_FRONTEND_PORT": "3100", "COMPOSE_PROJECT_NAME": "test-e2e"}
        fake_log_path = tmp_path / "env_up.log"
        fake_log_path.write_text("some failure output\n")

        manager = make_manager(tmp_path, db)
        db.query.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.filter_by.return_value.first.return_value = MagicMock()

        with (
            patch(
                "orch.daemon.browser_env.is_browser_verification_step",
                return_value=True,
            ),
            patch(
                "orch.daemon.browser_env.allocate_browser_env",
                return_value=bv_env,
            ),
            patch(
                "orch.daemon.browser_env.run_env_up_hook",
                return_value=(False, fake_log_path),
            ),
            patch("orch.daemon.browser_env.run_env_down_hook") as mock_down,
        ):
            manager._launch_step(db, step, worktree_info)

        mock_down.assert_called_once_with(
            manager.project_config,
            "/wt/F-00001",
            bv_env,
            "F-00001",
            "S01",
        )

    def test_env_down_called_even_when_it_raises(self, tmp_path):
        """run_env_down_hook raising must be caught — _launch_step must not propagate it."""
        db = MagicMock()
        step = MagicMock(spec=WorkflowStep)
        step.work_item_id = "F-00002"
        step.step_id = "S01"
        step.step_type = MagicMock()
        step.id = 2
        step.started_at = None
        step.command = None
        step.prompt_file = None
        step.timeout_secs = None
        step.opencode_agent = None
        step.agent_label = "test-agent"

        worktree_info = {"path": "/wt/F-00002"}
        bv_env = {"E2E_FRONTEND_PORT": "3101"}
        fake_log_path = tmp_path / "env_up2.log"
        fake_log_path.write_text("failure\n")

        manager = make_manager(tmp_path, db)
        db.query.return_value.filter.return_value.count.return_value = 0
        db.query.return_value.filter_by.return_value.first.return_value = MagicMock()

        with (
            patch(
                "orch.daemon.browser_env.is_browser_verification_step",
                return_value=True,
            ),
            patch(
                "orch.daemon.browser_env.allocate_browser_env",
                return_value=bv_env,
            ),
            patch(
                "orch.daemon.browser_env.run_env_up_hook",
                return_value=(False, fake_log_path),
            ),
            patch(
                "orch.daemon.browser_env.run_env_down_hook",
                side_effect=RuntimeError("teardown bombed"),
            ) as mock_down,
        ):
            # Must not raise — the exception from run_env_down_hook is swallowed
            manager._launch_step(db, step, worktree_info)

        mock_down.assert_called_once()


# ---------------------------------------------------------------------------
# CR-00036: auto_merge gate in _complete_item
# ---------------------------------------------------------------------------


class TestAutoMergeGate:
    """Unit tests for CR-00036: _complete_item gates on batch.auto_merge."""

    def _make_db_for_complete_item(self, batch: MagicMock) -> MagicMock:
        """Set up a minimal db mock that returns the given batch from db.get(Batch, ...)."""
        db = MagicMock()
        # db.get(Batch, (project_id, batch_id)) returns the batch
        db.get.return_value = batch
        return db

    def test_auto_merge_true_transitions_to_completed(self, tmp_path):
        """When batch.auto_merge=True, _complete_item sets status=completed."""
        db = MagicMock()
        batch = MagicMock(spec=Batch)
        batch.id = "B001"
        batch.auto_merge = True

        work_item = MagicMock(spec=WorkItem)
        work_item.status = WorkItemStatus.approved

        batch_item = MagicMock(spec=BatchItem)
        batch_item.work_item_id = "F-00001"
        batch_item.status = BatchItemStatus.executing
        batch_item.batch_id = "B001"
        batch_item.worktree_info = {"path": "/wt"}

        # db.get: Batch → batch, WorkItem → work_item
        # db.query: BatchItem → batch_item, WorkItem → work_item
        def get_side_effect(model, key):
            if model == Batch and key == ("test-proj", "B001"):
                return batch
            if model == WorkItem and key == ("test-proj", "F-00001"):
                return work_item
            return None

        q_batch_item = MagicMock()
        q_batch_item.filter.return_value.first.return_value = batch_item
        q_work_item = MagicMock()
        q_work_item.filter.return_value.one.return_value = work_item

        db.get.side_effect = get_side_effect
        db.query.side_effect = lambda model, *args, **kwargs: (  # noqa: ARG005
            {
                BatchItem: q_batch_item,
                WorkItem: q_work_item,
            }.get(model, MagicMock())
        )

        manager = make_manager(tmp_path, db)
        manager._complete_item(db, "F-00001")

        assert batch_item.status == BatchItemStatus.completed
        assert batch_item.status != BatchItemStatus.awaiting_merge_approval

    def test_auto_merge_false_transitions_to_awaiting_merge_approval(self, tmp_path):
        """When batch.auto_merge=False, _complete_item sets status=awaiting_merge_approval."""
        db = MagicMock()
        batch = MagicMock(spec=Batch)
        batch.id = "B001"
        batch.auto_merge = False

        work_item = MagicMock(spec=WorkItem)
        work_item.status = WorkItemStatus.approved

        batch_item = MagicMock(spec=BatchItem)
        batch_item.work_item_id = "F-00001"
        batch_item.status = BatchItemStatus.executing
        batch_item.batch_id = "B001"
        batch_item.worktree_info = {"path": "/wt"}

        def get_side_effect(model, key):
            if model == Batch and key == ("test-proj", "B001"):
                return batch
            if model == WorkItem and key == ("test-proj", "F-00001"):
                return work_item
            return None

        q_batch_item = MagicMock()
        q_batch_item.filter.return_value.first.return_value = batch_item
        q_work_item = MagicMock()
        q_work_item.filter.return_value.one.return_value = work_item

        db.get.side_effect = get_side_effect
        db.query.side_effect = lambda model, *args, **kwargs: (  # noqa: ARG005
            {
                BatchItem: q_batch_item,
                WorkItem: q_work_item,
            }.get(model, MagicMock())
        )

        manager = make_manager(tmp_path, db)
        manager._complete_item(db, "F-00001")

        assert batch_item.status == BatchItemStatus.awaiting_merge_approval
