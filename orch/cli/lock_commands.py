"""Migration lock CLI commands.

Commands: migration-lock acquire, migration-lock release, migration-lock status.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import click
from sqlalchemy import select

from orch.cli.utils import output_error, resolve_project
from orch.db.models import MigrationLock


@click.group("migration-lock")
def migration_lock() -> None:
    """Control migration lock for Alembic migrations (one holder per project)."""


@migration_lock.command("acquire")
@click.argument("item_id")
@click.option("--branch", default=None, help="Git branch name")
@click.pass_context
def acquire(ctx: click.Context, item_id: str, branch: str | None) -> None:
    """Acquire the migration lock for a work item."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            lock = session.execute(
                select(MigrationLock)
                .where(MigrationLock.project_id == project_id)
                .with_for_update()
            ).scalar_one_or_none()

            if lock is None:
                output_error(ctx, f"No migration lock row found for project {project_id}", 3)

            if lock.current_holder is not None:
                locked_at_iso = lock.locked_at.isoformat() if lock.locked_at else "unknown"
                output_error(
                    ctx,
                    f"Migration lock held by {lock.current_holder} since {locked_at_iso}",
                    4,
                )

            lock.current_holder = item_id
            lock.branch = branch
            lock.locked_at = datetime.now(UTC)
            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "project_id": project_id,
                    "holder": item_id,
                    "branch": branch,
                    "acquired": True,
                }
            )
        )
    else:
        branch_info = f" on branch {branch}" if branch else ""
        click.echo(f"Migration lock acquired for {item_id}{branch_info}")


@migration_lock.command("release")
@click.argument("item_id")
@click.pass_context
def release(ctx: click.Context, item_id: str) -> None:
    """Release the migration lock held by a work item."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            lock = session.execute(
                select(MigrationLock)
                .where(MigrationLock.project_id == project_id)
                .with_for_update()
            ).scalar_one_or_none()

            if lock is None:
                output_error(ctx, f"No migration lock row found for project {project_id}", 3)

            if lock.current_holder != item_id:
                actual = lock.current_holder or "nobody"
                output_error(
                    ctx,
                    f"Cannot release: lock is held by {actual}, not {item_id}",
                    4,
                )

            lock.current_holder = None
            lock.branch = None
            lock.locked_at = None
            session.flush()

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps({"project_id": project_id, "holder": None, "released": True}))
    else:
        click.echo(f"Migration lock released by {item_id}")


@migration_lock.command("status")
@click.pass_context
def lock_status(ctx: click.Context) -> None:
    """Show the current migration lock status."""
    project_id = resolve_project(ctx)
    get_session = ctx.obj["get_session"]

    lock_data: dict[str, Any] = {}

    try:
        with get_session() as session:
            lock = session.get(MigrationLock, project_id)

            if lock is None:
                output_error(ctx, f"No migration lock row found for project {project_id}", 3)

            lock_data = {
                "project_id": project_id,
                "holder": lock.current_holder,
                "branch": lock.branch,
                "locked_at": lock.locked_at.isoformat() if lock.locked_at else None,
                "head_revision": lock.head_revision,
            }

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps(lock_data))
    else:
        if lock_data.get("holder"):
            locked_at = (lock_data["locked_at"] or "unknown")[:19]
            branch = lock_data.get("branch") or "(no branch)"
            click.echo(
                f"Migration lock: held by {lock_data['holder']}"
                f" (branch: {branch}) since {locked_at}"
            )
        else:
            click.echo("Migration lock: free")
