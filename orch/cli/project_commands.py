"""Project management commands.

Commands: projects list.
"""

from __future__ import annotations

import json
from typing import Any

import click
from sqlalchemy import func, select

from orch.cli.utils import output_error
from orch.db.models import Batch, BatchStatus, Project, WorkItem

_ACTIVE_BATCH_STATUSES: list[BatchStatus] = [
    BatchStatus.planning,
    BatchStatus.approved,
    BatchStatus.executing,
    BatchStatus.paused,
    BatchStatus.blocked,
    BatchStatus.publishing,
    BatchStatus.publish_failed,
]


@click.group("projects")
def projects() -> None:
    """Manage registered projects."""


@projects.command("list")
@click.pass_context
def list_projects(ctx: click.Context) -> None:
    """List all registered projects with item and batch counts."""
    get_session = ctx.obj["get_session"]
    rows: list[dict[str, Any]] = []

    try:
        with get_session() as session:
            all_projects = session.execute(select(Project).order_by(Project.id)).scalars().all()

            for proj in all_projects:
                item_count = session.execute(
                    select(func.count(WorkItem.id)).where(WorkItem.project_id == proj.id)
                ).scalar_one()

                active_batch_count = session.execute(
                    select(func.count())
                    .select_from(Batch)
                    .where(
                        Batch.project_id == proj.id,
                        Batch.status.in_(_ACTIVE_BATCH_STATUSES),
                    )
                ).scalar_one()

                rows.append(
                    {
                        "id": proj.id,
                        "name": proj.display_name,
                        "enabled": proj.enabled,
                        "item_count": item_count,
                        "active_batches": active_batch_count,
                    }
                )

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    if ctx.obj.get("json"):
        click.echo(json.dumps(rows))
    else:
        if not rows:
            click.echo("No projects registered.")
            return

        id_w, name_w = 20, 25
        header = f"  {'ID':<{id_w}} | {'Name':<{name_w}} | {'Enabled':<7} | {'Items':<6} | Batches"
        click.echo(header)
        click.echo("  " + "-" * (id_w + name_w + 40))
        for r in rows:
            click.echo(
                f"  {r['id']:<{id_w}} | {r['name']:<{name_w}}"
                f" | {'yes' if r['enabled'] else 'no':<7}"
                f" | {r['item_count']:<6} | {r['active_batches']}"
            )
