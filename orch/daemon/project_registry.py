"""Project registry — loads projects.toml and syncs project configs to the DB.

projects.toml format:
    [projects.innoforge]
    enabled = true
    repo_root = "/home/sergiog/dev/innoforge"
    display_name = "InnoForge"   # optional — falls back to .iw-orch.json

Each project's .iw-orch.json (at repo_root/.iw-orch.json) provides additional
project-specific config merged into the DB projects.config JSONB column.

.iw-orch.json schema (all fields optional):
    {
        "display_name": "InnoForge",
        "cli_tool": "opencode",
        "worktree_base": ".worktrees",
        "timeout_overrides": {}
    }
"""

from __future__ import annotations

import json
import logging
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# ProjectConfig — in-memory representation of one project entry
# ---------------------------------------------------------------------------


@dataclass
class ProjectConfig:
    """In-memory configuration for a single managed project."""

    id: str
    display_name: str
    repo_root: str
    enabled: bool
    cli_tool: str
    worktree_base: str
    config: dict[str, Any]  # full .iw-orch.json content
    dev_clone: str | None = None

    @property
    def working_dir(self) -> str:
        """Directory used for worktree operations.

        Normally returns repo_root. dev_clone is a legacy escape hatch that
        redirects worktree creation to an alternate clone; leave it unset
        unless you have a specific reason to route agents elsewhere.
        """
        return self.dev_clone or self.repo_root


# ---------------------------------------------------------------------------
# toml / json loading helpers
# ---------------------------------------------------------------------------


def _read_iw_orch_json(repo_root: str) -> dict[str, Any]:
    """Read .iw-orch.json from the project repo root.

    Returns an empty dict if the file is missing or malformed (logs a warning).
    """
    iw_json = Path(repo_root) / ".iw-orch.json"
    if not iw_json.exists():
        logger.debug(".iw-orch.json not found in %s — using defaults", repo_root)
        return {}
    try:
        return json.loads(iw_json.read_text())  # type: ignore[no-any-return]
    except json.JSONDecodeError as exc:
        logger.warning("Invalid .iw-orch.json in %s: %s — project skipped context", repo_root, exc)
        return {}


def _build_project_config(project_id: str, entry: dict[str, Any]) -> ProjectConfig | None:
    """Build a ProjectConfig from a single projects.toml entry.

    Returns None if the entry is invalid (missing required fields, bad path).
    Logs a warning on error so the daemon can skip the project without crashing.
    """
    repo_root = entry.get("repo_root")
    if not repo_root:
        logger.warning("Project %r missing 'repo_root' — skipping", project_id)
        return None

    if not Path(repo_root).exists():
        logger.warning("Project %r repo_root %r does not exist — skipping", project_id, repo_root)
        return None

    enabled: bool = entry.get("enabled", True)
    iw_config = _read_iw_orch_json(repo_root)

    # display_name: projects.toml takes precedence over .iw-orch.json, then project_id
    display_name: str = entry.get("display_name") or iw_config.get("display_name") or project_id
    cli_tool: str = iw_config.get("cli_tool", "opencode")
    worktree_base: str = iw_config.get("worktree_base", ".worktrees")

    dev_clone: str | None = iw_config.get("dev_clone") or None

    # Sanity-validate staleness config if present (log warning and continue — do NOT
    # skip the project; staleness config is optional and read on demand at compute time).
    _validate_staleness_config(project_id, entry)

    return ProjectConfig(
        id=project_id,
        display_name=display_name,
        repo_root=repo_root,
        enabled=enabled,
        cli_tool=cli_tool,
        worktree_base=worktree_base,
        config=iw_config,
        dev_clone=dev_clone,
    )


def _validate_staleness_config(project_id: str, entry: dict[str, Any]) -> None:
    """Parse and validate the staleness config for sanity — log on error, never raise.

    This is a best-effort validation pass at registry-load time. The staleness
    config is intentionally NOT stored on ProjectConfig; it is re-read from
    disk on every staleness computation call (F-00063 Invariant 6).
    """
    if "services" not in entry and "alembic" not in entry:
        return  # opt-out — nothing to validate

    try:
        from orch.staleness.config import parse_project_staleness  # noqa: PLC0415

        parse_project_staleness(entry)
    except ValueError as exc:
        logger.warning(
            "Project %r has invalid staleness config — services/alembic will be unavailable: %s",
            project_id,
            exc,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Project %r staleness config validation failed unexpectedly: %s",
            project_id,
            exc,
        )


def load_projects_toml(path: Path) -> dict[str, ProjectConfig]:
    """Parse projects.toml and return a {project_id: ProjectConfig} mapping.

    Projects with invalid config are skipped (logged as warnings).
    Returns an empty dict if the file is empty, has no [projects] section,
    or fails to parse. To distinguish parse failure from "file has no
    projects", call :func:`try_load_projects_toml` instead.
    """
    result = try_load_projects_toml(path)
    return {} if result is None else result


