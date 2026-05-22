"""Work item management CLI commands: register, approve, unapprove, archive, item-status."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
from sqlalchemy import select
from sqlalchemy.orm import load_only

from orch.active_files import ensure_active_files_committed
from orch.archive import archive_all_completed, archive_work_item
from orch.cli.utils import TYPE_TO_ID_PREFIX, output_error, resolve_project, validate_id_prefix
from orch.daemon.execution_report import (
    assemble_execution_report,
    render_execution_report_markdown,
    write_execution_report,
)
from orch.db.models import (
    Batch,
    BatchItem,
    BatchStatus,
    DaemonEvent,
    EvidencePhase,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)
from orch.design_doc_parser import parse_dependencies
from orch.evidences import EvidenceTooLargeError, ingest_phase_from_disk
from orch.qv_gate_validator import auto_skip_phantom_qv_gates
from orch.services import approve_merge

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
# Pure validation helpers (used by unit tests without DB)
# ---------------------------------------------------------------------------


def validate_approve_transition(
    current_status: WorkItemStatus, item_type: WorkItemType | None = None
) -> str | None:
    """Return an error message if approve is invalid, or None if OK."""
    if item_type == WorkItemType.Research:
        return (
            "Cannot approve research items — they auto-complete when the "
            "research document is created via 'iw doc-update'"
        )
    if current_status != WorkItemStatus.draft:
        return f"Cannot approve: current status is '{current_status.value}'"
    return None


def validate_unapprove_transition(
    current_status: WorkItemStatus,
    active_batch_id: str | None,
    item_type: WorkItemType | None = None,
) -> str | None:
    """Return an error message if unapprove is invalid, or None if OK."""
    if item_type == WorkItemType.Research:
        return "Cannot unapprove research items — they do not use the approval workflow"
    if current_status != WorkItemStatus.approved:
        return f"Cannot unapprove: current status is '{current_status.value}'"
    if active_batch_id:
        return f"Cannot unapprove: item is in batch {active_batch_id}"
    return None


# ---------------------------------------------------------------------------
# Agent → StepType inference for workflow manifests
# ---------------------------------------------------------------------------

# Ordered longest-match first so "code-review-fix-final" beats "code-review"
_AGENT_STEP_TYPE_PATTERNS: list[tuple[str, StepType]] = [
    ("code-review-fix-final", StepType.code_review_fix_final),
    ("code-review-final", StepType.code_review_final),
    ("code-review-fix", StepType.code_review_fix),
    ("code-review", StepType.code_review),
    ("backend-review", StepType.code_review),
    ("api-review", StepType.code_review),
    ("frontend-review", StepType.code_review),
    ("tests-review", StepType.code_review),
    ("database-review", StepType.code_review),
    ("pipeline-review", StepType.code_review),
    ("template-review", StepType.code_review),
    ("quality-validation", StepType.quality_validation),
    ("qv-gate", StepType.quality_validation),
    ("qv-fix", StepType.qv_fix),
    ("qv-browser", StepType.browser_verification),
    ("browser-verification", StepType.browser_verification),
    ("self-assess", StepType.self_assess),  # matches self-assess-impl, self_assess
]


def agent_to_step_type(agent: str) -> StepType:
    """Infer StepType from agent name slug. Defaults to implementation."""
    for pattern, step_type in _AGENT_STEP_TYPE_PATTERNS:
        if pattern in agent:
            return step_type
    return StepType.implementation


def agent_to_label(agent: str) -> str:
    """Convert agent slug to CamelCase label (strips trailing -impl)."""
    cleaned = agent.replace("-impl", "")
    return "".join(part.capitalize() for part in cleaned.split("-"))


# ---------------------------------------------------------------------------
# Manifest parsing
# ---------------------------------------------------------------------------


def _compute_manifest_digest(steps: list[dict[str, Any]]) -> str:
    """Compute a deterministic SHA-256 hex digest of a manifest's steps array.

    Canonicalization rules:
    - Drop keys whose values are None or empty strings from each step dict.
    - Serialize each step via json.dumps with sort_keys=True, separators=(",", ":").
    - Join with "\\n" and hash the result.

    This digest is stored on the WorkItem at register/approve time. On subsequent
    approves the on-disk manifest is re-parsed and re-digested; if the digest
    differs and the item is still in `draft`, the workflow_steps rows are
    atomically rebuilt from the current manifest.

    The digest covers only the steps array. Top-level manifest fields
    (title, _note, scope, browser_verification, …) are intentionally excluded:
    - `_note` is auto-stamped by _stamp_manifest_note() so it would flag every
      approve as drift if included.
    - `title` lives on the WorkItem row.
    - `scope` changes are caught downstream by the merge-time scope gate.
    """
    canonical_lines: list[str] = []
    for step in steps:
        # Drop None-valued and empty-string-valued keys
        filtered = {k: v for k, v in step.items() if v is not None and v != ""}
        canonical_lines.append(json.dumps(filtered, sort_keys=True, separators=(",", ":")))
    content = "\n".join(canonical_lines).encode("utf-8")
    return hashlib.sha256(content).hexdigest()


def parse_manifest_steps(manifest_path: Path) -> list[dict[str, Any]]:
    """Parse a workflow-manifest.json and return the steps list."""
    data: Any = json.loads(manifest_path.read_text())
    steps: list[Any] = data.get("steps", [])
    return [dict(s) for s in steps]


# CR-00023: marker text written into manifests at register time. Agents reading
# the manifest see this and know to prefer `iw item-status` for runtime state.
MANIFEST_NOTE_TEXT = (
    "This file is a design-time snapshot and may be out of date. "
    "For current step state, run: iw item-status <ID> --json. "
    "The DB is the authoritative source of truth (CR-00023)."
)


def _stamp_manifest_note(manifest_path: Path) -> None:
    """Rewrite the manifest in place to add a top-level `_note` field.

    Idempotent: skips the write when the note is already present and equal.
    Preserves all existing keys with byte-identical contents (only the `_note`
    key is added at the head of the JSON object). Failures to read or write
    the manifest are reported as warnings but do not fail the register
    operation.
    """
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        click.echo(
            f"Warning: could not read manifest to stamp _note: {exc}",
            err=True,
        )
        return

    if not isinstance(raw, dict):
        return
    if raw.get("_note") == MANIFEST_NOTE_TEXT:
        return

    stamped = {"_note": MANIFEST_NOTE_TEXT, **{k: v for k, v in raw.items() if k != "_note"}}
    try:
        manifest_path.write_text(
            json.dumps(stamped, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        click.echo(
            f"Warning: could not stamp manifest with _note header: {exc}",
            err=True,
        )


def _insert_workflow_steps_from_manifest(
    session: Any,
    project_id: str,
    item_id: str,
    manifest_steps: list[dict[str, Any]],
) -> int:
    """Bulk-insert WorkflowStep rows from a manifest's steps list.

    Used by both :func:`register` (first insert) and :func:`approve` (drift
    rebuild). Keeping the insertion logic in one place guarantees that
    register and approve-rebuild never diverge.

    Raises
    ------
    ValueError
        When a step has an invalid (non-integer) ``timeout`` value. The
        outer ``try/except`` in the caller converts this to an operator-facing
        error via :func:`output_error`.

    Returns
    -------
    int
        Number of rows inserted.
    """
    count = 0
    for idx, step_data in enumerate(manifest_steps):
        step_id_str = str(step_data.get("step", f"S{idx + 1:02d}"))
        agent = str(step_data.get("agent", ""))

        # Explicit step_type overrides inference
        step_type_raw = step_data.get("step_type")
        if isinstance(step_type_raw, str):
            try:
                step_type: StepType = StepType(step_type_raw)
            except ValueError:
                step_type = agent_to_step_type(agent)
        else:
            step_type = agent_to_step_type(agent)

        # Explicit agent_label overrides derivation
        label_raw = step_data.get("agent_label")
        label = str(label_raw) if label_raw else agent_to_label(agent) or step_id_str

        description_raw = step_data.get("description")
        description = str(description_raw) if description_raw else None

        label_raw_val = step_data.get("step_label")
        step_label = str(label_raw_val) if label_raw_val else None

        # Derive numeric step_number from step_id ("S01" → 1)
        num_str = step_id_str.lstrip("Ss")
        try:
            step_number = int(num_str)
        except ValueError:
            step_number = idx + 1

        # CR-00023: ingest manifest's prompt/command/gate/timeout into the
        # WorkflowStep row so iw item-status --json is a true superset of
        # the manifest and the daemon can read runtime info from the DB.
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
# Lookup tables
# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

_ITEM_TYPE_MAP: dict[str, WorkItemType] = {
    "feature": WorkItemType.Feature,
    "incident": WorkItemType.Issue,
    "cr": WorkItemType.ChangeRequest,
    "research": WorkItemType.Research,
}

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
# Commands
# ---------------------------------------------------------------------------


@click.command("register")
@click.argument("item_id")
@click.argument("title")
@click.option(
    "--type",
    "item_type",
    required=True,
    type=click.Choice(["feature", "incident", "cr", "research"]),
    help="Work item type",
)
@click.option("--design-doc", default=None, help="Relative path to design document")
@click.option("--steps-from", default=None, help="Path to workflow-manifest.json")
@click.option(
    "--functional-doc",
    default=None,
    help="Relative path to functional design document (auto-detected if not given)",
)
@click.pass_context
def register(
    ctx: click.Context,
    item_id: str,
    title: str,
    item_type: str,
    design_doc: str | None,
    steps_from: str | None,
    functional_doc: str | None,
) -> None:
    """Register a new work item in the database (idempotent)."""
    if not validate_id_prefix(item_id, item_type):
        expected = TYPE_TO_ID_PREFIX.get(item_type, "?")
        output_error(
            ctx,
            f"ID '{item_id}' does not match expected prefix '{expected}' for type '{item_type}'",
            2,
        )

    project_id = resolve_project(ctx)

    # Pre-parse manifest steps (fail fast before touching DB)
    manifest_steps: list[dict[str, Any]] = []
    if steps_from:
        manifest_path = Path(steps_from)
        if not manifest_path.exists():
            output_error(ctx, f"Manifest file not found: {steps_from}", 2)
        try:
            manifest_steps = parse_manifest_steps(manifest_path)
        except (json.JSONDecodeError, OSError) as exc:
            output_error(ctx, f"Invalid manifest file: {exc}", 2)

    get_session = ctx.obj["get_session"]
    try:
        with get_session() as session:
            # Idempotency check
            existing = session.execute(
                select(WorkItem)
                .options(load_only(*_WORK_ITEM_CLI_COLUMNS))
                .where(WorkItem.project_id == project_id, WorkItem.id == item_id)
            ).scalar_one_or_none()
            if existing is not None:
                if ctx.obj.get("json"):
                    click.echo(
                        json.dumps(
                            {
                                "project_id": project_id,
                                "id": item_id,
                                "status": existing.status.value,
                                "created": False,
                                "message": "Already registered",
                            }
                        )
                    )
                else:
                    click.echo(
                        f"Already registered {item_id}: {existing.title} [{existing.status.value}]"
                    )
                return

            # Load the design doc content from disk so downstream consumers
            # (batch planner file-overlap detection, FTS, dashboard preview)
            # have the full text — not just a path. Resolved relative to the
            # current working directory, which by convention is the project
            # repo root when `iw register` is invoked from the
            # iw-new-* skills. Missing files are tolerated with a warning so
            # that registration stays idempotent when the doc lives outside
            # the checkout (e.g. planned items).
            design_doc_content: str | None = None
            if design_doc:
                doc_path = Path(design_doc)
                if not doc_path.is_absolute():
                    doc_path = Path.cwd() / doc_path
                try:
                    design_doc_content = doc_path.read_text(encoding="utf-8")
                except FileNotFoundError:
                    click.echo(
                        f"Warning: design doc not found at {doc_path} — "
                        "item will be registered without content (batch planner "
                        "file-overlap detection will not see this item's files)",
                        err=True,
                    )
                except OSError as exc:
                    click.echo(
                        f"Warning: could not read design doc {doc_path}: {exc}",
                        err=True,
                    )

            # Load the functional doc content from disk, auto-detected next to the
            # technical design doc (same directory, sibling file) or explicitly
            # provided via --functional-doc.  The "explicit override with missing
            # file" branch must fail with a non-zero exit; absent sibling is
            # tolerated.
            functional_doc_content: str | None = None
            functional_doc_path: str | None = None

            if functional_doc is not None:
                # Explicit override — resolve relative to CWD like design_doc does
                explicit_path = Path(functional_doc)
                if not explicit_path.is_absolute():
                    explicit_path = Path.cwd() / explicit_path
                if not explicit_path.exists():
                    output_error(
                        ctx,
                        f"Functional doc file not found: {explicit_path}",
                        2,
                    )
                try:
                    functional_doc_content = explicit_path.read_text(encoding="utf-8")
                    functional_doc_path = functional_doc
                except OSError as exc:
                    output_error(
                        ctx,
                        f"Could not read functional doc {explicit_path}: {exc}",
                        2,
                    )
            elif design_doc:
                # Auto-detect sibling <ID>_Functional.md next to the technical doc
                design_doc_base = Path(design_doc)
                if not design_doc_base.is_absolute():
                    design_doc_base = Path.cwd() / design_doc_base
                candidate = design_doc_base.parent / f"{item_id}_Functional.md"
                if candidate.exists():
                    try:
                        functional_doc_content = candidate.read_text(encoding="utf-8")
                        # An empty file is treated as absent — both fields None,
                        # consistent with how the design doc treats empty/missing.
                        if not functional_doc_content:
                            functional_doc_content = None
                            functional_doc_path = None
                        else:
                            functional_doc_path = str(candidate.relative_to(Path.cwd()))
                    except OSError as exc:
                        click.echo(
                            f"Warning: could not read functional doc {candidate}: {exc} "
                            "— proceeding without it",
                            err=True,
                        )
                        functional_doc_path = None
                        functional_doc_content = None
                # else: candidate absent — leave both fields None, proceed normally

            # Parse dependencies from design doc content
            deps = parse_dependencies(design_doc_content)
            filtered_depends_on = [d for d in deps.depends_on if d != item_id]
            if any(d == item_id for d in deps.depends_on):
                click.echo(
                    f"Warning: {item_id} declares a self-dependency — filtering out",
                    err=True,
                )

            # F-00076: populate impacted_paths from declared section, fallback to regex.
            from datetime import UTC, datetime

            from orch.batch_planner import extract_affected_files
            from orch.design_doc_parser import parse_impacted_paths

            try:
                scope_result = parse_impacted_paths(design_doc_content)
            except ValueError as ve:
                output_error(
                    ctx,
                    f"Design doc validation error in ## Impacted Paths: {ve}",
                    1,
                )

            if scope_result.found:
                impacted_paths = scope_result.paths
                scope_extraction: dict[str, object] = {"source": "declared"}
            else:
                impacted_paths = extract_affected_files(design_doc_content)
                if impacted_paths:
                    scope_extraction = {
                        "source": "regex_fallback",
                        "warned_at": datetime.now(UTC).isoformat(),
                    }
                    click.echo(
                        f"Warning: {item_id}: scope auto-extracted, please verify — "
                        "no '## Impacted Paths' section in design doc",
                        err=True,
                    )
                else:
                    scope_extraction = {"source": "none"}

            # Compute digest for initial registration (only on first insert —
            # the early-return branch above does not reach here).
            initial_digest: str | None = None
            if manifest_steps:
                initial_digest = _compute_manifest_digest(manifest_steps)

            # Insert work item
            work_item = WorkItem(
                project_id=project_id,
                id=item_id,
                type=_ITEM_TYPE_MAP[item_type],
                title=title,
                design_doc_path=design_doc,
                design_doc_content=design_doc_content,
                functional_doc_path=functional_doc_path,
                functional_doc_content=functional_doc_content,
                status=WorkItemStatus.draft,
                phase=WorkItemPhase.active,
                impacted_paths=impacted_paths,
                config={"scope_extraction": scope_extraction},
                depends_on=filtered_depends_on,
                blocks=deps.blocks,
                manifest_digest=initial_digest,
            )
            session.add(work_item)
            session.flush()

            # Blocks inversion: for each item this work item blocks, add this
            # item's ID to the blocked item's depends_on (de-duplicated).
            for blocked_id in deps.blocks:
                blocked_item = session.execute(
                    select(WorkItem)
                    .options(load_only(*_WORK_ITEM_CLI_COLUMNS))
                    .where(WorkItem.project_id == project_id, WorkItem.id == blocked_id)
                ).scalar_one_or_none()
                if blocked_item is None:
                    click.echo(
                        f"Warning: {item_id} blocks '{blocked_id}' which is not yet "
                        f"registered — skipping inversion",
                        err=True,
                    )
                    continue
                if item_id not in blocked_item.depends_on:
                    blocked_item.depends_on = blocked_item.depends_on + [item_id]

            _insert_workflow_steps_from_manifest(session, project_id, item_id, manifest_steps)

            session.flush()

            # CR-00023: stamp the on-disk manifest as a non-authoritative snapshot.
            # Idempotent: only writes if the _note key is missing or stale.
            if steps_from:
                _stamp_manifest_note(Path(steps_from))

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "project_id": project_id,
                    "id": item_id,
                    "title": title,
                    "status": "draft",
                    "created": True,
                }
            )
        )
    else:
        click.echo(f"Registered {item_id}: {title} [draft]")


@click.command("approve")
@click.argument("item_id")
@click.pass_context
def approve(ctx: click.Context, item_id: str) -> None:
    """Approve a work item for execution (draft → approved).

    Before flipping status, this command checks whether the on-disk
    workflow-manifest.json has drifted from the digest stored at register
    time. When drift is detected and the item is still in ``draft``, the
    ``workflow_steps`` rows are atomically rebuilt from the current manifest
    and a ``manifest_refreshed`` daemon event is emitted.

    Items registered before the ``manifest_digest`` column (pre-I-00102) have
    NULL stored; the first approve always triggers a refresh and stores the
    digest, so old items are backfill-safe.
    """
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]
    manifest_refreshed = False
    old_step_count = 0
    new_step_count = 0

    try:
        with get_session() as session:
            item = session.execute(
                select(WorkItem)
                .options(load_only(*_WORK_ITEM_CLI_COLUMNS, WorkItem.manifest_digest))
                .where(WorkItem.project_id == project_id, WorkItem.id == item_id)
            ).scalar_one_or_none()
            if item is None:
                output_error(ctx, f"Work item {item_id} not found in project {project_id}", 1)

            error = validate_approve_transition(item.status, item.type)
            if error:
                output_error(ctx, error, 1)

            # -----------------------------------------------------------------
            # §1  Resolve on-disk manifest path
            # -----------------------------------------------------------------
            repo_root_raw = ctx.obj.get("repo_root", "") or str(Path.cwd())
            repo_root = Path(repo_root_raw)
            if item.design_doc_path:
                # Derive from design doc: sibling workflow-manifest.json next to the design doc
                design_doc = Path(item.design_doc_path)
                if not design_doc.is_absolute():
                    design_doc = repo_root / design_doc
                manifest_path = design_doc.parent / "workflow-manifest.json"
            else:
                # Fallback: canonical location relative to repo_root
                manifest_path = repo_root / "ai-dev" / "active" / item_id / "workflow-manifest.json"

            # -----------------------------------------------------------------
            # §2  Parse and digest current on-disk manifest
            # -----------------------------------------------------------------
            # Only require the on-disk manifest when we have a path to check:
            # - old_digest is not None → item was registered with a manifest (drift possible)
            # - design_doc_path is not None → deterministic path derivation exists
            # When neither holds (pre-I-00102 item, or item registered without manifest)
            # no drift detection is possible — skip the check and proceed with approve.
            old_digest = item.manifest_digest  # may be NULL for pre-I-00102 items
            manifest_required = old_digest is not None or item.design_doc_path is not None

            if manifest_required and not manifest_path.exists():
                output_error(
                    ctx,
                    (
                        f"Manifest file not found: {manifest_path} — "
                        "cannot approve without the current manifest"
                    ),
                    1,
                )

            new_digest: str | None = None  # set below when manifest_required is True

            if manifest_required:
                try:
                    disk_steps = parse_manifest_steps(manifest_path)
                except (json.JSONDecodeError, OSError) as exc:
                    output_error(ctx, f"Invalid manifest file {manifest_path}: {exc}", 1)

                new_digest = _compute_manifest_digest(disk_steps)

            # -----------------------------------------------------------------
            # §3  Drift detection — only when a manifest is available to compare
            # -----------------------------------------------------------------
            if not manifest_required:
                # No drift detection possible — no manifest path and no stored digest.
                # Approve proceeds without refresh (no manifest to rebuild from).
                manifest_refreshed = False
            elif new_digest == old_digest:
                # No drift — proceed with existing workflow_steps unchanged
                pass  # pragma: no cover  (branch exercised by integration tests)
            elif item.status != WorkItemStatus.draft:
                # Cannot arise in approve() (status guard above), but kept as a
                # hard defensive assert so the refresh path stays draft-only even
                # if future callers reuse this logic.
                raise RuntimeError(
                    f"manifest_refreshed path called on non-draft item {item_id} "
                    f"(status={item.status.value}) — refresh is draft-only by design (AC3)"
                )
            else:
                # -----------------------------------------------------------------
                # §4  Drift detected AND item is in draft — rebuild workflow_steps
                # -----------------------------------------------------------------
                old_step_count = (
                    session.query(WorkflowStep)
                    .filter(
                        WorkflowStep.project_id == project_id,
                        WorkflowStep.work_item_id == item_id,
                    )
                    .count()
                )

                # Delete all existing rows (unique constraint on step_number means
                # an in-place UPDATE is fragile — full replace is correct because
                # the item is in draft and no run history exists)
                session.query(WorkflowStep).filter(
                    WorkflowStep.project_id == project_id,
                    WorkflowStep.work_item_id == item_id,
                ).delete(synchronize_session=False)

                # Re-insert from current on-disk manifest using the shared helper
                new_step_count = _insert_workflow_steps_from_manifest(
                    session, project_id, item_id, disk_steps
                )

                # Update digest on the WorkItem
                item.manifest_digest = new_digest

                # Emit audit event
                session.add(
                    DaemonEvent(
                        project_id=project_id,
                        event_type="manifest_refreshed",
                        entity_id=item_id,
                        entity_type="work_item",
                        message=(
                            f"Workflow steps populated from manifest for {item_id} "
                            f"({old_step_count} → {new_step_count} steps)"
                            if old_digest is None
                            else f"Manifest drifted since register — workflow_steps rebuilt "
                            f"for {item_id} ({old_step_count} → {new_step_count} steps)"
                        ),
                        event_metadata={
                            "old_digest": old_digest,
                            "new_digest": new_digest,
                            "old_step_count": old_step_count,
                            "new_step_count": new_step_count,
                            "trigger": "approve",
                            "backfill": old_digest is None,
                        },
                    )
                )
                manifest_refreshed = True

            # -----------------------------------------------------------------
            # §5  Proceed with the rest of approve (unchanged)
            # -----------------------------------------------------------------
            # Only check active-file commitment when a design doc was registered.
            # Items registered without --design-doc have no guaranteed active
            # directory structure (test_full_flow_next_id_register_approve and
            # similar minimal flows); skip the check so approve is not gated
            # on an absent ai-dev/active/<ID>/ path.
            if repo_root and item.design_doc_path:
                try:
                    ensure_active_files_committed(repo_root, item_id, item.title)
                except ValueError as exc:
                    output_error(ctx, str(exc), 1)

            try:
                ingest_phase_from_disk(
                    session=session,
                    project_id=project_id,
                    work_item_id=item_id,
                    phase=EvidencePhase.pre,
                    root=repo_root,
                    step_id=None,
                )
            except EvidenceTooLargeError as exc:
                output_error(ctx, str(exc), 1)

            item.status = WorkItemStatus.approved
            item.updated_at = datetime.now(UTC)

            session.flush()

            skipped = auto_skip_phantom_qv_gates(session, project_id, item_id, trigger="approve")

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        result: dict[str, Any] = {
            "project_id": project_id,
            "id": item_id,
            "status": "approved",
            "manifest_refreshed": manifest_refreshed,
        }
        if skipped:
            result["auto_skipped_steps"] = [
                {"step_id": s, "gate": g, "reason": r} for s, g, r in skipped
            ]
        click.echo(json.dumps(result))
    else:
        click.echo(f"Approved {item_id}")
        if manifest_refreshed:
            click.echo(
                f"Refreshed workflow_steps from manifest "
                f"({old_step_count} → {new_step_count} steps)"
            )
        for step_id, gate, reason in skipped:
            click.echo(f"  Auto-skipped phantom gate {step_id} ({gate}): {reason}")


@click.command("unapprove")
@click.argument("item_id")
@click.pass_context
def unapprove(ctx: click.Context, item_id: str) -> None:
    """Revert an approved work item back to draft (approved → draft)."""
    from sqlalchemy import select

    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            item = session.execute(
                select(WorkItem)
                .options(load_only(*_WORK_ITEM_CLI_COLUMNS))
                .where(WorkItem.project_id == project_id, WorkItem.id == item_id)
            ).scalar_one_or_none()
            if item is None:
                output_error(ctx, f"Work item {item_id} not found in project {project_id}", 1)

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
                output_error(ctx, error, exit_code)

            item.status = WorkItemStatus.draft
            item.updated_at = datetime.now(UTC)
            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps({"project_id": project_id, "id": item_id, "status": "draft"}))
    else:
        click.echo(f"Unapproved {item_id}")


@click.command("archive")
@click.argument("item_id", required=False, default=None)
@click.option("--all-completed", is_flag=True, help="Archive all completed items in the project")
@click.option(
    "--no-cleanup",
    is_flag=True,
    help="Store in DB but do not delete active files from project repo",
)
@click.option(
    "--archive-dir",
    envvar="IW_CORE_ARCHIVE_DIR",
    default=None,
    help="Directory for compressed archives (defaults to IW_CORE_ARCHIVE_DIR env var)",
)
@click.pass_context
def archive(
    ctx: click.Context,
    item_id: str | None,
    all_completed: bool,
    no_cleanup: bool,
    archive_dir: str | None,
) -> None:
    """Archive completed work items (Tier 1 DB + Tier 2 .tar.zst compression)."""
    if not item_id and not all_completed:
        output_error(ctx, "Provide an item ID or use --all-completed", 2)
    if item_id and all_completed:
        output_error(ctx, "Cannot specify both an item ID and --all-completed", 2)

    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]
    cleanup = not no_cleanup

    try:
        with get_session() as session:
            if all_completed:
                archived_ids = archive_all_completed(session, project_id, archive_dir)
            else:
                if item_id is None:
                    output_error(ctx, "Provide an item ID or use --all-completed", 2)
                archive_work_item(session, project_id, item_id, archive_dir, cleanup=cleanup)
                archived_ids = [item_id]

    except ValueError as exc:
        output_error(ctx, str(exc), 1)
    except Exception as exc:
        output_error(ctx, f"Archive error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {"project_id": project_id, "archived": archived_ids, "count": len(archived_ids)}
            )
        )
    else:
        for aid in archived_ids:
            click.echo(f"Archived {aid}")


@click.command("item-cancel")
@click.argument("item_id")
@click.option(
    "--to-draft",
    is_flag=True,
    help="After cancelling, reset status to 'draft' and reset all workflow steps to pending.",
)
@click.option(
    "--reason",
    default="cancelled by operator",
    show_default=True,
    help="Free-text reason recorded on the cancellation event.",
)
@click.pass_context
def item_cancel(ctx: click.Context, item_id: str, to_draft: bool, reason: str) -> None:
    """Cancel a single work item not owned by an active batch.

    Kills any running step process, marks pending/in-progress workflow steps
    as skipped, and tears down any leftover worktree compose stack. Moves the
    item to 'cancelled' by default, or to 'draft' (with steps reset) when
    --to-draft is passed.

    If the item is in an *active* (non-terminal) batch, this command refuses
    and prompts the operator to run 'iw batch-cancel' instead.
    """
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    from orch.cancel import cancel_work_item  # noqa: PLC0415

    result_payload: dict[str, Any] = {}
    try:
        with get_session() as session:
            cancel_result = cancel_work_item(
                session,
                project_id,
                item_id,
                reason=reason,
                to_draft=to_draft,
            )
            new_status = "draft" if to_draft else "cancelled"
            result_payload = {
                "project_id": project_id,
                "id": item_id,
                "status": new_status,
                "to_draft": to_draft,
                "teardown_errors": cancel_result.teardown_errors,
            }

    except LookupError as exc:
        output_error(ctx, str(exc), 1)
    except ValueError as exc:
        # Exit 4 mirrors `unapprove` when the item is gated by batch membership;
        # all other validation errors use exit 1.
        exit_code = 4 if "active batch" in str(exc) else 1
        output_error(ctx, str(exc), exit_code)
    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps(result_payload))
    else:
        verb = "Cancelled and reset to draft" if to_draft else "Cancelled"
        click.echo(f"{verb} {item_id} ({reason})")
        for err in result_payload.get("teardown_errors", []):
            click.echo(f"  Warning: {err}")


@click.command("item-status")
@click.argument("item_id")
@click.option("--json", "-j", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.pass_context
def item_status(ctx: click.Context, item_id: str, json_output: bool) -> None:
    """Show the current status of a work item."""
    if json_output:
        ctx.obj["json"] = True
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    result: dict[str, Any] = {}

    try:
        with get_session() as session:
            item = session.execute(
                select(WorkItem)
                .options(load_only(*_WORK_ITEM_CLI_COLUMNS))
                .where(WorkItem.project_id == project_id, WorkItem.id == item_id)
            ).scalar_one_or_none()
            if item is None:
                output_error(ctx, f"Work item {item_id} not found in project {project_id}", 1)

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
                        secs = int(
                            (datetime.now(UTC) - s.started_at.replace(tzinfo=UTC)).total_seconds()
                        )
                        duration_str = f"{secs // 60}m {secs % 60}s"
                    current_step = {
                        "step_id": s.step_id,
                        "label": s.agent_label,
                        "status": s.status.value,
                        "duration": duration_str,
                    }
                    break

            # Find active batch membership
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

            result = {
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
                        # CR-00023: per-step entries are a true superset of the
                        # workflow-manifest.json `steps[]` shape so agents can
                        # use iw item-status --json as the single source of
                        # truth for runtime step info.
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

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps(result))
    else:
        click.echo(f"{item_id}: {result['title']}")
        click.echo(f"  Status: {result['status']} | Phase: {result['phase']}")
        step_info = f"{result['completed_steps']}/{result['total_steps']} completed"
        if result.get("current_step"):
            cs = result["current_step"]
            dur = f", {cs['duration']}" if cs.get("duration") else ""
            step_info += f" | Current: {cs['step_id']} {cs['label']} ({cs['status']}{dur})"
        click.echo(f"  Steps: {step_info}")
        batch_str = result.get("batch_id") or "—"
        wt_str = result.get("worktree") or "—"
        click.echo(f"  Batch: {batch_str} | Worktree: {wt_str}")
        created = (result.get("created_at") or "")[:16]
        updated = (result.get("updated_at") or "")[:16]
        click.echo(f"  Created: {created} | Updated: {updated}")


@click.command("item-report")
@click.argument("item_id")
@click.option("--stdout", is_flag=True, help="Print report to stdout instead of writing to disk")
@click.option(
    "--archive-dir",
    envvar="IW_CORE_ARCHIVE_DIR",
    default=None,
    help="Archive directory override",
)
@click.pass_context
def item_report(ctx: click.Context, item_id: str, stdout: bool, archive_dir: str | None) -> None:  # noqa: ARG001
    """Generate and write the execution report for a work item."""
    from orch.daemon.execution_report import ExecutionReportResolutionError

    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            item = session.execute(
                select(WorkItem)
                .options(load_only(*_WORK_ITEM_CLI_COLUMNS))
                .where(WorkItem.project_id == project_id, WorkItem.id == item_id)
            ).scalar_one_or_none()
            if item is None:
                output_error(ctx, f"Work item {item_id} not found in project {project_id}", 1)

            data = assemble_execution_report(session, project_id, item_id)

            if stdout:
                markdown = render_execution_report_markdown(data)
                click.echo(markdown)
                return

            path = write_execution_report(session, project_id, item_id)
            click.echo(f"Report written to {path}")

    except ExecutionReportResolutionError as exc:
        output_error(ctx, str(exc), 2)
    except Exception as exc:
        output_error(ctx, f"Report error: {exc}", 1)


@click.command("approve-merge")
@click.argument("item_id")
@click.option(
    "--project",
    "project_id_opt",
    default=None,
    help="Override project id (default: current project)",
)
@click.pass_context
def approve_merge_cmd(ctx: click.Context, item_id: str, project_id_opt: str | None) -> None:
    """Approve a manual merge for a batch item awaiting approval."""
    project_id = project_id_opt if project_id_opt else resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            approve_merge(session, project_id, item_id)

    except ValueError as exc:
        output_error(ctx, str(exc), 4)
    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps({"item_id": item_id, "status": "completed"}))
    else:
        click.echo(f"Approved merge for {item_id}")
