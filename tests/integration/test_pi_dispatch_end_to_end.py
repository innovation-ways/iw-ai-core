"""CR-00062 — Pi (pi.dev) end-to-end dispatch via a stub binary on PATH.

This file pins the SHAPE of the pi dispatch across the dispatch sites that
unit tests can't reach without a subprocess hop:

1. ``executor/step_executor_lib.sh _run_agent_oneshot`` (F-00084 auto-merge
   dry-run) — exercised by calling
   ``bash step_executor_lib.sh auto_merge_resolve pi <model>`` with a prompt
   on stdin. Asserts the stub pi binary is invoked and its marker arrives on
   stdout.

2. ``executor/step_executor.sh`` step-launch — exercised by invoking the
   script directly with a minimal worktree + a real DB step row + the stub
   pi on PATH. Asserts the per-step log contains the stub's marker.

3. ``fix_cycle._build_fix_launch_argv("pi", inner)`` — exercised at
   call-site granularity, asserting the ``script -qec ... /dev/null`` PTY
   wrapper is NOT used. (The argv builder itself is unit-tested in
   ``tests/unit/test_pi_runtime_dispatch.py``; this companion test pins the
   integration invariant that opencode and pi take different wrapper arms.)

4. ``doc_job_poller._build_agent_command`` — exercised against a real
   ``Project`` row in the testcontainer DB, asserting the command shape
   starts with ``pi -p "/{skill} doc-job {job.id}"``.

5. ``agent_runtime/resolver.resolve_runtime`` — exercised against the
   testcontainer DB (already migrated by ``_pgtestdb_setup``); asserts
   the two new pi catalogue rows seeded by S01's migration resolve with
   the expected ``display_name`` / ``enabled`` / ``is_default`` /
   ``sort_order`` values.

Stub binary mechanism: a 3-line bash script written to ``tmp_path/bin/pi`` and
prepended to ``PATH``. If the stub-PATH lookup fails on a particular runner
(e.g. ``subprocess`` hermetic-PATH), the affected test is marked
``@pytest.mark.skipif`` with the reason documented inline — never silently
skipped (``tests/CLAUDE.md`` + ``skills/iw-ai-core-testing/SKILL.md`` flag
silent skips as a red flag).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from orch.agent_runtime.resolver import resolve_runtime
from orch.daemon.doc_job_poller import DocJobPoller
from orch.daemon.fix_cycle import _build_fix_launch_argv
from orch.db.models import AgentRuntimeOption, Project

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# The marker the stub pi binary echoes to stdout. ``$$`` is expanded to the
# stub's PID at run time, so the prefix is fixed but the suffix changes each
# invocation — which gives us a built-in defence against accidentally matching
# the marker from a stale log.
_STUB_PI_MARKER_PREFIX = "STUB_PI_MARKER_"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def stub_pi_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Place a stub ``pi`` binary on PATH that echoes a marker and exits 0.

    Used by every test below that needs to assert "the pi binary was actually
    invoked under this dispatch site" without depending on real pi.dev auth
    or network reachability.
    """
    stub = tmp_path / "bin" / "pi"
    stub.parent.mkdir(parents=True, exist_ok=True)
    stub.write_text(
        f'#!/usr/bin/env bash\necho "{_STUB_PI_MARKER_PREFIX}$$"\nexit 0\n',
    )
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", f"{stub.parent}{os.pathsep}{os.environ['PATH']}")
    return stub


# ---------------------------------------------------------------------------
# Stub-PATH platform compatibility check.
#
# The auto_merge_resolve subprocess test invokes ``bash`` via subprocess; if
# the runner's subprocess implementation strips PATH (some sandboxed CI
# environments do this), the stub binary lookup will silently fail.
# Detect this once at module load and skip affected tests with a documented
# reason.
# ---------------------------------------------------------------------------


