"""Utility for capturing agent log files into StepRun.log_content."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from orch.db.models import StepRun

logger = logging.getLogger(__name__)

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

DEFAULT_MAX_BYTES = 2 * 1024 * 1024  # 2 MB


def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return _ANSI_RE.sub("", text)


def capture_log_content(step_run: StepRun, max_bytes: int = DEFAULT_MAX_BYTES) -> None:
    """Read the log file from disk and store its content in step_run.log_content.

    - Strips ANSI escape codes
    - Truncates to *max_bytes* from the tail if the file is too large
    - No-op if log_file is None
    - Graceful if the file is missing or unreadable
    """
    if step_run.log_file is None:
        return

    path = Path(step_run.log_file)
    if not path.is_file():
        step_run.log_content = f"[Log file not found: {step_run.log_file}]"
        return

    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        step_run.log_content = f"[Error reading log file: {exc}]"
        logger.warning("Failed to read log file %s: %s", path, exc)
        return

    cleaned = strip_ansi(raw)

    if len(cleaned.encode("utf-8")) > max_bytes:
        # Keep the tail — most useful info is at the end
        total_size = len(cleaned.encode("utf-8"))
        header = f"[truncated: showing last ~2MB of {total_size:,} bytes]\n"
        # Slice from the end; slightly approximate since we slice chars not bytes
        tail = cleaned[-max_bytes:]
        # Find the first newline to avoid a partial first line
        nl = tail.find("\n")
        if nl != -1:
            tail = tail[nl + 1 :]
        step_run.log_content = header + tail
    else:
        step_run.log_content = cleaned
