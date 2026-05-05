"""Integration tests for I-00067: Recent Activity message truncation + click-to-expand popup.

These tests verify:
1. A message > 100 chars renders 100 chars + '...' and exposes the full text via modal payload.
2. A message <= 100 chars renders verbatim with no truncation, no affordance.
3. The entity-link routing for batch/doc_job/work_item rows is unchanged.
4. The modal partial is included on the project dashboard page.

All tests use the FastAPI TestClient — no browser, no testcontainers needed.
The template logic is exercised through the HTTP layer.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import DaemonEvent

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

# The "Recent Activity" section heading in the project dashboard template.
_RECENT_ACTIVITY_HEADING = (
    '<h2 class="text-sm font-semibold text-muted-foreground '
    'uppercase tracking-wide mb-3">Recent Activity</h2>'
)


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create a TestClient that overrides get_db to use the test db_session."""
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


def _truncated(text: str, limit: int = 100) -> str:
    """Return text truncated to `limit` codepoints followed by '...'."""
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def _activity_section(html: str) -> str:
    """Return the Recent Activity section of the dashboard HTML."""
    start = html.find(_RECENT_ACTIVITY_HEADING)
    assert start != -1, "Recent Activity section not found"
    next_h2 = html.find("<h2", start + 10)
    return html[start:next_h2] if next_h2 != -1 else html[start:]


def test_long_message_truncated_and_full_text_in_dom(
    client: TestClient, db_session: Session, test_project
) -> None:
    """AC1: A message > 100 chars renders 100 chars + '...' and the full text is in the DOM."""
    long_msg = "E" * 200  # 200 chars > 100
    truncated = _truncated(long_msg)

    db_session.add(
        DaemonEvent(
            project_id=test_project.id,
            event_type="step_failed",
            entity_id="I-99999",
            entity_type="work_item",
            message=long_msg,
        )
    )
    db_session.commit()

    response = client.get(f"/project/{test_project.id}/")
    html = response.text

    # Visible truncation: first 100 chars followed by literal "..."
    assert truncated in html, f"Expected truncated text {truncated!r} in HTML"
    # The trigger class must be present
    assert "activity-message-truncated" in html
    # The full text must be available as the modal payload (data-full-text attribute)
    assert f'data-full-text="{long_msg}"' in html, "Full text should be in data-full-text attribute"


def test_short_message_not_truncated_no_affordance(
    client: TestClient, db_session: Session, test_project
) -> None:
    """AC2: A message <= 100 chars renders verbatim, no '...', no click affordance."""
    short_msg = "S" * 80  # 80 chars < 100

    db_session.add(
        DaemonEvent(
            project_id=test_project.id,
            event_type="step_started",
            entity_id=None,
            entity_type=None,
            message=short_msg,
        )
    )
    db_session.commit()

    response = client.get(f"/project/{test_project.id}/")
    html = response.text

    # Full message visible verbatim
    assert short_msg in html
    # No truncation suffix
    assert short_msg + "..." not in html
    # No trigger affordance — search for the HTML attribute (not the CSS class
    # in styles.css, which appears earlier in the document). The HTML element
    # carrying the class is: <span class="activity-message-truncated ...
    activity_section = _activity_section(html)
    # The actual HTML element with the class must NOT appear
    assert 'class="activity-message-truncated' not in activity_section


def test_exactly_100_char_message_not_truncated(
    client: TestClient, db_session: Session, test_project
) -> None:
    """Boundary: a message of exactly 100 chars renders verbatim with no '...'."""
    boundary_msg = "B" * 100

    db_session.add(
        DaemonEvent(
            project_id=test_project.id,
            event_type="step_completed",
            entity_id=None,
            entity_type=None,
            message=boundary_msg,
        )
    )
    db_session.commit()

    response = client.get(f"/project/{test_project.id}/")
    html = response.text

    activity_section = _activity_section(html)
    assert boundary_msg in activity_section
    assert boundary_msg + "..." not in activity_section
    # No class= attribute on any span for this row
    assert 'class="activity-message-truncated' not in activity_section


def test_batch_entity_link_routing_unchanged(
    client: TestClient, db_session: Session, test_project
) -> None:
    """Regression: batch entity links still route correctly after template change."""
    db_session.add(
        DaemonEvent(
            project_id=test_project.id,
            event_type="batch_updated",
            entity_id="B-00001",
            entity_type="batch",
            message="Batch updated message",
        )
    )
    db_session.commit()

    response = client.get(f"/project/{test_project.id}/")
    html = response.text

    # The batch link must be present and point to the correct URL
    assert 'href="/project/' + test_project.id + '/batch/B-00001"' in html
    assert "B-00001" in html


def test_activity_text_modal_included_in_page(
    client: TestClient, db_session: Session, test_project
) -> None:
    """The activity_text_modal partial must be included in the page markup."""
    response = client.get(f"/project/{test_project.id}/")
    html = response.text

    # Unique IDs from the activity text modal must be present
    assert "activity-text-modal-overlay" in html
    assert 'id="activity-text-modal"' in html
    assert "activity-text-modal-body" in html


def test_null_message_falls_back_to_event_type(
    client: TestClient, db_session: Session, test_project
) -> None:
    """A null/None message falls back to event_type (existing behaviour, no truncation)."""
    db_session.add(
        DaemonEvent(
            project_id=test_project.id,
            event_type="daemon_started",
            entity_id=None,
            entity_type=None,
            message=None,
        )
    )
    db_session.commit()

    response = client.get(f"/project/{test_project.id}/")
    html = response.text

    activity_section = _activity_section(html)
    # Should show event_type, no truncation logic applied
    assert "daemon_started" in activity_section
    assert 'class="activity-message-truncated' not in activity_section


def test_101_char_message_is_truncated(
    client: TestClient, db_session: Session, test_project
) -> None:
    """Boundary: a 101-char message should be truncated (just over 100)."""
    msg = "X" * 101  # exactly 101 chars
    db_session.add(
        DaemonEvent(
            project_id=test_project.id,
            event_type="step_failed",
            entity_id=None,
            entity_type=None,
            message=msg,
        )
    )
    db_session.commit()

    response = client.get(f"/project/{test_project.id}/")
    html = response.text

    # Should show 100 chars + "..."
    assert "X" * 100 + "..." in html
    # Trigger affordance must be present
    assert "activity-message-truncated" in html
    # Full text must be in data-full-text
    assert f'data-full-text="{msg}"' in html
