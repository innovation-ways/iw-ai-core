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
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

_AI_ASSISTANT_MODEL_PATTERN = re.compile(r"^[a-z0-9._-]+/[A-Za-z0-9._:/-]+$")


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
    model: str
    worktree_base: str
    config: dict[str, Any]  # full .iw-orch.json content
    dev_clone: str | None = None
    # Opt-in scope-gate enforcement at merge time. Default is False because the
    # gate's design (added after I-00034) blocks merges on legitimate cross-cutting
    # changes (formatter sweeps, post-merge test fixups). Projects opt in via
    # .iw-orch.json: {"scope_gate_enabled": true}. CR-00030 will replace this
    # blanket toggle with a more discriminating mechanism.
    scope_gate_enabled: bool = False
    # Opt-in self-assessment step (iw-item-analyze) run before merge. When True,
    # a self_assess step is injected into manifests and the daemon treats its
    # failures as soft (item proceeds to merge regardless). Read from
    # projects.toml: [projects.<id>] self_assess = true.
    self_assess_enabled: bool = False
    # Per-project default for auto_merge. When True (default), successful batch
    # items go straight to the merge queue. When False, they park in
    # awaiting_merge_approval and require an operator to click Merge
    # (dashboard) or run `iw item approve-merge` (CLI) before the merge queue
    # picks them up. Read from projects.toml: [projects.<id>] auto_merge.
    auto_merge_default: bool = True
    # Per-gate fix-cycle budgets for quality_validation steps.
    # Keys are gate names (e.g. "lint", "unit-tests"); values are integers.
    # When empty the global defaults in fix_cycle._DEFAULT_QV_GATE_BUDGETS apply.
    # Read from projects.toml: [projects.<id>] qv_fix_cycle_max = { lint = 3 }.
    qv_fix_cycle_max: dict[str, int] = field(default_factory=dict)
    # Cascade thrashing detector: how many times the same trigger step must fire
    # cascades before the thrashing guard short-circuits. Default 3.
    # Read from projects.toml: [projects.<id>] cascade_thrashing_threshold = 3.
    cascade_thrashing_threshold: int = 3
    # Minimum Jaccard similarity between consecutive cascade reset-sets to
    # classify repeated cascades from the same trigger as "thrashing". Default 0.5.
    # Read from projects.toml: [projects.<id>] cascade_thrashing_jaccard_min = 0.5.
    cascade_thrashing_jaccard_min: float = 0.5
    # Aggregate per-work-item fix-cycle budget — backstop independent of per-step
    # caps. Prevents pathological cascades from burning unbounded total cycles.
    # Default 25. Read from projects.toml: [projects.<id>] aggregate_fix_cycle_max = 25.
    aggregate_fix_cycle_max: int = 25

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
    # cli_tool: projects.toml entry takes precedence; .iw-orch.json is fallback
    # for backwards compat. .iw-orch.json ONLY supplies cli_tool (not model).
    cli_tool: str = entry.get("cli_tool") or iw_config.get("cli_tool", "opencode")
    # model: read from projects.toml entry; default "minimax/MiniMax-M2.7"
    # (opencode --model expects provider/model_id format; bare "minimax" crashes)
    model: str = entry.get("model", "minimax/MiniMax-M2.7")
    worktree_base: str = iw_config.get("worktree_base", ".worktrees")

    dev_clone: str | None = iw_config.get("dev_clone") or None

    # Sanity-validate staleness config if present (log warning and continue — do NOT
    # skip the project; staleness config is optional and read on demand at compute time).
    _validate_staleness_config(project_id, entry)

    parsed_ai_assistant = _parse_ai_assistant_block(project_id, entry.get("ai_assistant"))
    if parsed_ai_assistant is not None:
        iw_config["ai_assistant"] = parsed_ai_assistant
    else:
        iw_config.pop("ai_assistant", None)

    scope_gate_enabled: bool = bool(iw_config.get("scope_gate_enabled", False))

    # self_assess flag — read from projects.toml entry, not .iw-orch.json
    raw_self_assess = entry.get("self_assess", False)
    if isinstance(raw_self_assess, bool):
        self_assess_enabled = raw_self_assess
    else:
        logger.warning(
            "Project %r has non-bool 'self_assess' value %r — defaulting to False",
            project_id,
            raw_self_assess,
        )
        self_assess_enabled = False

    # auto_merge flag — read from projects.toml entry, default True
    raw_auto_merge = entry.get("auto_merge", True)
    if isinstance(raw_auto_merge, bool):
        auto_merge_default = raw_auto_merge
    else:
        logger.warning(
            "Project %r has non-bool 'auto_merge' value %r — defaulting to True",
            project_id,
            raw_auto_merge,
        )
        auto_merge_default = True

    # qv_fix_cycle_max — per-gate budget overrides for quality_validation steps.
    # Expected: { lint = 3, format = 3, "unit-tests" = 5, ... }
    # Silently drops non-integer values with a warning so a bad entry doesn't
    # prevent the project from loading.
    raw_qv_budgets = entry.get("qv_fix_cycle_max", {})
    if isinstance(raw_qv_budgets, dict):
        qv_fix_cycle_max: dict[str, int] = {}
        for gate_name, budget in raw_qv_budgets.items():
            if isinstance(budget, int):
                qv_fix_cycle_max[gate_name] = budget
            else:
                logger.warning(
                    "Project %r qv_fix_cycle_max[%r] is not an int (%r) — ignoring",
                    project_id,
                    gate_name,
                    budget,
                )
    else:
        logger.warning(
            "Project %r has non-dict 'qv_fix_cycle_max' value — ignoring",
            project_id,
        )
        qv_fix_cycle_max = {}

    # cascade_thrashing_threshold — number of same-trigger cascades before
    # the thrashing guard fires. Default 3. Must be a positive integer.
    raw_ct_threshold = entry.get("cascade_thrashing_threshold", 3)
    if isinstance(raw_ct_threshold, int) and raw_ct_threshold > 0:
        cascade_thrashing_threshold = raw_ct_threshold
    else:
        logger.warning(
            "Project %r has invalid 'cascade_thrashing_threshold' value %r — defaulting to 3",
            project_id,
            raw_ct_threshold,
        )
        cascade_thrashing_threshold = 3

    # cascade_thrashing_jaccard_min — minimum Jaccard similarity of consecutive
    # reset-sets to count as thrashing. Default 0.5. Must be in [0.0, 1.0].
    raw_ct_jaccard = entry.get("cascade_thrashing_jaccard_min", 0.5)
    if isinstance(raw_ct_jaccard, (int, float)) and 0.0 <= float(raw_ct_jaccard) <= 1.0:
        cascade_thrashing_jaccard_min = float(raw_ct_jaccard)
    else:
        logger.warning(
            "Project %r has invalid 'cascade_thrashing_jaccard_min' value %r — defaulting to 0.5",
            project_id,
            raw_ct_jaccard,
        )
        cascade_thrashing_jaccard_min = 0.5

    # aggregate_fix_cycle_max — total fix cycles across all steps per work item.
    # Backstop against pathological cascades. Default 25. Must be a positive int.
    raw_aggregate_max = entry.get("aggregate_fix_cycle_max", 25)
    if isinstance(raw_aggregate_max, int) and raw_aggregate_max > 0:
        aggregate_fix_cycle_max = raw_aggregate_max
    else:
        logger.warning(
            "Project %r has invalid 'aggregate_fix_cycle_max' value %r — defaulting to 25",
            project_id,
            raw_aggregate_max,
        )
        aggregate_fix_cycle_max = 25

    return ProjectConfig(
        id=project_id,
        display_name=display_name,
        repo_root=repo_root,
        enabled=enabled,
        cli_tool=cli_tool,
        model=model,
        worktree_base=worktree_base,
        config=iw_config,
        dev_clone=dev_clone,
        scope_gate_enabled=scope_gate_enabled,
        self_assess_enabled=self_assess_enabled,
        auto_merge_default=auto_merge_default,
        qv_fix_cycle_max=qv_fix_cycle_max,
        cascade_thrashing_threshold=cascade_thrashing_threshold,
        cascade_thrashing_jaccard_min=cascade_thrashing_jaccard_min,
        aggregate_fix_cycle_max=aggregate_fix_cycle_max,
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


def _parse_ai_assistant_block(project_id: str, raw: object) -> dict[str, Any] | None:
    """Validate and normalize the optional ai_assistant config block."""
    if raw is None:
        return None

    if not isinstance(raw, dict):
        logger.warning(
            "Project %r ai_assistant block missing or invalid `models` — ignoring", project_id
        )
        return None

    models_raw = raw.get("models")
    if not isinstance(models_raw, list) or len(models_raw) == 0:
        logger.warning(
            "Project %r ai_assistant block missing or invalid `models` — ignoring", project_id
        )
        return None

    valid_models: list[str] = []
    seen: set[str] = set()
    for model in models_raw:
        if isinstance(model, str) and _AI_ASSISTANT_MODEL_PATTERN.fullmatch(model):
            if model not in seen:
                valid_models.append(model)
                seen.add(model)
            continue

        logger.warning(
            "Project %r invalid ai_assistant model entry %r — ignoring",
            project_id,
            model,
        )

    if not valid_models:
        logger.warning(
            "Project %r ai_assistant block has no valid models after filtering — ignoring",
            project_id,
        )
        return None

    parsed: dict[str, Any] = {"models": valid_models}
    default_model = raw.get("default_model")
    if default_model is None:
        return parsed

    if isinstance(default_model, str) and default_model in valid_models:
        parsed["default_model"] = default_model
    else:
        logger.warning(
            "Project %r ai_assistant default_model %r not present "
            "in filtered models — ignoring default_model",
            project_id,
            default_model,
        )

    return parsed


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
