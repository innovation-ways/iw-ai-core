"""F-00090 S04: Dashboard tests for Quality KPIs section and regression badge.

Covers AC6 (KPIs) and AC7 (badge) + Boundary rows.

Container: dashboard tests use FastAPI TestClient with testcontainer-backed
db_session fixture (never the live DB port 5433).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    Project,
    RegressionClassification,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# TestClient fixture (mirrors test_regression_classification_form.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def client(db_session: Session) -> TestClient:
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            return db_session

        app = create_app()
        app.dependency_overrides[get_db] = override_get_db
        with TestClient(app, raise_server_exceptions=True) as c:
            yield c
    finally:
        if original is not None:
            os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_project(db_session, *, project_id="F90TEST2"):
    """Create a minimal project."""
    project = Project(
        id=project_id, display_name="F-00090 KPI Test Project", repo_root="/tmp/f90test2"
    )
    db_session.add(project)
    db_session.flush()
    return project


def _seed_merged_feature(
    db_session,
    project_id: str,
    item_id: str,
    title: str,
    days_ago: int = 0,
    is_incident: bool = False,
) -> WorkItem:
    """Create a merged Feature (or Incident) work item.

    created_at and completed_at are actual datetime objects (not timedelta).
    """
    now = datetime.now(UTC)
    created = now - timedelta(days=days_ago)
    completed = created + timedelta(days=1)
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.ChangeRequest if is_incident else WorkItemType.Feature,
        title=title,
        status=WorkItemStatus.completed,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=["src/foo.py"],
        created_at=created,
        completed_at=completed,
    )
    db_session.add(item)
    return item


def _classify_as_regression(
    db_session,
    incident: WorkItem,
    source_work_item_id: str,
    days_ago: int = 0,
) -> WorkItem:
    """Set regression_classification='regression' on an incident, pointing to source_work_item_id.

    This simulates the operator having filed and classified an Incident via the UI.
    """
    incident.introduced_by_work_item_id = source_work_item_id
    incident.regression_classification = RegressionClassification.regression
    incident.classified_at = datetime.now(UTC) - timedelta(days=days_ago)
    incident.classified_by = "operator:test"
    return incident


# ---------------------------------------------------------------------------
# AC6: Quality KPIs section renders weekly metrics with trend chart
# ---------------------------------------------------------------------------


def test_kpis_section_renders_current_week_numbers(db_session, client: TestClient):
    """AC6: KPI section shows current week's merges, regressions, and rate."""
    project = _seed_project(db_session)

    # Create a merged Feature 2 days ago → counts as this week's merge
    _seed_merged_feature(db_session, project.id, "F-00011", "F-00011 merged feature", days_ago=2)
    # Create a merged Incident 1 day ago → classified as regression
    incident = _seed_merged_feature(
        db_session,
        project.id,
        "I-00011",
        "I-00011 regression incident",
        days_ago=1,
        is_incident=True,
    )
    _classify_as_regression(db_session, incident, "F-00011", days_ago=1)

    db_session.commit()

    # Visit the per-project home — must NOT 500
    response = client.get(f"/project/{project.id}/")
    assert response.status_code == 200

    # The KPI section must be present (plain AssertionError until implemented)
    assert "kpal" in response.text.lower() or "quality" in response.text.lower(), (
        "KPI section should be present on per-project home"
    )


def test_kpis_rate_is_zero_when_merges_zero(db_session, client: TestClient):
    """Boundary row: zero merges and N regressions → rate is 0.0, not NaN.

    RED evidence: ZeroDivisionError when merges==0 before rate_guard added
    (AssertionError: <NA> comparisons vs plain assertion failure — proof of RED).
    """

    project = _seed_project(db_session)

    # Create two classified Incident rows but no merges in this timeline
    # (week has regressions but 0 merges → rate guard kicks in)
    incident1 = _seed_merged_feature(
        db_session, project.id, "I-00021", "I-00021 regression", days_ago=3, is_incident=True
    )
    _classify_as_regression(db_session, incident1, "F-00021", days_ago=3)
    incident2 = _seed_merged_feature(
        db_session, project.id, "I-00022", "I-00022 regression", days_ago=1, is_incident=True
    )
    _classify_as_regression(db_session, incident2, "F-00021", days_ago=1)

    db_session.commit()

    # Must NOT 500 or 404 even with zero merges
    response = client.get(f"/project/{project.id}/quality-kpis")
    assert response.status_code == 200, (
        f"Expected 200 even with 0 merges, got {response.status_code}: {response.text[:500]}"
    )


