"""Integration tests for OssFindingDetail model + persistence + route.

Covers:
- OssFindingDetail rows are created by persist_findings when a finding's
  evidence carries a `results` array.
- Detail rows cascade-delete when their parent OssFinding is deleted.
- The `evidence_json` stored on the finding strips the heavy `results` list
  (those live in the detail table) but keeps aggregate fields.
- The dashboard route `GET /project/{pid}/oss/findings/{fid}/details`
  paginates, reports `total` and `capped`, refuses cross-project access.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    OssFinding,
    OssScan,
    OssScanStatus,
    Project,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.engine import Engine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def details_connection(db_engine: Engine):
    """Outer-transaction-with-savepoint pattern so committed writes are visible
    across sessions but rolled back at teardown."""
    connection = db_engine.connect()
    transaction = connection.begin()
    yield connection
    transaction.rollback()
    connection.close()


@pytest.fixture
def db_session(details_connection) -> Generator[Session, None, None]:
    session = Session(
        bind=details_connection,
        autocommit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    yield session
    session.close()


@pytest.fixture
def client(
    db_session: Session,
    details_connection,
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    import os

    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:
        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
        app.dependency_overrides.clear()
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


@pytest.fixture
def project_a(db_session: Session, tmp_path: Path) -> Project:
    repo = tmp_path / "proj-a"
    repo.mkdir()
    p = Project(
        id="proj-a",
        display_name="Project A",
        repo_root=str(repo),
        config={},
        oss_enabled=True,
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def project_b(db_session: Session, tmp_path: Path) -> Project:
    repo = tmp_path / "proj-b"
    repo.mkdir()
    p = Project(
        id="proj-b",
        display_name="Project B",
        repo_root=str(repo),
        config={},
        oss_enabled=True,
    )
    db_session.add(p)
    db_session.flush()
    return p


def _make_scan_with_finding(
    session: Session,
    project: Project,
    *,
    n_results: int = 3,
    capped: bool = False,
    total_results: int | None = None,
) -> tuple[OssScan, OssFinding]:
    """Insert a scan + a single OssFinding with `n_results` detail records via
    persist_findings()."""
    from orch.oss.persistence import persist_findings

    scan = OssScan(project_id=project.id, status=OssScanStatus.complete)
    session.add(scan)
    session.flush()

    results = [
        {
            "file": f"src/file_{i}.py",
            "line": i + 1,
            "rule": "generic-api-key",
            "snippet_masked": f"sk-a***{i:02}",
        }
        for i in range(n_results)
    ]
    real_total = total_results if total_results is not None else n_results

    findings_json = {
        "findings": [
            {
                "id": "OSS-SEC-01",
                "severity": "MUST",
                "status": "fail",
                "domain": "secrets",
                "summary": f"{real_total} secret(s) detected (tree scan)",
                "detail": "",
                "remediation": "Review SARIF.",
                "auto_fix_available": False,
                "auto_apply_safe": False,
                "tool": "gitleaks",
                "evidence": {
                    "sarif": "/tmp/gitleaks-tree.sarif",
                    "finding_count": real_total,
                    "total_results": real_total,
                    "capped": capped,
                    "results": results,
                },
            }
        ],
        "tools_available": {"gitleaks": "8.21.2"},
    }
    persist_findings(session, scan, findings_json)
    session.flush()

    finding = (
        session.query(OssFinding)
        .filter(OssFinding.scan_id == scan.id, OssFinding.check_id == "OSS-SEC-01")
        .one()
    )
    return scan, finding


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistDetails:
    def test_detail_rows_created(self, db_session: Session, project_a: Project) -> None:
        from orch.db.models import OssFindingDetail

        _, finding = _make_scan_with_finding(db_session, project_a, n_results=3)
        details = (
            db_session.query(OssFindingDetail)
            .filter(OssFindingDetail.finding_id == finding.id)
            .order_by(OssFindingDetail.ordinal)
            .all()
        )
        assert len(details) == 3
        assert details[0].file_path == "src/file_0.py"
        assert details[0].line_number == 1
        assert details[0].rule_id == "generic-api-key"
        assert details[0].snippet_masked.startswith("sk-a")
        # Ordinals are stable, monotonically increasing from 0.
        assert [d.ordinal for d in details] == [0, 1, 2]

    def test_evidence_json_strips_results(self, db_session: Session, project_a: Project) -> None:
        """The heavy `results` array goes to the detail table; evidence_json
        should keep only the aggregate fields."""
        _, finding = _make_scan_with_finding(db_session, project_a, n_results=2)
        ev = finding.evidence_json or {}
        assert "results" not in ev
        assert ev.get("finding_count") == 2
        assert ev.get("total_results") == 2
        assert ev.get("capped") is False
        assert ev.get("sarif") == "/tmp/gitleaks-tree.sarif"

    def test_no_results_means_no_detail_rows(self, db_session: Session, project_a: Project) -> None:
        """Findings without a `results` array (e.g. OSS-LIC-01) must not create
        spurious detail rows."""
        from orch.db.models import OssFindingDetail
        from orch.oss.persistence import persist_findings

        scan = OssScan(project_id=project_a.id, status=OssScanStatus.complete)
        db_session.add(scan)
        db_session.flush()
        persist_findings(
            db_session,
            scan,
            {
                "findings": [
                    {
                        "id": "OSS-LIC-01",
                        "severity": "MUST",
                        "status": "fail",
                        "domain": "license",
                        "summary": "LICENSE file missing",
                        "evidence": {"paths_checked": ["LICENSE"]},
                    }
                ],
                "tools_available": {},
            },
        )
        db_session.flush()
        assert db_session.query(OssFindingDetail).count() == 0, (
            "license findings should not produce detail rows"
        )

    def test_cascade_delete_on_finding(self, db_session: Session, project_a: Project) -> None:
        from orch.db.models import OssFindingDetail

        _, finding = _make_scan_with_finding(db_session, project_a, n_results=4)
        finding_id = finding.id
        db_session.delete(finding)
        db_session.flush()
        remaining = (
            db_session.query(OssFindingDetail)
            .filter(OssFindingDetail.finding_id == finding_id)
            .count()
        )
        assert remaining == 0


# Route tests for the new /oss/findings/{id}/details endpoint follow.


class TestFindingDetailsRoute:
    def test_returns_paginated_results(
        self,
        client: TestClient,
        db_session: Session,
        project_a: Project,
    ) -> None:
        _, finding = _make_scan_with_finding(db_session, project_a, n_results=5)
        db_session.commit()

        r = client.get(
            f"/project/{project_a.id}/oss/findings/{finding.id}/details?limit=2&offset=1"
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 5
        assert body["limit"] == 2
        assert body["offset"] == 1
        assert body["capped"] is False
        assert len(body["results"]) == 2
        # offset=1 → ordinals 1 and 2.
        assert [row["ordinal"] for row in body["results"]] == [1, 2]
        assert body["results"][0]["file"] == "src/file_1.py"
        assert body["results"][0]["line"] == 2
        assert body["results"][0]["rule"] == "generic-api-key"
        # No raw secret content.
        assert "snippet_masked" in body["results"][0]

    def test_default_limit(
        self,
        client: TestClient,
        db_session: Session,
        project_a: Project,
    ) -> None:
        _, finding = _make_scan_with_finding(db_session, project_a, n_results=3)
        db_session.commit()
        r = client.get(f"/project/{project_a.id}/oss/findings/{finding.id}/details")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 3
        # Default page returns everything for a small finding.
        assert len(body["results"]) == 3

    def test_capped_flag_propagated(
        self,
        client: TestClient,
        db_session: Session,
        project_a: Project,
    ) -> None:
        _, finding = _make_scan_with_finding(
            db_session,
            project_a,
            n_results=2,
            capped=True,
            total_results=99999,
        )
        db_session.commit()
        r = client.get(f"/project/{project_a.id}/oss/findings/{finding.id}/details")
        assert r.status_code == 200
        body = r.json()
        assert body["capped"] is True
        # The `total` reported is the capped detail-table count, not the raw
        # SARIF aggregate. UI shows `evidence.total_results` separately.
        assert body["total"] == 2

    def test_404_when_finding_unknown(
        self,
        client: TestClient,
        project_a: Project,
    ) -> None:
        r = client.get(f"/project/{project_a.id}/oss/findings/9999999/details")
        assert r.status_code == 404

    def test_404_when_finding_belongs_to_other_project(
        self,
        client: TestClient,
        db_session: Session,
        project_a: Project,
        project_b: Project,
    ) -> None:
        # Finding belongs to project_b but request asks under project_a.
        _, finding = _make_scan_with_finding(db_session, project_b, n_results=1)
        db_session.commit()
        r = client.get(f"/project/{project_a.id}/oss/findings/{finding.id}/details")
        assert r.status_code == 404

    def test_no_detail_table_returns_empty(
        self,
        client: TestClient,
        db_session: Session,
        project_a: Project,
    ) -> None:
        """A finding without detail rows (e.g. OSS-LIC-01) should still
        respond 200 with total=0, not 404."""
        from orch.oss.persistence import persist_findings

        scan = OssScan(project_id=project_a.id, status=OssScanStatus.complete)
        db_session.add(scan)
        db_session.flush()
        persist_findings(
            db_session,
            scan,
            {
                "findings": [
                    {
                        "id": "OSS-LIC-01",
                        "severity": "MUST",
                        "status": "fail",
                        "domain": "license",
                        "summary": "LICENSE missing",
                    }
                ],
                "tools_available": {},
            },
        )
        db_session.flush()
        finding = db_session.query(OssFinding).filter(OssFinding.scan_id == scan.id).one()
        db_session.commit()

        r = client.get(f"/project/{project_a.id}/oss/findings/{finding.id}/details")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["results"] == []


# ---------------------------------------------------------------------------
# DDL sanity
# ---------------------------------------------------------------------------


class TestSchema:
    def test_oss_finding_detail_table_exists(self, db_engine: Engine) -> None:
        with db_engine.connect() as conn:
            r = conn.execute(
                text("SELECT to_regclass('public.oss_finding_detail') IS NOT NULL")
            ).scalar()
        assert r is True
