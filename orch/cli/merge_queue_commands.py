"""Merge-queue CLI commands — operator surface for merge queue freeze/unfreeze.

iw merge-queue status    — show frozen/unfrozen state + last migration log
iw merge-queue unfreeze   — clear frozen flag (requires --ack reason)
"""

from __future__ import annotations

import getpass
import json
import os
import sys

import click
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from orch.cli.utils import output_error
from orch.config import get_db_url
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
