"""CR-00062 — Pi (pi.dev) dispatch argv builders for all three runtimes.

These tests pin the per-cli_tool argv shape produced by the daemon's initial
step launcher, the fix-cycle inner-command builder, the fix-cycle launch-argv
wrapper, the doc-job poller command builder, and the doc-service inline
command-issued builder. They exist primarily to guard the ``pi`` branch
(added by CR-00062), but every case is parametrised so a future regression
in the claude/opencode branches surfaces here too.

The RED-phase evidence for CR-00062 S03 was the
``test_build_initial_command_pi_uses_pi_print_mode`` assertion failing because
``_build_initial_command`` fell through to the claude branch for ``cli_tool="pi"``.

For S05, additional coverage was added so every dispatch site is parametrised
across ``cli_tool ∈ {"opencode", "claude", "pi"}`` and each site that S03 made
strict on unknown ``cli_tool`` carries a negative test (``raise ValueError``).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from orch.daemon.batch_manager import _build_initial_command
from orch.daemon.doc_job_poller import DocJobPoller
from orch.daemon.fix_cycle import _build_fix_inner_command, _build_fix_launch_argv

# ---------------------------------------------------------------------------
# batch_manager._build_initial_command (3 cli_tools + 1 unknown = 4 tests)
# ---------------------------------------------------------------------------


def test_build_initial_command_opencode_shape() -> None:
    cmd = _build_initial_command(
        cli_tool="opencode",
        prompt_file="/wt/.tmp/X_S01.prompt",
        resolved_model="minimax/MiniMax-M2.7",
        agent_args="--agent backend-impl",
    )
    assert cmd.startswith("opencode run ")
    assert '"$(cat /wt/.tmp/X_S01.prompt)"' in cmd
    assert "--model minimax/MiniMax-M2.7" in cmd
    assert "--dangerously-skip-permissions" in cmd
    assert "--agent backend-impl" in cmd
    # opencode is the only runtime that takes the PTY wrap downstream — make
    # sure the initial command itself isn't yet wrapped.
    assert "script -qec" not in cmd
    assert "/bin/sh -c" not in cmd


def test_build_initial_command_claude_shape() -> None:
    cmd = _build_initial_command(
        cli_tool="claude",
        prompt_file="/wt/.tmp/X_S01.prompt",
        resolved_model="anthropic/claude-sonnet-4-6",
        agent_args="",
    )
    assert cmd.startswith("claude -p ")
    assert '"$(cat /wt/.tmp/X_S01.prompt)"' in cmd
    assert "--model anthropic/claude-sonnet-4-6" in cmd
    assert "--dangerously-skip-permissions" in cmd
    # Claude must not be confused with opencode — neither `opencode` nor the
    # PTY wrapper should appear in the claude arm.
    assert "opencode" not in cmd
    assert "script -qec" not in cmd


def test_build_initial_command_pi_uses_pi_print_mode() -> None:
    """RED-phase assertion for CR-00062 S03.

    Before the pi branch landed, this assertion failed with:
        AssertionError: assert "pi -p" in cmd
    because the helper fell through to the claude branch and produced
    ``claude -p "$(cat ...)"`` instead.
    """
    cmd = _build_initial_command(
        cli_tool="pi",
        prompt_file="/wt/.tmp/X_S01.prompt",
        resolved_model="minimax/MiniMax-M2.7",
        agent_args="",
    )
    # Strict positional shape: ``pi -p "$(cat …)" --model <model>``. Just
    # asserting "pi" in cmd would pass for ``pi-broken -p`` or ``mpi -p`` —
    # those would still be wrong even though they "contain pi".
    assert cmd.startswith("pi -p ")
    assert '"$(cat /wt/.tmp/X_S01.prompt)"' in cmd
    assert "--model minimax/MiniMax-M2.7" in cmd
    # Pi gates capabilities via extension permissions, not a CLI flag — see
    # R-00072 §7. No ``--dangerously-skip-permissions`` / ``--permission-mode``.
    assert "--dangerously-skip-permissions" not in cmd
    assert "--permission-mode" not in cmd
    # Must not have fallen through to the claude / opencode branches.
    assert not cmd.startswith("claude ")
    assert "opencode run" not in cmd


def test_build_initial_command_unknown_cli_tool_raises() -> None:
    """S03 made unknown ``cli_tool`` fail loud — guard the ``ValueError`` text
    so a future refactor doesn't quietly revert to the lenient
    ``else: claude form`` fall-through that masked I-00074-style typos.
    """
    with pytest.raises(ValueError, match="Unknown cli_tool"):
        _build_initial_command(
            cli_tool="aider",
            prompt_file="/wt/.tmp/X.prompt",
            resolved_model="some/model",
            agent_args="",
        )


# ---------------------------------------------------------------------------
# fix_cycle._build_fix_inner_command (3 cli_tools + 1 unknown = 4 tests)
# ---------------------------------------------------------------------------


def test_build_fix_inner_command_opencode_shape() -> None:
    cmd = _build_fix_inner_command(
        cli_tool="opencode",
        prompt_path="/wt/.tmp/I-00074_S06_fix1.prompt",
        resolved_model="minimax/MiniMax-M2.7",
    )
    assert cmd.startswith("opencode run ")
    assert '"$(cat /wt/.tmp/I-00074_S06_fix1.prompt)"' in cmd
    assert "--model minimax/MiniMax-M2.7" in cmd
    assert "--dangerously-skip-permissions" in cmd


def test_build_fix_inner_command_claude_shape() -> None:
    cmd = _build_fix_inner_command(
        cli_tool="claude",
        prompt_path="/wt/.tmp/I-00074_S06_fix1.prompt",
        resolved_model="anthropic/claude-sonnet-4-6",
    )
    assert cmd.startswith("claude -p ")
    assert '"$(cat /wt/.tmp/I-00074_S06_fix1.prompt)"' in cmd
    assert "--model anthropic/claude-sonnet-4-6" in cmd
    assert "--dangerously-skip-permissions" in cmd
    assert "opencode" not in cmd


def test_build_fix_inner_command_pi_shape() -> None:
    cmd = _build_fix_inner_command(
        cli_tool="pi",
        prompt_path="/wt/.tmp/I-00074_S06_fix1.prompt",
        resolved_model="minimax/MiniMax-M2.7",
    )
    assert cmd.startswith("pi -p ")
    assert '"$(cat /wt/.tmp/I-00074_S06_fix1.prompt)"' in cmd
    assert "--model minimax/MiniMax-M2.7" in cmd
    # R-00072 §7: no permission-mode flag in Pi arm.
    assert "--dangerously-skip-permissions" not in cmd
    assert "--permission-mode" not in cmd
    assert not cmd.startswith("claude ")


def test_build_fix_inner_command_unknown_cli_tool_raises() -> None:
    """Mirror of ``_build_initial_command``: S03 made unknown ``cli_tool`` fail
    loud here too, since drift between these two helpers is exactly how
    I-00074 surfaced (see ``_build_fix_inner_command`` docstring).
    """
    with pytest.raises(ValueError, match="Unknown cli_tool"):
        _build_fix_inner_command(
            cli_tool="aider",
            prompt_path="/wt/.tmp/X.prompt",
            resolved_model="some/model",
        )


# ---------------------------------------------------------------------------
# fix_cycle._build_fix_launch_argv (3 cli_tools — pi falls into /bin/sh -c arm)
# ---------------------------------------------------------------------------


def test_build_fix_launch_argv_opencode_wraps_with_script_pty() -> None:
    """opencode behaves differently without a controlling TTY, so it is
    wrapped in ``script -qec <inner> /dev/null`` (regression guard for
    I-00074).
    """
    inner = 'timeout 600 opencode run "$(cat /wt/.tmp/X.prompt)" --model x/y'
    argv = _build_fix_launch_argv("opencode", inner)
    assert argv == ["script", "-qec", inner, "/dev/null"]


def test_build_fix_launch_argv_claude_uses_sh_c_no_pty_wrap() -> None:
    """claude takes the unwrapped ``/bin/sh -c <inner>`` arm — no PTY wrap."""
    inner = 'timeout 600 claude -p "$(cat /wt/.tmp/X.prompt)" --model anthropic/claude-sonnet-4-6'
    argv = _build_fix_launch_argv("claude", inner)
    assert argv == ["/bin/sh", "-c", inner]
    assert "script" not in argv


def test_build_fix_launch_argv_pi_uses_sh_c_no_pty_wrap() -> None:
    """Pi's print mode works under non-TTY stdout (R-00072 §1), so it falls
    into the same ``/bin/sh -c <inner>`` arm as claude. The ``script -qec
    ... /dev/null`` PTY wrapper is opencode-only — Pi must not be wrapped.
    """
    inner = 'timeout 600 pi -p "$(cat /wt/.tmp/X.prompt)" --model minimax/MiniMax-M2.7'
    argv = _build_fix_launch_argv("pi", inner)
    assert argv == ["/bin/sh", "-c", inner]
    assert "script" not in argv
    assert "-qec" not in argv


# ---------------------------------------------------------------------------
# doc_job_poller._build_agent_command (3 cli_tools + 1 unknown = 4 tests)
# ---------------------------------------------------------------------------


def _make_poller_with_project(cli_tool: str | None) -> tuple[DocJobPoller, MagicMock, MagicMock]:
    """Build a poller + project + job suitable for ``_build_agent_command``."""
    project = MagicMock()
    project.config = {} if cli_tool is None else {"cli_tool": cli_tool}

    job = MagicMock()
    job.id = "doc-job-abc123"

    poller = DocJobPoller.__new__(DocJobPoller)
    return poller, project, job


def test_doc_job_build_agent_command_opencode() -> None:
    poller, project, job = _make_poller_with_project("opencode")
    cmd_list = poller._build_agent_command(job, project, skill="iw-doc-generator")
    assert len(cmd_list) == 1
    cmd = cmd_list[0]
    assert cmd.startswith("opencode run ")
    assert '"/iw-doc-generator doc-job doc-job-abc123"' in cmd
    assert "--dangerously-skip-permissions" in cmd


def test_doc_job_build_agent_command_claude() -> None:
    poller, project, job = _make_poller_with_project("claude")
    cmd_list = poller._build_agent_command(job, project, skill="iw-doc-system")
    assert len(cmd_list) == 1
    cmd = cmd_list[0]
    assert cmd.startswith("claude -p ")
    assert '"/iw-doc-system doc-job doc-job-abc123"' in cmd
    assert "--permission-mode bypassPermissions" in cmd


def test_doc_job_build_agent_command_pi() -> None:
    poller, project, job = _make_poller_with_project("pi")
    cmd_list = poller._build_agent_command(job, project, skill="iw-doc-generator")
    assert len(cmd_list) == 1
    cmd = cmd_list[0]
    # Strict positional shape: ``pi -p "/{skill} doc-job {job.id}"``.
    assert cmd.startswith("pi -p ")
    assert '"/iw-doc-generator doc-job doc-job-abc123"' in cmd
    # R-00072 §7: Pi takes no permission-mode flag.
    assert "--dangerously-skip-permissions" not in cmd
    assert "--permission-mode" not in cmd
    assert not cmd.startswith("claude ")


def test_doc_job_build_agent_command_unknown_cli_tool_raises() -> None:
    poller, project, job = _make_poller_with_project("aider")
    with pytest.raises(ValueError, match="Unknown cli_tool"):
        poller._build_agent_command(job, project, skill="iw-doc-system")


# ---------------------------------------------------------------------------
# doc_service.complete_doc_job inline command-issued shape (CR-00062 S03).
#
# There is no extracted ``_build_command`` helper in doc_service — the
# per-cli_tool dispatch is inline inside ``complete_doc_job``. We test
# the inline branch by driving ``complete_doc_job`` with a mock session
# and asserting on the ``report["command_issued"]`` field.
# ---------------------------------------------------------------------------


def _make_doc_service_with_project_cli_tool(cli_tool: str | None) -> tuple[MagicMock, MagicMock]:
    """Build a (session, job) pair that drives ``complete_doc_job`` happy path."""
    from datetime import UTC, datetime

    from orch.db.models import JobStatus

    session = MagicMock()
    job = MagicMock()
    job.id = "doc-job-svc-xyz"
    job.status = JobStatus.running
    job.doc_id = None  # short-circuits the doc-lint branch
    job.started_at = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
    job.lint_warnings = None
    job.skill_used = "iw-doc-generator"
    job.duration_seconds = 5
    job.project_id = "test-proj"
    # ``report`` is set as an attribute on the job inside complete_doc_job; we
    # capture the assigned value via the mock's attribute assignment.

    project = MagicMock()
    project.config = {} if cli_tool is None else {"cli_tool": cli_tool}
    project.repo_root = "/nonexistent-test-repo-root-for-complete-doc-job"

    # session.get(DocGenerationJob, id) → job; session.get(Project, id) → project.
    # ``doc_id is None`` so ProjectDoc.get is not called.
    def _session_get(model: object, _id: str) -> object:
        from orch.db.models import DocGenerationJob, Project

        if model is DocGenerationJob:
            return job
        if model is Project:
            return project
        return None

    session.get.side_effect = _session_get
    return session, job


@pytest.mark.parametrize(
    ("cli_tool", "expected_prefix"),
    [
        ("opencode", 'opencode run "/doc-job doc-job-svc-xyz" --dangerously-skip-permissions'),
        ("claude", 'claude -p "/doc-job doc-job-svc-xyz" --permission-mode bypassPermissions'),
        ("pi", 'pi -p "/doc-job doc-job-svc-xyz"'),
    ],
)
def test_doc_service_complete_doc_job_command_issued_shape(
    cli_tool: str, expected_prefix: str
) -> None:
    """The ``command_issued`` field embedded in the report is the
    audit-trail proof that the doc-service dispatch picked the right per-runtime
    shape. The pi arm carries no ``--dangerously-skip-permissions`` and no
    ``--permission-mode``.
    """
    from orch.doc_service import DocService

    session, job = _make_doc_service_with_project_cli_tool(cli_tool)
    svc = DocService(session)
    svc.complete_doc_job("doc-job-svc-xyz")

    # job.report was set by complete_doc_job — verify command_issued shape.
    assert isinstance(job.report, dict)
    cmd = job.report["command_issued"]
    assert cmd == expected_prefix
    # Defensive: cli_tool key in report must match the project's runtime.
    assert job.report["cli_tool"] == cli_tool


def test_doc_service_complete_doc_job_unknown_cli_tool_raises() -> None:
    from orch.doc_service import DocService

    session, _ = _make_doc_service_with_project_cli_tool("aider")
    svc = DocService(session)
    with pytest.raises(ValueError, match="Unknown cli_tool"):
        svc.complete_doc_job("doc-job-svc-xyz")
