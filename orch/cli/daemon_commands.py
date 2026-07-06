"""Daemon control commands.

Commands: daemon start, daemon stop, daemon status.
"""

from __future__ import annotations

import json
import os
import signal
import time
from pathlib import Path
from typing import Any

import click
from sqlalchemy import func, select

import orch.config  # noqa: F401 — triggers load_dotenv() so IW_CORE_PID_FILE is in os.environ
from orch.cli.utils import output_error
from orch.db.models import Batch, BatchStatus, DaemonEvent, Project, StepStatus, WorkflowStep

_ACTIVE_BATCH_STATUSES: list[BatchStatus] = [
    BatchStatus.executing,
    BatchStatus.publishing,
]


# ---------------------------------------------------------------------------
# PID file helpers (pure — used by unit tests)
# ---------------------------------------------------------------------------


def get_pid_file_path() -> Path:
    """Return the daemon PID file path from IW_CORE_PID_FILE or a default.

    A **relative** ``IW_CORE_PID_FILE`` is resolved against the IW AI Core repo
    root (``orch.config.CORE_ROOT``), NOT the current working directory, so the
    daemon, the ``iw`` CLI, and the MCP server all agree on one absolute path
    regardless of where each was launched. A CWD-relative default (``.daemon.pid``)
    previously caused a split-brain: a daemon started with its CWD inside a
    worktree wrote its PID file there, so ``./ai-core.sh`` (checking the repo
    root) could not see it and started a second daemon, while the ``iw-mcp``
    server — running from yet another CWD — reported the daemon as stopped.
    (Diagnosed 2026-07-06.)

    Returns:
        Absolute path to the daemon PID file.
    """
    pid_file = os.environ.get("IW_CORE_PID_FILE")
    if pid_file:
        path = Path(pid_file)
        if not path.is_absolute():
            path = orch.config.CORE_ROOT / path
        return path
    return Path("/tmp/iw-orch-daemon.pid")  # noqa: S108  # nosec B108


def read_pid(pid_file: Path) -> int | None:
    """Read PID from file. Returns None if file is missing or contents are invalid."""
    try:
        return int(pid_file.read_text().strip())
    except (OSError, ValueError):
        return None


def is_process_alive(pid: int) -> bool:
    """Check if a process is alive via os.kill(pid, 0). Returns False if not found."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------


@click.group("daemon")
def daemon() -> None:
    """Control the IW AI Core orchestration daemon."""


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@daemon.command("start")
@click.option("--foreground", is_flag=True, help="Run in foreground (don't daemonize)")
@click.pass_context
def start(ctx: click.Context, foreground: bool) -> None:
    """Start the orchestration daemon."""
    pid_file = get_pid_file_path()

    existing_pid = read_pid(pid_file)
    if existing_pid is not None and is_process_alive(existing_pid):
        output_error(ctx, f"Daemon is already running (PID {existing_pid})", 1)

    if foreground:
        from orch.config import load_config  # noqa: PLC0415
        from orch.daemon.main import Daemon, DaemonAlreadyRunning  # noqa: PLC0415

        try:
            config = load_config()
        except RuntimeError as exc:
            output_error(ctx, f"Configuration error: {exc}", 1)

        try:
            Daemon(config).run()
        except DaemonAlreadyRunning as exc:
            output_error(ctx, str(exc), 1)
        return

    # Background start: spawn subprocess and write PID file
    import subprocess  # noqa: PLC0415
    import sys  # noqa: PLC0415

    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "orch.daemon"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # The daemon subprocess writes its own PID file during _startup().
    # We do NOT write the PID file here to avoid a race condition where
    # the daemon reads its own PID and raises DaemonAlreadyRunning.
    # Wait briefly to confirm the subprocess is still alive.
    time.sleep(1)
    if proc.poll() is not None:
        output_error(ctx, "Daemon subprocess exited immediately — check logs", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps({"status": "started", "pid": proc.pid}))
    else:
        click.echo(f"Daemon started (PID {proc.pid})")


@daemon.command("stop")
@click.pass_context
def stop(ctx: click.Context) -> None:
    """Stop the running daemon gracefully (SIGTERM, wait up to 30s)."""
    pid_file = get_pid_file_path()
    pid = read_pid(pid_file)

    if pid is None:
        output_error(ctx, "Daemon PID file not found — is the daemon running?", 1)

    if not is_process_alive(pid):
        pid_file.unlink(missing_ok=True)
        output_error(ctx, f"Daemon (PID {pid}) is not running — removed stale PID file", 1)

    os.kill(pid, signal.SIGTERM)
    for _ in range(30):
        time.sleep(1)
        if not is_process_alive(pid):
            break
    else:
        output_error(ctx, f"Daemon (PID {pid}) did not stop within 30 seconds", 1)

    pid_file.unlink(missing_ok=True)

    if ctx.obj.get("json"):
        click.echo(json.dumps({"status": "stopped", "pid": pid}))
    else:
        click.echo(f"Daemon stopped (PID {pid})")


@daemon.command("status")
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show daemon health and operational statistics."""
    pid_file = get_pid_file_path()
    pid = read_pid(pid_file)
    is_running = pid is not None and is_process_alive(pid)

    get_session = ctx.obj["get_session"]
    stats: dict[str, Any] = {
        "status": "running" if is_running else "stopped",
        "pid": pid if is_running else None,
    }

    try:
        with get_session() as session:
            last_poll = session.execute(
                select(DaemonEvent)
                .where(DaemonEvent.event_type == "daemon_poll")
                .order_by(DaemonEvent.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()

            poll_count = session.execute(
                select(func.count(DaemonEvent.id)).where(DaemonEvent.event_type == "daemon_poll")
            ).scalar_one()

            running_steps = session.execute(
                select(func.count(WorkflowStep.id)).where(
                    WorkflowStep.status == StepStatus.in_progress
                )
            ).scalar_one()

            active_batches = session.execute(
                select(func.count())
                .select_from(Batch)
                .where(Batch.status.in_(_ACTIVE_BATCH_STATUSES))
            ).scalar_one()

            enabled_projects = session.execute(
                select(func.count(Project.id)).where(Project.enabled.is_(True))
            ).scalar_one()

            disabled_projects = session.execute(
                select(func.count(Project.id)).where(Project.enabled.is_(False))
            ).scalar_one()

            stats.update(
                {
                    "last_poll_at": (last_poll.created_at.isoformat() if last_poll else None),
                    "poll_count": poll_count,
                    "projects": {"enabled": enabled_projects, "disabled": disabled_projects},
                    "running_steps": running_steps,
                    "active_batches": active_batches,
                }
            )

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps(stats))
    else:
        pid_info = f" (PID {pid})" if is_running else ""
        click.echo(f"Daemon: {stats['status']}{pid_info}")
        projects = stats.get("projects", {})
        click.echo(
            f"  Projects: {projects.get('enabled', 0)} enabled,"
            f" {projects.get('disabled', 0)} disabled"
        )
        click.echo(
            f"  Last poll: {stats.get('last_poll_at') or 'never'}"
            f" | Poll count: {stats.get('poll_count', 0)}"
        )
        click.echo(f"  Running steps: {stats.get('running_steps', 0)}")
        click.echo(f"  Active batches: {stats.get('active_batches', 0)}")
