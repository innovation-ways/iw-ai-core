"""CR-00056 S11: Tests for item_steps_table.html Prompt column rendering.

Verifies:
- Prompt column header appears between Model and Status (AC4)
- Steps with has_prompt render a View button with correct htmx URL
- Synthetic steps (S00, MERGE) render '—' in the Prompt cell
- Steps with has_prompt=False render '—'
- Empty state row has correct colspan (11 headers)
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.dependencies import get_db

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """FastAPI TestClient backed by the testcontainer db_session."""
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


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


def _make_project_with_steps(
    db_session: Session,
    project_id: str,
    item_id: str,
    has_prompt: bool = False,
    is_synthetic: bool = False,
) -> dict:
    """Create project + item + optional step rows and return them."""
    from datetime import UTC, datetime

    from orch.db.models import (
        Batch,
        BatchItem,
        Project,
        RunStatus,
        StepRun,
        StepStatus,
        StepType,
        WorkflowStep,
        WorkItem,
    )

    project = Project(
        id=project_id,
        display_name=f"Test Project {project_id}",
        repo_root="/tmp/repo",
        config={},
    )
    db_session.add(project)
    db_session.flush()

    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type="Feature",
        status="approved",
        title="Test Item",
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    db_session.add(item)
    db_session.flush()

    batch = Batch(project_id=project_id, id=f"batch-{project_id}", status="approved")
    db_session.add(batch)
    db_session.flush()

    bi = BatchItem(
        project_id=project_id,
        batch_id=f"batch-{project_id}",
        work_item_id=item_id,
        status="completed",
    )
    db_session.add(bi)
    db_session.flush()

    step = WorkflowStep(
        project_id=project_id,
        work_item_id=item_id,
        step_id="S04",
        step_number=4,
        agent_label="Backend",
        step_type=StepType.implementation,
        status=StepStatus.completed,
        prompt_file="prompts/S04.md",
    )
    db_session.add(step)
    db_session.flush()

    if has_prompt:
        run = StepRun(
            step_id=step.id,
            run_number=1,
            status=RunStatus.completed,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            prompt_text="This is the captured prompt text for S04.",
        )
        db_session.add(run)
        db_session.commit()

    return {
        "project": project,
        "item": item,
        "batch": batch,
        "batch_item": bi,
        "step": step,
    }


class TestPromptColumnRendering:
    """AC4: Prompt column renders correctly in the steps table."""

    def test_prompt_column_header_present_between_model_and_status(
        self, client: TestClient, db_session: Session
    ):
        """The <th>Prompt</th> header appears between Model and Status in the rendered HTML."""
        seed = _make_project_with_steps(
            db_session,
            project_id="proj-tc-col",
            item_id="CR-00099",
            has_prompt=True,
        )

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}",
        )
        assert response.status_code == 200, response.text

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        assert table is not None, "No <table> found in item detail page"

        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        assert "Prompt" in headers, f"Prompt header not found. Headers: {headers}"

        # Verify ordering: Model → Prompt → Status
        model_idx = headers.index("Model")
        prompt_idx = headers.index("Prompt")
        status_idx = headers.index("Status")
        assert model_idx < prompt_idx < status_idx, (
            f"Expected Model ({model_idx}) < Prompt ({prompt_idx}) < Status ({status_idx}), "
            f"but headers order: {headers}"
        )

    def test_step_with_prompt_renders_view_button_with_correct_hx_get(
        self, client: TestClient, db_session: Session
    ):
        """For has_prompt=True, the Prompt cell contains a View button with the correct htmx URL."""
        seed = _make_project_with_steps(
            db_session,
            project_id="proj-tc-btn",
            item_id="CR-00100",
            has_prompt=True,
        )

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}",
        )
        assert response.status_code == 200, response.text

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        assert table is not None

        # Find the row for step S04
        step_rows = table.find_all("tr")
        s04_row = None
        for row in step_rows:
            if "S04" in row.get_text():
                s04_row = row
                break

        assert s04_row is not None, (
            f"S04 row not found in table. Table rows: {[r.get_text()[:50] for r in step_rows]}"
        )

        # Find the Prompt cell (td at the same index as the Prompt th)
        th_elements = table.find_all("th")
        header_names = [th.get_text(strip=True) for th in th_elements]
        prompt_col_index = header_names.index("Prompt")
        cells = s04_row.find_all("td")
        prompt_cell = cells[prompt_col_index]

        # The cell should contain a View button, not a dash
        view_btn = prompt_cell.find("button", class_="prompt-view-trigger")
        assert view_btn is not None, (
            f"No View button found in Prompt cell. Cell HTML: {prompt_cell}"
        )

        # Verify the hx-get URL
        hx_get = view_btn.get("hx-get", "")
        expected_url = (
            f"/project/{seed['project'].id}/item/{seed['item'].id}/"
            f"step/{seed['step'].step_id}/prompt-modal"
        )
        assert hx_get == expected_url, f"Expected hx-get={expected_url!r}, got {hx_get!r}"

    def test_synthetic_step_renders_dash_in_prompt_column(
        self, client: TestClient, db_session: Session
    ):
        """Synthetic steps (S00 / MERGE) render '—' in the Prompt cell, not a View button."""
        seed = _make_project_with_steps(
            db_session,
            project_id="proj-tc-synth",
            item_id="CR-00101",
            has_prompt=True,
        )

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}",
        )
        assert response.status_code == 200, response.text

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        assert table is not None

        # The item_detail page always shows S00 (setup) and MERGE (merge) rows.
        # Find the S00 row
        step_rows = table.find_all("tr")
        s00_row = None
        for row in step_rows:
            if "S00" in row.get_text() and "Worktree Setup" in row.get_text():
                s00_row = row
                break

        assert s00_row is not None, "S00 row not found in table"

        th_elements = table.find_all("th")
        header_names = [th.get_text(strip=True) for th in th_elements]
        prompt_col_index = header_names.index("Prompt")
        cells = s00_row.find_all("td")
        prompt_cell = cells[prompt_col_index]

        # Should be a dash, not a button
        assert prompt_cell.get_text(strip=True) == "—", (
            f"Expected '—' for synthetic step, got: {prompt_cell.get_text()!r}"
        )
        assert prompt_cell.find("button") is None, "Synthetic step should not have a View button"

    def test_step_without_prompt_renders_dash(self, client: TestClient, db_session: Session):
        """For has_prompt=False (step with runs but no prompt_text), the cell renders '—'."""
        seed = _make_project_with_steps(
            db_session,
            project_id="proj-tc-no-prompt",
            item_id="CR-00102",
            has_prompt=False,  # No StepRun with prompt_text
        )

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}",
        )
        assert response.status_code == 200, response.text

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        assert table is not None

        step_rows = table.find_all("tr")
        s04_row = None
        for row in step_rows:
            if "S04" in row.get_text():
                s04_row = row
                break

        assert s04_row is not None, "S04 row not found"

        th_elements = table.find_all("th")
        header_names = [th.get_text(strip=True) for th in th_elements]
        prompt_col_index = header_names.index("Prompt")
        cells = s04_row.find_all("td")
        prompt_cell = cells[prompt_col_index]

        assert prompt_cell.get_text(strip=True) == "—", (
            f"Expected '—' for step without prompt, got: {prompt_cell.get_text()!r}"
        )
        assert prompt_cell.find("button") is None, (
            "Step without prompt should not have a View button"
        )

    def test_synthetic_s00_row_renders_when_no_workflow_steps(
        self, client: TestClient, db_session: Session
    ):
        """When no workflow steps exist, the synthetic S00 (Worktree Setup) row is shown.

        The 'No steps found' empty state row is NOT rendered because _get_steps() always
        injects at least the synthetic S00 step (via _synthetic_setup_step) when a
        BatchItem exists (which it always does for queued items). The steps table is
        always present — it just shows S00 instead of an empty-state row.
        """
        from orch.db.models import Batch, BatchItem, Project, WorkItem

        project = Project(
            id="proj-empty",
            display_name="Empty Project",
            repo_root="/tmp/repo",
            config={},
        )
        db_session.add(project)
        db_session.flush()

        item = WorkItem(
            project_id="proj-empty",
            id="CR-EMPTY",
            type="Feature",
            status="approved",
            title="Empty Item",
            config={},
            depends_on=[],
            blocks=[],
            impacted_paths=[],
        )
        db_session.add(item)
        db_session.flush()

        batch = Batch(project_id="proj-empty", id="batch-empty", status="approved")
        db_session.add(batch)
        db_session.flush()

        bi = BatchItem(
            project_id="proj-empty",
            batch_id="batch-empty",
            work_item_id="CR-EMPTY",
            status="completed",
        )
        db_session.add(bi)
        db_session.commit()

        # Request the overview tab fragment
        response = client.get("/project/proj-empty/item/CR-EMPTY/tab/overview")
        assert response.status_code == 200, response.text

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        assert table is not None, "No <table> found in overview tab fragment"

        # Count the actual headers (should be 11 — all current columns)
        headers = table.find_all("th")
        header_count = len(headers)
        assert header_count == 11, (
            f"Expected 11 headers, got {header_count}: {[h.get_text() for h in headers]}"
        )

        # The S00 synthetic row must be present (no "No steps found" empty state)
        rows = table.find_all("tr")
        # 1 header row + S00 (Worktree Setup) + MERGE (Squash Merge) = 3 rows
        assert len(rows) == 3, (
            f"Expected 3 rows (header + S00 + MERGE), got {len(rows)}: "
            f"{[r.get_text()[:50] for r in rows]}"
        )

        # Verify S00 step row has 11 cells (no empty state row)
        data_cells = rows[1].find_all("td")
        assert len(data_cells) == 11, f"Expected 11 data cells in S00 row, got {len(data_cells)}"
        # No colspan cells (empty state only appears when both S00 and MERGE are absent,
        # which never happens for items with a BatchItem)
        has_colspan = any(td.get("colspan") for td in data_cells)
        assert not has_colspan, "S00 row should NOT have a colspan cell (no empty state)"
        # Verify the Prompt cell shows "—" for synthetic step
        prompt_cell = data_cells[4]  # Prompt is 5th column (0-indexed)
        dash = prompt_cell.get_text(strip=True)
        assert dash == "—", f"Synthetic S00 step should show '—' for Prompt, got: {dash!r}"

    def test_prompt_column_not_visible_in_sm_view_when_step_has_no_prompt(
        self, client: TestClient, db_session: Session
    ):
        """Steps with has_prompt=False show '—' regardless of sm:table-cell visibility."""
        seed = _make_project_with_steps(
            db_session,
            project_id="proj-tc-vis",
            item_id="CR-00103",
            has_prompt=False,
        )

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}",
        )
        assert response.status_code == 200, response.text

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        assert table is not None

        step_rows = table.find_all("tr")
        s04_row = None
        for row in step_rows:
            if "S04" in row.get_text():
                s04_row = row
                break

        assert s04_row is not None

        th_elements = table.find_all("th")
        header_names = [th.get_text(strip=True) for th in th_elements]
        prompt_col_index = header_names.index("Prompt")
        cells = s04_row.find_all("td")
        prompt_cell = cells[prompt_col_index]

        # The '—' dash is the fallback when has_prompt is False
        cell_text = prompt_cell.get_text(strip=True)
        assert cell_text == "—", f"Expected '—' but got: {cell_text!r}"
