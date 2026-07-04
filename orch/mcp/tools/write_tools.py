"""Gated write MCP tool functions for IW AI Core.

Defines write tools at two blast-radius tiers:

**Tier-1** (plain sync, ungated — allow by default):
  - ``work_item_next_id``
  - ``work_item_register``

**Tier-2** (async, gated via ``enforce_and_run`` — ask by default):
  - ``work_item_approve``
  - ``batch_create``
  - ``batch_approve``
  - ``batch_control``
  - ``item_retry``

**Tier-3** (async, gated via ``enforce_and_run`` — deny by default, irreversible):
  - ``approve_merge``
  - ``batch_cancel``
  - ``work_item_archive``
  - ``work_item_cancel``

All tools are registered on the MCP server via ``register(mcp)`` ONLY when
``write_tools_enabled()`` returns True (i.e. ``IW_CORE_MCP_ENABLE_WRITE_TOOLS``
is set to ``1``/``true``/``yes``).  The plain functions are always importable
and callable by tests regardless of the env flag.

Gated tools accept an optional ``approval_token`` parameter. When the effective
policy is ``ask`` and no token is supplied, the tool returns an
``approval_required`` envelope instead of executing — get a human to
``iw mcp approve <token>``, then retry with ``approval_token`` set.

Batch execution is **asynchronous**: ``batch_approve`` queues the batch for the
daemon, which processes it on the next poll (default interval 60 s). Poll
``batch_status`` to observe progress.

Item IDs must be ``approved`` before they can be added to a batch via
``batch_create`` — use ``work_item_approve`` first.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

# Context must be at module level (not TYPE_CHECKING only) so FastMCP's
# transform_context_annotations can resolve it via get_type_hints() at
# tool-registration time.  Moving it into TYPE_CHECKING breaks registration.
from fastmcp import Context  # noqa: TC002

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Tier-1 tools — plain sync, ungated (allow by default)
# ---------------------------------------------------------------------------


def work_item_next_id(project_id: str, item_type: str) -> dict[str, Any]:
    """Allocate the next sequential ID for a given item type.

    Atomically increments the per-project ID sequence for the requested type
    and returns the formatted ID (e.g. ``F-00042``).  This call is NOT
    idempotent — each invocation consumes one sequence slot.

    Args:
        project_id: Project identifier (see ``project_list``).
        item_type: Work-item type: ``feature``, ``incident``, ``cr``, or
            ``research``.

    Returns:
        Dict with ``item_id`` (e.g. ``F-00042``), ``item_type``, and
        ``project_id``.

    Raises:
        ToolError: When ``project_id`` does not exist or ``item_type`` is not
            a recognised type.
    """
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from orch.cli.id_commands import allocate_next_id  # noqa: PLC0415
    from orch.cli.utils import TYPE_TO_PREFIX  # noqa: PLC0415
    from orch.mcp.audit import record_audit  # noqa: PLC0415
    from orch.mcp.context import session_scope  # noqa: PLC0415
    from orch.services._common import ServiceError, resolve_and_validate_project  # noqa: PLC0415

    _args = {"project_id": project_id, "item_type": item_type}
    # Map MCP item_type strings → id_sequence prefix letters.
    _type_to_prefix_key = {
        "feature": "feature",
        "incident": "incident",
        "cr": "cr",
        "research": "research",
    }
    prefix_key = _type_to_prefix_key.get(item_type)
    if prefix_key is None:
        record_audit(
            tool_name="work_item_next_id",
            project_id=project_id,
            arguments=_args,
            outcome="error",
            error=f"Unknown item type: {item_type!r}",
        )
        raise ToolError(f"Unknown item type: {item_type!r}")

    prefix = TYPE_TO_PREFIX.get(prefix_key)
    if prefix is None:
        record_audit(
            tool_name="work_item_next_id",
            project_id=project_id,
            arguments=_args,
            outcome="error",
            error=f"No prefix mapping for item type: {item_type!r}",
        )
        raise ToolError(f"No prefix mapping for item type: {item_type!r}")

    try:
        with session_scope() as session:
            resolve_and_validate_project(session, project_id)
            _num, item_id = allocate_next_id(session, project_id, prefix)
    except ServiceError as e:
        record_audit(
            tool_name="work_item_next_id",
            project_id=project_id,
            arguments=_args,
            outcome="error",
            error=e.message,
        )
        raise ToolError(e.message) from e

    result = {"item_id": item_id, "item_type": item_type, "project_id": project_id}
    record_audit(
        tool_name="work_item_next_id",
        project_id=project_id,
        arguments=_args,
        outcome="success",
        result_summary=f"Allocated {item_id}",
    )
    return result


def work_item_register(
    project_id: str,
    item_id: str,
    title: str,
    item_type: str,
    design_doc_path: str | None = None,
    design_doc_content: str | None = None,
    manifest_path: str | None = None,
    manifest_steps: list[dict[str, Any]] | None = None,
    functional_doc_path: str | None = None,
    functional_doc_content: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Register a new work item, optionally from disk paths or inline content.

    This tool is idempotent by ``(project_id, item_id)``: calling it a second
    time with the same identifiers returns ``{"created": False}`` without
    modifying any existing data.

    Supply either ``design_doc_path`` (reads from disk) OR
    ``design_doc_content`` (inline string).  Similarly, supply either
    ``manifest_path`` (reads the JSON file) OR ``manifest_steps`` (inline
    list).  Path arguments take precedence when both are supplied.

    When ``dry_run=True``, the spec is built and validated but no DB rows
    are written.  The returned dict contains ``{"dry_run": True,
    "would_register": {...}}`` so callers can preview the registration without
    side-effects.

    Args:
        project_id: Project identifier (see ``project_list``).
        item_id: Work-item identifier (e.g. ``F-00001``).
        title: Human-readable title.
        item_type: Lowercase type string: ``feature``, ``incident``, ``cr``,
            or ``research``.
        design_doc_path: Relative or absolute path to the design document.
        design_doc_content: Full text of the design document (used when no
            ``design_doc_path`` is given).
        manifest_path: Path to ``workflow-manifest.json``.
        manifest_steps: Inline steps list (used when no ``manifest_path`` is
            given).
        functional_doc_path: Path to the functional design document.
        functional_doc_content: Full text of the functional document.
        dry_run: When ``True``, validate and preview without persisting.

    Returns:
        On success: dict with ``project_id``, ``id``, ``title``, ``status``,
        ``created`` (bool).  On ``dry_run=True``: dict with ``dry_run: True``
        and ``would_register`` preview.

    Raises:
        ToolError: When the project does not exist, the item type is invalid,
            or a required file cannot be read.
    """
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from orch.mcp.audit import record_audit  # noqa: PLC0415
    from orch.mcp.context import session_scope  # noqa: PLC0415
    from orch.services._common import ServiceError, resolve_and_validate_project  # noqa: PLC0415
    from orch.services.work_items import (  # noqa: PLC0415
        build_registration_spec_from_content,
        create_work_item,
        load_registration_spec_from_disk,
    )

    _args = {
        "project_id": project_id,
        "item_id": item_id,
        "title": title,
        "item_type": item_type,
        "design_doc_path": design_doc_path,
        "manifest_path": manifest_path,
        "functional_doc_path": functional_doc_path,
        "dry_run": dry_run,
    }

    try:
        # Build the spec — prefer disk paths over inline content.
        if design_doc_path or manifest_path or functional_doc_path:
            spec = load_registration_spec_from_disk(
                project_id,
                item_id=item_id,
                title=title,
                item_type=item_type,
                design_doc=design_doc_path,
                steps_from=manifest_path,
                functional_doc=functional_doc_path,
            )
        else:
            spec = build_registration_spec_from_content(
                item_id,
                title,
                item_type,
                design_doc_content=design_doc_content,
                functional_doc_content=functional_doc_content,
                manifest_steps=list(manifest_steps) if manifest_steps else None,
            )
    except (FileNotFoundError, ValueError) as exc:
        record_audit(
            tool_name="work_item_register",
            project_id=project_id,
            arguments=_args,
            outcome="error",
            error=str(exc),
        )
        raise ToolError(str(exc)) from exc

    if dry_run:
        preview = {
            "item_id": spec.item_id,
            "title": spec.title,
            "type": spec.item_type,
            "step_count": len(spec.manifest_steps),
            "impacted_paths": spec.impacted_paths,
        }
        record_audit(
            tool_name="work_item_register",
            project_id=project_id,
            arguments=_args,
            outcome="success",
            result_summary="dry_run preview only — no DB write",
        )
        return {"dry_run": True, "would_register": preview}

    try:
        with session_scope() as session:
            resolve_and_validate_project(session, project_id)
            result = create_work_item(session, project_id, spec)
    except ServiceError as e:
        record_audit(
            tool_name="work_item_register",
            project_id=project_id,
            arguments=_args,
            outcome="error",
            error=e.message,
        )
        raise ToolError(e.message) from e

    record_audit(
        tool_name="work_item_register",
        project_id=project_id,
        arguments=_args,
        outcome="success",
        result_summary=f"{'created' if result.get('created') else 'already existed'}: {item_id}",
    )
    return result


