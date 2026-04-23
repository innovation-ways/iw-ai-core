"""OSS e2e seed — F-00058 browser verification fixtures.

Seeds:
  - project 'oss-demo' with oss_enabled=true, one completed oss_scan (pill_color=yellow)
    with findings across multiple domains + tool_runs, head_sha='abc0000000000000000000000000000000000000a'
    (deliberately different from current HEAD so V7 exercises the stale banner).
  - project 'oss-clean' with oss_enabled=true but no scans (gray pill).
  - The default 'iw-ai-core' project is left with oss_enabled=false (V2/V3).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from orch.db.models import (
    OssFinding,
    OssFindingSeverity,
    OssFindingStatus,
    OssPillColor,
    OssScan,
    OssScanStatus,
    OssToolRun,
    OssToolRunStatus,
    Project,
    ProjectOssJob,
    ProjectOssJobKind,
    ProjectOssJobStatus,
)
from orch.db.session import get_session

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

DEMO_PROJECT_ID = "oss-demo"
CLEAN_PROJECT_ID = "oss-clean"
STALE_HEAD_SHA = "abc0000000000000000000000000000000000000a"


def seed(db: Session) -> None:
    # ── oss-demo: enabled + scanned (yellow pill) ──────────────────────────────
    demo = db.get(Project, DEMO_PROJECT_ID)
    if demo is None:
        demo = Project(
            id=DEMO_PROJECT_ID,
            display_name="OSS Demo (E2E)",
            repo_root="/app",
            config={},
            enabled=True,
            oss_enabled=True,
        )
        db.add(demo)
        db.flush()
    else:
        demo.oss_enabled = True
        db.flush()

    # Remove any existing scans so we start clean
    for existing in db.query(OssScan).filter(OssScan.project_id == DEMO_PROJECT_ID).all():
        db.delete(existing)
    db.flush()

    now = datetime.now(UTC)
    yesterday = now - timedelta(hours=24)

    scan = OssScan(
        project_id=DEMO_PROJECT_ID,
        started_at=yesterday,
        completed_at=yesterday + timedelta(minutes=3),
        status=OssScanStatus.complete,
        head_sha=STALE_HEAD_SHA,
        pill_color=OssPillColor.yellow,
        summary_json={"must": 2, "should": 1, "info": 0, "blockers": 0},
    )
    db.add(scan)
    db.flush()

    tool_runs_data = [
        ("gitleaks", "v8.18.2", 4200, 0, OssToolRunStatus.ok),
        ("syft", "v1.9.0", 8500, 0, OssToolRunStatus.ok),
        ("grype", "v0.99.0", 12000, 1, OssToolRunStatus.failed),
        ("osv-scanner", "v1.1.0", 3000, 0, OssToolRunStatus.ok),
        ("ripgrep", "14.1.0", 500, 0, OssToolRunStatus.ok),
        ("grant", "v0.8.0", 2000, None, OssToolRunStatus.missing),
    ]
    for tool, version, runtime_ms, exit_code, status in tool_runs_data:
        db.add(
            OssToolRun(
                scan_id=scan.id,
                tool=tool,
                version=version,
                status=status,
                started_at=yesterday + timedelta(seconds=1),
                runtime_ms=runtime_ms,
                exit_code=exit_code,
                output_summary=f"{tool}: checked",
            )
        )

    findings_data = [
        ("secrets", OssFindingSeverity.MUST, OssFindingStatus.fail, "Hardcoded API key detected", True),
        ("license", OssFindingSeverity.MUST, OssFindingStatus.fail, "GPL-3.0 license conflict", False),
        ("community", OssFindingSeverity.SHOULD, OssFindingStatus.fail, "Outdated dependency version", True),
        ("secrets", OssFindingSeverity.INFO, OssFindingStatus.pass_status, "Test fixture detected", False),
    ]
    for domain, severity, status, summary, auto_fix in findings_data:
        db.add(
            OssFinding(
                scan_id=scan.id,
                check_id=f"OSS-{domain[:3].upper()}-01",
                domain=domain,
                severity=severity,
                status=status,
                summary=summary,
                remediation="Upgrade to latest version" if auto_fix else None,
                auto_fix_available=auto_fix,
                tool="grype" if domain == "community" else "gitleaks",
            )
        )

    # ── oss-clean: enabled + never scanned (gray pill) ────────────────────────
    clean = db.get(Project, CLEAN_PROJECT_ID)
    if clean is None:
        clean = Project(
            id=CLEAN_PROJECT_ID,
            display_name="OSS Clean (E2E)",
            repo_root="/app",
            config={},
            enabled=True,
            oss_enabled=True,
        )
        db.add(clean)
        db.flush()
    else:
        clean.oss_enabled = True
        db.flush()

    db.commit()


if __name__ == "__main__":
    import os
    e2e_db_port = os.environ.get("E2E_DB_PORT", "5432")
    e2e_db_url = f"postgresql+psycopg://iw_e2e:iw_e2e_dev@localhost:{e2e_db_port}/iw_e2e"
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine_e2e = create_engine(e2e_db_url, pool_pre_ping=True)
    SessionE2E = sessionmaker(bind=engine_e2e)
    with SessionE2E() as db:
        seed(db)
    print("Seed applied OK")
