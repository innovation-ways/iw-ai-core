"""Unit tests for orch.cancel service layer.

Covers teardown error paths and cancel_batch loop paths that require
mocked subprocess/os.kill calls not exercised by the dashboard integration tests.
"""

from __future__ import annotations

import signal
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from orch.cancel import (
    _teardown_compose_stack,
    _teardown_item_worktree,
    cancel_batch,
    cancel_work_item,
)
from orch.db.models import (
    BatchItemStatus,
    BatchStatus,
    RunStatus,
    StepStatus,
    WorkItemStatus,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _exec_scalar(value):
    """Mock execute() result that returns `value` from scalar_one_or_none()."""
    m = MagicMock()
    m.scalar_one_or_none.return_value = value
    return m


def _exec_scalars(values):
    """Mock execute() result that returns `values` from scalars().all()."""
    m = MagicMock()
    m.scalars.return_value.all.return_value = values
    return m


# ---------------------------------------------------------------------------
# _teardown_compose_stack
# ---------------------------------------------------------------------------


class TestTeardownComposeStack:
    """Tests for TeardownComposeStack scenarios."""

    def test_none_path_is_noop(self):
        """Verifies that none path is noop."""
        errors: list[str] = []
        _teardown_compose_stack(None, None, errors)
        assert errors == []

    def test_empty_string_path_is_noop(self):
        """Verifies that empty string path is noop."""
        errors: list[str] = []
        _teardown_compose_stack(1, "", errors)
        assert errors == []

    def test_success_calls_docker_compose(self):
        """Verifies that success calls docker compose."""
        errors: list[str] = []
        with patch("orch.cancel.subprocess.run") as mock_run:
            _teardown_compose_stack(1, "/path/compose.yml", errors)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "docker" in call_args
        assert "compose" in call_args
        assert errors == []

    def test_timeout_appends_error(self):
        """Verifies that timeout appends error."""
        errors: list[str] = []
        with patch(
            "orch.cancel.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=120),
        ):
            _teardown_compose_stack(1, "/path/compose.yml", errors)

        assert len(errors) == 1
        assert "timed out" in errors[0]

    def test_oserror_appends_error(self):
        """Verifies that oserror appends error."""
        errors: list[str] = []
        with patch(
            "orch.cancel.subprocess.run",
            side_effect=OSError("docker not found"),
        ):
            _teardown_compose_stack(1, "/path/compose.yml", errors)

        assert len(errors) == 1
        assert "failed" in errors[0]


# ---------------------------------------------------------------------------
# _teardown_item_worktree
# ---------------------------------------------------------------------------


class TestTeardownItemWorktree:
    """Tests for TeardownItemWorktree scenarios."""

    def test_no_batch_item_is_noop(self):
        """Verifies that no batch item is noop."""
        db = MagicMock()
        db.execute.return_value = _exec_scalar(None)
        errors: list[str] = []
        _teardown_item_worktree(db, "proj", "I-001", errors)
        assert errors == []

    def test_no_worktree_path_no_compose_is_noop(self):
        """Verifies that no worktree path no compose is noop."""
        db = MagicMock()
        bi = MagicMock()
        bi.worktree_info = {}
        bi.worktree_compose_path = None
        db.execute.return_value = _exec_scalar(bi)
        errors: list[str] = []
        with patch("orch.cancel.subprocess.run") as mock_run:
            _teardown_item_worktree(db, "proj", "I-001", errors)
        mock_run.assert_not_called()
        assert errors == []

    def test_no_worktree_path_but_compose_tears_down_compose(self):
        """Verifies that no worktree path but compose tears down compose."""
        db = MagicMock()
        bi = MagicMock()
        bi.id = 42
        bi.worktree_info = {}
        bi.worktree_compose_path = "/path/compose.yml"
        db.execute.return_value = _exec_scalar(bi)
        errors: list[str] = []
        with patch("orch.cancel.subprocess.run") as mock_run:
            _teardown_item_worktree(db, "proj", "I-001", errors)
        mock_run.assert_called_once()
        assert errors == []

    def test_with_worktree_path_calls_git_worktree_remove(self):
        """Verifies that with worktree path calls git worktree remove."""
        db = MagicMock()
        bi = MagicMock()
        bi.worktree_info = {"path": "/tmp/test-wt"}
        bi.worktree_compose_path = None
        db.execute.return_value = _exec_scalar(bi)
        errors: list[str] = []
        with patch("orch.cancel.subprocess.run") as mock_run:
            _teardown_item_worktree(db, "proj", "I-001", errors)
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "git" in call_args
        assert "worktree" in call_args
        assert errors == []

    def test_with_worktree_path_and_compose_tears_down_both(self):
        """Verifies that with worktree path and compose tears down both."""
        db = MagicMock()
        bi = MagicMock()
        bi.id = 99
        bi.worktree_info = {"path": "/tmp/test-wt"}
        bi.worktree_compose_path = "/path/compose.yml"
        db.execute.return_value = _exec_scalar(bi)
        errors: list[str] = []
        with patch("orch.cancel.subprocess.run") as mock_run:
            _teardown_item_worktree(db, "proj", "I-001", errors)
        assert mock_run.call_count == 2

    def test_worktree_remove_timeout_appends_error(self):
        """Verifies that worktree remove timeout appends error."""
        db = MagicMock()
        bi = MagicMock()
        bi.worktree_info = {"path": "/tmp/test-wt"}
        bi.worktree_compose_path = None
        db.execute.return_value = _exec_scalar(bi)
        errors: list[str] = []
        with patch(
            "orch.cancel.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=30),
        ):
            _teardown_item_worktree(db, "proj", "I-001", errors)
        assert len(errors) == 1
        assert "timed out" in errors[0]

    def test_worktree_remove_oserror_appends_error(self):
        """Verifies that worktree remove oserror appends error."""
        db = MagicMock()
        bi = MagicMock()
        bi.worktree_info = {"path": "/tmp/test-wt"}
        bi.worktree_compose_path = None
        db.execute.return_value = _exec_scalar(bi)
        errors: list[str] = []
        with patch("orch.cancel.subprocess.run", side_effect=OSError("No such file")):
            _teardown_item_worktree(db, "proj", "I-001", errors)
        assert len(errors) == 1
        assert "failed" in errors[0]


# ---------------------------------------------------------------------------
# cancel_work_item — kill running step paths
# ---------------------------------------------------------------------------


class TestCancelWorkItemKillPaths:
    """Tests for CancelWorkItemKillPaths scenarios."""

    def _make_item(self, status=WorkItemStatus.in_progress):
        item = MagicMock()
        item.status = status
        item.id = "I-001"
        item.updated_at = None
        return item

    def _make_step(self):
        step = MagicMock()
        step.id = 1
        step.status = StepStatus.in_progress
        return step

    def _make_run(self, pid=12345):
        run = MagicMock()
        run.pid = pid
        run.status = RunStatus.running
        run.completed_at = None
        return run

    def _make_db(self, item, running_steps, step_run):
        """Build a mock Session for cancel_work_item with running steps."""
        db = MagicMock()
        calls = [
            _exec_scalar(item),  # WorkItem lookup
            _exec_scalar(None),  # BatchItem.join(Batch) — not in active batch
            _exec_scalars(running_steps),  # WorkflowStep in_progress
        ]
        for _ in running_steps:
            calls.append(_exec_scalar(step_run))  # StepRun per step
        calls.append(_exec_scalar(None))  # BatchItem for teardown → None
        db.execute.side_effect = calls
        return db

    def test_running_step_pid_sigterm_sent(self):
        """Verifies that running step pid sigterm sent."""
        item = self._make_item()
        step = self._make_step()
        run = self._make_run(pid=12345)
        db = self._make_db(item, [step], run)

        with patch("orch.cancel.os.kill") as mock_kill:
            result = cancel_work_item(db, "proj", "I-001")

        mock_kill.assert_called_once_with(12345, signal.SIGTERM)
        assert run.status == RunStatus.killed
        assert run.completed_at is not None
        assert result.new_status == WorkItemStatus.cancelled

    def test_running_step_pid_oserror_appended_to_teardown_errors(self):
        """Verifies that running step pid oserror appended to teardown errors."""
        item = self._make_item()
        step = self._make_step()
        run = self._make_run(pid=12345)
        db = self._make_db(item, [step], run)

        with patch("orch.cancel.os.kill", side_effect=OSError("operation not permitted")):
            result = cancel_work_item(db, "proj", "I-001")

        assert any("12345" in e for e in result.teardown_errors)
        assert result.new_status == WorkItemStatus.cancelled

    def test_no_running_steps_skips_kill(self):
        """Verifies that no running steps skips kill."""
        item = self._make_item()
        db = MagicMock()
        db.execute.side_effect = [
            _exec_scalar(item),
            _exec_scalar(None),
            _exec_scalars([]),
            _exec_scalar(None),
        ]
        with patch("orch.cancel.os.kill") as mock_kill:
            result = cancel_work_item(db, "proj", "I-001")
        mock_kill.assert_not_called()
        assert result.new_status == WorkItemStatus.cancelled

    def test_not_found_raises_lookup_error(self):
        """Verifies that not found raises lookup error."""
        db = MagicMock()
        db.execute.return_value = _exec_scalar(None)
        with pytest.raises(LookupError, match="I-999"):
            cancel_work_item(db, "proj", "I-999")

    def test_wrong_status_raises_value_error(self):
        """Verifies that wrong status raises value error."""
        item = self._make_item(status=WorkItemStatus.draft)
        db = MagicMock()
        db.execute.return_value = _exec_scalar(item)
        with pytest.raises(ValueError, match="Cannot cancel"):
            cancel_work_item(db, "proj", "I-001")


# ---------------------------------------------------------------------------
# cancel_batch — loop paths (PID kill, compose, worktree, else branch)
# ---------------------------------------------------------------------------


class TestCancelBatchLoopPaths:
    """Tests for CancelBatchLoopPaths scenarios."""

    def _make_batch(self, status=BatchStatus.executing):
        batch = MagicMock()
        batch.status = status
        batch.id = "B-001"
        batch.updated_at = None
        return batch

    def _make_batch_item(self, work_item_id="I-001", pid=None, compose=None, worktree=None):
        bi = MagicMock()
        bi.id = 10
        bi.work_item_id = work_item_id
        bi.status = BatchItemStatus.executing
        bi.pid = pid
        bi.worktree_compose_path = compose
        bi.worktree_info = worktree
        return bi

    def _make_work_item(self):
        wi = MagicMock()
        wi.status = WorkItemStatus.in_progress
        wi.updated_at = None
        return wi

    def _make_db(self, batch, batch_items, work_item, running_runs=None, steps=None):
        """Build a mock Session matching cancel_batch's query order.

        Per batch_item, cancel_batch issues three reads:
        1. running StepRun rows (scalars list — joined with WorkflowStep)
        2. all WorkflowStep rows for the item (scalars list)
        3. the WorkItem row (scalar)
        """
        running_runs = running_runs if running_runs is not None else []
        steps = steps if steps is not None else []

        db = MagicMock()
        calls = [
            _exec_scalar(batch),
            _exec_scalars(batch_items),
        ]
        for _ in batch_items:
            calls.append(_exec_scalars(running_runs))
            calls.append(_exec_scalars(steps))
            calls.append(_exec_scalar(work_item))
        db.execute.side_effect = calls
        return db

    def test_not_found_raises_lookup_error(self):
        """Verifies that not found raises lookup error."""
        db = MagicMock()
        db.execute.return_value = _exec_scalar(None)
        with pytest.raises(LookupError, match="B-999"):
            cancel_batch(db, "proj", "B-999")

    def test_wrong_status_raises_value_error(self):
        """Verifies that wrong status raises value error."""
        batch = self._make_batch(status=BatchStatus.completed)
        db = MagicMock()
        db.execute.return_value = _exec_scalar(batch)
        with pytest.raises(ValueError, match="Cannot cancel"):
            cancel_batch(db, "proj", "B-001")

    def test_batch_item_with_pid_sends_sigterm(self):
        """Verifies that batch item with pid sends sigterm."""
        batch = self._make_batch()
        bi = self._make_batch_item(pid=54321)
        wi = self._make_work_item()
        db = self._make_db(batch, [bi], wi)

        with patch("orch.cancel.os.kill") as mock_kill:
            result = cancel_batch(db, "proj", "B-001")

        mock_kill.assert_called_once_with(54321, signal.SIGTERM)
        assert result.killed_pids == [54321]

    def test_batch_item_pid_oserror_appended(self):
        """Verifies that batch item pid oserror appended."""
        batch = self._make_batch()
        bi = self._make_batch_item(pid=54321)
        wi = self._make_work_item()
        db = self._make_db(batch, [bi], wi)

        with patch("orch.cancel.os.kill", side_effect=OSError("not permitted")):
            result = cancel_batch(db, "proj", "B-001")

        assert any("54321" in e for e in result.teardown_errors)
        assert result.killed_pids == []

    def test_batch_item_with_compose_tears_down(self):
        """Verifies that batch item with compose tears down."""
        batch = self._make_batch()
        bi = self._make_batch_item(compose="/path/compose.yml")
        wi = self._make_work_item()
        db = self._make_db(batch, [bi], wi)

        with patch("orch.cancel.subprocess.run") as mock_run:
            result = cancel_batch(db, "proj", "B-001")

        mock_run.assert_called_once()
        assert result.teardown_errors == []

    def test_batch_item_with_worktree_runs_git_remove(self):
        """Verifies that batch item with worktree runs git remove."""
        batch = self._make_batch()
        bi = self._make_batch_item(worktree={"path": "/tmp/wt"})
        wi = self._make_work_item()
        db = self._make_db(batch, [bi], wi)

        with patch("orch.cancel.subprocess.run") as mock_run:
            result = cancel_batch(db, "proj", "B-001")

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "git" in call_args
        assert result.teardown_errors == []

    def test_batch_item_worktree_timeout_appended(self):
        """Verifies that batch item worktree timeout appended."""
        batch = self._make_batch()
        bi = self._make_batch_item(worktree={"path": "/tmp/wt"})
        wi = self._make_work_item()
        db = self._make_db(batch, [bi], wi)

        with patch(
            "orch.cancel.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="git", timeout=30),
        ):
            result = cancel_batch(db, "proj", "B-001")

        assert any("timed out" in e for e in result.teardown_errors)

    def test_batch_item_worktree_oserror_appended(self):
        """Verifies that batch item worktree oserror appended."""
        batch = self._make_batch()
        bi = self._make_batch_item(worktree={"path": "/tmp/wt"})
        wi = self._make_work_item()
        db = self._make_db(batch, [bi], wi)

        with patch("orch.cancel.subprocess.run", side_effect=OSError("git missing")):
            result = cancel_batch(db, "proj", "B-001")

        assert any("failed" in e for e in result.teardown_errors)

    def test_batch_item_work_item_missing_skips_status_update(self):
        """When the WorkItem row is missing the batch item is still tidied up.

        In practice the FK on batch_items.(project_id, work_item_id) makes this
        path very rare, but cancel_batch must not crash or count a phantom
        cancellation. The BatchItem is still marked skipped and its notes are
        populated so an operator can see what happened.
        """
        batch = self._make_batch()
        bi = self._make_batch_item()
        db = MagicMock()
        db.execute.side_effect = [
            _exec_scalar(batch),
            _exec_scalars([bi]),
            _exec_scalars([]),  # running_runs for this bi
            _exec_scalars([]),  # workflow_steps for this bi
            _exec_scalar(None),  # WorkItem lookup → None
        ]

        result = cancel_batch(db, "proj", "B-001")

        assert result.cancelled_batch_items == []
        assert result.reset_to_draft == []
        assert bi.status == BatchItemStatus.skipped
        assert bi.notes is not None
        assert "B-001" in bi.notes

    def test_reset_items_flag_routes_to_draft(self):
        """--reset-items must push the work item to draft, not cancelled."""
        batch = self._make_batch()
        bi = self._make_batch_item()
        wi = self._make_work_item()
        db = self._make_db(batch, [bi], wi)

        result = cancel_batch(db, "proj", "B-001", reset_items=True)

        assert wi.status == WorkItemStatus.draft
        assert result.reset_to_draft == ["I-001"]
        assert result.cancelled_batch_items == []

    def test_completed_work_item_status_not_regressed(self):
        """A completed historical item on the batch must NOT regress to cancelled."""
        batch = self._make_batch()
        bi = self._make_batch_item()
        wi = self._make_work_item()
        wi.status = WorkItemStatus.completed
        db = self._make_db(batch, [bi], wi)

        result = cancel_batch(db, "proj", "B-001")

        assert wi.status == WorkItemStatus.completed
        # Item not counted because nothing was changed.
        assert result.cancelled_batch_items == []

    def test_empty_batch_no_items_returns_empty_result(self):
        """Verifies that empty batch no items returns empty result."""
        batch = self._make_batch()
        db = MagicMock()
        db.execute.side_effect = [
            _exec_scalar(batch),
            _exec_scalars([]),
        ]
        result = cancel_batch(db, "proj", "B-001")
        assert result.cancelled_batch_items == []
        assert result.killed_pids == []
        assert result.teardown_errors == []

    def test_running_step_run_killed_via_kill_process_group(self):
        """Running StepRuns owned by batch items are SIGTERM'd via step_monitor.

        Production agents are launched in their own session — only
        ``kill_process_group`` reaches the inner CLI; a plain ``os.kill``
        on the wrapper PID leaks the agent. Locking that choice here means
        a regression that switches back to ``os.kill`` would fail the test.
        """
        from orch.db.models import RunStatus

        batch = self._make_batch()
        bi = self._make_batch_item()
        wi = self._make_work_item()
        run = MagicMock()
        run.pid = 99999
        run.status = RunStatus.running
        run.pid_alive = True
        run.completed_at = None
        db = self._make_db(batch, [bi], wi, running_runs=[run])

        with patch("orch.daemon.step_monitor.kill_process_group") as mock_kpg:
            mock_kpg.return_value = True
            result = cancel_batch(db, "proj", "B-001")

        mock_kpg.assert_called_once_with(99999)
        assert result.killed_pids == [99999]
        assert run.status == RunStatus.killed
        assert run.pid_alive is False
        assert run.completed_at is not None

    def test_running_step_run_with_no_pid_still_marked_killed(self):
        """A running StepRun row with NULL pid still gets its status flipped."""
        from orch.db.models import RunStatus

        batch = self._make_batch()
        bi = self._make_batch_item()
        wi = self._make_work_item()
        run = MagicMock()
        run.pid = None
        run.status = RunStatus.running
        run.pid_alive = True
        run.completed_at = None
        db = self._make_db(batch, [bi], wi, running_runs=[run])

        with patch("orch.daemon.step_monitor.kill_process_group") as mock_kpg:
            result = cancel_batch(db, "proj", "B-001")

        mock_kpg.assert_not_called()
        assert result.killed_pids == []
        assert run.status == RunStatus.killed
        assert run.pid_alive is False
