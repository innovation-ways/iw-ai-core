"""Merge-queue CLI commands — operator surface for merge queue freeze/unfreeze/retry.

iw merge-queue status        — show frozen/unfrozen state + last migration log
iw merge-queue unfreeze      — clear frozen flag (requires --ack reason)
iw merge-queue retry-merge   — reset a failed merge so the daemon re-attempts it
"""

from __future__ import annotations

import getpass
import json
import os
import sys
from pathlib import Path

import click
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from orch.cli.utils import output_error
from orch.config import get_db_url
from orch.daemon.merge_queue import OPERATOR_RECOVERABLE_MERGE_STATUSES
from orch.daemon.migration_pipeline import (
    is_merge_queue_frozen,
    set_merge_queue_frozen,
)
from orch.db.session import safe_create_engine

EXIT_SUCCESS = 0
EXIT_AGENT_CONTEXT = 2
EXIT_MISSING_FLAG = 3
EXIT_UNKNOWN = 1

AGENT_CONTEXT_ENV = "IW_CORE_AGENT_CONTEXT"


@click.group("merge-queue")
def merge_queue_group() -> None:
    """Show and control the merge queue frozen state.

    The merge queue is frozen automatically when a migration rollback fails.
    Use 'unfreeze' to clear the frozen flag after resolving the issue.
    """


