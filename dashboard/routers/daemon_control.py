"""Daemon control endpoints — start, stop, restart, panel refresh."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from dashboard.dependencies import get_db
from dashboard.routers.system import _daemon_status

if TYPE_CHECKING:
    from fastapi.templating import Jinja2Templates
    from sqlalchemy.orm import Session

router = APIRouter(prefix="/system/daemon")

_STOP_WAIT_SECS = 10  # max seconds to wait for graceful shutdown before returning


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_panel(request: Request, db: Session) -> HTMLResponse:
    """Render the daemon panel fragment with fresh status."""
    daemon = _daemon_status(db)
    templates: Jinja2Templates = request.app.state.templates
    return templates.TemplateResponse(
        request,
        "fragments/daemon_panel.html",
        {"daemon": daemon},
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/panel", response_class=HTMLResponse)
def daemon_panel(request: Request, db: Session = Depends(get_db)) -> Any:
    """Return the daemon status panel fragment (used for auto-refresh)."""
    return _render_panel(request, db)


@router.post("/start", response_class=HTMLResponse)
def daemon_start(request: Request, db: Session = Depends(get_db)) -> Any:
    """Start the daemon if it is not already running."""
    from orch.cli.daemon_commands import (  # noqa: PLC0415
        get_pid_file_path,
        is_process_alive,
        read_pid,
    )

    pid_file = get_pid_file_path()
    pid = read_pid(pid_file)
    if pid is not None and is_process_alive(pid):
        # Already running — just refresh the panel
        return _render_panel(request, db)

    subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "orch.daemon"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    # Brief pause so the daemon has time to write its PID file
    time.sleep(1.5)
    return _render_panel(request, db)


@router.post("/stop", response_class=HTMLResponse)
def daemon_stop(request: Request, db: Session = Depends(get_db)) -> Any:
    """Send SIGTERM to the running daemon and wait up to _STOP_WAIT_SECS."""
    from orch.cli.daemon_commands import (  # noqa: PLC0415
        get_pid_file_path,
        is_process_alive,
        read_pid,
    )

    pid_file = get_pid_file_path()
    pid = read_pid(pid_file)
    if pid is None or not is_process_alive(pid):
        return _render_panel(request, db)

    os.kill(pid, signal.SIGTERM)
    for _ in range(_STOP_WAIT_SECS):
        time.sleep(1)
        if not is_process_alive(pid):
            pid_file.unlink(missing_ok=True)
            break

    return _render_panel(request, db)


@router.post("/restart", response_class=HTMLResponse)
def daemon_restart(request: Request, db: Session = Depends(get_db)) -> Any:
    """Stop the running daemon then start a fresh one."""
    from orch.cli.daemon_commands import (  # noqa: PLC0415
        get_pid_file_path,
        is_process_alive,
        read_pid,
    )

    pid_file = get_pid_file_path()
    pid = read_pid(pid_file)

    # Stop if running
    if pid is not None and is_process_alive(pid):
        os.kill(pid, signal.SIGTERM)
        for _ in range(_STOP_WAIT_SECS):
            time.sleep(1)
            if not is_process_alive(pid):
                pid_file.unlink(missing_ok=True)
                break

    # Start fresh
    subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "orch.daemon"],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(1.5)
    return _render_panel(request, db)