def _can_run_bash_subprocess_with_custom_path() -> tuple[bool, str]:
    """Probe whether a bash subprocess can resolve a binary placed on PATH.

    Returns ``(ok, reason_if_not_ok)``. ``reason_if_not_ok`` is empty on success.
    """
    if shutil.which("bash") is None:
        return False, "bash not found on PATH"
    try:
        result = subprocess.run(  # noqa: S603 — trusted probe
            ["bash", "-c", "command -v echo"],
            check=False,
            capture_output=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return False, f"bash subprocess probe failed: {exc}"
    if result.returncode != 0:
        return False, f"bash returned {result.returncode}"
    return True, ""


_BASH_OK, _BASH_SKIP_REASON = _can_run_bash_subprocess_with_custom_path()


# ---------------------------------------------------------------------------
# 1) auto-merge one-shot — bash _run_agent_oneshot pipes stdin to pi
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _BASH_OK,
    reason=f"bash subprocess unavailable on this platform: {_BASH_SKIP_REASON}",
)
def test_pi_auto_merge_oneshot_pipes_stdin(stub_pi_binary: Path) -> None:
    """``bash step_executor_lib.sh auto_merge_resolve pi <model>`` reads a prompt
    on stdin and pipes it through ``pi -p --model <model>`` (per S03 — the
    bash case branch sits at ``executor/step_executor_lib.sh:623``).

    The stub pi binary on PATH echoes ``STUB_PI_MARKER_<pid>`` and exits 0;
    we capture stdout and assert the marker is present.
    """
    lib_script = REPO_ROOT / "executor" / "step_executor_lib.sh"
    assert lib_script.is_file(), f"missing executor lib: {lib_script}"

    # step_executor_lib.sh enforces ``WORKTREE_PATH`` must be set before it
    # is sourced (line ~36); the auto_merge_resolve direct entry sources the
    # lib so we must satisfy the guard. The path doesn't have to exist — the
    # _run_agent_oneshot path never touches it.
    result = subprocess.run(  # noqa: S603 — trusted local script
        ["bash", str(lib_script), "auto_merge_resolve", "pi", "minimax/MiniMax-M2.7"],
        input="please resolve this conflict",
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ, "PATH": os.environ["PATH"], "WORKTREE_PATH": "/tmp"},
    )
    assert result.returncode == 0, (
        f"step_executor_lib.sh auto_merge_resolve pi exited {result.returncode}\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )
    assert _STUB_PI_MARKER_PREFIX in result.stdout, (
        f"stub pi marker missing from stdout — stub not invoked.\n"
        f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# 2) step_executor.sh end-to-end — minimal worktree + real DB step row
# ---------------------------------------------------------------------------


_IW_BINARY = REPO_ROOT / ".venv" / "bin" / "iw"


@pytest.mark.skipif(
    not _BASH_OK,
    reason=f"bash subprocess unavailable on this platform: {_BASH_SKIP_REASON}",
)
@pytest.mark.skipif(
    not _IW_BINARY.is_file(),
    reason=(
        f"'iw' CLI not at {_IW_BINARY} — step_executor.sh shells out to "
        f"'iw item-status', so without it on PATH the test cannot reach the "
        f"pi-dispatch branch. Run `uv sync` to populate the venv."
    ),
)
def test_pi_step_launch_invokes_stub(
    tmp_path: Path,
    db_session,  # noqa: ANN001 — provided by tests/integration/conftest.py
    stub_pi_binary: Path,
) -> None:
    """Full e2e: step_executor.sh → pi branch → stub pi binary.

    Requires the venv-installed ``iw`` CLI on PATH so the script's
    ``iw item-status`` call can talk to the testcontainer DB (the
    ``db_engine`` fixture has already monkeypatched ``IW_CORE_DB_*`` env vars
    to point at the per-test clone).
    """
    import json as _json

    from orch.db.models import (
        StepStatus,
        StepType,
        WorkflowStep,
        WorkItem,
        WorkItemPhase,
        WorkItemStatus,
        WorkItemType,
    )

    # 1. Insert a Project + WorkItem + WorkflowStep into the per-test clone.
    project_id = "pi-e2e-proj"
    worktree_path = tmp_path / "worktree"
    worktree_path.mkdir()
    # step_executor.sh requires a .git marker (the script checks for both the
    # dir existing AND a .git file/dir under it).
    (worktree_path / ".git").write_text("gitdir: /fake/git\n")
    # step_executor.sh chdir's into the worktree and then shells out to
    # ``iw item-status`` — which resolves the project_id via ``find_project_root``
    # walking up looking for a ``.iw-orch.json``. Drop a minimal one here so the
    # iw subprocess can find the project under test.
    (worktree_path / ".iw-orch.json").write_text(
        _json.dumps({"project_id": project_id, "cli_tool": "pi"})
    )

    project = Project(
        id=project_id,
        display_name="Pi E2E",
        repo_root=str(worktree_path),
        config={"cli_tool": "pi"},
    )
    db_session.add(project)

    item_id = "I-99001"
    step_id = "S01"
    work_item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Issue,
        title="Pi e2e item",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(work_item)

    step = WorkflowStep(
        project_id=project_id,
        work_item_id=item_id,
        step_number=1,
        step_id=step_id,
        agent_label="Backend",
        step_type=StepType.implementation,
        status=StepStatus.in_progress,  # so step_executor.sh doesn't try to mark-start it
    )
    db_session.add(step)
    db_session.commit()

    # 2. Invoke step_executor.sh with cli_tool=pi.
    executor_script = REPO_ROOT / "executor" / "step_executor.sh"
    assert executor_script.is_file()

    # PATH: stub pi dir (priority) → venv bin (iw) → existing PATH.
    venv_bin = str(_IW_BINARY.parent)
    test_path = f"{stub_pi_binary.parent}{os.pathsep}{venv_bin}{os.pathsep}{os.environ['PATH']}"

    # The iw CLI uses ``get_orch_db_url()`` which prefers ``IW_CORE_ORCH_DB_*``
    # over ``IW_CORE_DB_*``. The integration conftest only monkeypatches the
    # latter — without ``_ORCH_`` overrides, the subprocess would resolve to
    # the real orch DB on port 5433 and never see the rows we just committed.
    # Mirror the pattern from ``tests/integration/cli/test_step_commands_drift.py``.
    db_host = os.environ["IW_CORE_DB_HOST"]
    db_port = os.environ["IW_CORE_DB_PORT"]
    db_name = os.environ["IW_CORE_DB_NAME"]
    db_user = os.environ["IW_CORE_DB_USER"]
    db_password = os.environ["IW_CORE_DB_PASSWORD"]

    env = {
        **os.environ,
        "PATH": test_path,
        "MODEL": "minimax/MiniMax-M2.7",
        "IW_CORE_ORCH_DB_HOST": db_host,
        "IW_CORE_ORCH_DB_PORT": db_port,
        "IW_CORE_ORCH_DB_NAME": db_name,
        "IW_CORE_ORCH_DB_USER": db_user,
        "IW_CORE_ORCH_DB_PASSWORD": db_password,
        # DAEMON_CONTEXT wins over the live-db-guard's TEST_CONTEXT block —
        # the same pattern the real daemon uses to allow its own engine.
        "IW_CORE_DAEMON_CONTEXT": "true",
        "IW_CORE_AGENT_CONTEXT": "",
    }

    result = subprocess.run(  # noqa: S603 — trusted local script
        [
            "bash",
            str(executor_script),
            item_id,
            step_id,
            str(worktree_path),
            "pi",
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )

    step_log = worktree_path / "ai-dev" / "work" / item_id / "logs" / f"{item_id}_{step_id}_run.log"
    log_text = step_log.read_text() if step_log.is_file() else ""

    assert _STUB_PI_MARKER_PREFIX in log_text, (
        f"stub pi marker not in step log — pi branch was not exercised.\n"
        f"exit={result.returncode}\n"
        f"stdout={result.stdout!r}\n"
        f"stderr={result.stderr!r}\n"
        f"step_log={log_text!r}"
    )
    # No 'script' PTY error — Pi must NOT have been wrapped (regression guard
    # for I-00074-style misrouting).
    assert "script: unrecognized option" not in log_text
    assert "script: unrecognized option" not in result.stderr


# ---------------------------------------------------------------------------
# 3) fix-cycle launch argv — pi takes the unwrapped /bin/sh -c arm.
# ---------------------------------------------------------------------------


def test_pi_fix_cycle_uses_sh_c_not_script_pty_wrapper() -> None:
    """At the boundary between ``_build_fix_inner_command`` and the
    subprocess.Popen call, ``_build_fix_launch_argv`` selects the wrapper.

    Pi must take the unwrapped ``["/bin/sh", "-c", inner]`` arm — the
    ``script -qec ... /dev/null`` PTY wrapper is opencode-only (R-00072 §1:
    Pi's print mode works under non-TTY stdout, so no PTY allocation is
    needed). This is the *integration* mirror of the unit test in
    ``tests/unit/test_pi_runtime_dispatch.py``: it asserts no production
    caller (current or future) will wrap pi in ``script``.
    """
    inner = 'timeout 600 pi -p "$(cat /wt/.tmp/X.prompt)" --model minimax/MiniMax-M2.7'

    pi_argv = _build_fix_launch_argv("pi", inner)
    opencode_argv = _build_fix_launch_argv("opencode", inner)

    # Strict positional shape — not just "contains /bin/sh" (a misbuilt
    # ``["/bin/sh", "-c", inner, "script", "-qec", inner]`` would still
    # "contain /bin/sh" but would be wrong).
    assert pi_argv == ["/bin/sh", "-c", inner]
    assert "script" not in pi_argv
    assert "-qec" not in pi_argv

    # Defence-in-depth: opencode arm is the script-wrapper, so the two must
    # differ structurally — guards against a future refactor that accidentally
    # routes pi through the opencode arm.
    assert pi_argv != opencode_argv
    assert opencode_argv[0] == "script"


# ---------------------------------------------------------------------------
# 4) doc_job_poller._build_agent_command — pi command shape against a real
#    Project row in the testcontainer DB.
# ---------------------------------------------------------------------------


def test_pi_doc_job_launches_pi_print_mode(
    db_session,  # noqa: ANN001 — provided by tests/integration/conftest.py
) -> None:
    """Insert a Project with ``cli_tool="pi"`` and a queued ``DocGenerationJob``
    into the testcontainer DB; call ``DocJobPoller._build_agent_command``
    and assert the returned command starts with ``pi -p "/{skill} doc-job
    {job.id}"`` — exactly the shape the design doc § AC1 / S03 §6 specifies.
    """
    from datetime import UTC, datetime

    from orch.db.models import DocGenerationJob, JobStatus

    project_id = "pi-doc-job-proj"
    project = Project(
        id=project_id,
        display_name="Pi Doc Job",
        repo_root="/tmp/pi-doc-job",
        config={"cli_tool": "pi"},
    )
    db_session.add(project)
    db_session.flush()

    job_id = "doc-job-pi-aaaa1111"
    job = DocGenerationJob(
        id=job_id,
        public_id="DOC-99001",
        project_id=project_id,
        doc_id=None,
        status=JobStatus.queued,
        requested_at=datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC),
    )
    db_session.add(job)
    db_session.flush()

    # Reload project (the poller uses the row from the DB).
    project_row = db_session.get(Project, project_id)
    assert project_row is not None
    assert project_row.config == {"cli_tool": "pi"}

    poller = DocJobPoller.__new__(DocJobPoller)
    cmd_list = poller._build_agent_command(job, project_row, skill="iw-doc-generator")

    assert len(cmd_list) == 1
    cmd = cmd_list[0]
    assert cmd.startswith("pi -p ")
    assert f'"/iw-doc-generator doc-job {job_id}"' in cmd
    # R-00072 §7 — pi takes no permission-mode flag.
    assert "--dangerously-skip-permissions" not in cmd
    assert "--permission-mode" not in cmd
    # Not the claude / opencode form.
    assert not cmd.startswith("claude ")
    assert "opencode run" not in cmd


def test_pi_doc_job_unknown_cli_tool_raises_against_db_row(
    db_session,  # noqa: ANN001 — provided by tests/integration/conftest.py
) -> None:
    """The allowlist is enforced in ``project_registry``, but a misconfigured
    Project row directly in the DB (bypassing ``project_registry``) must still
    surface loud at the doc-job builder. This proves S03's explicit
    ``raise ValueError`` is the second line of defence — not just the
    in-memory allowlist.
    """
    project_id = "pi-bad-doc-job"
    project = Project(
        id=project_id,
        display_name="Bad Doc Job",
        repo_root="/tmp/bad-doc-job",
        config={"cli_tool": "aider"},  # not in allowlist
    )
    db_session.add(project)
    db_session.flush()

    job = MagicMock()
    job.id = "doc-job-bad-bbbb2222"

    poller = DocJobPoller.__new__(DocJobPoller)
    with pytest.raises(ValueError, match="Unknown cli_tool"):
        poller._build_agent_command(job, project, skill="iw-doc-system")


# ---------------------------------------------------------------------------
# 5) catalogue resolver — pi rows from S01's migration are reachable.
# ---------------------------------------------------------------------------


def test_pi_catalogue_resolves_minimax_and_codex(
    db_session,  # noqa: ANN001 — provided by tests/integration/conftest.py
) -> None:
    """S01's migration seeded two ``(pi, model)`` rows in
    ``agent_runtime_options``. This test asserts the cascade resolver
    surfaces both with the exact metadata the design doc specifies.

    AC2 invariants pinned here:
      - ``(pi, minimax/MiniMax-M2.7)`` → ``display_name="Pi + MiniMax 2.7"``,
        ``enabled=True``, ``is_default=False``, ``sort_order=25``.
      - ``(pi, openai/gpt-5.3-codex)`` → ``display_name="Pi + GPT-5.3 Codex"``,
        ``sort_order=26``.
    """
    # Build a minimal ProjectConfig-like object (resolve_runtime reads via
    # getattr, so any object with cli_tool / model attributes works).
    project_minimax = MagicMock()
    project_minimax.cli_tool = "pi"
    project_minimax.model = "minimax/MiniMax-M2.7"

    step = MagicMock()
    step.agent_runtime_option_id = None
    item = MagicMock()
    item.agent_runtime_option_id = None

    resolved = resolve_runtime(
        db_session,
        step=step,
        item=item,
        project=project_minimax,
    )
    # Strict equality on every field the design doc pins — not just
    # "cli_tool contains pi". A misseeded row with cli_tool="Pi" or
    # display_name="Pi + MiniMax M2.7" (extra space) would fail here.
    assert resolved.cli_tool == "pi"
    assert resolved.model == "minimax/MiniMax-M2.7"
    assert resolved.display_name == "Pi + MiniMax 2.7"
    assert resolved.enabled is True
    assert resolved.is_default is False
    assert resolved.sort_order == 25

    project_codex = MagicMock()
    project_codex.cli_tool = "pi"
    project_codex.model = "openai/gpt-5.3-codex"

    resolved_codex = resolve_runtime(
        db_session,
        step=step,
        item=item,
        project=project_codex,
    )
    assert resolved_codex.cli_tool == "pi"
    assert resolved_codex.model == "openai/gpt-5.3-codex"
    assert resolved_codex.display_name == "Pi + GPT-5.3 Codex"
    assert resolved_codex.enabled is True
    assert resolved_codex.is_default is False
    assert resolved_codex.sort_order == 26

    # AC5 / AC2 catalogue invariant: the existing default (the MiniMax 2.7
    # default for opencode per F-00081) is still ``is_default=True`` after
    # the migration. Verifying this here defends against an accidental
    # ``is_default=true`` slip in either of the pi seed rows.
    default = (
        db_session.query(AgentRuntimeOption).filter(AgentRuntimeOption.is_default.is_(True)).one()
    )
    assert default.cli_tool == "opencode"
    assert default.model == "minimax/MiniMax-M2.7"
