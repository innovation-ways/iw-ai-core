"""I-00105 S05: Dashboard context gauge tests — effective-budget percentage.

Verifies:
- Per-step gauge with MiniMax-M2.7-like runtime (window=204800, max_output=131072)
  at ~131K input → effective_pct ≥ 100%
- Per-step gauge with runtime that has NULL max_output_tokens → raw-window %
- Bar width clamps to 100% even when effective_pct > 100
- Label allows ≥100% values (not clamped to 100 in display)
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
    """Provide a TestClient with get_db overridden to the test db_session."""
    original = os.environ.pop("IW_CORE_EXPECTED_INSTANCE_ID", None)
    try:

        def override_get_db() -> Session:
            """Yield the test db_session for FastAPI dependency injection."""
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
# MiniMax-M2.7-like effective-budget scenario
# ---------------------------------------------------------------------------


def _find_minimax_runtime(db_session) -> int | None:
    """Return the id of the seeded MiniMax-M2.7 runtime option (if present).

    The testcontainer DB runs the production migration which backfills
    ``pi/minimax/MiniMax-M2.7`` with ``max_output_tokens=131072``.
    """
    from sqlalchemy import select

    from orch.db.models import AgentRuntimeOption

    return db_session.execute(
        select(AgentRuntimeOption.id).where(
            AgentRuntimeOption.cli_tool == "pi",
            AgentRuntimeOption.model == "minimax/MiniMax-M2.7",
            AgentRuntimeOption.enabled.is_(True),
        )
    ).scalar_one_or_none()


def _make_project_with_step_runtime(
    db_session: Session,
    project_id: str,
    item_id: str,
    runtime_opt_id: int | None,
    context_tokens_peak: int,
    context_tokens_last: int,
) -> dict:
    """Create project + item + workflow step with context token data."""
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
        agent_runtime_option_id=runtime_opt_id,
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
    )
    db_session.add(step)
    db_session.flush()

    run = StepRun(
        step_id=step.id,
        run_number=1,
        status=RunStatus.completed,
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),
        context_tokens_peak=context_tokens_peak,
        context_tokens_last=context_tokens_last,
        agent_runtime_option_id=runtime_opt_id,
    )
    db_session.add(run)
    db_session.commit()

    return {
        "project": project,
        "item": item,
        "batch": batch,
        "batch_item": bi,
        "step": step,
        "run": run,
    }


class TestEffectiveContextGauge:
    """I-00105 S05: per-step gauge reads effective-budget percentage."""

    def test_minimax_at_ceiling_reads_over_100_pct(
        self, client: TestClient, db_session: Session
    ) -> None:
        """MiniMax-M2.7 at 131K input → effective_pct ≥ 100% (not ~64%)."""
        minimax_opt_id = _find_minimax_runtime(db_session)
        assert minimax_opt_id is not None, (
            "MiniMax-M2.7 runtime option not found in DB — "
            "ensure the testcontainer DB runs migration 2be8dc12874f"
        )

        seed = _make_project_with_step_runtime(
            db_session,
            project_id="proj-minimax",
            item_id="I-00105-GAUGE",
            runtime_opt_id=minimax_opt_id,
            context_tokens_peak=131072,  # at ceiling of effective budget
            context_tokens_last=130000,
        )

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}",
        )
        assert response.status_code == 200, response.text

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        assert table is not None

        # Find the S04 row
        step_rows = table.find_all("tr")
        s04_row = None
        for row in step_rows:
            if "S04" in row.get_text():
                s04_row = row
                break
        assert s04_row is not None, "S04 row not found"

        # Locate the Context cell (last column before Started)
        th_elements = table.find_all("th")
        header_names = [th.get_text(strip=True) for th in th_elements]
        ctx_col_index = header_names.index("Context")

        cells = s04_row.find_all("td")
        ctx_cell = cells[ctx_col_index]

        # Extract the label text (the percentage shown)
        label_div = ctx_cell.find_all("div")[-1]  # last div is the label
        label_text = label_div.get_text(strip=True)
        # Label format: "244%" or "131%" etc.
        assert label_text.endswith("%"), f"Expected percentage label, got: {label_text!r}"

        pct_value = int(label_text.rstrip("%"))
        assert pct_value >= 100, (
            f"Expected effective pct ≥ 100% for near-ceiling step, got {pct_value}%. "
            f"MiniMax-M2.7 at 131K input: effective budget = 204800 - 131072 - 20000 = 53728 → "
            f"131072/53728*100 ≈ 244%. "
            f"Old raw-window calculation gave 131072/204800*100 ≈ 64%."
        )

    def test_minimax_bar_width_clamps_to_100(self, client: TestClient, db_session: Session) -> None:
        """Bar width is clamped to 100% even when effective_pct > 100 (no overflow)."""
        minimax_opt_id = _find_minimax_runtime(db_session)
        assert minimax_opt_id is not None

        seed = _make_project_with_step_runtime(
            db_session,
            project_id="proj-bar",
            item_id="I-00105-BAR",
            runtime_opt_id=minimax_opt_id,
            context_tokens_peak=131072,
            context_tokens_last=130000,
        )

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}",
        )
        assert response.status_code == 200, response.text

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        step_rows = table.find_all("tr")
        s04_row = None
        for row in step_rows:
            if "S04" in row.get_text():
                s04_row = row
                break
        assert s04_row is not None

        th_elements = table.find_all("th")
        header_names = [th.get_text(strip=True) for th in th_elements]
        ctx_col_index = header_names.index("Context")
        cells = s04_row.find_all("td")
        ctx_cell = cells[ctx_col_index]

        # Find the bar fill element
        bar_fill = ctx_cell.find("div", class_="ctx-bar-fill")
        assert bar_fill is not None, f"No ctx-bar-fill found in cell: {ctx_cell}"

        width_style = bar_fill.get("style", "")
        # Extract width value: style="width: 100%"
        import re

        match = re.search(r"width:\s*(\d+)%", width_style)
        assert match is not None, f"Could not parse width from style={width_style!r}"
        bar_width_pct = int(match.group(1))
        assert bar_width_pct == 100, (
            f"Bar width must clamp to 100% (no overflow), got {bar_width_pct}%"
        )

    def test_null_max_output_falls_back_to_raw_window(
        self, client: TestClient, db_session: Session
    ) -> None:
        """Runtime with NULL max_output_tokens → raw-window percentage (not clamped)."""
        from orch.db.models import AgentRuntimeOption

        # Create a runtime with no max_output_tokens (NULL)
        opt = AgentRuntimeOption(
            id=999902,
            cli_tool="pi",
            model="unknown/model",
            cli_label="Unknown Model",
            model_label="Unknown Model",
            display_name="Unknown Model",
            context_window_tokens=100000,
            max_output_tokens=None,  # NULL — no output reservation
            enabled=True,
            is_default=False,
            sort_order=2,
        )
        db_session.add(opt)
        db_session.flush()

        seed = _make_project_with_step_runtime(
            db_session,
            project_id="proj-null-out",
            item_id="I-00105-NULL-OUT",
            runtime_opt_id=opt.id,
            context_tokens_peak=50_000,  # 50K of 100K window = 50%
            context_tokens_last=49_000,
        )

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}",
        )
        assert response.status_code == 200, response.text

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        step_rows = table.find_all("tr")
        s04_row = None
        for row in step_rows:
            if "S04" in row.get_text():
                s04_row = row
                break
        assert s04_row is not None

        th_elements = table.find_all("th")
        header_names = [th.get_text(strip=True) for th in th_elements]
        ctx_col_index = header_names.index("Context")
        cells = s04_row.find_all("td")
        ctx_cell = cells[ctx_col_index]

        label_div = ctx_cell.find_all("div")[-1]
        label_text = label_div.get_text(strip=True)
        assert label_text.endswith("%")
        pct_value = int(label_text.rstrip("%"))

        # 50K used / 100K window = 50%; NULL max_output → raw-window fallback
        assert pct_value == 50, (
            f"Expected 50% (raw-window fallback for NULL max_output), got {pct_value}%"
        )

    def test_green_threshold_for_low_usage(self, client: TestClient, db_session: Session) -> None:
        """30K/100K window with NULL max_output → ≤60% → green bar."""
        from orch.db.models import AgentRuntimeOption

        opt = AgentRuntimeOption(
            id=999903,
            cli_tool="pi",
            model="lowusage/model",
            cli_label="Low Usage",
            model_label="Low Usage",
            display_name="Low Usage Model",
            context_window_tokens=100000,
            max_output_tokens=None,
            enabled=True,
            is_default=False,
            sort_order=3,
        )
        db_session.add(opt)
        db_session.flush()

        seed = _make_project_with_step_runtime(
            db_session,
            project_id="proj-low",
            item_id="I-00105-LOW",
            runtime_opt_id=opt.id,
            context_tokens_peak=30_000,  # 30% → green (≤60%)
            context_tokens_last=30_000,
        )

        response = client.get(
            f"/project/{seed['project'].id}/item/{seed['item'].id}",
        )
        assert response.status_code == 200, response.text

        soup = BeautifulSoup(response.text, "html.parser")
        table = soup.find("table")
        step_rows = table.find_all("tr")
        s04_row = None
        for row in step_rows:
            if "S04" in row.get_text():
                s04_row = row
                break
        assert s04_row is not None

        th_elements = table.find_all("th")
        ctx_col_index = [th.get_text(strip=True) for th in th_elements].index("Context")
        cells = s04_row.find_all("td")
        ctx_cell = cells[ctx_col_index]

        bar_fill = ctx_cell.find("div", class_="ctx-bar-fill")
        assert bar_fill is not None
        assert "ctx-bar-green" in bar_fill.get("class", []), (
            "30% usage should have green bar (≤60% threshold)"
        )
