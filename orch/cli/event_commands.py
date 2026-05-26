"""Daemon event CLI commands."""

from __future__ import annotations

import json
from typing import Any

import click

from orch.cli.utils import output_error, resolve_project
from orch.db.models import DaemonEvent


@click.command("daemon")
@click.option("--event-type", required=True, help="Free-form daemon event type")
@click.option("--entity-type", default=None, help="Entity type (e.g. work_item, batch, step)")
@click.option("--entity-id", default=None, help="Entity identifier")
@click.option("--message", default=None, help="Human-readable event message")
@click.option("--metadata", "metadata_raw", default=None, help="JSON metadata object")
@click.pass_context
def daemon_event(
    ctx: click.Context,
    event_type: str,
    entity_type: str | None,
    entity_id: str | None,
    message: str | None,
    metadata_raw: str | None,
) -> None:
    """Insert a row into daemon_events."""
    project_id = resolve_project(ctx)

    if not event_type.strip():
        output_error(ctx, "--event-type must be a non-empty string", 2)

    metadata: dict[str, Any]
    if metadata_raw is None:
        metadata = {}
    else:
        try:
            parsed = json.loads(metadata_raw)
        except json.JSONDecodeError as exc:
            output_error(ctx, f"--metadata must be valid JSON: {exc}", 2)
        if not isinstance(parsed, dict):
            output_error(ctx, "--metadata must be a JSON object", 2)
        metadata = parsed

    get_session = ctx.obj["get_session"]

    try:
        with get_session() as session:
            event = DaemonEvent(
                project_id=project_id,
                event_type=event_type,
                entity_type=entity_type,
                entity_id=entity_id,
                message=message,
                event_metadata=metadata,
            )
            session.add(event)
            session.flush()
            event_id = event.id
    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps({"id": event_id}))
    else:
        click.echo(str(event_id))
