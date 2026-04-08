"""Batch management CLI commands.

Commands: batch-create, batch-approve, batch-status, batch-pause, batch-resume.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import click
from sqlalchemy import select

from orch.cli.id_commands import allocate_next_id
from orch.cli.utils import output_error, resolve_project
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    WorkItem,
    WorkItemStatus,
)

# ---------------------------------------------------------------------------
# Active batch statuses (same set as in item_commands)
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
# Dependency graph / execution group planner (pure — used by unit tests)
# ---------------------------------------------------------------------------


def build_execution_groups(item_deps: dict[str, list[str]]) -> dict[str, int]:
    """Compute execution group assignments using Kahn's topological sort.

    item_deps maps each item_id to its list of dependency item_ids.
    Only dependencies that are within the batch (keys of item_deps) are
    considered; external dependencies are ignored.

    Returns a dict mapping item_id → group_number (0-based).
    Raises ValueError if a circular dependency is detected.
    """
    all_items = set(item_deps.keys())

    # Filter deps to only items within this batch
    in_batch_deps: dict[str, set[str]] = {
        item: {d for d in deps if d in all_items} for item, deps in item_deps.items()
    }

    # Build reverse adjacency: dep → set of items that depend on dep
    reverse: dict[str, set[str]] = {item: set() for item in all_items}
    for item, deps in in_batch_deps.items():
        for dep in deps:
            reverse[dep].add(item)

    # Kahn's algorithm with level (group) tracking
    in_degree = {item: len(deps) for item, deps in in_batch_deps.items()}
    groups: dict[str, int] = {}
    current_group = 0
    queue = [item for item, deg in in_degree.items() if deg == 0]

    while queue:
        for item in queue:
            groups[item] = current_group
        next_queue: list[str] = []
        for item in queue:
            for dependent in reverse[item]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    next_queue.append(dependent)
        queue = next_queue
        if queue:
            current_group += 1

    if len(groups) != len(all_items):
        unresolved = sorted(all_items - set(groups.keys()))
        raise ValueError(f"Circular dependency detected among: {unresolved}")

    return groups


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def validate_batch_approve_transition(current_status: BatchStatus) -> str | None:
    if current_status != BatchStatus.planning:
        return f"Cannot approve batch: current status is '{current_status.value}'"
    return None


def validate_batch_pause_transition(current_status: BatchStatus) -> str | None:
    if current_status != BatchStatus.executing:
        return f"Cannot pause batch: current status is '{current_status.value}'"
    return None


def validate_batch_resume_transition(current_status: BatchStatus) -> str | None:
    if current_status != BatchStatus.paused:
        return f"Cannot resume batch: current status is '{current_status.value}'"
    return None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@click.command("batch-create")
@click.argument("item_ids", nargs=-1, required=True)
@click.option("--max-parallel", default=4, show_default=True, help="Maximum concurrent items")
@click.option("--auto-publish", is_flag=True, help="Auto-push to origin after all items merged")
@click.pass_context
def batch_create(
    ctx: click.Context,
    item_ids: tuple[str, ...],
    max_parallel: int,
    auto_publish: bool,
) -> None:
    """Create a new batch from a list of approved work items."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            # 1. Validate all items exist and are approved
            items: list[WorkItem] = []
            for iid in item_ids:
                item = session.get(WorkItem, (project_id, iid))
                if item is None:
                    output_error(ctx, f"Work item {iid} not found in project {project_id}", 1)
                if item.status != WorkItemStatus.approved:
                    output_error(
                        ctx,
                        f"Work item {iid} is not approved (status: {item.status.value})",
                        1,
                    )
                items.append(item)

            # 2. Validate no item is already in an active batch
            for iid in item_ids:
                active = session.execute(
                    select(BatchItem)
                    .join(
                        Batch,
                        (BatchItem.project_id == Batch.project_id)
                        & (BatchItem.batch_id == Batch.id),
                    )
                    .where(
                        BatchItem.project_id == project_id,
                        BatchItem.work_item_id == iid,
                        Batch.status.in_(_ACTIVE_BATCH_STATUSES),
                    )
                ).scalar_one_or_none()
                if active is not None:
                    output_error(
                        ctx,
                        f"Work item {iid} is already in active batch {active.batch_id}",
                        4,
                    )

            # 3. Build execution groups from dependency graph
            item_deps: dict[str, list[str]] = {
                item.id: list(item.depends_on or []) for item in items
            }
            try:
                group_assignments = build_execution_groups(item_deps)
            except ValueError as exc:
                output_error(ctx, str(exc), 1)

            # 4. Allocate batch ID
            _num, batch_id = allocate_next_id(session, project_id, "BATCH")

            # 5. Create batch row
            batch = Batch(
                project_id=project_id,
                id=batch_id,
                status=BatchStatus.planning,
                max_parallel=max_parallel,
                auto_publish=auto_publish,
            )
            session.add(batch)
            session.flush()

            # 6. Create batch_items with execution groups
            for iid in item_ids:
                session.add(
                    BatchItem(
                        project_id=project_id,
                        batch_id=batch_id,
                        work_item_id=iid,
                        execution_group=group_assignments[iid],
                        status=BatchItemStatus.pending,
                    )
                )
            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    # 7. Build groups summary for output
    groups_map: dict[int, list[str]] = {}
    for iid, grp in group_assignments.items():
        groups_map.setdefault(grp, []).append(iid)
    group_numbers = sorted(groups_map.keys())
    sorted_groups = [{"group": g, "items": groups_map[g]} for g in group_numbers]

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "batch_id": batch_id,
                    "project_id": project_id,
                    "status": "planning",
                    "max_parallel": max_parallel,
                    "groups": sorted_groups,
                }
            )
        )
    else:
        total = len(item_ids)
        click.echo(f"Created {batch_id} with {total} item(s) (max parallel: {max_parallel})")
        for grp_num in group_numbers:
            grp_items = groups_map[grp_num]
            dep_note = ""
            if grp_num > 0:
                prev = groups_map[grp_num - 1]
                dep_note = f" (depends on group {grp_num - 1}: {', '.join(prev)})"
            click.echo(f"  Group {grp_num}: {', '.join(grp_items)}{dep_note}")
        click.echo(f"Status: planning (approve with: iw batch-approve {batch_id})")


