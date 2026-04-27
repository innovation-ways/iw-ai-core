"""orch.staleness.service — Staleness computation orchestrator.

``compute_project_staleness`` is the public entry point for computing the
full staleness picture for a managed project: running service states and
Alembic migration head status.

``projects.toml`` is re-read from disk on every call — no caching, per the
F-00063 design invariant (Invariant 6).
"""

from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

from orch.staleness.alembic_check import AlembicStatus, check_alembic
from orch.staleness.config import parse_project_staleness
from orch.staleness.detection import find_running_pid, read_process_start_time
from orch.staleness.git_lookup import CommitSummary, commits_since, find_commit_at

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Path resolver — patched in tests via monkeypatch / patch
# ---------------------------------------------------------------------------


def _projects_toml_path() -> Path:
    """Return the path to projects.toml.

    This is a named function (not a module-level constant) so tests can
    patch it easily:  ``patch("orch.staleness.service._projects_toml_path", ...)``.
    """
    from orch.config import CORE_ROOT  # noqa: PLC0415

    return CORE_ROOT / "projects.toml"


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class ServiceStaleness:
    """Staleness state for a single declared service.

    Attributes:
        name: Service name as declared in projects.toml.
        status: One of "up_to_date", "stale", "not_running",
            "hot_reload_skipped", "unknown".
        start_time: Wall-clock start time of the running process (UTC), or
            None when not running.
        start_commit: SHA of the commit that was HEAD when the process started,
            or None.
        commits: Commits on main since start_commit that touch watch_paths.
        error: Error string when status is "unknown" (e.g. git failure).
        hot_reload: True iff the service has hot_reload=True in its config.
        actions: Subset of ["restart", "start", "stop"] that are available,
            derived from the configured commands and the current status.
    """

    name: str
    status: str
    start_time: datetime | None = None
    start_commit: str | None = None
    commits: list[CommitSummary] = field(default_factory=list)
    error: str | None = None
    hot_reload: bool = False
    actions: list[str] = field(default_factory=list)


@dataclass
class ProjectStalenessResult:
    """Full staleness picture for a managed project.

    Attributes:
        project_id: The project identifier.
        services: Per-service staleness records (empty if no services declared).
        alembic: Alembic migration status (None if no alembic block declared).
        is_stale: True iff at least one service is "stale" OR alembic is
            "stale". "not_running" and "hot_reload_skipped" do NOT contribute.
    """

    project_id: str
    services: list[ServiceStaleness] = field(default_factory=list)
    alembic: AlembicStatus | None = None
    is_stale: bool = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _derive_actions(svc_config: Any, running: bool) -> list[str]:
    """Derive the list of available action names for a service.

    When the service is running:
      - "restart" if restart_command is set
      - "stop" if stop_command is set (and no restart)
    When the service is not running:
      - "start" if start_command is set

    The design says: show Restart button when running; show Stop/Start when
    running and those are configured; show Start when not running.
    """
    actions: list[str] = []
    if running:
        if svc_config.restart_command:
            actions.append("restart")
        if svc_config.stop_command:
            actions.append("stop")
    else:
        if svc_config.start_command:
            actions.append("start")
    return actions


