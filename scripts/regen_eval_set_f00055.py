#!/usr/bin/env python3
"""Regenerate tests/fixtures/eval_set_f00055.json from the live platform DB.

Run manually after significant work-item churn.
NOT automatically invoked by tests.

Usage:
    python scripts/regen_eval_set_f00055.py
    python scripts/regen_eval_set_f00055.py --project-id iw-ai-core
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from orch.config import load_config  # noqa: E402
from orch.db.models import WorkItem  # noqa: E402


def _load_curation(curation_path: Path) -> dict:
    """Load the curation JSON file and return its parsed contents.

    Args:
        curation_path: Path to the ``eval_set_f00055_curation.json`` file.

    Returns:
        Parsed JSON dict with ``project_id`` and ``queries`` keys.
    """
    with curation_path.open() as f:
        return json.load(f)


def _verify_work_items_exist(
    session: Session, must_cite_ids: list[str], project_id: str
) -> list[str]:
    """Verify that all must_cite IDs exist in the DB. Returns list of missing IDs."""
    if not must_cite_ids:
        return []
    query = select(WorkItem).where(
        WorkItem.project_id == project_id,
        WorkItem.id.in_(must_cite_ids),
    )
    result = session.execute(query)
    found_ids = {row[0].id for row in result.fetchall()}
    return [wid for wid in must_cite_ids if wid not in found_ids]


def _get_work_item_info(session: Session, wi_id: str, project_id: str) -> dict | None:
    """Get title and summary for a work item."""
    query = select(WorkItem).where(
        WorkItem.project_id == project_id,
        WorkItem.id == wi_id,
    )
    result = session.execute(query)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return {
        "id": row.id,
        "title": row.title,
        "summary": row.summary or "",
        "type": row.type.value if hasattr(row.type, "value") else str(row.type),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _build_eval_tuple(
    curation_entry: dict,
    session: Session,
    project_id: str,
) -> dict:
    """Build a complete eval tuple by enriching a curation entry with live DB titles.

    Args:
        curation_entry: Single query dict from the curation file with keys such
                        as ``question``, ``must_cite_work_items``, and
                        ``expected_terms``.
        session: Active SQLAlchemy session for work-item title lookups.
        project_id: Project to query when resolving work-item metadata.

    Returns:
        Enriched eval tuple dict ready for serialisation into the fixture file.
    """
    question = curation_entry["question"]
    context_chips = curation_entry.get("context_chips", [])
    must_cite = curation_entry.get("must_cite_work_items", [])
    may_cite = curation_entry.get("may_cite_work_items", [])
    expected_terms = curation_entry.get("expected_terms", [])
    register = curation_entry.get("register", "functional")
    notes = curation_entry.get("notes", "")

    # Determine expected phase sequence based on chips and query type
    has_why_or_history = context_chips and ("why" in context_chips or "history" in context_chips)
    has_findusages = context_chips and "findusages" in context_chips
    if has_why_or_history or has_findusages:
        expected_phase_sequence = ["retrieving", "finding_items", "reading_docs", "composing"]
    else:
        # Code-only queries should NOT have phase events
        expected_phase_sequence = []

    # Enrich may_cite with titles if we can find them
    enriched_may_cite = []
    for wid in may_cite:
        info = _get_work_item_info(session, wid, project_id)
        if info:
            enriched_may_cite.append(
                {
                    "id": wid,
                    "title": info["title"],
                    "type": info["type"],
                }
            )

    # Enrich must_cite with titles if we can find them
    enriched_must_cite = []
    for wid in must_cite:
        info = _get_work_item_info(session, wid, project_id)
        if info:
            enriched_must_cite.append(
                {
                    "id": wid,
                    "title": info["title"],
                    "type": info["type"],
                }
            )

    return {
        "question": question,
        "context_chips": context_chips,
        "expected_phase_sequence": expected_phase_sequence,
        "must_cite_work_items": must_cite,
        "may_cite_work_items": may_cite,
        "enriched_must_cite": enriched_must_cite,
        "enriched_may_cite": enriched_may_cite,
        "expected_terms": expected_terms,
        "register": register,
        "notes": notes,
    }


def main() -> int:
    """Connect to the platform DB and regenerate the F-00055 eval fixture file.

    Returns:
        0 on success, 1 when the curation file is missing or any ``must_cite``
        IDs are no longer present in the DB.
    """
    parser = argparse.ArgumentParser(description="Regenerate eval_set_f00055.json from platform DB")
    parser.add_argument(
        "--project-id",
        default="iw-ai-core",
        help="Project ID to query (default: iw-ai-core)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path (default: tests/fixtures/eval_set_f00055.json)",
    )
    args = parser.parse_args()

    # Determine paths
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    curation_path = script_dir / "eval_set_f00055_curation.json"
    output_path = args.output or (repo_root / "tests" / "fixtures" / "eval_set_f00055.json")

    if not curation_path.exists():
        logger.error(f"Curation file not found: {curation_path}")
        return 1

    # Load curation
    curation = _load_curation(curation_path)
    project_id = args.project_id or curation.get("project_id", "iw-ai-core")

    # Connect to DB via orch.config
    config = load_config()
    db_url = config.get_db_url()

    # Create engine and session
    engine = create_engine(db_url)
    with Session(engine) as session:
        # Verify all must_cite IDs exist
        all_missing: list[str] = []
        for query_entry in curation.get("queries", []):
            must_cite = query_entry.get("must_cite_work_items", [])
            missing = _verify_work_items_exist(session, must_cite, project_id)
            all_missing.extend(missing)

        if all_missing:
            logger.error(f"The following must_cite IDs no longer exist in DB: {all_missing}")
            logger.error("Update scripts/eval_set_f00055_curation.json to remove stale IDs.")
            return 1

        # Build eval tuples
        eval_tuples = []
        for query_entry in curation.get("queries", []):
            tuple_ = _build_eval_tuple(query_entry, session, project_id)
            eval_tuples.append(tuple_)

    # Build output
    output = {
        "_generated_at": datetime.now(UTC).isoformat(),
        "_generator": "scripts/regen_eval_set_f00055.py",
        "_project_id": project_id,
        "_curation_source": "scripts/eval_set_f00055_curation.json",
        "evaluation_set": eval_tuples,
    }

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Generated {len(eval_tuples)} eval tuples -> {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