@merge_queue_group.command("status")
@click.option("--json", "-j", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.pass_context
def merge_queue_status(ctx: click.Context, json_output: bool) -> None:
    """Show current merge queue frozen state with last migration log entry.

    This command is read-only and safe for anyone to run.
    """
    db_url = get_db_url()
    engine = safe_create_engine(db_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()

    try:
        frozen = is_merge_queue_frozen()

        result = session.execute(
            text(
                "SELECT message, metadata, created_at FROM daemon_events "
                "WHERE event_type = 'merge_queue_frozen' "
                "ORDER BY created_at DESC LIMIT 1"
            )
        )
        freeze_event = result.fetchone()

        result = session.execute(
            text(
                "SELECT revision, phase, success, error_message, started_at, completed_at "
                "FROM pending_migration_log "
                "ORDER BY started_at DESC LIMIT 1"
            )
        )
        last_migration = result.fetchone()

        if json_output:
            data: dict[str, object] = {
                "frozen": frozen,
                "freeze_event": None,
                "last_migration": None,
            }
            if freeze_event:
                data["freeze_event"] = {
                    "message": freeze_event[0],
                    "metadata": freeze_event[1],
                    "created_at": (freeze_event[2].isoformat() if freeze_event[2] else None),
                }
            if last_migration:
                data["last_migration"] = {
                    "revision": last_migration[0],
                    "phase": last_migration[1],
                    "success": last_migration[2],
                    "error_message": last_migration[3],
                    "started_at": (last_migration[4].isoformat() if last_migration[4] else None),
                    "completed_at": (last_migration[5].isoformat() if last_migration[5] else None),
                }
            click.echo(json.dumps(data, indent=2))
        else:
            if frozen:
                click.echo("Merge queue: FROZEN")
                if freeze_event:
                    reason = freeze_event[0] or "unknown reason"
                    created = (
                        freeze_event[2].strftime("%Y-%m-%d %H:%M:%S")
                        if freeze_event[2]
                        else "unknown time"
                    )
                    click.echo(f"  Reason: {reason}")
                    click.echo(f"  Since: {created}")
            else:
                click.echo("Merge queue: OK (not frozen)")

            if last_migration:
                rev = last_migration[0] or "?"
                phase = last_migration[1] or "?"
                success = "YES" if last_migration[2] else "NO"
                error = last_migration[3] or ""
                started = (
                    last_migration[4].strftime("%Y-%m-%d %H:%M:%S") if last_migration[4] else "?"
                )
                click.echo(
                    f"Last migration: rev={rev} phase={phase} success={success} at {started}"
                )
                if error:
                    click.echo(f"  Error: {error}")

    except Exception as exc:
        output_error(ctx, f"Status error: {exc}", EXIT_UNKNOWN)
    finally:
        session.close()
        engine.dispose()


@merge_queue_group.command("unfreeze")
@click.option(
    "--ack",
    "ack_text",
    required=False,
    default="",
    help="Reason/acknowledgement for unfreezing (required)",
)
@click.option("--json", "-j", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.pass_context
def merge_queue_unfreeze(ctx: click.Context, json_output: bool, ack_text: str) -> None:
    """Clear the merge queue frozen flag.

    Requires --ack with a non-empty reason string.
    Refuses if IW_CORE_AGENT_CONTEXT=true.
    """
    if os.environ.get(AGENT_CONTEXT_ENV) == "true":
        msg = (
            "Refusing to unfreeze merge queue from agent context. "
            "IW_CORE_AGENT_CONTEXT is set. Only operators may unfreeze."
        )
        if json_output:
            click.echo(json.dumps({"error": msg, "code": EXIT_AGENT_CONTEXT}))
        else:
            click.echo(f"Error: {msg}", err=True)
        sys.exit(EXIT_AGENT_CONTEXT)

    if not ack_text or not ack_text.strip():
        click.echo(
            "Error: --ack '<reason>' flag is required to unfreeze the merge queue.",
            err=True,
        )
        sys.exit(EXIT_MISSING_FLAG)

    try:
        user = getpass.getuser()
        set_merge_queue_frozen(
            active=False,
            reason=ack_text.strip(),
            acknowledged_by=user,
        )

        if json_output:
            click.echo(
                json.dumps(
                    {
                        "frozen": False,
                        "reason": ack_text.strip(),
                        "acknowledged_by": user,
                    },
                    indent=2,
                )
            )
        else:
            click.echo(f"Merge queue unfrozen by {user}. Reason: {ack_text.strip()}")

    except Exception as exc:
        output_error(ctx, f"Unfreeze error: {exc}", EXIT_UNKNOWN)


@merge_queue_group.command("retry-merge")
@click.argument("item_id")
@click.option("--json", "-j", "json_output", is_flag=True, help="Machine-readable JSON output")
@click.pass_context
def merge_queue_retry(ctx: click.Context, item_id: str, json_output: bool) -> None:
    """Reset a failed merge so the daemon re-attempts it on the next poll cycle.

    The worktree must still exist. Use this after manually resolving rebase
    conflicts in the worktree, or when the merge failed due to a transient
    conflict that the updated worktree_commit.sh can now auto-resolve.

    Example:
        iw merge-queue retry-merge F-00073
    """
    from sqlalchemy import select

    from orch.db.models import BatchItem, BatchItemStatus, DaemonEvent, WorkItem, WorkItemStatus

    get_session = ctx.obj.get("get_session")
    if get_session is None:
        output_error(ctx, "No database session available", EXIT_UNKNOWN)
        return

    try:
        with get_session() as session:
            # Find the most recent operator-recoverable merge BatchItem
            batch_item = (
                session.execute(
                    select(BatchItem)
                    .where(BatchItem.work_item_id == item_id)
                    .where(BatchItem.status.in_(list(OPERATOR_RECOVERABLE_MERGE_STATUSES)))
                    .order_by(BatchItem.id.desc())
                )
                .scalars()
                .first()
            )

            # Back-compat: accept legacy `failed` rows that have merge-failure metadata
            if batch_item is None:
                legacy = (
                    session.execute(
                        select(BatchItem)
                        .where(BatchItem.work_item_id == item_id)
                        .where(BatchItem.status == BatchItemStatus.failed)
                        .order_by(BatchItem.id.desc())
                    )
                    .scalars()
                    .first()
                )
                if legacy is not None and (legacy.notes or "").startswith("Merge failed"):
                    batch_item = legacy
                elif legacy is not None:
                    # Found a failed item, but it failed during setup or execution, not merge
                    msg = (
                        f"Batch item {item_id} failed during setup or execution "
                        f"(notes: {(legacy.notes or '')!r}). "
                        "Use 'iw item restart' instead of 'iw merge-queue retry-merge'."
                    )
                    if json_output:
                        click.echo(json.dumps({"error": msg}))
                    else:
                        click.echo(f"Error: {msg}", err=True)
                    sys.exit(EXIT_UNKNOWN)
                else:
                    recoverable = ", ".join(
                        sorted(s.name for s in OPERATOR_RECOVERABLE_MERGE_STATUSES)
                    )
                    msg = (
                        f"No retryable batch item found for {item_id} "
                        f"(status must be one of {recoverable} or legacy failed-with-merge-notes)"
                    )
                    if json_output:
                        click.echo(json.dumps({"error": msg}))
                    else:
                        click.echo(f"Error: {msg}", err=True)
                    sys.exit(EXIT_UNKNOWN)

            # Verify worktree still exists
            worktree_path = (batch_item.worktree_info or {}).get("path")
            if not worktree_path or not Path(worktree_path).exists():
                msg = f"Worktree not found at {worktree_path} — cannot retry merge"
                if json_output:
                    click.echo(json.dumps({"error": msg}))
                else:
                    click.echo(f"Error: {msg}", err=True)
                sys.exit(EXIT_UNKNOWN)

            # Reset BatchItem → completed so merge queue picks it up again
            batch_item.status = BatchItemStatus.completed
            batch_item.notes = "Retry requested via iw merge-queue retry-merge"

            # Reset WorkItem → completed (merge_queue._revert_work_item set it to failed)
            work_item = (
                session.execute(
                    select(WorkItem)
                    .where(WorkItem.id == item_id)
                    .where(WorkItem.project_id == batch_item.project_id)
                )
                .scalars()
                .first()
            )
            if work_item is not None and work_item.status == WorkItemStatus.failed:
                work_item.status = WorkItemStatus.completed

            # Emit audit event
            session.add(
                DaemonEvent(
                    project_id=batch_item.project_id,
                    event_type="merge_retry_requested",
                    entity_id=item_id,
                    entity_type="work_item",
                    message=f"Merge retry requested for {item_id} (batch item {batch_item.id})",
                    event_metadata={"batch_item_id": batch_item.id, "worktree_path": worktree_path},
                )
            )
            session.commit()

        if json_output:
            click.echo(
                json.dumps(
                    {
                        "item_id": item_id,
                        "batch_item_id": batch_item.id,
                        "worktree_path": worktree_path,
                        "status": "retry_queued",
                    },
                    indent=2,
                )
            )
        else:
            click.echo(f"Merge retry queued for {item_id} — daemon will re-attempt on next poll.")
            click.echo(f"  Worktree: {worktree_path}")

    except Exception as exc:
        output_error(ctx, f"retry-merge error: {exc}", EXIT_UNKNOWN)