def _compute_service_staleness(
    svc_config: Any,
    repo_root: Path,
) -> ServiceStaleness:
    """Compute the staleness state for a single service."""
    hot_reload: bool = svc_config.hot_reload

    # Docker services handled separately; for all others use find_running_pid.
    if svc_config.detect.type == "docker":
        # Docker detection is a stretch goal for service.py; treat as not_running
        # for now — the detection module's find_running_container is available
        # to callers who need it, but is not wired into the service orchestrator
        # in this step (wired in S03).
        logger.debug(
            "[staleness] docker service %r: detection deferred to API layer",
            svc_config.name,
        )
        actions = _derive_actions(svc_config, running=False)
        return ServiceStaleness(
            name=svc_config.name,
            status="not_running",
            hot_reload=hot_reload,
            actions=actions,
        )

    pid = find_running_pid(svc_config.detect, repo_root)

    if pid is None:
        actions = _derive_actions(svc_config, running=False)
        return ServiceStaleness(
            name=svc_config.name,
            status="not_running",
            hot_reload=hot_reload,
            actions=actions,
        )

    # Service is running
    actions = _derive_actions(svc_config, running=True)

    # If hot_reload is set, skip staleness check — the service self-reloads.
    if hot_reload:
        return ServiceStaleness(
            name=svc_config.name,
            status="hot_reload_skipped",
            hot_reload=True,
            actions=actions,
        )

    # Determine start time
    try:
        start_time = read_process_start_time(pid)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "[staleness] Cannot read start time for PID %d (%s): %s", pid, svc_config.name, exc
        )
        return ServiceStaleness(
            name=svc_config.name,
            status="unknown",
            hot_reload=hot_reload,
            error=str(exc),
            actions=actions,
        )

    # Find commit at start time
    start_commit = find_commit_at(repo_root, start_time)
    if start_commit is None:
        logger.debug("[staleness] Cannot find commit at start time for %s", svc_config.name)
        return ServiceStaleness(
            name=svc_config.name,
            status="unknown",
            start_time=start_time,
            hot_reload=hot_reload,
            error="Cannot determine start commit (git log returned nothing)",
            actions=actions,
        )

    # Compute commits since start
    new_commits = commits_since(
        repo_root,
        start_commit,
        svc_config.watch_paths,
        svc_config.ignore_paths,
    )

    status = "stale" if new_commits else "up_to_date"
    return ServiceStaleness(
        name=svc_config.name,
        status=status,
        start_time=start_time,
        start_commit=start_commit,
        commits=new_commits,
        hot_reload=hot_reload,
        actions=actions,
    )


# ---------------------------------------------------------------------------
# compute_project_staleness — public entry point
# ---------------------------------------------------------------------------


def compute_project_staleness(project_id: str) -> ProjectStalenessResult:
    """Compute the full staleness picture for a managed project.

    Re-reads projects.toml from disk on every call (no caching per Invariant 6).

    Args:
        project_id: The project identifier (key in projects.toml).

    Returns:
        ProjectStalenessResult. If the project is not found, or has no
        services/alembic config, returns an empty result with is_stale=False.
    """
    toml_path = _projects_toml_path()

    # Parse projects.toml
    try:
        raw = tomllib.loads(toml_path.read_text())
    except Exception as exc:  # noqa: BLE001
        logger.error("[staleness] Failed to parse projects.toml at %s: %s", toml_path, exc)
        return ProjectStalenessResult(project_id=project_id)

    projects_section: dict[str, Any] = raw.get("projects", {})
    project_entry = projects_section.get(project_id)

    if project_entry is None:
        logger.debug("[staleness] Project %r not found in projects.toml", project_id)
        return ProjectStalenessResult(project_id=project_id)

    # Parse staleness config
    try:
        staleness_cfg = parse_project_staleness(project_entry)
    except ValueError as exc:
        logger.warning("[staleness] Invalid staleness config for %r: %s", project_id, exc)
        return ProjectStalenessResult(project_id=project_id)

    # Opt-out: no services and no alembic
    if not staleness_cfg.services and staleness_cfg.alembic is None:
        return ProjectStalenessResult(project_id=project_id)

    repo_root = Path(project_entry.get("repo_root", ""))
    services: list[ServiceStaleness] = []

    # Compute per-service staleness
    for svc_config in staleness_cfg.services:
        svc = _compute_service_staleness(svc_config, repo_root)
        services.append(svc)

    # Compute alembic status
    alembic: AlembicStatus | None = None
    if staleness_cfg.alembic is not None:
        alembic = check_alembic(
            repo_root,
            staleness_cfg.alembic.config,
            staleness_cfg.alembic.db_url_env,
        )

    # Determine is_stale: any service "stale" OR alembic "stale"
    is_stale = any(svc.status == "stale" for svc in services) or (
        alembic is not None and alembic.status == "stale"
    )

    return ProjectStalenessResult(
        project_id=project_id,
        services=services,
        alembic=alembic,
        is_stale=is_stale,
    )
