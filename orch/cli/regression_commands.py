"""Regression classification CLI command for F-00090.

Usage:
    uv run iw regression-classify --incident I-NNNNN [--project PROJECT_ID] [--repo /path]
    uv run iw regression-classify --incident I-NNNNN --accept N [--repo /path]
"""

from __future__ import annotations

import logging
from pathlib import Path

import click
from sqlalchemy import select

from orch.cli.utils import output_error, resolve_project
from orch.db.models import RegressionClassification, WorkItem
from orch.regression_link_service import classify, suggest_introducer

log = logging.getLogger(__name__)


@click.command("regression-classify")
@click.option(
    "--incident",
    required=True,
    help="Incident ID (e.g. I-00001)",
)
@click.option(
    "--accept",
    "accept_rank",
    type=int,
    default=None,
    help="Rank (1-indexed) of the heuristic suggestion to accept and persist",
)
@click.option(
    "--repo",
    "repo_path",
    type=click.Path(path_type=Path, exists=True),
    default=None,
    help="Path to the project git repository (default: current working directory)",
)
@click.pass_context
def regression_classify(
    ctx: click.Context,
    incident: str,
    accept_rank: int | None,
    repo_path: Path | None,
) -> None:
    """Show (or accept) heuristic regression-introducer suggestions for an Incident.

    Without --accept: invoke suggest_introducer() and print ranked candidates.
    With --accept N: persist the Nth candidate as a regression classification
    with classified_by='heuristic:auto'.

    Exit codes:
      0 — success (suggestions printed or classification persisted)
      2 — validation error (unknown incident, out-of-range accept, etc.)
      1 — unexpected error
    """
    project_id = resolve_project(ctx)
    get_session = ctx.obj.get("get_session")

    try:
        with get_session() as session:
            # Validate incident exists
            item = session.execute(
                select(WorkItem).where(WorkItem.project_id == project_id, WorkItem.id == incident)
            ).scalar_one_or_none()
            if item is None:
                output_error(
                    ctx,
                    f"Incident {incident} not found in project {project_id}",
                    2,
                )

            candidates = suggest_introducer(
                session,
                project_id=project_id,
                item_id=incident,
                repo_path=repo_path or Path.cwd(),
            )

            if not candidates:
                click.echo("No suggestions")
                return

            # Print ranked table
            click.echo(f"Suggestions for {incident}:")
            click.echo(f"{'Rank':<6} {'SHA':<12} {'Work Item':<14} {'Score':<6}")
            click.echo("-" * 42)
            for rank, cand in enumerate(candidates, start=1):
                wi = cand.work_item_id or "—"
                sha_short = cand.commit_sha[:12]
                click.echo(f"{rank:<6} {sha_short:<12} {wi:<14} {cand.score:<6}")

            if accept_rank is None:
                return

            if accept_rank < 1 or accept_rank > len(candidates):
                output_error(
                    ctx,
                    f"Accept rank {accept_rank} is out of range "
                    f"(1-{len(candidates)}) — no suggestions available",
                    2,
                )

            selected = candidates[accept_rank - 1]

            try:
                classify(
                    session,
                    project_id=project_id,
                    item_id=incident,
                    introduced_by_work_item_id=selected.work_item_id,
                    introduced_by_commit_sha=(
                        selected.commit_sha if not selected.work_item_id else None
                    ),
                    classification=RegressionClassification.regression,
                    classified_by="heuristic:auto",
                )
            except ValueError as exc:
                output_error(ctx, str(exc), 2)

            source = selected.work_item_id or selected.commit_sha[:12]
            click.echo(f"Classified {incident} as regression introduced by {source}")

    except Exception as exc:
        output_error(ctx, f"Unexpected error: {exc}", 1)
