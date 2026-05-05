"""E2E fixture for I-00068: seed BATCH- events for browser verification.

Inserts:
- A Batch row with status=archived so the batch detail page returns 200 (not 404).
- Two DaemonEvent rows for the same batch:
  - entity_type=None  (legacy/buggy emission — the template fallback must route this to /batch/)
  - entity_type="batch" (correct emission — already routes to /batch/)
"""

from datetime import UTC, datetime

from orch.db.models import Batch, BatchStatus, DaemonEvent


def seed(db) -> None:
    now = datetime.now(UTC)

    # Batch row — needed so the batch detail page returns 200 when the link is clicked.
    # Without this, clicking the BATCH-99999 link in Recent Activity would land on a
    # page that returns 404 "Batch 'BATCH-99999' not found", which is a data-gap
    # rather than a routing bug.
    batch = Batch(
        project_id="iw-ai-core",
        id="BATCH-99999",
        status=BatchStatus.archived,
        max_parallel=4,
        cli_tool="opencode",
        archived_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(batch)
    db.flush()  # ensure the batch exists before the DaemonEvent rows reference it

    # Row 1: entity_type=None — simulates the legacy buggy emission that this fix targets.
    # The template's BATCH- prefix check (added in S03) must route this to /batch/.
    row_none = DaemonEvent(
        project_id="iw-ai-core",
        event_type="batch_archived",
        entity_id="BATCH-99999",
        entity_type=None,  # intentionally None — the bug this fix addresses
        message="Batch BATCH-99999 archived successfully",
        event_metadata={},
        created_at=now,
    )
    db.add(row_none)

    # Row 2: entity_type="batch" — the correct emission going forward.
    # Included so V3 can confirm that new archive events also route to /batch/.
    row_batch = DaemonEvent(
        project_id="iw-ai-core",
        event_type="batch_archiving_started",
        entity_id="BATCH-99999",
        entity_type="batch",
        message="Batch BATCH-99999 archiving started",
        event_metadata={},
        created_at=now,
    )
    db.add(row_batch)
    db.flush()