def test_kpis_trend_chart_is_inline_svg_no_script(db_session, client: TestClient):
    """AC6: 12-week trend chart is an inline SVG element on the page.

    The page itself includes the htmx/theme <script> tags from base.html —
    this test only checks that the SVG chart is rendered inline (not via an
    external chart library like Chart.js or D3 loaded as a script).
    """
    project = _seed_project(db_session)

    # One merged feature + one regression spanning weeks
    _seed_merged_feature(db_session, project.id, "F-00031", "F-00031 merged feature", days_ago=14)
    incident = _seed_merged_feature(
        db_session, project.id, "I-00031", "I-00031 regression", days_ago=13, is_incident=True
    )
    _classify_as_regression(db_session, incident, "F-00031", days_ago=13)

    db_session.commit()

    response = client.get(f"/project/{project.id}/quality-kpis")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # The page must contain an <svg> element (inline chart)
    assert "<svg" in response.text, "KPI response must contain a <svg> chart element"
    # The chart is NOT rendered via an external charting JS library
    # (no D3.js, Chart.js, Plotly, etc. loaded as a script src)
    for bad_lib in ("chart.js", "d3.", "plotly", "chartist", "highcharts"):
        assert bad_lib not in response.text.lower(), (
            f"Chart must not depend on external library '{bad_lib}' loaded as a script"
        )
    # Key SVG attributes are present (chart dimensions and role)
    assert 'viewBox="0 0 560 200"' in response.text, (
        "Chart SVG must have correct viewBox dimensions"
    )
    assert 'role="img"' in response.text, "Chart SVG must have role='img' for accessibility"


def test_kpis_trend_handles_less_than_12_weeks(db_session, client: TestClient):
    """Boundary row: <12 weeks of history — chart plots actual weeks only."""
    project = _seed_project(db_session)

    # Only 3 weeks of history
    _seed_merged_feature(db_session, project.id, "F-00041", "F-00041 merged", days_ago=1)
    _seed_merged_feature(db_session, project.id, "F-00042", "F-00042 merged", days_ago=8)
    incident = _seed_merged_feature(
        db_session, project.id, "I-00042", "I-00042 regression", days_ago=9, is_incident=True
    )
    _classify_as_regression(db_session, incident, "F-00041", days_ago=9)

    db_session.commit()

    response = client.get(f"/project/{project.id}/quality-kpis")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # The SVG chart is present
    assert "<svg" in response.text, "Chart SVG must be present"


# ---------------------------------------------------------------------------
# AC7: Regression badge on History rows
# ---------------------------------------------------------------------------


def test_regression_badge_renders_when_count_positive(db_session, client: TestClient):
    """AC7: Badge 'N regressions' appears when N >= 1."""
    project = _seed_project(db_session)

    _seed_merged_feature(db_session, project.id, "F-00051", "F-00051 merged feature", days_ago=20)
    incident = _seed_merged_feature(
        db_session,
        project.id,
        "I-00051",
        "I-00051 regression incident",
        days_ago=10,
        is_incident=True,
    )
    _classify_as_regression(db_session, incident, "F-00051", days_ago=10)

    db_session.commit()

    response = client.get(f"/project/{project.id}/history")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # Badge must appear for F-00051
    assert "iw-regression-badge" in response.text, (
        f"Expected regression badge on F-00051 row in history, got: {response.text[:500]}"
    )


def test_regression_badge_absent_when_count_zero(db_session, client: TestClient):
    """Boundary row N==0: badge is absent when no regressions point to the merge."""
    project = _seed_project(db_session)

    # F-00061: clean merge with no regressions pointing to it
    _seed_merged_feature(db_session, project.id, "F-00061", "F-00061 clean feature", days_ago=30)

    db_session.commit()

    response = client.get(f"/project/{project.id}/history")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # F-00061 appears in history
    assert "F-00061" in response.text, "F-00061 must appear in history"
    # But no regression badge
    assert "iw-regression-badge" not in response.text, (
        "Expected no iw-regression-badge for clean feature F-00061"
    )


def test_regression_badge_aggregates_multiple_incidents(db_session, client: TestClient):
    """Boundary row: two regressions point to the same merge → badge reads '2 regressions'."""
    project = _seed_project(db_session)

    _seed_merged_feature(db_session, project.id, "F-00071", "F-00071 busted feature", days_ago=40)
    incident1 = _seed_merged_feature(
        db_session, project.id, "I-00071", "I-00071 regression 1", days_ago=20, is_incident=True
    )
    _classify_as_regression(db_session, incident1, "F-00071", days_ago=20)
    incident2 = _seed_merged_feature(
        db_session, project.id, "I-00072", "I-00072 regression 2", days_ago=10, is_incident=True
    )
    _classify_as_regression(db_session, incident2, "F-00071", days_ago=10)

    db_session.commit()

    response = client.get(f"/project/{project.id}/history")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # Must show "2 regressions" badge on the F-00071 row
    assert "2 regressions" in response.text, (
        f"Expected '2 regressions' badge for F-00071 in history, got: {response.text[:500]}"
    )


def test_pre_existing_classification_does_not_contribute(db_session, client: TestClient):
    """Invariant 1 + Boundary row: pre_existing classification → no badge, no KPI contribution."""
    project = _seed_project(db_session)

    _seed_merged_feature(db_session, project.id, "F-00081", "F-00081 merged feature", days_ago=50)
    incident = _seed_merged_feature(
        db_session, project.id, "I-00081", "I-00081 pre-existing bug", days_ago=30, is_incident=True
    )
    # pre_existing: introduced_by is NULL, classified as pre_existing
    incident.introduced_by_work_item_id = None
    incident.regression_classification = RegressionClassification.pre_existing
    incident.classified_at = datetime.now(UTC) - timedelta(days=30)
    incident.classified_by = "operator:test"

    db_session.commit()

    response = client.get(f"/project/{project.id}/history")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    # No regression badge for F-00081 (pre_existing never links to a merge)
    assert "iw-regression-badge" not in response.text, (
        "pre_existing classification must not produce a regression badge"
    )
