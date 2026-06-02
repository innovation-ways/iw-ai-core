"""Auto-merge LLM runtime health probe.

Periodically fires a minimal prompt against the configured LLM runtime to
verify reachability before a real merge conflict attempt. Results are stored
as DaemonEvent rows so the dashboard can surface degraded runtime status.
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select

from orch.auto_merge_aggregator import resolve_project_config
from orch.daemon.auto_merge import EVENT_AUTO_MERGE_HEALTH_PROBE, AutoMergeConfig
from orch.db.models import DaemonEvent

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

PROBE_PROMPT = "Reply with the single word OK."
_EXECUTOR_DIR = Path(__file__).resolve().parent.parent.parent / "executor"


def maybe_run_probe(db: Session, project_id: str, toml_config: AutoMergeConfig) -> None:
    """Fire a minimal health probe against the configured LLM runtime if a probe is due.

    Skips if the project is at phase 0 (disabled) or if the last probe was
    fired within the configured ``health_probe_interval_seconds``. On completion,
    writes a DaemonEvent of type ``merge_auto_merge_health_probe`` with
    reachability status and duration.

    Args:
        db: Active database session — caller commits.
        project_id: Project whose runtime configuration should be probed.
        toml_config: Loaded ``AutoMergeConfig`` containing probe interval and
            failure-rate threshold settings.
    """
    resolved = resolve_project_config(db, project_id, toml_config)
    if resolved.phase == 0:
        return

    latest = db.execute(
        select(DaemonEvent)
        .where(DaemonEvent.project_id == project_id)
        .where(DaemonEvent.event_type == EVENT_AUTO_MERGE_HEALTH_PROBE)
        .order_by(DaemonEvent.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    interval = timedelta(seconds=toml_config.health_probe_interval_seconds)
    now = datetime.now(UTC)
    if latest is not None and (now - latest.created_at) < interval:
        return

    start = time.monotonic()
    error: str | None = None
    reachable = False
    try:
        result = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "bash",
                str(_EXECUTOR_DIR / "step_executor_lib.sh"),
                "auto_merge_resolve",
                resolved.cli_tool,
                resolved.model,
            ],
            input=PROBE_PROMPT,
            text=True,
            capture_output=True,
            timeout=max(15, toml_config.health_probe_interval_seconds // 4),
            env={
                "WORKTREE_PATH": str(_EXECUTOR_DIR),
                "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            },
        )
        if result.returncode == 0 and "OK" in result.stdout:
            reachable = True
        else:
            error = (result.stderr or result.stdout)[:1024]
    except subprocess.TimeoutExpired:
        error = "timeout"
    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"

    duration_ms = int((time.monotonic() - start) * 1000)
    db.add(
        DaemonEvent(
            project_id=project_id,
            event_type=EVENT_AUTO_MERGE_HEALTH_PROBE,
            entity_id=None,
            entity_type=None,
            message=None,
            event_metadata={
                "runtime_reachable": reachable,
                "cli_tool": resolved.cli_tool,
                "model": resolved.model,
                "probe_duration_ms": duration_ms,
                "error": error,
            },
        )
    )
    db.commit()
    logger.info(
        "[auto_merge_health] project=%s reachable=%s duration_ms=%d error=%s",
        project_id,
        reachable,
        duration_ms,
        error,
    )
