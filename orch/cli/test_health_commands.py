"""iw test-health-capture CLI command (CR-00086).

Reads the four test-health artefact sources for a named project and writes
one snapshot per metric to the test_health_snapshots table.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click

logger = logging.getLogger(__name__)


def _resolve_repo_root(project_id: str) -> Path | None:
    """Look up the project row and return its repo_root path.

    Returns None if the project is not registered in the DB.
    """
    from orch.db.models import Project
    from orch.db.session import get_session

    try:
        with get_session() as session:
            project = session.get(Project, project_id)
            if project is None:
                return None
            return Path(project.repo_root)
    except Exception as exc:
        logger.error("DB lookup failed: %s", exc)
        raise


@click.command("test-health-capture")
@click.option(
    "--project",
    "-p",
    "project_slug",
    required=True,
    help="Project slug (e.g. 'iw-ai-core')",
)
@click.pass_context
def test_health_capture(ctx: click.Context, project_slug: str) -> None:
    """Capture test-health snapshots for a project.

    Reads mutation-score JSON, coverage XML, flaky-test log, and
    assertion-baseline size artefacts; writes one row per metric to
    the test_health_snapshots table.

    Prints a JSON summary to stdout. Exit code 0 on success (including
    no-op captures); exit code 1 on DB errors; exit code 2 if the
    project is not found.
    """
    # Look up the project by slug
    get_session = ctx.obj.get("get_session")
    if get_session is None:
        click.echo("ERROR: get_session not available in context", err=True)
        sys.exit(1)

    try:
        with get_session() as session:
            from orch.db.models import Project

            project = session.query(Project).filter(Project.id == project_slug).first()
            if project is None:
                click.echo(f"ERROR: project '{project_slug}' not found in registry", err=True)
                sys.exit(2)

            project_id = project.id
            repo_root = Path(project.repo_root)
    except Exception as exc:
        click.echo(f"ERROR: database error looking up project: {exc}", err=True)
        sys.exit(1)

    # Read artefacts
    from orch.test_health_service import read_sources

    sources = read_sources(str(repo_root))

    captured: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []

    for metric, data in sources.items():
        if data is None:
            skipped.append({"metric": metric, "reason": "source not found or not parseable"})
            continue

        value, meta = data

        try:
            with get_session() as session:
                from orch.test_health_service import capture_snapshot

                snapshot = capture_snapshot(
                    session,
                    project_id=project_id,
                    metric=metric,
                    value=value,
                    meta=meta,
                )
                session.commit()

                captured.append(
                    {
                        "metric": metric,
                        "value": value,
                        "ts": snapshot.ts.isoformat() if snapshot.ts else None,
                        "source_shape": meta.get("source_shape"),
                    }
                )
        except Exception as exc:
            click.echo(f"ERROR: failed to capture {metric}: {exc}", err=True)
            sys.exit(1)

    summary = {
        "project": project_slug,
        "captured": captured,
        "skipped": skipped,
    }

    click.echo(json.dumps(summary, indent=2))
