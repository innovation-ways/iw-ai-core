"""E2E fixture: seed CR-00020-TEST workflow + DB evidence rows for S15 browser verification.

V1: Evidences tab shows pre+post DB evidence rows (no on-disk directory).
V2: Image URL serves bytes with correct Content-Type.
V3: Archived item (no DB rows) renders empty cleanly.

The fixture creates:
- A CR-00020-TEST ChangeRequest work item (approved, active)
- S01-S15 workflow steps (S15 = browser_verification, completed)
- work_item_evidences rows for both pre and post phases
- A Batch + BatchItem to give the item a worktree_path
"""

from __future__ import annotations

import io
import os
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    EvidencePhase,
    RunStatus,
    StepStatus,
    StepType,
    StepRun,
    WorkflowStep,
    WorkItem,
    WorkItemEvidence,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


PROJECT_ID = "iw-ai-core"
WORK_ITEM_ID = "CR-00020-TEST"
AGENT_LABEL = "QvBrowser"


def _png_pixel(width=120, height=90, r=100, g=130, b=200) -> bytes:
    """Minimal valid PNG (1 pixel, solid colour)."""
    import struct, zlib

    def png_chunk(name: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(name + data) & 0xffffffff
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", crc)

    # PNG signature
    sig = b"\x89PNG\r\n\x1a\n"

    # IHDR chunk: width(4) + height(4) + bit depth(1) + color type(1) +
    #             compression(1) + filter(1) + interlace(1) = 13 bytes
    ihdr_data = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    ihdr = png_chunk(b"IHDR", ihdr_data)

    # Raw pixel data: filter byte (0) + RGB row * height
    raw = b"\x00" + bytes([r, g, b]) * (width * height)
    compressed = zlib.compress(raw, 6)
    idat = png_chunk(b"IDAT", compressed)

    # IEND chunk
    iend = png_chunk(b"IEND", b"")

    return sig + ihdr + idat + iend


def seed(db: Session) -> None:
    existing = db.execute(
        db.query(WorkItem).filter(
            WorkItem.project_id == PROJECT_ID,
            WorkItem.id == WORK_ITEM_ID,
        )
    ).scalars().first()
    if existing is not None:
        return

    now = datetime.now(UTC)
    one_hour_ago = now - timedelta(hours=1)
    one_day_ago = now - timedelta(days=1)

    # --- Work item -------------------------------------------------------
    wi = WorkItem(
        project_id=PROJECT_ID,
        id=WORK_ITEM_ID,
        type=WorkItemType.ChangeRequest,
        title="[E2E] Work Item Evidence BLOBs — verification fixture",
        status="approved",
        phase="active",
    )
    db.add(wi)
    db.flush()

    # --- Batch (to get worktree_path non-None) --------------------------
    batch = Batch(
        project_id=PROJECT_ID,
        id="BATCH-E2E-CR00020",
        status=BatchStatus.executing,
        max_parallel=4,
        cli_tool="opencode",
        auto_publish=False,
    )
    db.add(batch)
    db.flush()

    batch_item = BatchItem(
        project_id=PROJECT_ID,
        batch_id=batch.id,
        work_item_id=WORK_ITEM_ID,
        execution_group=0,
        status=BatchItemStatus.executing,
    )
    db.add(batch_item)
    db.flush()

    # --- Workflow steps --------------------------------------------------
    step_defs = [
        ("S01", 1, StepType.implementation, StepStatus.completed),
        ("S02", 2, StepType.code_review, StepStatus.completed),
        ("S03", 3, StepType.implementation, StepStatus.completed),
        ("S04", 4, StepType.code_review, StepStatus.completed),
        ("S05", 5, StepType.implementation, StepStatus.completed),
        ("S06", 6, StepType.code_review, StepStatus.completed),
        ("S07", 7, StepType.implementation, StepStatus.completed),
        ("S08", 8, StepType.code_review, StepStatus.completed),
        ("S09", 9, StepType.code_review_final, StepStatus.completed),
        ("S10", 10, StepType.quality_validation, StepStatus.completed),
        ("S11", 11, StepType.quality_validation, StepStatus.completed),
        ("S12", 12, StepType.quality_validation, StepStatus.completed),
        ("S13", 13, StepType.quality_validation, StepStatus.completed),
        ("S14", 14, StepType.quality_validation, StepStatus.completed),
        ("S15", 15, StepType.browser_verification, StepStatus.completed),
    ]

    step_map: dict[str, WorkflowStep] = {}
    for step_id, step_number, step_type, status in step_defs:
        ws = WorkflowStep(
            project_id=PROJECT_ID,
            work_item_id=WORK_ITEM_ID,
            step_number=step_number,
            step_id=step_id,
            agent_label=AGENT_LABEL,
            step_type=step_type,
            status=status,
            started_at=one_hour_ago,
            completed_at=now,
        )
        db.add(ws)
        db.flush()
        step_map[step_id] = ws

    # --- One completed run per step -------------------------------------
    for step_id, step in step_map.items():
        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=one_hour_ago,
            completed_at=now,
            cli_tool=AGENT_LABEL,
        )
        db.add(run)
    db.flush()

    # --- Evidence rows (pre + post) --------------------------------------
    pre_image = _png_pixel(r=80, g=160, b=240)
    post_image = _png_pixel(r=240, g=160, b=80)

    pre_rows = [
        ("pre_screenshot_design.png", "image/png", pre_image, None),
        ("pre_snippet_config.png", "image/png", pre_image, None),
    ]
    post_rows = [
        ("post_qvbrowser_v1.png", "image/png", post_image, "S15"),
        ("post_qvbrowser_v2.png", "image/png", post_image, "S15"),
    ]

    for filename, content_type, content, step_id in pre_rows:
        ev = WorkItemEvidence(
            id=uuid.uuid4(),
            project_id=PROJECT_ID,
            work_item_id=WORK_ITEM_ID,
            phase=EvidencePhase.pre,
            filename=filename,
            content_type=content_type,
            content=content,
            size_bytes=len(content),
            captured_at=one_day_ago,
            step_id=step_id,
        )
        db.add(ev)

    for filename, content_type, content, step_id in post_rows:
        ev = WorkItemEvidence(
            id=uuid.uuid4(),
            project_id=PROJECT_ID,
            work_item_id=WORK_ITEM_ID,
            phase=EvidencePhase.post,
            filename=filename,
            content_type=content_type,
            content=content,
            size_bytes=len(content),
            captured_at=now,
            step_id=step_id,
        )
        db.add(ev)

    db.commit()