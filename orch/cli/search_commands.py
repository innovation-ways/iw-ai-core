"""Full-text search command."""

from __future__ import annotations

import json
from typing import Any

import click
from sqlalchemy import func, select

from orch.cli.utils import output_error
from orch.db.models import WorkItem, WorkItemType

_TYPE_MAP: dict[str, WorkItemType] = {
    "feature": WorkItemType.Feature,
    "incident": WorkItemType.Issue,
    "cr": WorkItemType.ChangeRequest,
}


@click.command("search")
@click.argument("query")
@click.option(
    "--type",
    "item_type",
    default=None,
    type=click.Choice(["feature", "incident", "cr"]),
    help="Filter by item type",
)
@click.option("--limit", default=20, show_default=True, help="Maximum number of results")
@click.pass_context
def search(
    ctx: click.Context,
    query: str,
    item_type: str | None,
    limit: int,
) -> None:
    """Full-text search across work items."""
    get_session = ctx.obj["get_session"]

    # Search is cross-project by default; optionally filtered via global --project flag
    project_id: str | None = ctx.obj.get("project_id")

    results: list[dict[str, Any]] = []

    try:
        with get_session() as session:
            tsquery = func.to_tsquery("english", query)
            rank_col = func.ts_rank(WorkItem.design_doc_search, tsquery).label("rank")

            stmt = (
                select(WorkItem, rank_col)
                .where(WorkItem.design_doc_search.op("@@")(tsquery))
                .order_by(rank_col.desc())
                .limit(limit)
            )

            if project_id:
                stmt = stmt.where(WorkItem.project_id == project_id)

            if item_type:
                stmt = stmt.where(WorkItem.type == _TYPE_MAP[item_type])

            rows = session.execute(stmt).all()

            for item, rank in rows:
                snippet = item.summary or ""
                if not snippet and item.design_doc_content:
                    snippet = item.design_doc_content[:100].replace("\n", " ").strip() + "..."

                results.append(
                    {
                        "project_id": item.project_id,
                        "id": item.id,
                        "type": item.type.value,
                        "title": item.title,
                        "status": item.status.value,
                        "summary": snippet,
                        "relevance": float(rank),
                        "created_at": item.created_at.isoformat() if item.created_at else None,
                    }
                )

    except Exception as exc:
        output_error(ctx, f"Database error: {exc}", 1)

    count = len(results)

    if ctx.obj.get("json"):
        click.echo(json.dumps({"query": query, "count": count, "results": results}))
    else:
        if count == 0:
            click.echo(f"No results for '{query}'")
            return

        click.echo(f"{count} result(s) for '{query}':\n")
        for r in results:
            click.echo(f"  {r['id']} [{r['project_id']}] {r['title']}")
            click.echo(f"  {r['type']} | {r['status']} | {(r['created_at'] or '')[:10]}")
            if r["summary"]:
                click.echo(f"  ...{r['summary']}...")
            click.echo()