# ---------------------------------------------------------------------------
# Tier-2 tools — async, gated (ask by default)
# ---------------------------------------------------------------------------


async def work_item_approve(
    project_id: str,
    item_id: str,
    approval_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Transition a work item from draft to approved.

    Approved items are eligible to be added to a batch via ``batch_create``.
    This tool is idempotent: approving an already-approved item returns an
    error (the item must be in ``draft`` status for the transition to succeed).

    Gated by policy; when the effective policy is 'ask' and no approval_token
    is supplied, returns an approval_required envelope — get a human to
    ``iw mcp approve`` the token, then retry with approval_token set.

    Args:
        project_id: Project identifier (see ``project_list``).
        item_id: Work-item identifier, e.g. ``F-00001``.
        approval_token: Pre-issued approval token from a previous
            ``approval_required`` response, or ``None``.
        ctx: FastMCP context (injected by the MCP runtime), or ``None``.

    Returns:
        Dict with ``project_id``, ``id``, ``status`` (``"approved"``), and
        ``manifest_refreshed`` (``False``).  Or an ``approval_required``
        envelope when human approval is needed.

    Raises:
        ToolError: When the project or item does not exist, or the item is
            not in a state that allows approval, or the policy denies execution.
    """
    from orch.mcp.gate import enforce_and_run  # noqa: PLC0415
    from orch.services.work_items import approve_work_item  # noqa: PLC0415

    _args = {"project_id": project_id, "item_id": item_id}

    def _execute(session: Session) -> dict[str, Any]:
        from orch.services._common import resolve_and_validate_project  # noqa: PLC0415

        resolve_and_validate_project(session, project_id)
        return approve_work_item(session, project_id, item_id)

    return await enforce_and_run(
        ctx,
        tool_name="work_item_approve",
        project_id=project_id,
        arguments=_args,
        approval_token=approval_token,
        execute=_execute,
    )


async def batch_create(
    project_id: str,
    item_ids: list[str],
    max_parallel: int | None = None,
    auto_publish: bool = False,
    dry_run: bool = False,
    approval_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Create a new batch from a list of approved work items.

    All items in ``item_ids`` must be ``approved`` before calling this tool —
    use ``work_item_approve`` first.  Batch execution is **asynchronous**: the
    daemon processes the batch on the next poll after ``batch_approve`` is
    called.  Poll ``batch_status`` to observe progress.

    When ``dry_run=True``, inputs are validated and the execution group plan
    is computed, but no ``Batch`` or ``BatchItem`` rows are written.

    Gated by policy; when the effective policy is 'ask' and no approval_token
    is supplied, returns an approval_required envelope — get a human to
    ``iw mcp approve`` the token, then retry with approval_token set.

    Args:
        project_id: Project identifier (see ``project_list``).
        item_ids: Ordered list of approved work-item identifiers.
        max_parallel: Maximum number of items to execute concurrently.
            Defaults to 4 when omitted.
        auto_publish: When ``True``, auto-push to origin after all items merge.
        dry_run: When ``True``, validate inputs and return a preview without
            persisting any rows.
        approval_token: Pre-issued approval token, or ``None``.
        ctx: FastMCP context (injected by the MCP runtime), or ``None``.

    Returns:
        Dict with ``batch_id``, ``project_id``, ``status``, ``max_parallel``,
        ``auto_merge``, ``auto_publish``, ``item_count``, and ``groups``.
        When ``dry_run=True``: ``{"dry_run": True, "item_ids": [...]}``.
        Or an ``approval_required`` envelope when human approval is needed.

    Raises:
        ToolError: When the project does not exist, an item is not found or
            not approved, an item is already in an active batch, or a circular
            dependency is detected, or the policy denies execution.
    """
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from orch.mcp.audit import record_audit  # noqa: PLC0415
    from orch.mcp.gate import enforce_and_run  # noqa: PLC0415
    from orch.services._common import ServiceError, resolve_and_validate_project  # noqa: PLC0415
    from orch.services.batches import create_batch  # noqa: PLC0415

    effective_max_parallel = max_parallel if max_parallel is not None else 4
    _args = {
        "project_id": project_id,
        "item_ids": item_ids,
        "max_parallel": effective_max_parallel,
        "auto_publish": auto_publish,
        "dry_run": dry_run,
    }

    if dry_run:
        # dry_run: validate then return preview without executing or gating.
        from orch.mcp.context import session_scope  # noqa: PLC0415

        try:
            with session_scope() as session:
                resolve_and_validate_project(session, project_id)
                from orch.db.models import WorkItem, WorkItemStatus  # noqa: PLC0415

                for iid in item_ids:
                    item = session.get(WorkItem, (project_id, iid))
                    if item is None:
                        raise ServiceError(
                            f"Work item {iid} not found in project {project_id}", code=1
                        )
                    if item.status != WorkItemStatus.approved:
                        raise ServiceError(
                            f"Work item {iid} is not approved (status: {item.status.value})",
                            code=1,
                        )
        except ServiceError as e:
            record_audit(
                tool_name="batch_create",
                project_id=project_id,
                arguments=_args,
                outcome="error",
                error=e.message,
            )
            raise ToolError(e.message) from e

        record_audit(
            tool_name="batch_create",
            project_id=project_id,
            arguments=_args,
            outcome="success",
            result_summary="dry_run preview — no batch created",
        )
        return {"dry_run": True, "item_ids": list(item_ids)}

    def _execute(session: Session) -> dict[str, Any]:
        resolve_and_validate_project(session, project_id)
        return create_batch(
            session,
            project_id,
            item_ids,
            max_parallel=effective_max_parallel,
            auto_publish=auto_publish,
        )

    return await enforce_and_run(
        ctx,
        tool_name="batch_create",
        project_id=project_id,
        arguments=_args,
        approval_token=approval_token,
        execute=_execute,
    )


async def batch_approve(
    project_id: str,
    batch_id: str,
    approval_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Transition a batch from planning to approved, queuing it for daemon execution.

    Batch execution is **asynchronous**: the daemon picks up the approved batch
    on the next poll cycle (default every 60 s) and begins launching agent
    worktrees.  Call ``batch_status`` to monitor progress.

    Gated by policy; when the effective policy is 'ask' and no approval_token
    is supplied, returns an approval_required envelope — get a human to
    ``iw mcp approve`` the token, then retry with approval_token set.

    Args:
        project_id: Project identifier (see ``project_list``).
        batch_id: Batch identifier (e.g. ``BATCH-00001``).
        approval_token: Pre-issued approval token, or ``None``.
        ctx: FastMCP context (injected by the MCP runtime), or ``None``.

    Returns:
        Dict with ``project_id``, ``batch_id``, ``status`` (``"approved"``),
        and optionally ``auto_skipped_steps``.  Or an ``approval_required``
        envelope when human approval is needed.

    Raises:
        ToolError: When the project or batch does not exist, or the batch is
            not in ``planning`` status, or the policy denies execution.
    """
    from orch.mcp.gate import enforce_and_run  # noqa: PLC0415
    from orch.services.batches import approve_batch  # noqa: PLC0415

    _args = {"project_id": project_id, "batch_id": batch_id}

    def _execute(session: Session) -> dict[str, Any]:
        from orch.services._common import resolve_and_validate_project  # noqa: PLC0415

        resolve_and_validate_project(session, project_id)
        return approve_batch(session, project_id, batch_id)

    return await enforce_and_run(
        ctx,
        tool_name="batch_approve",
        project_id=project_id,
        arguments=_args,
        approval_token=approval_token,
        execute=_execute,
    )


async def batch_control(
    project_id: str,
    batch_id: str,
    action: str,
    approval_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Pause or resume an executing batch.

    Valid actions: ``"pause"`` or ``"resume"``.

    Gated by policy; when the effective policy is 'ask' and no approval_token
    is supplied, returns an approval_required envelope — get a human to
    ``iw mcp approve`` the token, then retry with approval_token set.

    Args:
        project_id: Project identifier (see ``project_list``).
        batch_id: Batch identifier (e.g. ``BATCH-00001``).
        action: Either ``"pause"`` or ``"resume"``.
        approval_token: Pre-issued approval token, or ``None``.
        ctx: FastMCP context (injected by the MCP runtime), or ``None``.

    Returns:
        Dict with ``project_id``, ``batch_id``, and ``status``.  Or an
        ``approval_required`` envelope when human approval is needed.

    Raises:
        ToolError: When the project or batch does not exist, the action is
            invalid, or the batch is not in a state that allows the transition,
            or the policy denies execution.
    """
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from orch.mcp.audit import record_audit  # noqa: PLC0415
    from orch.mcp.gate import enforce_and_run  # noqa: PLC0415

    _args = {"project_id": project_id, "batch_id": batch_id, "action": action}

    if action not in {"pause", "resume"}:
        record_audit(
            tool_name="batch_control",
            project_id=project_id,
            arguments=_args,
            outcome="error",
            error=f"Invalid action {action!r}; must be 'pause' or 'resume'",
        )
        raise ToolError(f"Invalid action {action!r}; must be 'pause' or 'resume'")

    def _execute(session: Session) -> dict[str, Any]:
        from orch.services._common import resolve_and_validate_project  # noqa: PLC0415
        from orch.services.batches import pause_batch, resume_batch  # noqa: PLC0415

        resolve_and_validate_project(session, project_id)
        if action == "pause":
            return pause_batch(session, project_id, batch_id)
        return resume_batch(session, project_id, batch_id)

    return await enforce_and_run(
        ctx,
        tool_name="batch_control",
        project_id=project_id,
        arguments=_args,
        approval_token=approval_token,
        execute=_execute,
    )


async def item_retry(
    project_id: str,
    item_id: str,
    approval_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Re-drive a dead-ended work item so the daemon resumes execution.

    Use this when an item is stuck in ``failed`` or ``stalled`` state and you
    want the daemon to retry it without creating a new batch.

    Gated by policy; when the effective policy is 'ask' and no approval_token
    is supplied, returns an approval_required envelope — get a human to
    ``iw mcp approve`` the token, then retry with approval_token set.

    Args:
        project_id: Project identifier (see ``project_list``).
        item_id: Work-item identifier, e.g. ``F-00001``.
        approval_token: Pre-issued approval token, or ``None``.
        ctx: FastMCP context (injected by the MCP runtime), or ``None``.

    Returns:
        Dict with ``project_id``, ``id``, ``status`` (``"in_progress"``),
        and ``retry`` (``True`` on success).  Or an ``approval_required``
        envelope when human approval is needed.

    Raises:
        ToolError: When the project or item does not exist, or the item is not
            in a retryable state, or the policy denies execution.
    """
    from orch.mcp.gate import enforce_and_run  # noqa: PLC0415
    from orch.services.work_items import retry_work_item  # noqa: PLC0415

    _args = {"project_id": project_id, "item_id": item_id}

    def _execute(session: Session) -> dict[str, Any]:
        from orch.services._common import resolve_and_validate_project  # noqa: PLC0415

        resolve_and_validate_project(session, project_id)
        return retry_work_item(session, project_id, item_id)

    return await enforce_and_run(
        ctx,
        tool_name="item_retry",
        project_id=project_id,
        arguments=_args,
        approval_token=approval_token,
        execute=_execute,
    )


# ---------------------------------------------------------------------------
# Tier-3 tools — async, gated (deny by default, irreversible/destructive)
# ---------------------------------------------------------------------------


async def approve_merge(
    project_id: str,
    item_id: str,
    approval_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Approve the merge of a work item waiting in the merge queue.

    Transitions a ``BatchItem`` from ``awaiting_merge_approval`` to
    ``completed`` so the daemon's merge queue can proceed with the squash-merge.

    **IRREVERSIBLE** — once approved, the daemon will merge immediately on the
    next poll.  Default policy is ``deny``; requires an explicit operator
    override or a pre-issued approval token.

    Gated by policy; when the effective policy is 'ask' and no approval_token
    is supplied, returns an approval_required envelope — get a human to
    ``iw mcp approve`` the token, then retry with approval_token set.

    Args:
        project_id: Project identifier (see ``project_list``).
        item_id: Work-item identifier whose batch item should be approved for merge.
        approval_token: Pre-issued approval token, or ``None``.
        ctx: FastMCP context (injected by the MCP runtime), or ``None``.

    Returns:
        Dict with ``project_id``, ``item_id``, and ``status`` (``"completed"``).
        Or an ``approval_required`` envelope when human approval is needed.

    Raises:
        ToolError: When the item is not found, is not awaiting merge approval,
            or the policy denies execution.
    """
    from orch.mcp.gate import enforce_and_run  # noqa: PLC0415

    _args = {"project_id": project_id, "item_id": item_id}

    def _execute(session: Session) -> dict[str, Any]:
        from orch.services import approve_merge as _svc_approve_merge  # noqa: PLC0415
        from orch.services._common import ServiceError  # noqa: PLC0415

        try:
            bi = _svc_approve_merge(session, project_id, item_id)
        except ValueError as exc:
            raise ServiceError(str(exc), code=1) from exc
        return {
            "project_id": project_id,
            "item_id": item_id,
            "status": bi.status.value,
        }

    return await enforce_and_run(
        ctx,
        tool_name="approve_merge",
        project_id=project_id,
        arguments=_args,
        approval_token=approval_token,
        execute=_execute,
    )


async def batch_cancel(
    project_id: str,
    batch_id: str,
    reason: str,
    approval_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Cancel a batch and all its non-terminal work items.

    **IRREVERSIBLE** — cancelled batches and items cannot be un-cancelled
    (use ``item_retry`` on individual items if needed, after resetting them
    to ``draft``).  Default policy is ``deny``; requires an explicit operator
    override or a pre-issued approval token.

    Gated by policy; when the effective policy is 'ask' and no approval_token
    is supplied, returns an approval_required envelope — get a human to
    ``iw mcp approve`` the token, then retry with approval_token set.

    Args:
        project_id: Project identifier (see ``project_list``).
        batch_id: Batch identifier to cancel.
        reason: Free-text reason recorded on the batch and each cancelled item.
        approval_token: Pre-issued approval token, or ``None``.
        ctx: FastMCP context (injected by the MCP runtime), or ``None``.

    Returns:
        Dict with ``project_id``, ``batch_id``, ``status`` (``"cancelled"``),
        and cancellation summary fields.  Or an ``approval_required`` envelope.

    Raises:
        ToolError: When the batch is not found or is not in a cancellable state,
            or the policy denies execution.
    """
    from orch.mcp.gate import enforce_and_run  # noqa: PLC0415
    from orch.services.batches import cancel_batch_service  # noqa: PLC0415

    _args = {"project_id": project_id, "batch_id": batch_id, "reason": reason}

    def _execute(session: Session) -> dict[str, Any]:
        return cancel_batch_service(session, project_id, batch_id, reason=reason)

    return await enforce_and_run(
        ctx,
        tool_name="batch_cancel",
        project_id=project_id,
        arguments=_args,
        approval_token=approval_token,
        execute=_execute,
    )


async def work_item_archive(
    project_id: str,
    item_id: str,
    approval_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Archive a work item (Tier-1 DB content + optional Tier-2 .tar.zst).

    **IRREVERSIBLE** — archived items are removed from the active queue.
    Default policy is ``deny``; requires an explicit operator override or a
    pre-issued approval token.

    Gated by policy; when the effective policy is 'ask' and no approval_token
    is supplied, returns an approval_required envelope — get a human to
    ``iw mcp approve`` the token, then retry with approval_token set.

    Args:
        project_id: Project identifier (see ``project_list``).
        item_id: Work-item identifier to archive.
        approval_token: Pre-issued approval token, or ``None``.
        ctx: FastMCP context (injected by the MCP runtime), or ``None``.

    Returns:
        Dict with ``project_id``, ``item_id``, and ``status`` (``"archived"``).
        Or an ``approval_required`` envelope when human approval is needed.

    Raises:
        ToolError: When the work item is not found or the policy denies execution.
    """
    from orch.mcp.gate import enforce_and_run  # noqa: PLC0415

    _args = {"project_id": project_id, "item_id": item_id}

    def _execute(session: Session) -> dict[str, Any]:
        from orch.archive.archiver import archive_work_item  # noqa: PLC0415
        from orch.services._common import ServiceError  # noqa: PLC0415

        try:
            archive_work_item(session, project_id, item_id, archive_dir=None, cleanup=False)
        except ValueError as exc:
            raise ServiceError(str(exc), code=1) from exc
        return {"project_id": project_id, "item_id": item_id, "status": "archived"}

    return await enforce_and_run(
        ctx,
        tool_name="work_item_archive",
        project_id=project_id,
        arguments=_args,
        approval_token=approval_token,
        execute=_execute,
    )


async def work_item_cancel(
    project_id: str,
    item_id: str,
    reason: str,
    approval_token: str | None = None,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Cancel a work item, preventing further daemon processing.

    **IRREVERSIBLE** — a cancelled item cannot be re-queued without operator
    intervention (use ``item_retry`` after resetting to ``draft`` if needed).
    Default policy is ``deny``; requires an explicit operator override or a
    pre-issued approval token.

    Gated by policy; when the effective policy is 'ask' and no approval_token
    is supplied, returns an approval_required envelope — get a human to
    ``iw mcp approve`` the token, then retry with approval_token set.

    Args:
        project_id: Project identifier (see ``project_list``).
        item_id: Work-item identifier to cancel.
        reason: Free-text reason recorded in the audit trail.
        approval_token: Pre-issued approval token, or ``None``.
        ctx: FastMCP context (injected by the MCP runtime), or ``None``.

    Returns:
        Dict with ``project_id``, ``item_id``, ``status`` (``"cancelled"``),
        and ``reason``.  Or an ``approval_required`` envelope.

    Raises:
        ToolError: When the item is not found, is not in a cancellable state,
            or the policy denies execution.
    """
    from orch.mcp.gate import enforce_and_run  # noqa: PLC0415

    _args = {"project_id": project_id, "item_id": item_id, "reason": reason}

    def _execute(session: Session) -> dict[str, Any]:
        from orch.cancel import cancel_work_item as _svc_cancel  # noqa: PLC0415
        from orch.services._common import ServiceError  # noqa: PLC0415

        try:
            result = _svc_cancel(session, project_id, item_id, reason=reason)
        except (LookupError, ValueError) as exc:
            raise ServiceError(str(exc), code=1) from exc
        return {
            "project_id": project_id,
            "item_id": item_id,
            "status": result.new_status.value,
            "reason": result.reason,
        }

    return await enforce_and_run(
        ctx,
        tool_name="work_item_cancel",
        project_id=project_id,
        arguments=_args,
        approval_token=approval_token,
        execute=_execute,
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(mcp: FastMCP) -> None:
    """Register all write tools on the given FastMCP server instance — only when enabled.

    Registers 11 write tools **only** when ``write_tools_enabled()`` returns
    True (i.e. when ``IW_CORE_MCP_ENABLE_WRITE_TOOLS`` is set to
    ``1``/``true``/``yes``).  When disabled, this function is a no-op and the
    tools are absent from the catalog.

    Tier-1 tools use ``ToolAnnotations(readOnlyHint=False, destructiveHint=False,
    idempotentHint=False/True)``.  Tier-2 tools add the ``approval_token`` /
    ``ctx`` parameters and are marked ``idempotentHint=False`` (non-idempotent
    workflow mutations).  Tier-3 tools are marked ``destructiveHint=True,
    idempotentHint=False`` to signal irreversibility to MCP clients.

    Args:
        mcp: The :class:`fastmcp.FastMCP` server to register write tools on.
    """
    from orch.mcp.config import write_tools_enabled  # noqa: PLC0415

    if not write_tools_enabled():
        return

    from mcp.types import ToolAnnotations  # noqa: PLC0415

    _read_write_annotation = ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=False,
        openWorldHint=False,
    )
    _idempotent_write_annotation = ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
    _destructive_annotation = ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=True,
        idempotentHint=False,
        openWorldHint=False,
    )

    # --- Tier-1: ungated sync tools ---
    # idempotentHint=False: each call consumes a sequence slot.
    mcp.tool(annotations=_read_write_annotation)(work_item_next_id)

    # idempotentHint=True: second call with same item_id is a no-op.
    mcp.tool(annotations=_idempotent_write_annotation)(work_item_register)

    # --- Tier-2: gated async tools ---
    mcp.tool(annotations=_read_write_annotation)(work_item_approve)
    mcp.tool(annotations=_read_write_annotation)(batch_create)
    mcp.tool(annotations=_read_write_annotation)(batch_approve)
    mcp.tool(annotations=_read_write_annotation)(batch_control)
    mcp.tool(annotations=_read_write_annotation)(item_retry)

    # --- Tier-3: gated async tools, irreversible/destructive ---
    mcp.tool(annotations=_destructive_annotation)(approve_merge)
    mcp.tool(annotations=_destructive_annotation)(batch_cancel)
    mcp.tool(annotations=_destructive_annotation)(work_item_archive)
    mcp.tool(annotations=_destructive_annotation)(work_item_cancel)
