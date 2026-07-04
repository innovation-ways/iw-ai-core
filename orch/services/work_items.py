"""Work-item service functions for the orch platform.

Provides reusable, session-explicit functions that encapsulate all DB logic
for work-item lifecycle operations. The same functions are called by the
``iw`` CLI and (in future) by the MCP server tool-handlers. Callers receive
plain dicts matching the existing CLI ``--json`` output shapes.

Column pinning
--------------
The ``_WORK_ITEM_CLI_COLUMNS``, ``_WORKFLOW_STEP_CLI_COLUMNS``, and
``_BATCH_ITEM_CLI_COLUMNS`` tuples defined here are authoritative.  The CLI
modules import them from here so there is exactly ONE definition — any schema
drift is caught by the pinned-column discipline described in
``docs/IW_AI_Core_Agent_Constraints.md`` §R2b.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.orm import load_only

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    StepStatus,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)
from orch.services._common import ServiceError, clamp_limit

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# ---------------------------------------------------------------------------
# Agent-facing CLI column pinning — see R2b in docs/IW_AI_Core_Agent_Constraints.md
# ---------------------------------------------------------------------------

_WORK_ITEM_CLI_COLUMNS = (
    WorkItem.project_id,
    WorkItem.id,
    WorkItem.type,
    WorkItem.title,
    WorkItem.status,
    WorkItem.phase,
    WorkItem.config,
    WorkItem.depends_on,
    WorkItem.blocks,
    WorkItem.impacted_paths,
    WorkItem.design_doc_path,
    WorkItem.design_doc_content,
    WorkItem.functional_doc_path,
    WorkItem.functional_doc_content,
    WorkItem.summary,
    WorkItem.archive_path,
    WorkItem.archive_size_bytes,
    WorkItem.created_at,
    WorkItem.updated_at,
    WorkItem.completed_at,
    WorkItem.archived_at,
    # NOTE: manifest_digest intentionally excluded here — it is only used in
    # register/approve, not in general item-status output. Loading it via
    # load_only() would cause issues if the column is absent in pre-migration
    # DBs (e.g. during daemon-upgrade rolling restarts).
    # NOTE: diff_text, diff_summary, merge_commit_sha are intentionally
    # excluded — they are feature-gate columns (F-00079) that the live
    # orch DB may not have yet (migration un-applied). The CLI SELECT must
    # not mention them so it does not crash against a drifted schema.
)

_WORKFLOW_STEP_CLI_COLUMNS = (
    WorkflowStep.id,
    WorkflowStep.project_id,
    WorkflowStep.work_item_id,
    WorkflowStep.step_number,
    WorkflowStep.step_id,
    WorkflowStep.agent_label,
    WorkflowStep.opencode_agent,
    WorkflowStep.step_type,
    WorkflowStep.step_label,
    WorkflowStep.description,
    WorkflowStep.command,
    WorkflowStep.gate,
    # NOTE: gate is included in the pinned set — it was added by F-00079
    # (merged), so it is present in both the in-process ORM and the live DB.
    # Excluding it would break item-status output for all registered items.
    WorkflowStep.timeout_secs,
    WorkflowStep.status,
    WorkflowStep.prompt_file,
    WorkflowStep.report_file,
    WorkflowStep.report_content,
    WorkflowStep.started_at,
    WorkflowStep.completed_at,
)

_BATCH_ITEM_CLI_COLUMNS = (
    BatchItem.id,
    BatchItem.project_id,
    BatchItem.batch_id,
    BatchItem.work_item_id,
    BatchItem.execution_group,
    # NOTE: status intentionally excluded — batch_items.status may be added
    # by future features and not yet migrated to the live DB.
    BatchItem.pid,
    BatchItem.started_at,
    BatchItem.merged_at,
    BatchItem.notes,
    BatchItem.stall_count,
    BatchItem.last_progress,
    BatchItem.worktree_info,
    BatchItem.merge_info,
    BatchItem.worktree_db_host,
    BatchItem.worktree_db_port,
    BatchItem.worktree_db_name,
    BatchItem.worktree_db_user,
    BatchItem.worktree_db_password,
    BatchItem.worktree_app_port,
    BatchItem.worktree_compose_path,
)

# ---------------------------------------------------------------------------
# Active batch statuses (same as in item_commands and batch_commands)
# ---------------------------------------------------------------------------

_ACTIVE_BATCH_STATUSES: list[BatchStatus] = [
    BatchStatus.planning,
    BatchStatus.approved,
    BatchStatus.executing,
    BatchStatus.paused,
    BatchStatus.blocked,
    BatchStatus.publishing,
    BatchStatus.publish_failed,
]

# ---------------------------------------------------------------------------
# Retry-eligible batch item statuses (mirrors item_commands)
# ---------------------------------------------------------------------------


_RETRY_ELIGIBLE_BATCH_ITEM_STATUSES: frozenset[BatchItemStatus] = frozenset(
    {
        BatchItemStatus.failed,
        BatchItemStatus.setup_failed,
        BatchItemStatus.stalled,
        BatchItemStatus.migration_rebase_failed,
        BatchItemStatus.merge_failed,
    }
)

_NOT_STUCK_WORK_ITEM_STATUSES: frozenset[WorkItemStatus] = frozenset(
    {
        WorkItemStatus.draft,
        WorkItemStatus.approved,
        WorkItemStatus.in_progress,
        WorkItemStatus.paused,
    }
)

# ---------------------------------------------------------------------------
# RegistrationSpec dataclass
# ---------------------------------------------------------------------------


@dataclass
class RegistrationSpec:
    """All resolved inputs for work-item registration.

    This dataclass separates the disk-IO half of ``register`` (reading design
    docs, parsing manifests) from the DB half (inserting rows). Both the CLI
    and the MCP tool populate a ``RegistrationSpec`` then call
    :func:`create_work_item`.

    Attributes:
        item_id: Work-item identifier (e.g. ``F-00001``).
        title: Human-readable title.
        item_type: Lowercase type string: ``feature``, ``incident``,
            ``cr``, or ``research``.
        design_doc_path: Relative path to the design doc, or ``None``.
        design_doc_content: Full text of the design doc, or ``None``.
        functional_doc_path: Relative path to the functional doc, or ``None``.
        functional_doc_content: Full text of the functional doc, or ``None``.
        manifest_steps: Parsed steps list from the workflow manifest.
        manifest_digest: SHA-256 digest of ``manifest_steps``, or ``None``
            when there are no steps.
        impacted_paths: List of file globs / paths affected by this item.
        depends_on: IDs of work items this item depends on.
        blocks: IDs of work items this item blocks.
        config: Free-form config dict (e.g. ``scope_extraction`` metadata).
    """

    item_id: str
    title: str
    item_type: str
    design_doc_path: str | None
    design_doc_content: str | None
    functional_doc_path: str | None
    functional_doc_content: str | None
    manifest_steps: list[dict[str, Any]]
    manifest_digest: str | None
    impacted_paths: list[str]
    depends_on: list[str]
    blocks: list[str]
    config: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Item-type lookup
# ---------------------------------------------------------------------------

_ITEM_TYPE_MAP: dict[str, WorkItemType] = {
    "feature": WorkItemType.Feature,
    "incident": WorkItemType.Issue,
    "cr": WorkItemType.ChangeRequest,
    "research": WorkItemType.Research,
}


# ---------------------------------------------------------------------------
# Disk-IO helper
# ---------------------------------------------------------------------------


def load_registration_spec_from_disk(
    project_id: str,  # noqa: ARG001 — reserved for future project-relative path resolution
    *,
    item_id: str,
    title: str,
    item_type: str,
    design_doc: str | None,
    steps_from: str | None,
    functional_doc: str | None,
) -> RegistrationSpec:
    """Build a RegistrationSpec by reading design/functional docs and manifest from disk.

    This is the filesystem-only half of item registration.  No DB access
    occurs here.  Callers should invoke :func:`create_work_item` to persist
    the returned spec.

    Args:
        project_id: Project identifier (reserved for future project-relative
            resolution; currently unused).
        item_id: Work-item identifier.
        title: Human-readable title for the item.
        item_type: Lowercase type string (``feature``, ``incident``, ``cr``,
            ``research``).
        design_doc: Relative path to the design document, or ``None``.
        steps_from: Path to ``workflow-manifest.json``, or ``None``.
        functional_doc: Relative path to the functional design document, or
            ``None``.  When ``None``, a sibling ``<item_id>_Functional.md``
            next to the design doc is attempted.

    Returns:
        A fully-populated :class:`RegistrationSpec` ready for
        :func:`create_work_item`.

    Raises:
        FileNotFoundError: When ``steps_from`` or an explicitly supplied
            ``functional_doc`` path does not exist on disk.
        ValueError: When the manifest JSON is malformed.
    """
    # Inline imports to avoid circular dependency at module level
    from orch.batch_planner import extract_affected_files  # noqa: PLC0415
    from orch.design_doc_parser import parse_dependencies, parse_impacted_paths  # noqa: PLC0415

    # --- Read design doc ---
    design_doc_content: str | None = None
    if design_doc:
        doc_path = Path(design_doc)
        if not doc_path.is_absolute():
            doc_path = Path.cwd() / doc_path
        try:
            design_doc_content = doc_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            pass  # Tolerated — item registered without content
        except OSError:
            pass  # Tolerated with warning

    # --- Read functional doc ---
    functional_doc_content: str | None = None
    functional_doc_path: str | None = None

    if functional_doc is not None:
        explicit_path = Path(functional_doc)
        if not explicit_path.is_absolute():
            explicit_path = Path.cwd() / explicit_path
        if not explicit_path.exists():
            raise FileNotFoundError(f"Functional doc file not found: {explicit_path}")
        functional_doc_content = explicit_path.read_text(encoding="utf-8")
        functional_doc_path = functional_doc
    elif design_doc:
        design_doc_base = Path(design_doc)
        if not design_doc_base.is_absolute():
            design_doc_base = Path.cwd() / design_doc_base
        candidate = design_doc_base.parent / f"{item_id}_Functional.md"
        if candidate.exists():
            try:
                content = candidate.read_text(encoding="utf-8")
                if content:
                    functional_doc_content = content
                    functional_doc_path = str(candidate.relative_to(Path.cwd()))
            except OSError:
                pass

    # --- Parse manifest ---
    manifest_steps: list[dict[str, Any]] = []
    manifest_digest: str | None = None
    if steps_from:
        manifest_path = Path(steps_from)
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {steps_from}")
        try:
            data: Any = json.loads(manifest_path.read_text())
            manifest_steps = [dict(s) for s in data.get("steps", [])]
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"Invalid manifest file: {exc}") from exc
        if manifest_steps:
            manifest_digest = _compute_manifest_digest(manifest_steps)

    # --- Parse dependencies ---
    deps = parse_dependencies(design_doc_content)
    filtered_depends_on = [d for d in deps.depends_on if d != item_id]

    # --- Parse impacted paths ---
    scope_result = parse_impacted_paths(design_doc_content)
    if scope_result.found:
        impacted_paths = scope_result.paths
        scope_extraction: dict[str, object] = {"source": "declared"}
    else:
        impacted_paths = extract_affected_files(design_doc_content)
        scope_extraction = {"source": "regex_fallback" if impacted_paths else "none"}

    return RegistrationSpec(
        item_id=item_id,
        title=title,
        item_type=item_type,
        design_doc_path=design_doc,
        design_doc_content=design_doc_content,
        functional_doc_path=functional_doc_path,
        functional_doc_content=functional_doc_content,
        manifest_steps=manifest_steps,
        manifest_digest=manifest_digest,
        impacted_paths=impacted_paths,
        depends_on=filtered_depends_on,
        blocks=deps.blocks,
        config={"scope_extraction": scope_extraction},
    )


# ---------------------------------------------------------------------------
# Manifest digest helper
# ---------------------------------------------------------------------------


def _compute_manifest_digest(steps: list[dict[str, Any]]) -> str:
    """Compute a deterministic SHA-256 hex digest of a manifest's steps array.

    Canonicalization drops None/empty-string values from each step, then
    serialises with ``sort_keys=True`` and joins lines with ``\\n``.

    Args:
        steps: Parsed steps list from the workflow manifest.

    Returns:
        Lowercase hex-encoded SHA-256 digest string.
    """
    canonical_lines: list[str] = []
    for step in steps:
        filtered = {k: v for k, v in step.items() if v is not None and v != ""}
        canonical_lines.append(json.dumps(filtered, sort_keys=True, separators=(",", ":")))
    content = "\n".join(canonical_lines).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


# ---------------------------------------------------------------------------
# create_work_item
# ---------------------------------------------------------------------------


def build_registration_spec_from_content(
    item_id: str,
    title: str,
    item_type: str,
    *,
    design_doc_content: str | None = None,
    functional_doc_content: str | None = None,
    manifest_steps: list[dict[str, Any]] | None = None,
    impacted_paths: list[str] | None = None,
    depends_on: list[str] | None = None,
    blocks: list[str] | None = None,
    config: dict[str, Any] | None = None,
) -> RegistrationSpec:
    """Build a RegistrationSpec from in-memory content without any disk I/O.

    Mirrors what :func:`load_registration_spec_from_disk` produces but accepts
    raw content strings instead of file paths.  The same parsing helpers are
    reused so ``impacted_paths``, ``depends_on``, and ``blocks`` are extracted
    from ``design_doc_content`` identically to the disk-based path.

    When ``impacted_paths`` is explicitly supplied it takes precedence over any
    ``## Impacted Paths`` section found in ``design_doc_content``.  Likewise,
    when ``depends_on`` / ``blocks`` are supplied they bypass content parsing
    entirely.

    Args:
        item_id: Work-item identifier (e.g. ``F-00001``).
        title: Human-readable title.
        item_type: Lowercase type string: ``feature``, ``incident``, ``cr``,
            or ``research``.
        design_doc_content: Full text of the design document, or ``None``.
        functional_doc_content: Full text of the functional document, or ``None``.
        manifest_steps: Parsed steps list (same format as a workflow manifest's
            ``steps`` array).  When ``None`` or empty no digest is computed.
        impacted_paths: Explicit list of impacted file globs.  When ``None``,
            the list is parsed from ``design_doc_content``.
        depends_on: Explicit dependency IDs.  When ``None``, parsed from
            ``design_doc_content``.
        blocks: Explicit blocked-item IDs.  When ``None``, parsed from
            ``design_doc_content``.
        config: Free-form config dict.  When ``None``, a ``scope_extraction``
            entry is synthesised based on how ``impacted_paths`` was resolved.

    Returns:
        A fully-populated :class:`RegistrationSpec` ready for
        :func:`create_work_item`.
    """
    from orch.batch_planner import extract_affected_files  # noqa: PLC0415
    from orch.design_doc_parser import parse_dependencies, parse_impacted_paths  # noqa: PLC0415

    # --- Resolve impacted paths ---
    if impacted_paths is not None:
        resolved_paths = list(impacted_paths)
        scope_extraction: dict[str, object] = {"source": "explicit"}
    else:
        scope_result = parse_impacted_paths(design_doc_content)
        if scope_result.found:
            resolved_paths = scope_result.paths
            scope_extraction = {"source": "declared"}
        else:
            resolved_paths = extract_affected_files(design_doc_content)
            scope_extraction = {"source": "regex_fallback" if resolved_paths else "none"}

    # --- Resolve dependencies ---
    if depends_on is not None:
        resolved_depends_on = [d for d in depends_on if d != item_id]
        resolved_blocks = list(blocks) if blocks is not None else []
    else:
        deps = parse_dependencies(design_doc_content)
        resolved_depends_on = [d for d in deps.depends_on if d != item_id]
        resolved_blocks = list(blocks) if blocks is not None else deps.blocks

    # --- Manifest digest ---
    effective_steps: list[dict[str, Any]] = list(manifest_steps) if manifest_steps else []
    manifest_digest: str | None = None
    if effective_steps:
        manifest_digest = _compute_manifest_digest(effective_steps)

    # --- Config ---
    effective_config: dict[str, Any] = (
        dict(config) if config is not None else {"scope_extraction": scope_extraction}
    )

    return RegistrationSpec(
        item_id=item_id,
        title=title,
        item_type=item_type,
        design_doc_path=None,
        design_doc_content=design_doc_content,
        functional_doc_path=None,
        functional_doc_content=functional_doc_content,
        manifest_steps=effective_steps,
        manifest_digest=manifest_digest,
        impacted_paths=resolved_paths,
        depends_on=resolved_depends_on,
        blocks=resolved_blocks,
        config=effective_config,
    )


def create_work_item(session: Session, project_id: str, spec: RegistrationSpec) -> dict[str, Any]:
    """Insert a new WorkItem (and its WorkflowSteps) into the database.

    Idempotent: when a WorkItem with ``spec.item_id`` already exists for the
    project, no DB changes are made and the returned dict contains
    ``"created": False``.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project to scope the item under.
        spec: Resolved registration inputs from :func:`load_registration_spec_from_disk`
            or built directly by callers.

    Returns:
        Dict with keys ``project_id``, ``id``, ``title``, ``status``,
        ``created`` (bool).  Matches the CLI ``iw register --json`` shape.

    Raises:
        ServiceError: When the item type string is not recognised.
    """
    # Idempotency check
    existing = session.execute(
        select(WorkItem)
        .options(load_only(*_WORK_ITEM_CLI_COLUMNS))
        .where(WorkItem.project_id == project_id, WorkItem.id == spec.item_id)
    ).scalar_one_or_none()

    if existing is not None:
        return {
            "project_id": project_id,
            "id": spec.item_id,
            "status": existing.status.value,
            "created": False,
            "message": "Already registered",
        }

    item_type_enum = _ITEM_TYPE_MAP.get(spec.item_type)
    if item_type_enum is None:
        raise ServiceError(f"Unknown item type: {spec.item_type!r}", code=2)

    work_item = WorkItem(
        project_id=project_id,
        id=spec.item_id,
        type=item_type_enum,
        title=spec.title,
        design_doc_path=spec.design_doc_path,
        design_doc_content=spec.design_doc_content,
        functional_doc_path=spec.functional_doc_path,
        functional_doc_content=spec.functional_doc_content,
        status=WorkItemStatus.draft,
        phase=WorkItemPhase.active,
        impacted_paths=spec.impacted_paths,
        config=spec.config,
        depends_on=spec.depends_on,
        blocks=spec.blocks,
        manifest_digest=spec.manifest_digest,
    )
    session.add(work_item)
    session.flush()

    # Blocks inversion: update depends_on of blocked items
    for blocked_id in spec.blocks:
        blocked_item = session.execute(
            select(WorkItem)
            .options(load_only(*_WORK_ITEM_CLI_COLUMNS))
            .where(WorkItem.project_id == project_id, WorkItem.id == blocked_id)
        ).scalar_one_or_none()
        if blocked_item is not None and spec.item_id not in blocked_item.depends_on:
            blocked_item.depends_on = blocked_item.depends_on + [spec.item_id]

    if spec.manifest_steps:
        _insert_workflow_steps_from_manifest(session, project_id, spec.item_id, spec.manifest_steps)

    session.flush()

    return {
        "project_id": project_id,
        "id": spec.item_id,
        "title": spec.title,
        "status": "draft",
        "created": True,
    }


# ---------------------------------------------------------------------------
# Workflow step insertion helper (shared with approve rebuild)
# ---------------------------------------------------------------------------


def _insert_workflow_steps_from_manifest(
    session: Session,
    project_id: str,
    item_id: str,
    manifest_steps: list[dict[str, Any]],
) -> int:
    """Bulk-insert WorkflowStep rows from a manifest's steps list.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project scope.
        item_id: Owner work-item identifier.
        manifest_steps: Parsed steps list.

    Returns:
        Number of rows inserted.

    Raises:
        ValueError: When a step has an invalid ``timeout`` value.
    """
    from orch.cli.item_commands import (  # noqa: PLC0415
        agent_to_label,
        agent_to_step_type,
    )
    from orch.db.models import StepType  # noqa: PLC0415

    count = 0
    for idx, step_data in enumerate(manifest_steps):
        step_id_str = str(step_data.get("step", f"S{idx + 1:02d}"))
        agent = str(step_data.get("agent", ""))

        step_type_raw = step_data.get("step_type")
        if isinstance(step_type_raw, str):
            try:
                step_type: Any = StepType(step_type_raw)
            except ValueError:
                step_type = agent_to_step_type(agent)
        else:
            step_type = agent_to_step_type(agent)

        label_raw = step_data.get("agent_label")
        label = str(label_raw) if label_raw else agent_to_label(agent) or step_id_str

        description_raw = step_data.get("description")
        description = str(description_raw) if description_raw else None

        label_raw_val = step_data.get("step_label")
        step_label = str(label_raw_val) if label_raw_val else None

        num_str = step_id_str.lstrip("Ss")
        try:
            step_number = int(num_str)
        except ValueError:
            step_number = idx + 1

        prompt_raw = step_data.get("prompt")
        prompt_file = str(prompt_raw) if prompt_raw else None

        command_raw = step_data.get("command")
        command_val = str(command_raw) if command_raw else None

        gate_raw = step_data.get("gate")
        gate_val = str(gate_raw) if gate_raw else None

        timeout_raw = step_data.get("timeout")
        timeout_secs: int | None
        if timeout_raw is None:
            timeout_secs = None
        else:
            try:
                timeout_secs = int(timeout_raw)
            except (TypeError, ValueError):
                raise ValueError(
                    f"Invalid 'timeout' for step {step_id_str}: {timeout_raw!r} is not an integer"
                ) from None

        session.add(
            WorkflowStep(
                project_id=project_id,
                work_item_id=item_id,
                step_number=step_number,
                step_id=step_id_str,
                agent_label=label,
                opencode_agent=agent or None,
                step_type=step_type,
                step_label=step_label,
                description=description,
                prompt_file=prompt_file,
                command=command_val,
                gate=gate_val,
                timeout_secs=timeout_secs,
            )
        )
        count += 1

    session.flush()
    return count


# ---------------------------------------------------------------------------
# approve_work_item
# ---------------------------------------------------------------------------


def approve_work_item(session: Session, project_id: str, item_id: str) -> dict[str, Any]:
    """Transition a work item from draft to approved.

    This is a simplified service-layer approve that does NOT perform manifest
    drift detection, active-file commitment checks, or evidence ingestion —
    those are CLI-specific concerns tied to the operator's working directory.
    The MCP/service path approves the status transition only.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project scope.
        item_id: Work-item identifier.

    Returns:
        Dict with ``project_id``, ``id``, ``status`` (``"approved"``),
        ``manifest_refreshed`` (``False``).  Matches CLI ``iw approve --json``.

    Raises:
        ServiceError: When the item does not exist or the transition is invalid.
    """
    from orch.cli.item_commands import validate_approve_transition  # noqa: PLC0415

    item = session.execute(
        select(WorkItem)
        .options(load_only(*_WORK_ITEM_CLI_COLUMNS))
        .where(WorkItem.project_id == project_id, WorkItem.id == item_id)
    ).scalar_one_or_none()

    if item is None:
        raise ServiceError(f"Work item {item_id} not found in project {project_id}", code=1)

    error = validate_approve_transition(item.status, item.type)
    if error:
        raise ServiceError(error, code=1)

    item.status = WorkItemStatus.approved
    item.updated_at = datetime.now(UTC)
    session.flush()

    return {
        "project_id": project_id,
        "id": item_id,
        "status": "approved",
        "manifest_refreshed": False,
    }


# ---------------------------------------------------------------------------
# unapprove_work_item
# ---------------------------------------------------------------------------


def unapprove_work_item(session: Session, project_id: str, item_id: str) -> dict[str, Any]:
    """Transition a work item from approved back to draft.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project scope.
        item_id: Work-item identifier.

    Returns:
        Dict with ``project_id``, ``id``, ``status`` (``"draft"``).
        Matches CLI ``iw unapprove --json``.

    Raises:
        ServiceError: When the item does not exist or the transition is invalid
            (wrong status or item is in an active batch).
    """
    from orch.cli.item_commands import validate_unapprove_transition  # noqa: PLC0415

    item = session.execute(
        select(WorkItem)
        .options(load_only(*_WORK_ITEM_CLI_COLUMNS))
        .where(WorkItem.project_id == project_id, WorkItem.id == item_id)
    ).scalar_one_or_none()

    if item is None:
        raise ServiceError(f"Work item {item_id} not found in project {project_id}", code=1)

    # Detect active batch membership
    active_batch_item = session.execute(
        select(BatchItem)
        .options(load_only(*_BATCH_ITEM_CLI_COLUMNS))
        .join(
            Batch,
            (BatchItem.project_id == Batch.project_id) & (BatchItem.batch_id == Batch.id),
        )
        .where(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
            Batch.status.in_(_ACTIVE_BATCH_STATUSES),
        )
    ).scalar_one_or_none()

    active_batch_id: str | None = (
        active_batch_item.batch_id if active_batch_item is not None else None
    )

    error = validate_unapprove_transition(item.status, active_batch_id, item.type)
    if error:
        exit_code = 4 if active_batch_id else 1
        raise ServiceError(error, code=exit_code)

    item.status = WorkItemStatus.draft
    item.updated_at = datetime.now(UTC)
    session.flush()

    return {"project_id": project_id, "id": item_id, "status": "draft"}


# ---------------------------------------------------------------------------
# get_work_item_status
# ---------------------------------------------------------------------------


def get_work_item_status(session: Session, project_id: str, item_id: str) -> dict[str, Any]:
    """Return the full status dict for a work item.

    The returned dict is byte-identical to the CLI ``iw item-status --json``
    output shape. It uses the same pinned column tuples defined in this module.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project scope.
        item_id: Work-item identifier.

    Returns:
        Full status dict with ``project_id``, ``id``, ``title``, ``status``,
        ``phase``, ``total_steps``, ``completed_steps``, ``current_step``,
        ``batch_id``, ``worktree``, ``created_at``, ``updated_at``, ``steps``.

    Raises:
        ServiceError: When the item does not exist.
    """
    item = session.execute(
        select(WorkItem)
        .options(load_only(*_WORK_ITEM_CLI_COLUMNS))
        .where(WorkItem.project_id == project_id, WorkItem.id == item_id)
    ).scalar_one_or_none()

    if item is None:
        raise ServiceError(f"Work item {item_id} not found in project {project_id}", code=1)

    steps = (
        session.execute(
            select(WorkflowStep)
            .options(load_only(*_WORKFLOW_STEP_CLI_COLUMNS))
            .where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
            .order_by(WorkflowStep.step_number)
        )
        .scalars()
        .all()
    )

    total_steps = len(steps)
    completed_steps = sum(1 for s in steps if s.status == StepStatus.completed)

    current_step: dict[str, Any] | None = None
    for s in steps:
        if s.status == StepStatus.in_progress:
            duration_str = None
            if s.started_at:
                secs = int((datetime.now(UTC) - s.started_at.replace(tzinfo=UTC)).total_seconds())
                duration_str = f"{secs // 60}m {secs % 60}s"
            current_step = {
                "step_id": s.step_id,
                "label": s.agent_label,
                "status": s.status.value,
                "duration": duration_str,
            }
            break

    # Find active batch membership (most recent batch for this item)
    active_batch_item = session.execute(
        select(BatchItem)
        .options(load_only(*_BATCH_ITEM_CLI_COLUMNS))
        .join(
            Batch,
            (BatchItem.project_id == Batch.project_id) & (BatchItem.batch_id == Batch.id),
        )
        .where(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
        )
        .order_by(Batch.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    batch_id: str | None = active_batch_item.batch_id if active_batch_item else None
    worktree: str | None = None
    if active_batch_item and isinstance(active_batch_item.worktree_info, dict):
        worktree = active_batch_item.worktree_info.get("path")

    return {
        "project_id": project_id,
        "id": item_id,
        "title": item.title,
        "status": item.status.value,
        "phase": item.phase.value,
        "total_steps": total_steps,
        "completed_steps": completed_steps,
        "current_step": current_step,
        "batch_id": batch_id,
        "worktree": worktree,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        "steps": [
            {
                "step_id": s.step_id,
                "step_number": s.step_number,
                "label": s.agent_label,
                "agent_label": s.agent_label,
                "opencode_agent": s.opencode_agent,
                "type": s.step_type.value,
                "step_type": s.step_type.value,
                "step_label": s.step_label,
                "status": s.status.value,
                "description": s.description,
                "prompt_file": s.prompt_file,
                "command": s.command,
                "gate": s.gate,
                "timeout_secs": s.timeout_secs,
            }
            for s in steps
        ],
    }


# ---------------------------------------------------------------------------
# retry_work_item
# ---------------------------------------------------------------------------


def retry_work_item(session: Session, project_id: str, item_id: str) -> dict[str, Any]:
    """Re-drive a dead-ended work item so the daemon resumes execution.

    Resets non-completed workflow steps to pending, moves the work item to
    ``in_progress``, resets the batch_item to ``pending``, and (if needed)
    moves the owning batch from ``completed_with_errors`` to ``executing``.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project scope.
        item_id: Work-item identifier.

    Returns:
        Dict with ``project_id``, ``id``, ``status`` (``"in_progress"``),
        ``retry`` (``True``).  When the item is already recovered (idempotent
        no-op), returns ``retry=False``.

    Raises:
        ServiceError: When the item does not exist or is not in a retryable
            state.
    """
    from orch.cli.item_commands import validate_item_retry_transition  # noqa: PLC0415

    item = session.execute(
        select(WorkItem)
        .options(load_only(*_WORK_ITEM_CLI_COLUMNS))
        .where(WorkItem.project_id == project_id, WorkItem.id == item_id)
    ).scalar_one_or_none()

    if item is None:
        raise ServiceError(f"Work item {item_id} not found in project {project_id}", code=1)

    # Load the most recent batch_item
    batch_item_row = session.execute(
        select(BatchItem)
        .where(
            BatchItem.project_id == project_id,
            BatchItem.work_item_id == item_id,
        )
        .order_by(BatchItem.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    batch_item_status: BatchItemStatus | None = batch_item_row.status if batch_item_row else None

    # Load owning batch
    batch_row = None
    batch_status = None
    if batch_item_row and batch_item_row.batch_id:
        batch_row = session.execute(
            select(Batch).where(Batch.project_id == project_id, Batch.id == batch_item_row.batch_id)
        ).scalar_one_or_none()
        batch_status = batch_row.status if batch_row else None

    error, is_idempotent_noop = validate_item_retry_transition(
        item.status, batch_item_status, batch_status
    )
    if error:
        raise ServiceError(error, code=1)

    if is_idempotent_noop:
        return {
            "project_id": project_id,
            "id": item_id,
            "status": item.status.value,
            "retry": False,
            "message": "Already recovered — no changes made",
        }

    # Capture prior states for audit
    prior_work_item_status = item.status
    prior_batch_item_status = batch_item_status
    prior_batch_status = batch_status

    # Reset non-completed workflow steps
    steps = (
        session.execute(
            select(WorkflowStep)
            .options(load_only(*_WORKFLOW_STEP_CLI_COLUMNS))
            .where(
                WorkflowStep.project_id == project_id,
                WorkflowStep.work_item_id == item_id,
            )
            .order_by(WorkflowStep.step_number)
        )
        .scalars()
        .all()
    )

    reset_step_ids: list[str] = []
    for step in steps:
        if step.status != StepStatus.completed:
            step.status = StepStatus.pending
            step.started_at = None
            step.completed_at = None
            reset_step_ids.append(step.step_id)

    item.status = WorkItemStatus.in_progress
    item.completed_at = None

    if batch_row and batch_status == BatchStatus.completed_with_errors:
        batch_row.status = BatchStatus.executing

    if batch_item_row:
        batch_item_row.status = BatchItemStatus.pending

    session.add(
        DaemonEvent(
            project_id=project_id,
            event_type="item_retry",
            entity_id=item_id,
            entity_type="work_item",
            message=(
                f"Item {item_id} re-driven by operator after recovery. "
                f"Prior work_item={prior_work_item_status.value}, "
                f"batch_item="
                f"{prior_batch_item_status.value if prior_batch_item_status else 'N/A'}, "
                f"batch={prior_batch_status.value if prior_batch_status else 'N/A'}. "
                f"Reset steps: {reset_step_ids}"
            ),
            event_metadata={
                "prior_work_item_status": prior_work_item_status.value,
                "prior_batch_item_status": (
                    prior_batch_item_status.value if prior_batch_item_status else None
                ),
                "prior_batch_status": (prior_batch_status.value if prior_batch_status else None),
                "new_work_item_status": item.status.value,
                "new_batch_item_status": (batch_item_row.status.value if batch_item_row else None),
                "new_batch_status": (batch_row.status.value if batch_row else None),
                "reset_step_ids": reset_step_ids,
                "operator_initiated": True,
            },
        )
    )
    session.flush()

    return {
        "project_id": project_id,
        "id": item_id,
        "status": "in_progress",
        "retry": True,
        "message": "Item re-driven — daemon will resume from first non-completed step",
    }


# ---------------------------------------------------------------------------
# list_work_items
# ---------------------------------------------------------------------------


def list_work_items(
    session: Session,
    project_id: str,
    *,
    status: str | None = None,
    item_type: str | None = None,
    phase: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Return a paginated list of work items for a project.

    Uses opaque-cursor (offset) pagination; the cursor is a base-10 string
    representation of the row offset.  Results are ordered newest-first by
    ``created_at``.

    Args:
        session: Active SQLAlchemy session.
        project_id: Project to query.
        status: Optional status filter (e.g. ``"draft"``, ``"approved"``).
        item_type: Optional type filter (e.g. ``"feature"``).
        phase: Optional phase filter (e.g. ``"active"``).
        cursor: Opaque pagination cursor returned by a previous call.
        limit: Maximum number of items to return (server-side cap: 50).

    Returns:
        Dict with keys:

        - ``items``: list of item dicts, each with ``id``, ``type``,
          ``title``, ``status``, ``phase``, ``created_at``, ``updated_at``,
          ``batch_id`` (``None`` when not in a batch).
        - ``next_cursor``: opaque string to pass as ``cursor`` on the next
          call, or ``None`` when there are no more results.
        - ``has_more``: bool.
        - ``total``: total number of rows matching the filters (unpaginated).
    """
    effective_limit = clamp_limit(limit)
    offset = int(cursor) if cursor and cursor.isdigit() else 0

    stmt = select(WorkItem).where(WorkItem.project_id == project_id)

    if status:
        try:
            status_enum = WorkItemStatus(status)
        except ValueError:
            valid = ", ".join(s.value for s in WorkItemStatus)
            raise ServiceError(
                f"Invalid status filter {status!r}; valid values: {valid}",
                code=1,
            ) from None
        stmt = stmt.where(WorkItem.status == status_enum)

    if item_type:
        matched = next(
            (wt for wt in WorkItemType if wt.value.lower() == item_type.lower()),
            None,
        )
        if matched is None:
            valid = ", ".join(t.value for t in WorkItemType)
            raise ServiceError(
                f"Invalid type filter {item_type!r}; valid values: {valid}",
                code=1,
            )
        stmt = stmt.where(WorkItem.type == matched)

    if phase:
        try:
            phase_enum = WorkItemPhase(phase)
        except ValueError:
            valid = ", ".join(p.value for p in WorkItemPhase)
            raise ServiceError(
                f"Invalid phase filter {phase!r}; valid values: {valid}",
                code=1,
            ) from None
        stmt = stmt.where(WorkItem.phase == phase_enum)

    stmt = stmt.order_by(WorkItem.created_at.desc())

    # Total count (before pagination)
    from sqlalchemy import func  # noqa: PLC0415

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = session.execute(count_stmt).scalar_one()

    # Paginated page
    rows = (
        session.execute(
            stmt.options(load_only(*_WORK_ITEM_CLI_COLUMNS)).offset(offset).limit(effective_limit)
        )
        .scalars()
        .all()
    )

    next_offset = offset + len(rows)
    has_more = next_offset < total
    next_cursor: str | None = str(next_offset) if has_more else None

    items = [
        {
            "id": r.id,
            "type": r.type.value,
            "title": r.title,
            "status": r.status.value,
            "phase": r.phase.value,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "batch_id": None,  # Populated below
        }
        for r in rows
    ]

    # Enrich batch_id: find the most recent batch membership for each item
    if rows:
        row_ids = [r.id for r in rows]
        batch_items = session.execute(
            select(BatchItem.work_item_id, BatchItem.batch_id)
            .where(
                BatchItem.project_id == project_id,
                BatchItem.work_item_id.in_(row_ids),
            )
            .order_by(BatchItem.id.desc())
        ).all()
        # Map: item_id → first (most recent) batch_id
        batch_map: dict[str, str] = {}
        for brow in batch_items:
            if brow.work_item_id not in batch_map:
                batch_map[brow.work_item_id] = brow.batch_id
        for item_dict in items:
            _id = item_dict["id"]
            item_dict["batch_id"] = batch_map.get(_id) if isinstance(_id, str) else None

    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "total": total,
    }