@click.command("batch-approve")
@click.argument("batch_id")
@click.pass_context
def batch_approve(ctx: click.Context, batch_id: str) -> None:
    """Approve a batch for execution (planning → approved)."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            batch = session.get(Batch, (project_id, batch_id))
            if batch is None:
                output_error(ctx, f"Batch {batch_id} not found in project {project_id}", 1)

            error = validate_batch_approve_transition(batch.status)
            if error:
                output_error(ctx, error, 1)

            batch.status = BatchStatus.approved
            batch.updated_at = datetime.now(UTC)
            session.flush()

            # Emit daemon event
            session.add(
                DaemonEvent(
                    project_id=project_id,
                    event_type="batch_approved",
                    entity_id=batch_id,
                    message=f"Batch {batch_id} approved for execution",
                )
            )
            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps({"project_id": project_id, "batch_id": batch_id, "status": "approved"})
        )
    else:
        click.echo(f"Approved {batch_id}")


@click.command("batch-status")
@click.argument("batch_id")
@click.pass_context
def batch_status(ctx: click.Context, batch_id: str) -> None:
    """Show the current status of a batch."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    batch_data: dict[str, Any] = {}

    try:
        with get_session() as session:
            batch = session.get(Batch, (project_id, batch_id))
            if batch is None:
                output_error(ctx, f"Batch {batch_id} not found in project {project_id}", 1)

            batch_items = (
                session.execute(
                    select(BatchItem)
                    .where(
                        BatchItem.project_id == project_id,
                        BatchItem.batch_id == batch_id,
                    )
                    .order_by(BatchItem.execution_group, BatchItem.work_item_id)
                )
                .scalars()
                .all()
            )

            batch_data = {
                "batch_id": batch_id,
                "project_id": project_id,
                "status": batch.status.value,
                "max_parallel": batch.max_parallel,
                "auto_publish": batch.auto_publish,
                "created_at": batch.created_at.isoformat() if batch.created_at else None,
                "items": [
                    {
                        "work_item_id": bi.work_item_id,
                        "execution_group": bi.execution_group,
                        "status": bi.status.value,
                        "started_at": bi.started_at.isoformat() if bi.started_at else None,
                        "merged_at": bi.merged_at.isoformat() if bi.merged_at else None,
                    }
                    for bi in batch_items
                ],
            }

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps(batch_data))
    else:
        _print_batch_status_human(batch_data)


