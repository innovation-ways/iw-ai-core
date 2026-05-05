"""E2E fixture: seed I-00066 OSS findings for S14 browser verification.

The browser verification steps V1–V3 navigate to the OSS compliance page
at /project/iw-ai-core/oss, open the "..." (View details) modal on an OSS
finding row, and assert:
  V1: Modal opens at ~80vw, footer buttons visible
  V2: Footer Close button dismisses the modal
  V3: No regressions on the OSS page

This fixture creates a completed OssScan with at least one failing
OssFinding row so the dashboard renders the OSS table with a "View
details" button and the modal can be opened.

The fixture is idempotent — skips if the scan already exists.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import and_, select

from orch.db.models import (
    OssFinding,
    OssFindingSeverity,
    OssFindingStatus,
    OssScan,
    OssScanMode,
    OssScanStatus,
    Project,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"


def seed(db: Session) -> None:
    existing = db.scalar(
        select(OssScan).where(
            and_(
                OssScan.project_id == PROJECT_ID,
                OssScan.status == OssScanStatus.complete,
            )
        )
    )
    if existing is not None:
        return

    project = db.get(Project, PROJECT_ID)
    if project is None:
        return

    now = datetime.now(UTC)
    scan = OssScan(
        project_id=PROJECT_ID,
        status=OssScanStatus.complete,
        started_at=now,
        completed_at=now,
        mode=OssScanMode.scan,
        exit_code=0,
        head_sha="0000000",
        summary_json={"MUST": 1, "SHOULD": 0, "MAY": 0, "INFO": 0},
    )
    db.add(scan)
    db.flush()

    finding = OssFinding(
        scan_id=scan.id,
        check_id="OSS-SEC-01",
        severity=OssFindingSeverity.MUST,
        status=OssFindingStatus.fail,
        domain="secrets",
        summary="Hardcoded secret detected in repository",
        detail="A hardcoded API key was found in src/api_keys.py line 42.",
        remediation="Remove the hardcoded secret and use environment variables.",
        auto_fix_available=False,
        auto_apply_safe=False,
        tool="gitleaks",
        evidence_json={"matches": [{"file": "src/api_keys.py", "line": 42, "secret": "sk-abc123"}]},
    )
    db.add(finding)
    db.flush()