def try_load_projects_toml(path: Path) -> dict[str, ProjectConfig] | None:
    """Parse projects.toml, returning None on TOML syntax errors.

    Distinguishes "file is valid but empty" (→ ``{}``) from "file is
    unparseable" (→ ``None``). Used by :class:`ProjectRegistry` to avoid
    wiping the in-memory registry when the file is temporarily corrupt.
    """
    try:
        raw = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as exc:
        logger.error("Failed to parse projects.toml at %s: %s", path, exc)
        return None

    projects_section: dict[str, Any] = raw.get("projects", {})
    result: dict[str, ProjectConfig] = {}

    for project_id, entry in projects_section.items():
        if not isinstance(entry, dict):
            logger.warning("Project %r entry is not a table — skipping", project_id)
            continue
        config = _build_project_config(project_id, entry)
        if config is not None:
            result[project_id] = config

    return result


# ---------------------------------------------------------------------------
# DB sync helper
# ---------------------------------------------------------------------------


def sync_project_to_db(db: Session, config: ProjectConfig) -> None:
    """Upsert a project record in the DB from a ProjectConfig.

    Uses INSERT ... ON CONFLICT UPDATE so the daemon can call this idempotently
    on every startup and reload.
    """
    from sqlalchemy.dialects.postgresql import insert  # noqa: PLC0415

    from orch.db.models import IdSequence, MigrationLock, Project  # noqa: PLC0415

    dev_clone = config.config.get("dev_clone")
    stmt = insert(Project).values(
        id=config.id,
        display_name=config.display_name,
        repo_root=config.repo_root,
        dev_clone=dev_clone,
        config=config.config,
        enabled=config.enabled,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["id"],
        set_={
            "display_name": stmt.excluded.display_name,
            "repo_root": stmt.excluded.repo_root,
            "dev_clone": stmt.excluded.dev_clone,
            "config": stmt.excluded.config,
            "enabled": stmt.excluded.enabled,
        },
    )
    db.execute(stmt)

    # Ensure id_sequences rows exist (INSERT ... ON CONFLICT DO NOTHING)
    for prefix in ("F", "I", "CR", "BATCH"):
        seq_stmt = insert(IdSequence).values(prefix=prefix, next_number=1)
        seq_stmt = seq_stmt.on_conflict_do_nothing()
        db.execute(seq_stmt)

    # Ensure migration_locks row exists
    lock_stmt = insert(MigrationLock).values(project_id=config.id, current_holder=None)
    lock_stmt = lock_stmt.on_conflict_do_nothing()
    db.execute(lock_stmt)

    db.commit()
    logger.debug("Synced project %r to DB", config.id)


# ---------------------------------------------------------------------------
# ProjectRegistry — stateful registry with mtime-based reload detection
# ---------------------------------------------------------------------------


@dataclass
class ProjectRegistry:
    """Tracks projects.toml state and detects changes for the daemon reload loop."""

    path: Path
    _mtime: float = field(default=0.0, init=False, repr=False)
    _projects: dict[str, ProjectConfig] = field(default_factory=dict, init=False, repr=False)

    def load(self) -> dict[str, ProjectConfig]:
        """Initial load. Reads the file and caches the result.

        Returns the loaded {project_id: ProjectConfig} mapping.
        """
        self._projects = load_projects_toml(self.path)
        try:
            self._mtime = self.path.stat().st_mtime
        except OSError:
            self._mtime = 0.0
        return dict(self._projects)

    def is_stale(self) -> bool:
        """Return True if projects.toml has been modified since the last load."""
        try:
            return self.path.stat().st_mtime != self._mtime
        except OSError:
            return False

    def reload(self) -> tuple[dict[str, ProjectConfig], dict[str, str]]:
        """Re-read projects.toml and return the new projects plus a change summary.

        If the file fails to parse (e.g. a SIGHUP fires mid-edit or a test
        leaked duplicate ``[projects.x]`` tables), the in-memory registry is
        preserved and an empty change set is returned — better to keep the
        last-known-good state than to silently mark every project as removed.

        Returns:
            (new_projects, changes) where changes maps project_id → one of:
            "added", "removed", "disabled", "enabled", "unchanged".
        """
        new_projects = try_load_projects_toml(self.path)
        try:
            self._mtime = self.path.stat().st_mtime
        except OSError:
            self._mtime = 0.0

        if new_projects is None:
            logger.warning(
                "projects.toml is unparseable — preserving previous registry of %d project(s)",
                len(self._projects),
            )
            return dict(self._projects), {}

        changes: dict[str, str] = {}
        old = self._projects
        all_ids = set(old) | set(new_projects)

        for pid in all_ids:
            if pid not in old and pid in new_projects:
                changes[pid] = "added"
            elif pid in old and pid not in new_projects:
                changes[pid] = "removed"
            elif pid in old and pid in new_projects:
                was_enabled = old[pid].enabled
                is_enabled = new_projects[pid].enabled
                if was_enabled and not is_enabled:
                    changes[pid] = "disabled"
                elif not was_enabled and is_enabled:
                    changes[pid] = "enabled"
                else:
                    changes[pid] = "unchanged"

        self._projects = new_projects
        return dict(new_projects), changes

    @property
    def projects(self) -> dict[str, ProjectConfig]:
        """Current in-memory project map (last loaded state)."""
        return dict(self._projects)
