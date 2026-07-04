"""Read-only MCP tool functions for IW AI Core.

Defines 8 plain module-level functions that wrap the Phase 0 service layer.
Each function is also registered on the MCP server via ``register(mcp)`` with
``ToolAnnotations(readOnlyHint=True, destructiveHint=False, ...)``.

Structure is split so tests can call the plain functions synchronously while
the server registers the same callables asynchronously under FastMCP.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastmcp import FastMCP


# ---------------------------------------------------------------------------
# Tool implementations (plain sync functions, testable without MCP runtime)
# ---------------------------------------------------------------------------


def project_list() -> dict[str, Any]:
    """List all projects registered with IW AI Core.

    Returns every project the orchestrator knows about, ordered by ID.  Use
    the returned ``id`` values as the ``project_id`` argument in all other
    tools.  A project must be ``enabled: true`` for the daemon to schedule
    work on it.

    Returns:
        Dict with key ``projects``: a list of project dicts each containing
        ``id`` (short identifier, e.g. ``"innoforge"``), ``display_name``,
        ``enabled`` (bool — whether the daemon processes this project), and
        ``repo_root`` (absolute path to the main git clone).
    """
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from orch.mcp.context import session_scope  # noqa: PLC0415
    from orch.services._common import ServiceError  # noqa: PLC0415
    from orch.services.monitoring import list_projects  # noqa: PLC0415

    try:
        with session_scope() as session:
            return list_projects(session)
    except ServiceError as e:
        raise ToolError(e.message) from e


def work_item_list(
    project_id: str,
    status: str | None = None,
    item_type: str | None = None,
    phase: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """List work items for a project with optional filters and cursor pagination.

    Work items represent individual pieces of engineering work (features,
    incidents, change requests, research) tracked through a governed lifecycle.

    Status enum values (``WorkItemStatus``) and their meanings:

    - ``draft`` — created but not yet approved for execution.
    - ``approved`` — operator-approved; queued for the daemon to pick up.
    - ``in_progress`` — daemon has launched an agent worktree for this item.
    - ``paused`` — execution temporarily halted by operator.
    - ``completed`` — all steps finished and the branch merged; work complete.
    - ``failed`` — execution ended in a terminal failure.
    - ``cancelled`` — item cancelled before completion.

    Args:
        project_id: Project identifier (see ``project_list``).
        status: Optional status filter.  Must be one of the values above.
        item_type: Optional type filter: ``Feature``, ``Issue``,
            ``ChangeRequest``, or ``Research``.
        phase: Optional phase filter (``WorkItemPhase``): ``active``, ``work``,
            or ``done``.
        cursor: Opaque cursor returned by a previous call for pagination.
        limit: Maximum rows to return per page (server cap: 50).

    Returns:
        Dict with ``items`` (list), ``next_cursor`` (str or ``None``),
        ``has_more`` (bool), and ``total`` (int — unpaginated count).

    Raises:
        ToolError: When ``project_id`` does not exist or a filter value is
            not a valid enum member.
    """
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from orch.mcp.context import session_scope  # noqa: PLC0415
    from orch.services._common import ServiceError, resolve_and_validate_project  # noqa: PLC0415
    from orch.services.work_items import list_work_items  # noqa: PLC0415

    try:
        with session_scope() as session:
            resolve_and_validate_project(session, project_id)
            return list_work_items(
                session,
                project_id,
                status=status,
                item_type=item_type,
                phase=phase,
                cursor=cursor,
                limit=limit,
            )
    except ServiceError as e:
        raise ToolError(e.message) from e


def work_item_get(project_id: str, item_id: str) -> dict[str, Any]:
    """Get the full status of a single work item, including all its steps.

    Returns the same information as ``iw item-status --json``.  Use this to
    check whether an item's steps have completed, which step is currently
    running, and the item's current batch membership.

    Step ``status`` values:

    - ``pending`` — not yet started.
    - ``in_progress`` — agent is currently executing this step.
    - ``completed`` — step finished successfully.
    - ``failed`` — step failed; fix cycle may retry.
    - ``skipped`` — step was skipped (e.g. a phantom QV gate auto-skipped).

    Args:
        project_id: Project identifier (see ``project_list``).
        item_id: Work-item identifier, e.g. ``F-00001``.

    Returns:
        Dict with ``id``, ``project_id``, ``title``, ``status``, ``phase``,
        ``total_steps``, ``completed_steps``, ``current_step``, ``batch_id``,
        ``worktree``, ``created_at``, ``updated_at``, and ``steps`` (list of
        step dicts with ``step_id``, ``status``, ``label``, ``gate``, etc.).

    Raises:
        ToolError: When ``project_id`` or ``item_id`` does not exist.
    """
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from orch.mcp.context import session_scope  # noqa: PLC0415
    from orch.services._common import ServiceError, resolve_and_validate_project  # noqa: PLC0415
    from orch.services.work_items import get_work_item_status  # noqa: PLC0415

    try:
        with session_scope() as session:
            resolve_and_validate_project(session, project_id)
            return get_work_item_status(session, project_id, item_id)
    except ServiceError as e:
        raise ToolError(e.message) from e


def batch_list(project_id: str, status: str | None = None) -> dict[str, Any]:
    """List batches for a project, ordered newest-first.

    A batch groups one or more approved work items for concurrent execution
    by the daemon.

    Batch ``status`` values:

    - ``planning`` — created, not yet approved for daemon execution.
    - ``approved`` — queued for daemon pickup (daemon polls for this status).
    - ``executing`` — daemon is actively running worktrees for this batch.
    - ``paused`` — execution paused by operator; no new items launched.
    - ``blocked`` — execution blocked pending operator action.
    - ``publishing`` — all items merged; auto-push in progress.
    - ``publish_failed`` — auto-push failed; operator intervention needed.
    - ``completed`` — all items finished successfully.
    - ``completed_with_errors`` — batch done but some items failed.
    - ``cancelled`` — batch cancelled.

    Args:
        project_id: Project identifier (see ``project_list``).
        status: Optional status filter.  Must be one of the values above.

    Returns:
        Dict with key ``batches``: a list of batch summary dicts each
        containing ``batch_id``, ``status``, ``item_count``,
        ``completed_count``, and ``created_at``.

    Raises:
        ToolError: When ``project_id`` does not exist.
    """
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from orch.mcp.context import session_scope  # noqa: PLC0415
    from orch.services._common import ServiceError, resolve_and_validate_project  # noqa: PLC0415
    from orch.services.batches import list_batches  # noqa: PLC0415

    try:
        with session_scope() as session:
            resolve_and_validate_project(session, project_id)
            return list_batches(session, project_id, status=status)
    except ServiceError as e:
        raise ToolError(e.message) from e


def batch_status(project_id: str, batch_id: str) -> dict[str, Any]:
    """Get the full status of a single batch, including all batch items.

    Returns the same information as ``iw batch-status --json``.  Use this
    to poll whether a batch has finished executing and to see each item's
    individual status within the batch.

    Batch item ``status`` values (different from work-item status):

    - ``pending`` — not yet launched by the daemon.
    - ``setting_up`` — daemon is cloning the worktree.
    - ``executing`` — agent process is running inside the worktree.
    - ``completed`` — item finished; branch exists but not yet merged.
    - ``awaiting_merge_approval`` — waiting for operator ``approve-merge``.
    - ``merging`` — squash-merge in progress.
    - ``merged`` — branch squash-merged to main.
    - ``failed`` / ``stalled`` / ``setup_failed`` — terminal error states.
    - ``merge_failed`` / ``migration_rebase_failed`` — merge-phase failures.

    Args:
        project_id: Project identifier (see ``project_list``).
        batch_id: Batch identifier, e.g. ``BATCH-00001``.

    Returns:
        Dict with ``batch_id``, ``project_id``, ``status``, ``max_parallel``,
        ``auto_publish``, ``created_at``, and ``items`` (list of batch-item
        dicts with ``work_item_id``, ``execution_group``, ``status``,
        ``started_at``, ``merged_at``).

    Raises:
        ToolError: When ``project_id`` or ``batch_id`` does not exist.
    """
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from orch.mcp.context import session_scope  # noqa: PLC0415
    from orch.services._common import ServiceError, resolve_and_validate_project  # noqa: PLC0415
    from orch.services.batches import get_batch_status  # noqa: PLC0415

    try:
        with session_scope() as session:
            resolve_and_validate_project(session, project_id)
            return get_batch_status(session, project_id, batch_id)
    except ServiceError as e:
        raise ToolError(e.message) from e


def job_list(
    project_id: str,
    types: list[str] | None = None,
    statuses: list[str] | None = None,
    page: int = 1,
    page_size: int = 25,
) -> dict[str, Any]:
    """List background jobs for a project from all job sources.

    Aggregates across code-index jobs, doc-generation jobs, batch executions,
    and research drafts into a single paginated view.

    Job type strings (``job_type`` field):

    - ``batch_execution`` — a daemon-driven batch execution.
    - ``doc_generation`` — an AI-doc-regen job.
    - ``code_index`` — a LanceDB code-indexing job.
    - ``research_draft`` — a research-doc generation job.

    Status strings normalised across job types:

    - ``queued`` — job is waiting to be picked up.
    - ``running`` — job is actively executing.
    - ``completed`` — job finished successfully.
    - ``failed`` / ``error`` — job ended in an error state.

    Args:
        project_id: Project identifier (see ``project_list``).
        types: Optional list of ``job_type`` strings to filter on.
        statuses: Optional list of normalised status strings to filter on.
        page: 1-based page number.
        page_size: Rows per page (default 25).

    Returns:
        Dict with ``jobs`` (list of job dicts), ``total`` (int),
        ``page``, and ``page_size``.

    Raises:
        ToolError: When ``project_id`` does not exist.
    """
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from orch.mcp.context import session_scope  # noqa: PLC0415
    from orch.services._common import ServiceError, resolve_and_validate_project  # noqa: PLC0415
    from orch.services.monitoring import list_jobs  # noqa: PLC0415

    try:
        with session_scope() as session:
            resolve_and_validate_project(session, project_id)
            return list_jobs(
                session,
                project_id,
                types=types,
                statuses=statuses,
                page=page,
                page_size=page_size,
            )
    except ServiceError as e:
        raise ToolError(e.message) from e


def worktree_status(project_id: str) -> dict[str, Any]:
    """List active agent worktrees for a project.

    Returns batch items that have a non-null ``worktree_info`` payload or a
    ``started_at`` without a ``merged_at`` — i.e. worktrees that the daemon
    has created and not yet torn down.  No git subprocess is invoked; all
    data comes from the database.

    Args:
        project_id: Project identifier (see ``project_list``).

    Returns:
        Dict with key ``worktrees``: a list of dicts each containing
        ``work_item_id``, ``batch_id``, ``execution_group``,
        ``worktree_info`` (JSON payload or ``None``), and ``started_at``
        (ISO-8601 string or ``None``).

    Raises:
        ToolError: When ``project_id`` does not exist.
    """
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from orch.mcp.context import session_scope  # noqa: PLC0415
    from orch.services._common import ServiceError, resolve_and_validate_project  # noqa: PLC0415
    from orch.services.monitoring import list_worktrees  # noqa: PLC0415

    try:
        with session_scope() as session:
            resolve_and_validate_project(session, project_id)
            return list_worktrees(session, project_id)
    except ServiceError as e:
        raise ToolError(e.message) from e


def daemon_status() -> dict[str, Any]:
    """Get daemon liveness and operational statistics.

    Combines OS-level PID-file liveness (is the daemon process alive?) with
    database statistics (last poll time, running steps, active batches,
    project counts).  Use this to confirm the daemon is healthy and to
    understand current system load before submitting new work.

    Returns:
        Dict with:

        - ``status``: ``"running"`` or ``"stopped"``.
        - ``pid``: Integer OS process ID when running, ``None`` when stopped.
        - ``last_poll_at``: ISO-8601 timestamp of the last daemon poll, or
          ``None`` if the daemon has never polled.
        - ``poll_count``: Total number of daemon polls recorded in the DB.
        - ``running_steps``: Number of workflow steps currently ``in_progress``.
        - ``active_batches``: Number of batches in ``executing`` or
          ``publishing`` status.
        - ``projects``: Dict ``{"enabled": int, "disabled": int}`` with project
          counts broken down by enabled status.
    """
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from orch.cli.daemon_commands import (  # noqa: PLC0415
        get_pid_file_path,
        is_process_alive,
        read_pid,
    )
    from orch.mcp.context import session_scope  # noqa: PLC0415
    from orch.services._common import ServiceError  # noqa: PLC0415
    from orch.services.monitoring import get_daemon_db_stats  # noqa: PLC0415

    try:
        pid_file = get_pid_file_path()
        pid = read_pid(pid_file)
        is_running = pid is not None and is_process_alive(pid)

        with session_scope() as session:
            db_stats = get_daemon_db_stats(session)

        return {
            "status": "running" if is_running else "stopped",
            "pid": pid if is_running else None,
            **db_stats,
        }
    except ServiceError as e:
        raise ToolError(e.message) from e


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


def register(mcp: FastMCP) -> None:
    """Register all 8 read tools on the given FastMCP server instance.

    Each tool is wrapped with ``ToolAnnotations(readOnlyHint=True,
    destructiveHint=False, idempotentHint=True, openWorldHint=False)`` so
    agents understand they cannot cause side-effects.

    Args:
        mcp: The :class:`fastmcp.FastMCP` server to register tools on.
    """
    from mcp.types import ToolAnnotations  # noqa: PLC0415

    _annotations = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    _tool_fns = [
        project_list,
        work_item_list,
        work_item_get,
        batch_list,
        batch_status,
        job_list,
        worktree_status,
        daemon_status,
    ]
    for fn in _tool_fns:
        mcp.tool(annotations=_annotations)(fn)  # type: ignore[type-var]
