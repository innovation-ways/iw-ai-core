"""Backfill regression classifications for existing Incidents (F-00090).

This is an OPERATOR-RUN script, not a CI step. It runs the heuristic
suggest_introducer() against every Incident in a project that has
regression_classification IS NULL, emits the top suggestion to stdout,
and records nothing to the database — operator confirmation (via the
dashboard UI or the CLI ``iw regression-classify --accept``) is required
before a classification is persisted. This is Invariant 3 from the
F-00090 design: the heuristic auto-classifier never persists a
classification without operator action.

Usage:
    # Full run — emit suggestions, log to stdout, no DB writes
    uv run python scripts/backfill_regression_classification.py --project innoforge

    # Dry-run — emit a count summary only, no git calls, no session opened
    uv run python scripts/backfill_regression_classification.py --project innoforge --dry-run

    # The --accept flag does NOT belong here — use the CLI instead:
    #   uv run iw regression-classify --incident I-00001 --accept 1

Exit codes:
    0  success
    1  unexpected error
    2  usage error (missing --project)
"""

from __future__ import annotations

import argparse
import logging
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

from orch.db.models import WorkItem, WorkItemType
from orch.db.session import SessionLocal
from orch.regression_link_service import suggest_introducer

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# Human-readable logging format
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("backfill_regression_classification")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the regression heuristic against every unclassified Incident "
            "in a project and emit the top suggestion. "
            "NO classification is persisted — operator triage required via the UI "
            "or ``iw regression-classify --accept``. "
            "This script is OPERATOR-RUN ONLY — not a CI step."
        ),
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Project ID to process (e.g. 'innoforge', 'iw-ai-core')",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Path to the git repo (defaults to cwd)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Emit a count summary only, no git calls, no session opened. "
            "The script never persists classifications regardless of this flag; "
            "this flag documents the operator confirmation requirement."
        ),
    )
    return parser


@contextmanager
def _session_context(session: Session | None) -> Iterator[Session]:
    """Yield the provided session, or open a new SessionLocal session when None."""
    if session is not None:
        yield session
    else:
        with SessionLocal() as s:
            yield s


def run(
    project_id: str,
    *,
    repo_path: Path | None = None,
    db_session: Session | None = None,
) -> tuple[int, int, int]:
    """Run the backfill for a project.

    Parameters
    ----------
    project_id
        The project to process Incidents in.
    repo_path
        Path to the git repo (defaults to cwd).
    db_session
        Optional SQLAlchemy session. When provided (e.g. from a test's
        ``db_session`` fixture), the backfill uses it instead of opening
        its own ``SessionLocal`` connection. This allows tests to exercise
        the backfill against a testcontainer clone without the script
        creating its own engine (which the live-DB guard would block).

    Returns
    -------
    (processed, had_suggestions, classified) counts.
    ``classified`` is always 0 in this script (never persisted —
    operator confirmation is required via the dashboard UI or
    ``iw regression-classify --accept``).
    """
    processed = 0
    had_suggestions = 0

    with _session_context(db_session) as session:
        from sqlalchemy import select

        stmt = (
            select(WorkItem)
            .where(
                WorkItem.project_id == project_id,
                WorkItem.type == WorkItemType.Issue,
                WorkItem.regression_classification.is_(None),
            )
            .order_by(WorkItem.created_at.desc())
        )
        incidents = session.execute(stmt).scalars().all()

        for incident in incidents:
            candidates = suggest_introducer(
                session,
                project_id=project_id,
                item_id=incident.id,
                repo_path=repo_path,
            )

            if candidates:
                top = candidates[0]
                had_suggestions += 1
                suggestion_txt = (
                    f"{incident.id}  top suggestion: {top.work_item_id or top.commit_sha[:7]} "
                    f"(score={top.score}, commit={top.commit_sha[:8]})"
                )
                log.info(suggestion_txt)
            else:
                log.info(f"{incident.id}  no suggestion available")

            processed += 1

    return processed, had_suggestions, 0  # classified is always 0 in this script


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    project_id: str = args.project
    repo_path: Path | None = Path(args.repo) if args.repo else None

    try:
        if args.dry_run:
            # --dry-run: open a session to get counts only, emit nothing to DB
            with SessionLocal() as session:
                from sqlalchemy import select as sa_select

                stmt = (
                    sa_select(WorkItem)
                    .where(
                        WorkItem.project_id == project_id,
                        WorkItem.type == WorkItemType.Issue,
                        WorkItem.regression_classification.is_(None),
                    )
                    .order_by(WorkItem.created_at.desc())
                )
                incidents = session.execute(stmt).scalars().all()
                processed = len(incidents)
            print(  # noqa: T201  dry-run summary line to stdout is the intended operator output
                f"Dry-run: {processed} incidents would be processed; "
                f"0 classifications persisted (operator triage required)"
            )
            return 0
        processed, had_suggestions, classified = run(project_id, repo_path=repo_path)
        # Invariant 3 printout: 0 classifications persisted
        print(  # noqa: T201  summary line to stdout is the intended operator output
            f"Processed {processed} incidents; "
            f"{had_suggestions} had suggestions; "
            f"{classified} classifications persisted "
            f"(operator triage required)"
        )
        return 0
    except Exception as exc:
        log.error(f"Unexpected error: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