def _print_batch_status_human(data: dict[str, Any]) -> None:
    """Print batch status as a human-readable table using Rich."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    items = data["items"]

    # Summary counts
    status_counts: dict[str, int] = {}
    for it in items:
        status_counts[it["status"]] = status_counts.get(it["status"], 0) + 1

    total = len(items)
    merged = status_counts.get("merged", 0)
    executing = status_counts.get("executing", 0)
    pending = status_counts.get("pending", 0)

    console.print(f"[bold]{data['batch_id']}[/bold] [{data['status']}] — {data['project_id']}")
    console.print(
        f"  Items: {total} total | {merged} merged | {executing} executing | {pending} pending"
    )

    table = Table(show_header=True, header_style="bold")
    table.add_column("Item", style="cyan")
    table.add_column("Group", justify="center")
    table.add_column("Status")
    table.add_column("Duration")

    now = datetime.now(UTC)
    for it in items:
        duration = "—"
        if it["merged_at"] and it["started_at"]:
            from datetime import datetime as dt

            start = dt.fromisoformat(it["started_at"])
            end = dt.fromisoformat(it["merged_at"])
            secs = int((end - start).total_seconds())
            duration = f"{secs // 60}m {secs % 60}s"
        elif it["started_at"] and it["status"] == "executing":
            from datetime import datetime as dt

            start = dt.fromisoformat(it["started_at"])
            secs = int((now - start).total_seconds())
            duration = f"{secs // 60}m {secs % 60}s"

        table.add_row(
            it["work_item_id"],
            str(it["execution_group"]),
            it["status"],
            duration,
        )

    console.print(table)
    if data.get("created_at"):
        console.print(f"  Created: {data['created_at'][:19]}")


@click.command("batch-pause")
@click.argument("batch_id")
@click.pass_context
def batch_pause(ctx: click.Context, batch_id: str) -> None:
    """Pause a running batch (executing → paused)."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            batch = session.get(Batch, (project_id, batch_id))
            if batch is None:
                output_error(ctx, f"Batch {batch_id} not found in project {project_id}", 1)

            error = validate_batch_pause_transition(batch.status)
            if error:
                output_error(ctx, error, 1)

            batch.status = BatchStatus.paused
            batch.updated_at = datetime.now(UTC)
            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps({"project_id": project_id, "batch_id": batch_id, "status": "paused"}))
    else:
        click.echo(f"Paused {batch_id}")


@click.command("batch-resume")
@click.argument("batch_id")
@click.pass_context
def batch_resume(ctx: click.Context, batch_id: str) -> None:
    """Resume a paused batch (paused → executing)."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            batch = session.get(Batch, (project_id, batch_id))
            if batch is None:
                output_error(ctx, f"Batch {batch_id} not found in project {project_id}", 1)

            error = validate_batch_resume_transition(batch.status)
            if error:
                output_error(ctx, error, 1)

            batch.status = BatchStatus.executing
            batch.updated_at = datetime.now(UTC)
            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps({"project_id": project_id, "batch_id": batch_id, "status": "executing"})
        )
    else:
        click.echo(f"Resumed {batch_id}")
