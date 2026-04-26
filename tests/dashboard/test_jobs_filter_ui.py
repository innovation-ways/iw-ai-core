"""I-00039 reproduction + regression tests for the Jobs page filter UI.

These tests verify the fix for the Jobs page:
1. Type column is plain text (no per-type colour chips)
2. Filter uses multi-select dropdown markup (not flat checkboxes)
3. Multi-value filter query-string contract is preserved

All tests use FastAPI's TestClient against a PostgreSQL testcontainer
(via the existing fixtures from tests/dashboard/conftest.py — never the live DB).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from tests.integration.test_jobs_api import _seed_all_sources

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create a TestClient that overrides get_db to use the test db_session."""
    import os

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
        app.dependency_overrides.clear()


LEGACY_TYPE_COLOR_CLASSES = (
    "bg-blue-100",
    "bg-purple-100",
    "bg-orange-100",
    "bg-teal-100",
    "bg-emerald-100",
)


def test_jobs_type_cell_is_plain_text_no_color_chip(
    client: TestClient, db_session: Session, test_project
) -> None:
    """RED before fix: the Type cell uses bg-* utility classes from type_chip.

    Asserts the FIX is in place: the rendered HTML must NOT contain any of the
    legacy per-type background classes anywhere on the Jobs page.
    """
    _seed_all_sources(db_session, test_project.id)
    db_session.commit()

    resp = client.get(f"/project/{test_project.id}/jobs")
    assert resp.status_code == 200
    html = resp.text

    for cls in LEGACY_TYPE_COLOR_CLASSES:
        assert cls not in html, (
            f"Legacy color class {cls!r} still present in Jobs page HTML — "
            "Type chip color-coding was not removed."
        )


def test_jobs_filter_uses_multiselect_dropdown_not_checkbox_groups(
    client: TestClient, test_project
) -> None:
    """RED before fix: Type/Status filters are flat <input type=checkbox name=type>.

    Asserts the FIX: the page renders a multi_select dropdown component
    (button + popover) for both filters, instead of flat checkbox rows.

    The checkboxes now live INSIDE [data-multi-select-panel] — they must not
    appear outside that wrapper.
    """
    resp = client.get(f"/project/{test_project.id}/jobs")
    assert resp.status_code == 200
    html = resp.text

    assert 'data-multi-select="type"' in html, (
        "Multi-select dropdown wrapper not found for Type filter"
    )
    assert 'data-multi-select="status"' in html, (
        "Multi-select dropdown wrapper not found for Status filter"
    )

    assert 'data-multi-select-panel="type"' in html, "Multi-select panel not found for Type filter"
    assert 'data-multi-select-panel="status"' in html, (
        "Multi-select panel not found for Status filter"
    )

    normalized = "".join(html.split())

    type_panel_match = re.search(
        r'data-multi-select-panel="type"[^>]*>(.*?)</div>',
        normalized,
        re.DOTALL,
    )
    status_panel_match = re.search(
        r'data-multi-select-panel="status"[^>]*>(.*?)</div>',
        normalized,
        re.DOTALL,
    )

    assert type_panel_match, "Type panel not found in normalised HTML"
    assert status_panel_match, "Status panel not found in normalised HTML"

    type_panel_content = type_panel_match.group(1)
    status_panel_content = status_panel_match.group(1)

    assert '<inputtype="checkbox"name="type"' in type_panel_content, (
        "Type checkboxes not inside Type panel"
    )
    assert '<inputtype="checkbox"name="status"' in status_panel_content, (
        "Status checkboxes not inside Status panel"
    )

    before_type_panel = normalized[: type_panel_match.start()]
    before_status_panel = normalized[: status_panel_match.start()]
    assert '<inputtype="checkbox"name="type"' not in before_type_panel, (
        "Legacy flat Type checkbox found outside multi-select panel"
    )
    assert '<inputtype="checkbox"name="status"' not in before_status_panel, (
        "Legacy flat Status checkbox found outside multi-select panel"
    )


def test_jobs_filter_multiple_types_still_filters(
    client: TestClient, db_session: Session, test_project
) -> None:
    """REGRESSION: query-string contract preserved.

    Submitting ?type=code_mapping&type=research must filter to those two types
    only (matches the pre-fix behaviour — the form still emits repeated
    name=value pairs).
    """
    ids = _seed_all_sources(db_session, test_project.id)
    db_session.commit()

    resp = client.get(f"/project/{test_project.id}/jobs?type=code_mapping&type=research")
    assert resp.status_code == 200
    html = resp.text

    assert ids["cij_id"] in html, "code_mapping row should be present"
    assert ids["res_doc_id"] in html, "research row should be present"
    assert ids["batch_id"] not in html, "batch_execution row should be excluded"
    assert ids["dgj_id"] not in html, "doc_generation row should be excluded"
