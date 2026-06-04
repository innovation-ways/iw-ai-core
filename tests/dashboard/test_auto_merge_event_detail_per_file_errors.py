"""Dashboard tests for I-00103: per_file_errors rendering in the event-detail modal.

Three cases:
1. per_file_errors present → section renders with semantic content
2. per_file_errors missing (historical shape) → section hidden
3. per_file_errors present but empty list → section hidden

These tests use the FastAPI TestClient fixture from tests/dashboard/conftest.py,
which re-exports the testcontainer db_session from tests/integration/conftest.py.

Attribute-scoped CSS class assertions are used throughout (I-00067 lesson):
  assert 'class="auto-merge-modal__per-file-error"' in html
rather than bare-substring 'per-file-error'.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import DaemonEvent, Project

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Provide a TestClient with the test db_session wired into get_db."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _seed_event_with_metadata(
    db_session: Session,
    project_id: str,
    metadata: dict[str, object],
    event_type: str = "merge_auto_resolution_failed",
) -> DaemonEvent:
    """Insert a DaemonEvent row with the given metadata and flush it."""
    event = DaemonEvent(
        project_id=project_id,
        event_type=event_type,
        entity_id="W",
        entity_type="work_item",
        message=f"test {event_type} event",
        event_metadata=metadata,
        created_at=datetime.now(UTC),
    )
    db_session.add(event)
    db_session.flush()
    return event


# ---------------------------------------------------------------------------
# Test 1: section renders when per_file_errors is present
# ---------------------------------------------------------------------------


def test_event_detail_renders_per_file_errors_section_when_present(
    client: TestClient,
    test_project: Project,
    db_session: Session,
) -> None:
    """HTTP 200; the labelled section appears in the HTML with semantic content.

    The section class is auto-merge-modal__per-file-errors (the outer wrapper),
    each entry has class auto-merge-modal__per-file-error (S03 naming).
    Assertions verify specific expected values, not just shape.
    """
    metadata = {
        "phase": 1,
        "abstained_files": [],
        "error_files": ["tests/dashboard/test_auto_merge_routes.py"],
        "proposed_files": [],
        "runtime_option_id": 1,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "per_file_errors": [
            {
                "file_path": "tests/dashboard/test_auto_merge_routes.py",
                "error": "LLM call timed out after 120s: subprocess.TimeoutExpired(..., 120)",
                "cli_tool": "opencode",
                "model": "minimax/MiniMax-M2.7",
            },
        ],
    }

    event = _seed_event_with_metadata(db_session, test_project.id, metadata)
    db_session.flush()

    response = client.get(f"/project/{test_project.id}/auto-merge/events/{event.id}")
    assert response.status_code == 200, response.text
    html = response.text

    # Attribute-scoped: the section wrapper class appears
    assert 'class="auto-merge-modal__per-file-errors"' in html, (
        "per-file-errors section must render when per_file_errors is present"
    )

    # Attribute-scoped: each entry card class
    assert 'class="auto-merge-modal__per-file-error"' in html, (
        "per-file-error entry card must be rendered"
    )

    # Semantic: the literal error substring renders in the HTML
    assert "LLM call timed out after 120s" in html, (
        "the error string must appear verbatim in the modal"
    )

    # Semantic: the file path renders
    assert "tests/dashboard/test_auto_merge_routes.py" in html, (
        "the file_path must appear in the modal"
    )

    # Semantic: the runtime label (cli_tool/model) renders
    assert "opencode" in html, "the cli_tool must appear in the modal"
    assert "minimax/MiniMax-M2.7" in html, "the model must appear in the modal"
    # Also verify the combined label format from the template: cli_tool/model
    assert "opencode/minimax/MiniMax-M2.7" in html, (
        "the combined runtime label must render as 'cli_tool/model'"
    )


# ---------------------------------------------------------------------------
# Test 2: section hidden when per_file_errors key is absent (historical shape)
# ---------------------------------------------------------------------------


def test_event_detail_hides_per_file_errors_section_when_absent(
    client: TestClient,
    test_project: Project,
    db_session: Session,
) -> None:
    """HTTP 200; the new section is NOT rendered for historical events missing the key.

    Historical events (e.g. 80689, 88770) have 7 keys but no per_file_errors.
    No template exception; existing JSON metadata block still renders.
    """
    # The exact 7-key shape from pre-fix events 80689 / 88770
    historical_metadata = {
        "phase": 1,
        "abstained_files": [],
        "error_files": ["tests/dashboard/test_auto_merge_routes.py"],
        "proposed_files": [],
        "runtime_option_id": 1,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        # No 'per_file_errors' key
    }

    event = _seed_event_with_metadata(db_session, test_project.id, historical_metadata)
    db_session.flush()

    response = client.get(f"/project/{test_project.id}/auto-merge/events/{event.id}")
    assert response.status_code == 200, response.text
    html = response.text

    # Section class must NOT appear in the HTML (attribute-scoped)
    assert 'class="auto-merge-modal__per-file-errors"' not in html, (
        "per-file-errors section must not be rendered when the key is absent"
    )

    # The entry card class must also not appear
    assert 'class="auto-merge-modal__per-file-error"' not in html, (
        "per-file-error entry card must not be rendered when the key is absent"
    )

    # The Metadata block must still render (backward compatibility)
    assert "Metadata" in html, "existing Metadata section must still render"


# ---------------------------------------------------------------------------
# Test 3: section hidden when per_file_errors is an empty list
# ---------------------------------------------------------------------------


def test_event_detail_hides_per_file_errors_section_when_empty_list(
    client: TestClient,
    test_project: Project,
    db_session: Session,
) -> None:
    """HTTP 200; the section is not rendered when per_file_errors is present but [].

    Jinja2 truthiness of an empty list is False, so the section is skipped.
    Same assertions as the missing-key case.
    """
    metadata = {
        "phase": 1,
        "abstained_files": [],
        "error_files": [],
        "proposed_files": [],
        "runtime_option_id": 1,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "per_file_errors": [],  # present but empty
    }

    event = _seed_event_with_metadata(db_session, test_project.id, metadata)
    db_session.flush()

    response = client.get(f"/project/{test_project.id}/auto-merge/events/{event.id}")
    assert response.status_code == 200, response.text
    html = response.text

    # Section class must NOT appear in the HTML (attribute-scoped)
    assert 'class="auto-merge-modal__per-file-errors"' not in html, (
        "per-file-errors section must not be rendered when the list is empty"
    )

    # The entry card class must also not appear
    assert 'class="auto-merge-modal__per-file-error"' not in html, (
        "per-file-error entry card must not be rendered when the list is empty"
    )

    # The Metadata block must still render
    assert "Metadata" in html, "existing Metadata section must still render"
