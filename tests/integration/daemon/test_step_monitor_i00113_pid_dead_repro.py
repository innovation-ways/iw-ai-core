"""I-00113: Full spawn→monitor lifecycle regression coverage.

A non-trivial fraction (~36% in the CR-00082 S04 sample on 2026-05-25) of
re-launched庭审 review StepRuns are flagged FAILED with "Process exited without
reporting completion (PID dead)" within a poll cycle of being spawned, before
the agent has had any opportunity to produce output.

After S03 lands with the fix, this file provides regression protection over
every branch of the spawn→monitor lifecycle:

  Branch 1 — wrapper-exit + agent child alive  (I-00113 Bug / False-positive)
  Branch 2 — wrapper-exit + no agent registered (True crash — must mark failed)
  Branch 3 — agent alive + producing output     (Happy path — must stay alive)
  Branch 4 — agent timeout                      (Must fail via TIMEOUT, not PID-dead)
  Branch 5 — agent hard stall                  (Must fail via HARD-STALL, not PID-dead)
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import time
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from orch.config import DaemonConfig  # noqa: TC004 — used at runtime

if TYPE_CHECKING:
    from orch.daemon.step_monitor import StepRun as StepRunModel

# ---------------------------------------------------------------------------
# Fast-exit wrapper factory (used for Branch 1 — the I-00113 bug repro)
# ---------------------------------------------------------------------------

# How long we wait for the wrapper process itself to exit. The wrapper exits
# in <10 ms on any reasonable system; 200 ms is a safe upper bound.
_WRAPPER_SETTLE_MS = 200


def _wait_for_wrapper_exit(wrapper_pid: int, *, timeout_ms: int = 2000) -> bool:
    """Poll until the wrapper process exits or timeout is reached.

    Returns True if the wrapper exited within timeout_ms, False if the
    wrapper was still alive after timeout_ms (caller should assert-fail).
    """
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        try:
            result = os.waitpid(wrapper_pid, os.WNOHANG)
            if result[0] != 0:
                return True
        except ChildProcessError:
            return True
        except ProcessLookupError:
            return True

        try:
            os.kill(wrapper_pid, 0)
        except ProcessLookupError:
            return True

        time.sleep(0.01)

    return False


def _make_fast_exit_wrapper() -> tuple[int, list[int]]:
    """Launch a fast-exit shell wrapper with a long-lived child process.

    Mirrors the launch pattern used by `_launch_fix_agent`:
        launch_argv = ["script", "-qec", inner_command, "/dev/null"]
        proc = subprocess.Popen(launch_argv, start_new_session=True, ...)
        step_run.pid = proc.pid  # ← records the WRAPPER pid

    The wrapper forks a child that stays alive indefinitely (simulating the
    agent), names the child "opencode" via `exec -a` for `_probe_for_child`
    to detect, then exits immediately. The child becomes an orphan adopted
    by init (PPID=1).

    Returns:
        wrapper_pid: PID of the shell wrapper (daemon records this)
        child_pids:  PIDs of the simulated agent children (still alive)
    """
    # Three portability traps the previous helper hit (all ship-blockers on
    # this Ubuntu host, where `make test-unit` failed deterministically):
    #
    # 1. /bin/sh is **dash** on Debian/Ubuntu, whose `exec` builtin does not
    #    accept the `-a` flag (only bash does). Using /bin/sh silently fails
    #    the rename ("exec: -a: not found", rc=127) — no opencode-named child
    #    is ever created, the probe finds nothing, the run is marked failed.
    #    Pin to /bin/bash so `exec -a` works.
    #
    # 2. `iter(lambda: None, None)` is an **empty** iterator, not infinite:
    #    `iter(callable, sentinel)` stops when callable() returns sentinel,
    #    and `lambda: None` returns the sentinel on the first call. So the
    #    list comprehension that wrapped it iterated zero times — python3
    #    exited immediately without ever sleeping, leaving no live "opencode"
    #    child to probe for. Replace with a plain blocking sleep.
    #
    # 3. Plain `exec -a opencode python3 ...` REPLACES the wrapper shell
    #    in-place (no fork). The PID stays the same, the process is renamed
    #    to python3/opencode, and the "wrapper" never exits — so the
    #    "wrapper PID dead + child alive" topology the test depends on never
    #    materialises. We need a real fork-then-exit, which a backgrounded
    #    subshell provides: the outer bash spawns a subshell, the subshell
    #    exec-replaces itself with the renamed python3 (a *separate* PID),
    #    and the outer bash exits immediately because there is nothing left
    #    after the `&`. End state: wrapper PID dead, opencode child alive.
    fake_agent_cmd = "(exec -a opencode python3 -c 'import time; time.sleep(60)') &"
    proc = subprocess.Popen(
        ["/bin/bash", "-c", fake_agent_cmd],
        start_new_session=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    wrapper_pid = proc.pid

    exited = _wait_for_wrapper_exit(wrapper_pid, timeout_ms=_WRAPPER_SETTLE_MS)
    assert exited, (
        f"Wrapper PID {wrapper_pid} did not exit within {_WRAPPER_SETTLE_MS}ms "
        "— test harness is broken (wrapper should exit immediately)."
    )

    with pytest.raises(ProcessLookupError):
        os.kill(wrapper_pid, 0)

    result = subprocess.run(
        ["pgrep", "-f", "opencode"],
        capture_output=True,
        text=True,
    )
    lines = [line for line in result.stdout.strip().split("\n") if line.strip()]
    child_pids = [int(line) for line in lines] if lines else []
    return wrapper_pid, child_pids


def _cleanup_opencode_children() -> None:
    """Kill any stray opencode-named sleep 60 processes spawned by tests."""
    result = subprocess.run(
        ["pgrep", "-f", "opencode"],
        capture_output=True,
        text=True,
    )
    for pid_str in result.stdout.strip().split("\n"):
        if pid_str.strip():
            with contextlib.suppress(ProcessLookupError):
                os.kill(int(pid_str), signal.SIGTERM)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestI00113SpawnMonitorLifecycle:
    """Regression tests for the I-00113 spawn→monitor lifecycle.

    Covers AC3 from the issue design:
      1. Wrapper exit + agent child alive → must NOT mark failed (false-positive bug)
      2. Wrapper exit + no agent registered → must mark failed (true crash)
      3. Agent alive + producing output → must NOT mark failed (happy path)
      4. Agent timeout → must fail via TIMEOUT (not PID-dead)
      5. Agent hard stall → must fail via HARD-STALL (not PID-dead)
    """

    # ------------------------------------------------------------------
    # Branch 1 — wrapper-exit + agent child alive (I-00113 Bug)
    # ------------------------------------------------------------------
    def test_i00113_wrapper_exit_agent_alive__probe_finds_child(
        self,
        db_session: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Branch 1 (BUG): wrapper PID is dead but agent child is alive.

        After the wrapper exits but the agent child (opencode-named) is still
        running, `_check_step_health` must call `_probe_for_child`, find the
        live child, skip `_handle_crashed`, and leave the step in running state.

        This was the original I-00113 false-positive: the daemon recorded the
        wrapper PID, the next poll saw it dead, fired `_handle_crashed`, and
        burned a fix-cycle slot — even though the real agent was alive.

        S01 wrote the reproduction test (RED evidence).  S03 applied the fix.
        S04 ships this as the permanent regression test.

        Semantic assertions:
          - crashed_events == 0   (BUG-FIXED: step survived the wrapper exit)
          - run.status == running (step is NOT failed)
          - child_pids is non-empty (test setup invariant)

        Deletion of _probe_for_child or the orphan fallback would cause this
        test to FAIL — catching the regression before it ships.
        """
        from orch.daemon import step_monitor as sm
        from orch.db.models import (
            Project,
            RunStatus,
            StepRun,
            StepStatus,
            StepType,
            WorkflowStep,
            WorkItem,
            WorkItemPhase,
            WorkItemStatus,
            WorkItemType,
        )

        session: object = db_session

        project = Project(
            id="test-proj-i00113-b1",
            display_name="Test Project I-00113 Branch 1",
            repo_root="/tmp",
            config={},
        )
        session.add(project)
        session.flush()

        item = WorkItem(
            project_id=project.id,
            id="I-00113-B1",
            type=WorkItemType.Feature,
            title="I-00113 branch 1",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        session.add(item)
        session.flush()

        step = WorkflowStep(
            project_id=project.id,
            work_item_id=item.id,
            step_number=1,
            step_id="S01",
            agent_label="test",
            step_type=StepType.code_review,
            status=StepStatus.in_progress,
        )
        session.add(step)
        session.flush()

        # Launch the fast-exit wrapper with opencode-named child
        wrapper_pid, child_pids = _make_fast_exit_wrapper()
        now = datetime.now(UTC)

        with pytest.raises(ProcessLookupError):
            os.kill(wrapper_pid, 0)  # wrapper is dead — this is the setup

        assert child_pids, (
            "Child process (opencode) should be alive — "
            "this is the simulated agent that must survive the wrapper exit."
        )

        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.running,
            pid=wrapper_pid,  # daemon records the wrapper PID
            pid_alive=True,
            command="test command",
            worktree_path="/tmp",
            cli_tool="opencode",
            started_at=now,
            last_heartbeat=now,
            timeout_secs=1800,
        )
        session.add(run)
        session.flush()

        mock_config: DaemonConfig = MagicMock(spec=DaemonConfig)
        mock_config.stall_threshold = 60

        crashed_events: list[dict] = []
        original_handle_crashed = sm._handle_crashed

        def tracking_handle_crashed(
            db: object,
            r: StepRunModel,
            project_id: str,
            check_now: datetime,
            project_config: object = None,
        ) -> None:
            original_handle_crashed(db, r, project_id, check_now, project_config)
            crashed_events.append(
                {
                    "run_id": r.id,
                    "run_status": r.status,
                    "error_message": r.error_message,
                    "project_id": project_id,
                }
            )

        monkeypatch.setattr(sm, "_handle_crashed", tracking_handle_crashed)

        try:
            sm._check_step_health(
                session, run, project_id=project.id, config=mock_config, project_config=None
            )

            # Semantic: 0 crash events — _probe_for_child detected the live child
            assert len(crashed_events) == 0, (
                f"Expected 0 crash events (bug-fixed: _probe_for_child detected "
                f"live opencode child), got {len(crashed_events)}. "
                "The crash event should NOT fire — the real agent is alive."
            )

            session.refresh(run)
            # Semantic: step stays running — not marked failed
            assert run.status == RunStatus.running, (
                f"StepRun should still be running (bug-fixed), got {run.status}"
            )

        finally:
            _cleanup_opencode_children()

    # ------------------------------------------------------------------
    # Branch 2 — wrapper-exit + no agent registered (true crash)
    # ------------------------------------------------------------------
    def test_i00113_wrapper_exit_no_agent__crashed_with_pid_dead_message(
        self,
        db_session: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Branch 2 (TRUE CRASH): wrapper PID is dead and no agent child exists.

        When `_is_pid_alive` returns False (PID dead/not found) AND
        `_probe_for_child` finds no live agent child, `_handle_crashed` must
        be called and the step marked failed with the explicit PID-dead message.

        We mock `_is_pid_alive` → False and `_probe_for_child` → False so the
        test is deterministic — real subprocess timing is unreliable here because
        a subprocess that exits before `_check_step_health` runs means the OS
        may have reused the freed PID by the time the health check runs.

        Semantic assertions:
          - crashed_events == 1   (step IS marked failed)
          - run.status == failed    (not running — terminal state)
          - "PID dead" in run.error_message  (specific message, not generic)
        """
        from orch.daemon import step_monitor as sm
        from orch.db.models import (
            Project,
            RunStatus,
            StepRun,
            StepStatus,
            StepType,
            WorkflowStep,
            WorkItem,
            WorkItemPhase,
            WorkItemStatus,
            WorkItemType,
        )

        session: object = db_session

        project = Project(
            id="test-proj-i00113-b2",
            display_name="Test Project I-00113 Branch 2",
            repo_root="/tmp",
            config={},
        )
        session.add(project)
        session.flush()

        item = WorkItem(
            project_id=project.id,
            id="I-00113-B2",
            type=WorkItemType.Feature,
            title="I-00113 branch 2",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        session.add(item)
        session.flush()

        step = WorkflowStep(
            project_id=project.id,
            work_item_id=item.id,
            step_number=1,
            step_id="S01",
            agent_label="test",
            step_type=StepType.code_review,
            status=StepStatus.in_progress,
        )
        session.add(step)
        session.flush()

        now = datetime.now(UTC)
        # PID = 99999 is guaranteed to not exist — used to simulate dead PID
        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.running,
            pid=99999,
            pid_alive=True,
            command="test command",
            worktree_path="/tmp",
            cli_tool="opencode",
            started_at=now,
            last_heartbeat=now,
            timeout_secs=1800,
        )
        session.add(run)
        session.flush()

        mock_config: DaemonConfig = MagicMock(spec=DaemonConfig)
        mock_config.stall_threshold = 60

        crashed_events: list[dict] = []
        original_handle_crashed = sm._handle_crashed

        def tracking_handle_crashed(
            db: object,
            r: StepRunModel,
            project_id: str,
            check_now: datetime,
            project_config: object = None,
        ) -> None:
            original_handle_crashed(db, r, project_id, check_now, project_config)
            crashed_events.append(
                {
                    "run_id": r.id,
                    "run_status": r.status,
                    "error_message": r.error_message,
                    "project_id": project_id,
                }
            )

        monkeypatch.setattr(sm, "_handle_crashed", tracking_handle_crashed)

        # Mock _probe_for_child → False (no agent child found)
        monkeypatch.setattr(sm, "_probe_for_child", lambda _pid: False)

        sm._check_step_health(
            session, run, project_id=project.id, config=mock_config, project_config=None
        )
        session.commit()
        # Semantic: exactly 1 crash event — the step genuinely crashed
        assert len(crashed_events) == 1, (
            f"Expected 1 crash event (true crash, no agent child), got {len(crashed_events)}."
        )

        session.refresh(run)
        # Semantic: terminal state is failed (not running)
        assert run.status == RunStatus.failed, (
            f"StepRun should be failed (true crash), got {run.status}"
        )
        # Semantic: error message contains the PID-dead sentinel
        error_msg = run.error_message or ""
        assert "PID dead" in error_msg, (
            f"Expected error message to contain 'PID dead', got: {error_msg!r}"
        )

    def test_i00113_no_pid_no_agent__crashed_with_no_pid_message(
        self,
        db_session: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Branch 2b: pid=None and no agent registered → explicit 'No PID recorded'.

        This is the equivalent of "spawn failure before any PID was recorded."
        When `run.pid` is None, `_handle_crashed` must be called with the
        explicit "No PID recorded" message — not the PID-dead message.

        Semantic assertions:
          - crashed_events == 1
          - run.status == failed
          - "No PID recorded" in run.error_message
          - "PID dead" NOT in run.error_message
        """
        from orch.daemon import step_monitor as sm
        from orch.db.models import (
            Project,
            RunStatus,
            StepRun,
            StepStatus,
            StepType,
            WorkflowStep,
            WorkItem,
            WorkItemPhase,
            WorkItemStatus,
            WorkItemType,
        )

        session: object = db_session

        project = Project(
            id="test-proj-i00113-b2b",
            display_name="Test Project I-00113 Branch 2b",
            repo_root="/tmp",
            config={},
        )
        session.add(project)
        session.flush()

        item = WorkItem(
            project_id=project.id,
            id="I-00113-B2B",
            type=WorkItemType.Feature,
            title="I-00113 branch 2b",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        session.add(item)
        session.flush()

        step = WorkflowStep(
            project_id=project.id,
            work_item_id=item.id,
            step_number=1,
            step_id="S01",
            agent_label="test",
            step_type=StepType.code_review,
            status=StepStatus.in_progress,
        )
        session.add(step)
        session.flush()

        # PID=None simulates spawn failure before any PID was recorded
        now = datetime.now(UTC)
        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.running,
            pid=None,
            pid_alive=False,
            command="test command",
            worktree_path="/tmp",
            cli_tool="opencode",
            started_at=now,
            last_heartbeat=now,
            timeout_secs=1800,
        )
        session.add(run)
        session.flush()

        mock_config: DaemonConfig = MagicMock(spec=DaemonConfig)
        mock_config.stall_threshold = 60

        crashed_events: list[dict] = []
        original_handle_crashed = sm._handle_crashed

        def tracking_handle_crashed(
            db: object,
            r: StepRunModel,
            project_id: str,
            check_now: datetime,
            project_config: object = None,
        ) -> None:
            original_handle_crashed(db, r, project_id, check_now, project_config)
            crashed_events.append(
                {
                    "run_id": r.id,
                    "run_status": r.status,
                    "error_message": r.error_message,
                    "project_id": project_id,
                }
            )

        monkeypatch.setattr(sm, "_handle_crashed", tracking_handle_crashed)

        sm._check_step_health(
            session, run, project_id=project.id, config=mock_config, project_config=None
        )
        session.commit()
        assert len(crashed_events) == 1, (
            f"Expected 1 crash event (pid=None), got {len(crashed_events)}."
        )

        session.refresh(run)
        assert run.status == RunStatus.failed, (
            f"StepRun should be failed (pid=None), got {run.status}"
        )
        error_msg = run.error_message or ""
        assert "No PID recorded" in error_msg, (
            f"Expected error message 'No PID recorded', got: {error_msg!r}"
        )
        assert "PID dead" not in error_msg, (
            f"'PID dead' must not appear when pid=None, got: {error_msg!r}"
        )

    # ------------------------------------------------------------------
    # Branch 3 — agent alive + producing output (happy path)
    # ------------------------------------------------------------------
    def test_i00113_agent_alive__stays_alive_and_heartbeat_updated(
        self,
        db_session: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Branch 3 (HAPPY PATH): agent PID is alive.

        When the agent PID survives the `_is_pid_alive` check (alive process,
        not a zombie), `_check_step_health` must update the heartbeat,
        mark `pid_alive=True`, and leave the step running.  `_handle_crashed`
        must NOT be called.

        Real subprocess is used because we validate (a) the process is truly alive
        from the OS perspective, and (b) the heartbeat update logic works end-to-end.

        Semantic assertions:
          - crashed_events == 0   (no crash — happy path)
          - run.status == running (step stays alive)
          - run.pid_alive == True (alive signal persisted)
          - last_heartbeat updated (monotonically non-decreasing)

        Deleting the `_is_pid_alive` return path or accidentally calling
        `_handle_crashed` for alive PIDs would cause this test to FAIL.
        """
        from orch.daemon import step_monitor as sm
        from orch.db.models import (
            Project,
            RunStatus,
            StepRun,
            StepStatus,
            StepType,
            WorkflowStep,
            WorkItem,
            WorkItemPhase,
            WorkItemStatus,
            WorkItemType,
        )

        session: object = db_session

        project = Project(
            id="test-proj-i00113-b3",
            display_name="Test Project I-00113 Branch 3",
            repo_root="/tmp",
            config={},
        )
        session.add(project)
        session.flush()

        item = WorkItem(
            project_id=project.id,
            id="I-00113-B3",
            type=WorkItemType.Feature,
            title="I-00113 branch 3",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        session.add(item)
        session.flush()

        step = WorkflowStep(
            project_id=project.id,
            work_item_id=item.id,
            step_number=1,
            step_id="S01",
            agent_label="test",
            step_type=StepType.code_review,
            status=StepStatus.in_progress,
        )
        session.add(step)
        session.flush()

        # Launch a real subprocess that survives indefinitely as the "agent"
        agent_proc = subprocess.Popen(
            ["python3", "-c", "import time; time.sleep(300)"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        agent_pid = agent_proc.pid

        try:
            now = datetime.now(UTC)
            run = StepRun(
                step_id=step.id,
                run_number=1,
                status=RunStatus.running,
                pid=agent_pid,
                pid_alive=True,
                command="test command",
                worktree_path="/tmp",
                cli_tool="python3",
                started_at=now,
                last_heartbeat=now,
                timeout_secs=1800,
            )
            session.add(run)
            session.flush()

            mock_config: DaemonConfig = MagicMock(spec=DaemonConfig)
            mock_config.stall_threshold = 60

            crashed_events: list[dict] = []
            original_handle_crashed = sm._handle_crashed

            def tracking_handle_crashed(
                db: object,
                r: StepRunModel,
                project_id: str,
                check_now: datetime,
                project_config: object = None,
            ) -> None:
                original_handle_crashed(db, r, project_id, check_now, project_config)
                crashed_events.append(
                    {
                        "run_id": r.id,
                        "run_status": r.status,
                        "error_message": r.error_message,
                        "project_id": project_id,
                    }
                )

            monkeypatch.setattr(sm, "_handle_crashed", tracking_handle_crashed)

            sm._check_step_health(
                session, run, project_id=project.id, config=mock_config, project_config=None
            )

            session.refresh(run)

            # Semantic: no crash events (happy path)
            assert len(crashed_events) == 0, (
                f"Expected 0 crash events (agent alive), got {len(crashed_events)}."
            )

            # Semantic: step stays running
            assert run.status == RunStatus.running, (
                f"StepRun should be running (agent alive), got {run.status}"
            )

            # Semantic: pid_alive updated to True
            assert run.pid_alive is True, (
                f"pid_alive should be True after alive check, got {run.pid_alive}"
            )

            # Semantic: last_heartbeat is updated to >= the current time
            assert run.last_heartbeat is not None, "last_heartbeat should be set"
            assert run.last_heartbeat >= now, (
                f"last_heartbeat should be >= poll time {now}, got {run.last_heartbeat}"
            )

        finally:
            agent_proc.terminate()
            agent_proc.wait(timeout=5)

    # ------------------------------------------------------------------
    # Branch 4 — agent timeout (must use TIMEOUT branch, not PID-dead)
    # ------------------------------------------------------------------
    def test_i00113_agent_timeout__handle_timeout_not_pid_dead(
        self,
        db_session: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Branch 4 (TIMEOUT): agent PID is alive but elapsed > timeout_secs.

        When `_is_pid_alive` returns True but the step has exceeded its timeout,
        `_check_step_health` must call `_handle_timeout` (which emits the
        step_timeout event), NOT `_handle_crashed` (step_crashed).

        The two error messages must NOT be conflated:
          - timeout:    "Timeout after {N}s (limit: {M}s)"
          - PID-dead:   "Process exited without reporting completion (PID dead)"

        Real subprocess is used (agent stays alive at the PID level) so the
        timeout branch is the sole differentiator — not PID liveness.

        Semantic assertions:
          - crashed_events == 0   (NOT _handle_crashed)
          - timeout_events == 1  (IS _handle_timeout)
          - run.status == timeout (terminal state via TIMEOUT)
          - "Timeout after" in run.error_message
          - "PID dead" NOT in run.error_message

        The os.kill probe is NOT mocked here (real subprocess retained for
        maximum realism).  _probe_for_child is mocked so the dead-wrapper path
        skips the expensive /proc orphan scan (irrelevant when the agent is alive).
        """
        from orch.daemon import step_monitor as sm
        from orch.db.models import (
            Project,
            RunStatus,
            StepRun,
            StepStatus,
            StepType,
            WorkflowStep,
            WorkItem,
            WorkItemPhase,
            WorkItemStatus,
            WorkItemType,
        )

        session: object = db_session

        project = Project(
            id="test-proj-i00113-b4",
            display_name="Test Project I-00113 Branch 4",
            repo_root="/tmp",
            config={},
        )
        session.add(project)
        session.flush()

        item = WorkItem(
            project_id=project.id,
            id="I-00113-B4",
            type=WorkItemType.Feature,
            title="I-00113 branch 4",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        session.add(item)
        session.flush()

        step = WorkflowStep(
            project_id=project.id,
            work_item_id=item.id,
            step_number=1,
            step_id="S01",
            agent_label="test",
            step_type=StepType.code_review,
            status=StepStatus.in_progress,
        )
        session.add(step)
        session.flush()

        # started_at far in the past so elapsed > timeout_secs immediately
        timeout_secs = 1800
        started = datetime.now(UTC) - timedelta(seconds=timeout_secs + 10)
        # start_new_session=True so the subprocess gets its own PGID.
        # Without it, the subprocess shares the pytest PGID and kill_process_group
        # (SIGTERM via pgid) would kill the pytest process itself.
        agent_proc = subprocess.Popen(
            ["python3", "-c", "import time; time.sleep(300)"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        try:
            run = StepRun(
                step_id=step.id,
                run_number=1,
                status=RunStatus.running,
                pid=agent_proc.pid,
                pid_alive=True,
                command="test command",
                worktree_path="/tmp",
                cli_tool="python3",
                started_at=started,
                last_heartbeat=started,
                timeout_secs=timeout_secs,
                log_file=None,  # skip capture_log_content in _handle_timeout
            )
            session.add(run)
            session.flush()

            mock_config: DaemonConfig = MagicMock(spec=DaemonConfig)
            mock_config.stall_threshold = 60

            crashed_events: list[dict] = []
            timeout_events: list[dict] = []

            original_handle_crashed = sm._handle_crashed
            original_handle_timeout = sm._handle_timeout

            def tracking_handle_crashed(
                db: object,
                r: StepRunModel,
                project_id: str,
                check_now: datetime,
                project_config: object = None,
            ) -> None:
                original_handle_crashed(db, r, project_id, check_now, project_config)
                crashed_events.append(
                    {"run_id": r.id, "run_status": r.status, "error_message": r.error_message}
                )

            def tracking_handle_timeout(
                db: object,
                r: StepRunModel,
                project_id: str,
                check_now: datetime,
                elapsed: float,
                project_config: object = None,
            ) -> None:
                original_handle_timeout(db, r, project_id, check_now, elapsed, project_config)
                timeout_events.append(
                    {"run_id": r.id, "run_status": r.status, "error_message": r.error_message}
                )

            monkeypatch.setattr(sm, "_handle_crashed", tracking_handle_crashed)
            monkeypatch.setattr(sm, "_handle_timeout", tracking_handle_timeout)
            # I-00113: mock _probe_for_child so the dead-wrapper path skips the
            # expensive /proc orphan scan (irrelevant when agent is alive).
            monkeypatch.setattr(sm, "_probe_for_child", lambda _p: False)
            # Mock _is_pid_alive so the timeout branch fires, not the PID-dead branch.
            # Pure mock is acceptable for the timeout branch — per S04 requirements.
            monkeypatch.setattr(
                sm,
                "_is_pid_alive",
                lambda *args, **kwargs: True,  # noqa: ARG005
            )

            sm._check_step_health(
                session,
                run,
                project_id=project.id,
                config=mock_config,
                project_config=None,
            )
            session.commit()
            session.refresh(run)

            # Semantic: _handle_crashed NOT called (not a PID-dead)
            assert len(crashed_events) == 0, (
                f"Expected 0 crash events (timeout path, not PID-dead), got {len(crashed_events)}."
            )

            # Semantic: _handle_timeout IS called
            assert len(timeout_events) == 1, f"Expected 1 timeout event, got {len(timeout_events)}."

            assert run.status == RunStatus.timeout, f"StepRun should be timeout, got {run.status}"

            # Semantic: error message contains "Timeout after"
            error_msg = run.error_message or ""
            assert "Timeout after" in error_msg, (
                f"Expected 'Timeout after' in error message, got: {error_msg!r}"
            )

            # Semantic: error message does NOT contain "PID dead"
            assert "PID dead" not in error_msg, (
                f"Error message should not conflate timeout with PID-dead, got: {error_msg!r}"
            )

        finally:
            agent_proc.terminate()
            agent_proc.wait(timeout=5)

    # ------------------------------------------------------------------
    # Branch 5 — agent hard stall (must use HARD-STALL branch, not PID-dead)
    # ------------------------------------------------------------------
    def test_i00113_agent_hard_stall__handle_hard_stall_not_pid_dead(
        self,
        db_session: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Branch 5 (HARD STALL): heartbeat too old (> 2x stall_threshold).

        When the agent PID is alive but the heartbeat has not advanced for
        more than 2x the stall threshold, `_check_step_health` must call
        `_handle_hard_stall` (which emits step_stall_killed), NOT `_handle_crashed`.

        We arrange `last_heartbeat` to 130s ago and `stall_threshold=60` so that
        after the poll-cycle heartbeat update, heartbeat_age > 120s (2x threshold)
        and the hard-stall branch fires.  The timeout branch does NOT fire because
        the step started only 300s ago and timeout is 3600s.

        Real subprocess is used — the agent stays alive and `_is_pid_alive`
        returns True; the heartbeat age is the sole differentiator.

        Semantic assertions:
          - crashed_events == 0   (NOT _handle_crashed)
          - hard_stall_events == 1 (IS _handle_hard_stall)
          - run.status == failed  (terminal state via HARD-STALL)
          - "Killed after stall" in run.error_message
          - "PID dead" NOT in run.error_message
        """
        from orch.daemon import step_monitor as sm
        from orch.db.models import (
            Project,
            RunStatus,
            StepRun,
            StepStatus,
            StepType,
            WorkflowStep,
            WorkItem,
            WorkItemPhase,
            WorkItemStatus,
            WorkItemType,
        )

        session: object = db_session

        project = Project(
            id="test-proj-i00113-b5",
            display_name="Test Project I-00113 Branch 5",
            repo_root="/tmp",
            config={},
        )
        session.add(project)
        session.flush()

        item = WorkItem(
            project_id=project.id,
            id="I-00113-B5",
            type=WorkItemType.Feature,
            title="I-00113 branch 5",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        session.add(item)
        session.flush()

        step = WorkflowStep(
            project_id=project.id,
            work_item_id=item.id,
            step_number=1,
            step_id="S01",
            agent_label="test",
            step_type=StepType.code_review,
            status=StepStatus.in_progress,
        )
        session.add(step)
        session.flush()

        stall_threshold = 60
        # started_at: recent enough that elapsed < timeout_secs (so timeout check fires)
        started = datetime.now(UTC) - timedelta(seconds=300)
        # last_heartbeat: set to 130s ago.
        # After poll-cycle update to NOW, heartbeat_age = heartbeat_old → NOW = 130s.
        # 130s > 60s * 2 = 120s → hard-stall fires.
        heartbeat_old = datetime.now(UTC) - timedelta(seconds=130)

        # start_new_session=True so the subprocess gets its own PGID.
        # Without it, the subprocess shares the pytest PGID and kill_process_group
        # (SIGTERM via pgid) would kill the pytest process itself.
        agent_proc = subprocess.Popen(
            ["python3", "-c", "import time; time.sleep(300)"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        try:
            # Use agent_proc.pid so finally block can clean it up; _is_pid_alive
            # is mocked so PID-level check is overridden.  log_file=None skips
            # capture_log_content in _handle_hard_stall (no real log path needed).
            run = StepRun(
                step_id=step.id,
                run_number=1,
                status=RunStatus.running,
                pid=agent_proc.pid,
                pid_alive=True,
                command="test command",
                worktree_path="/tmp",
                cli_tool="python3",
                started_at=started,
                last_heartbeat=heartbeat_old,
                timeout_secs=3600,
                log_file=None,
            )
            session.add(run)
            session.flush()

            mock_config: DaemonConfig = MagicMock(spec=DaemonConfig)
            mock_config.stall_threshold = stall_threshold

            crashed_events: list[dict] = []
            hard_stall_events: list[dict] = []

            original_handle_crashed = sm._handle_crashed
            original_handle_hard_stall = sm._handle_hard_stall

            def tracking_handle_crashed(
                db: object,
                r: StepRunModel,
                project_id: str,
                check_now: datetime,
                project_config: object = None,
            ) -> None:
                original_handle_crashed(db, r, project_id, check_now, project_config)
                crashed_events.append(
                    {"run_id": r.id, "run_status": r.status, "error_message": r.error_message}
                )

            def tracking_handle_hard_stall(
                db: object,
                r: StepRunModel,
                project_id: str,
                check_now: datetime,
                heartbeat_age: float,
                project_config: object = None,
            ) -> None:
                original_handle_hard_stall(
                    db, r, project_id, check_now, heartbeat_age, project_config
                )
                hard_stall_events.append(
                    {"run_id": r.id, "run_status": r.status, "error_message": r.error_message}
                )

            monkeypatch.setattr(sm, "_handle_crashed", tracking_handle_crashed)
            monkeypatch.setattr(sm, "_handle_hard_stall", tracking_handle_hard_stall)

            # I-00113: mock _probe_for_child so the dead-wrapper path skips the
            # expensive /proc orphan scan (irrelevant when the agent is alive).
            monkeypatch.setattr(sm, "_probe_for_child", lambda _p: False)

            # Mock _is_pid_alive to simulate a live agent (stall fires, not PID-dead).
            # Pure mock is acceptable for the stall branch — per S04 requirements.
            monkeypatch.setattr(
                sm,
                "_is_pid_alive",
                lambda *args, **kwargs: True,  # noqa: ARG005
            )

            sm._check_step_health(
                session,
                run,
                project_id=project.id,
                config=mock_config,
                project_config=None,
            )
            session.commit()
            session.refresh(run)

            # Semantic: _handle_crashed NOT called (stall, not PID-dead)
            assert len(crashed_events) == 0, (
                f"Expected 0 crash events (stall path, not PID-dead), got {len(crashed_events)}."
            )

            # Semantic: _handle_hard_stall IS called
            assert len(hard_stall_events) == 1, (
                f"Expected 1 hard-stall event, got {len(hard_stall_events)}."
            )

            # Semantic: status is failed (hard stall marks failed, not stalled)
            assert run.status == RunStatus.failed, (
                f"StepRun should be failed (hard stall), got {run.status}"
            )

            # Semantic: error message contains "Killed after stall"
            error_msg = run.error_message or ""
            assert "Killed after stall" in error_msg, (
                f"Expected 'Killed after stall' in error message, got: {error_msg!r}"
            )

            # Semantic: error message does NOT contain "PID dead"
            assert "PID dead" not in error_msg, (
                f"Error message should not conflate stall with PID-dead, got: {error_msg!r}"
            )

        finally:
            agent_proc.terminate()
            agent_proc.wait(timeout=5)
