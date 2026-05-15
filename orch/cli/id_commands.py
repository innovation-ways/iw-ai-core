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


def allocate_next_id(
    session: Session,
    project_id: str,
    prefix: str,
    *,
    idempotency_key: str | None = None,
) -> tuple[int, str]:  # noqa: ARG001
    """Atomically allocate the next sequential ID for *prefix*.

    Uses INSERT … ON CONFLICT DO NOTHING to initialise the row, then
    SELECT … FOR UPDATE to lock-and-increment atomically.  Safe under
    concurrent callers — only one transaction can hold the row lock at a time.

    When *idempotency_key* is provided and a row already exists for
    (prefix, idempotency_key) in id_allocations, the previously-allocated
    number is returned without touching id_sequences.  Otherwise (key is new),
    id_sequences is incremented AND a row is written to id_allocations inside
    a SAVEPOINT so that a concurrent UniqueViolation on the INSERT can be
    recovered by rolling back the speculative id_sequences increment and
    retrying the SELECT.

    *project_id* is stored in id_allocations for audit purposes.

    Returns (number, formatted_id).
    """
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.exc import IntegrityError

    from orch.db.models import IdAllocation, IdSequence

    # --- No idempotency key: original behaviour, no id_allocations written ---
    if idempotency_key is None:
        session.execute(
            pg_insert(IdSequence).values(prefix=prefix, next_number=1).on_conflict_do_nothing()
        )
        session.flush()

        row = session.execute(
            select(IdSequence).where(IdSequence.prefix == prefix).with_for_update()
        ).scalar_one()

        number = row.next_number
        row.next_number = number + 1
        session.flush()

        return number, format_id(prefix, number)

    # --- Idempotency key provided: check for existing allocation first ---
    existing = (
        session.execute(
            select(IdAllocation).where(
                IdAllocation.prefix == prefix,
                IdAllocation.idempotency_key == idempotency_key,
            )
        )
        .scalars()
        .first()
    )

    if existing is not None:
        return existing.number, format_id(prefix, existing.number)

    # New key: increment id_sequences AND insert into id_allocations inside
    # a SAVEPOINT so that a concurrent INSERT UniqueViolation can be recovered.
    for attempt in range(3):
        try:
            with session.begin_nested():
                # Increment id_sequences (same lock-and-increment pattern as no-key path)
                session.execute(
                    pg_insert(IdSequence)
                    .values(prefix=prefix, next_number=1)
                    .on_conflict_do_nothing()
                )
                session.flush()

                seq_row = session.execute(
                    select(IdSequence).where(IdSequence.prefix == prefix).with_for_update()
                ).scalar_one()

                number = seq_row.next_number
                seq_row.next_number = number + 1
                session.flush()

                # Insert into id_allocations to record this keyed allocation
                session.add(
                    IdAllocation(
                        prefix=prefix,
                        number=number,
                        idempotency_key=idempotency_key,
                        project_id=project_id,
                    )
                )
                session.flush()

            # Success — commit the nested transaction and return
            return number, format_id(prefix, number)

        except IntegrityError:
            # Concurrent INSERT with the same (prefix, idempotency_key) won the race.
            # Rollback the SAVEPOINT (already done by context manager on exit if
            # exception propagates) and retry from the SELECT at the top of the loop.
            # The savepoint rollback also undoes the speculative id_sequences increment.
            if attempt == 2:
                raise
            # Fall through to retry

    # Unreachable: the loop exhausts 3 attempts then raises IntegrityError.
    raise RuntimeError("idempotent key allocation failed after 3 retries")  # pragma: no cover


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
    type=click.Choice(["feature", "incident", "cr", "batch", "research"]),
    help="Work item type",
)
@click.option(
    "--idempotency-key",
    "idempotency_key",
    required=False,
    default=None,
    type=str,
    help="If provided, return the previously-allocated ID for this "
    "(type, key) pair instead of allocating a new one.",
)
@click.pass_context
def next_id(ctx: click.Context, item_type: str, idempotency_key: str | None) -> None:
    """Atomically allocate the next sequential ID for a work item type."""
    project_id = resolve_project(ctx)
    prefix = TYPE_TO_PREFIX[item_type]

    get_session = ctx.obj["get_session"]
    try:
        with get_session() as session:
            number, formatted_id = allocate_next_id(
                session, project_id, prefix, idempotency_key=idempotency_key
            )
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
