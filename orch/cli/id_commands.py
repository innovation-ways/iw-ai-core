"""ID management CLI commands: next-id, current-project."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import click

from orch.cli.utils import (
    TYPE_TO_PREFIX,
    find_project_root,
    format_id,
    output_error,
    resolve_project,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Core allocation logic (also used directly in integration tests)
# ---------------------------------------------------------------------------


def allocate_next_id(session: Session, project_id: str, prefix: str) -> tuple[int, str]:  # noqa: ARG001
    """Atomically allocate the next sequential ID for *prefix*.

    Uses INSERT … ON CONFLICT DO NOTHING to initialise the row, then
    SELECT … FOR UPDATE to lock-and-increment atomically.  Safe under
    concurrent callers — only one transaction can hold the row lock at a time.

    *project_id* is accepted for call-site compatibility but is no longer
    stored — id_sequences is now a global (prefix-only) table.

    Returns (number, formatted_id).
    """
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from orch.db.models import IdSequence

    # Initialise the row if it doesn't exist yet (handles first-time creation
    # and concurrent first-time callers — only one INSERT wins).
    session.execute(
        pg_insert(IdSequence).values(prefix=prefix, next_number=1).on_conflict_do_nothing()
    )
    session.flush()  # make the new row visible within this transaction

    # Lock the row to prevent concurrent increments.
    row = session.execute(
        select(IdSequence).where(IdSequence.prefix == prefix).with_for_update()
    ).scalar_one()

    number = row.next_number
    row.next_number = number + 1
    session.flush()  # write the increment so subsequent calls in the same session see it

    return number, format_id(prefix, number)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@click.command("current-project")
@click.pass_context
def current_project(ctx: click.Context) -> None:
    """Print the current project ID detected from .iw-orch.json."""
    result = find_project_root(Path.cwd())
    if result is None:
        output_error(ctx, "No .iw-orch.json found in directory tree", 3)

    project_id, repo_root = result

    if ctx.obj.get("json"):
        click.echo(json.dumps({"project_id": project_id, "repo_root": str(repo_root)}))
    else:
        click.echo(project_id)


@click.command("next-id")
@click.option(
    "--type",
    "item_type",
    required=True,
    type=click.Choice(["feature", "incident", "cr", "batch"]),
    help="Work item type",
)
@click.pass_context
def next_id(ctx: click.Context, item_type: str) -> None:
    """Atomically allocate the next sequential ID for a work item type."""
    project_id = resolve_project(ctx)
    prefix = TYPE_TO_PREFIX[item_type]

    get_session = ctx.obj["get_session"]
    try:
        with get_session() as session:
            number, formatted_id = allocate_next_id(session, project_id, prefix)
    except Exception as exc:  # noqa: BLE001
        output_error(ctx, f"Database error: {exc}", 3)

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "id": formatted_id,
                    "project_id": project_id,
                    "prefix": prefix,
                    "number": number,
                }
            )
        )
    else:
        click.echo(formatted_id)
