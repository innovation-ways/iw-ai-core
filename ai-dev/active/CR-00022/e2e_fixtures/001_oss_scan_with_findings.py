"""E2E fixture: OSS scan with findings for CR-00022 browser verification."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from orch.db.models import OssFinding, OssFindingSeverity, OssFindingStatus, OssScan, OssScanStatus

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

PROJECT_ID = "iw-ai-core"


def seed(db: Session) -> None:
    """Insert OSS scan with findings for CR-00022 verification.

    Creates a complete scan with mixed severity/status findings including
    at least one MUST fail with auto_apply_safe=True and one MUST fail
    with auto_apply_safe=False.
    """
    existing = db.scalars(select(OssScan).where(OssScan.project_id == PROJECT_ID).limit(1)).first()
    if existing is not None:
        return

    now = datetime.now(UTC)
    scan = OssScan(
        project_id=PROJECT_ID,
        started_at=now,
        completed_at=now,
        status=OssScanStatus.complete,
        mode="scan",
        head_sha="abc123def456",
        pill_color="red",
        summary_json={
            "total": 5,
            "pass": 2,
            "fail": 3,
            "must_fail": 2,
            "should_fail": 1,
            "info_fail": 0,
        },
    )
    db.add(scan)
    db.flush()

    findings = [
        OssFinding(
            scan_id=scan.id,
            check_id="OSS-CH-01",
            severity=OssFindingSeverity.MUST,
            status=OssFindingStatus.fail,
            domain="secrets",
            summary="Secret detected in file content",
            detail="A hardcoded secret was found in the file.",
            remediation="Remove the secret and use environment variables.",
            auto_fix_available=True,
            auto_apply_safe=True,
            osps_control="A1.1",
            tool="gitleaks",
            evidence_json={"file": "README.md", "line": 10},
            rationale="Secrets in code can be exploited if committed.",
        ),
        OssFinding(
            scan_id=scan.id,
            check_id="OSS-CH-02",
            severity=OssFindingSeverity.MUST,
            status=OssFindingStatus.fail,
            domain="secrets",
            summary="Secret in git history",
            detail="A secret was found in git history.",
            remediation="Git history rewriting required.",
            auto_fix_available=False,
            auto_apply_safe=False,
            osps_control="A1.2",
            tool="gitleaks",
            evidence_json={"file": "config.py", "commit": "abc123"},
            rationale=(
                "Secrets in git history remain exploitable even if removed from current state."
            ),
        ),
        OssFinding(
            scan_id=scan.id,
            check_id="OSS-CH-03",
            severity=OssFindingSeverity.SHOULD,
            status=OssFindingStatus.fail,
            domain="license",
            summary="Missing license header",
            detail="A source file is missing the required license header.",
            remediation="Add the appropriate license header.",
            auto_fix_available=True,
            auto_apply_safe=True,
            tool="reuse",
            evidence_json={"file": "src/utils.py"},
            rationale="Missing license headers may cause compliance issues.",
        ),
        OssFinding(
            scan_id=scan.id,
            check_id="OSS-CH-04",
            severity=OssFindingSeverity.MUST,
            status=OssFindingStatus.pass_status,
            domain="pins",
            summary="No unpinable dependencies",
            detail="All dependencies use secure pinning.",
            remediation=None,
            auto_fix_available=False,
            auto_apply_safe=False,
            tool="pip-audit",
            evidence_json=None,
            rationale=None,
        ),
        OssFinding(
            scan_id=scan.id,
            check_id="OSS-CH-05",
            severity=OssFindingSeverity.INFO,
            status=OssFindingStatus.pass_status,
            domain="metadata",
            summary="Package metadata complete",
            detail="All packages have complete metadata.",
            remediation=None,
            auto_fix_available=False,
            auto_apply_safe=False,
            tool="pip-audit",
            evidence_json=None,
            rationale=None,
        ),
    ]

    for f in findings:
        db.add(f)
    db.flush()
