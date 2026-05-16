"""I-00086 S05: runtime override response/feedback regression tests."""

from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from dashboard.app import create_app
from dashboard.dependencies import get_db
from orch.db.models import (
    AgentRuntimeOption,
    DaemonEvent,
    Project,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def client(db_session: Session) -> TestClient:
    """Create a dashboard TestClient backed by the testcontainer db_session."""
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


@pytest.fixture
def seed_runtime_options(db_session: Session) -> list[AgentRuntimeOption]:
    """Upsert enabled runtime options used by runtime override selectors."""
    rows = [
        AgentRuntimeOption(
            id=1,
            cli_tool="opencode",
            model="minimax",
            cli_label="OpenCode",
            model_label="MiniMax 2.7",
            display_name="OpenCode + MiniMax 2.7",
            is_default=True,
            enabled=True,
            sort_order=10,
        ),
        AgentRuntimeOption(
            id=2,
            cli_tool="opencode",
            model="claude-sonnet-4-6",
            cli_label="OpenCode",
            model_label="Claude Sonnet 4.6",
            display_name="OpenCode + Claude Sonnet 4.6",
            is_default=False,
            enabled=True,
            sort_order=20,
        ),
        AgentRuntimeOption(
            id=3,
            cli_tool="opencode",
            model="claude-opus-4-7",
            cli_label="OpenCode",
            model_label="Claude Opus 4.7",
            display_name="OpenCode + Claude Opus 4.7",
            is_default=False,
            enabled=True,
            sort_order=30,
        ),
    ]
    merged = [db_session.merge(r) for r in rows]
    db_session.flush()
    return merged


def _seed_item_with_steps(
    db_session: Session,
    project: Project,
    item_id: str,
    statuses: list[StepStatus],
    option_by_step: dict[str, int | None] | None = None,
) -> WorkItem:
    item = WorkItem(
        id=item_id,
        project_id=project.id,
        type=WorkItemType.Feature,
        title=f"Runtime override test {item_id}",
        status=WorkItemStatus.in_progress,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
    )
    db_session.add(item)
    db_session.flush()

    for idx, step_status in enumerate(statuses, start=1):
        step_id = f"S{idx:02d}"
        db_session.add(
            WorkflowStep(
                project_id=project.id,
                work_item_id=item.id,
                step_number=idx,
                step_id=step_id,
                agent_label="tests-impl",
                step_type=StepType.implementation,
                status=step_status,
                agent_runtime_option_id=(option_by_step or {}).get(step_id),
            )
        )

    db_session.commit()
    return item


def _steps_by_id(db_session: Session, project_id: str, item_id: str) -> dict[str, WorkflowStep]:
    steps = list(
        db_session.scalars(
            select(WorkflowStep)
            .where(WorkflowStep.project_id == project_id, WorkflowStep.work_item_id == item_id)
            .order_by(WorkflowStep.step_number)
        ).all()
    )
    return {step.step_id: step for step in steps}


def _row_has_model_label(html: str, step_id: str, model_label: str) -> bool:
    row_pattern = (
        rf"<tr[^>]*>.*?<td[^>]*>\s*{re.escape(step_id)}.*?</td>"
        rf".*?<span class=\"text-xs text-muted-foreground\">{re.escape(model_label)}</span>"
    )
    return re.search(row_pattern, html, flags=re.DOTALL) is not None


def test_i00086_bulk_apply_returns_fragment_and_toast_trigger(
    client: TestClient,
    db_session: Session,
    test_project: Project,
    seed_runtime_options: list[AgentRuntimeOption],
) -> None:
    item = _seed_item_with_steps(
        db_session,
        test_project,
        "I00086-BULK-REPRO",
        statuses=[StepStatus.pending, StepStatus.pending, StepStatus.in_progress],
    )
    editable_step_count = 2

    resp = client.patch(
        f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
        data={"option_id": "2"},
    )

    assert resp.status_code == 200
    assert 'id="item-steps-table"' in resp.text
    parsed = json.loads(resp.headers["HX-Trigger"])
    assert parsed["showToast"]["type"] == "success"
    assert parsed["showToast"]["message"] == f"Model updated for {editable_step_count} step(s)"


def test_per_step_override_returns_fragment_and_toast_trigger(
    client: TestClient,
    db_session: Session,
    test_project: Project,
    seed_runtime_options: list[AgentRuntimeOption],
) -> None:
    item = _seed_item_with_steps(
        db_session,
        test_project,
        "I00086-PER-STEP-SET",
        statuses=[StepStatus.pending, StepStatus.completed],
    )

    resp = client.patch(
        f"/project/{test_project.id}/api/item/{item.id}/step/S01/runtime-override",
        data={"option_id": "2"},
    )

    assert resp.status_code == 200
    assert 'id="item-steps-table"' in resp.text
    assert json.loads(resp.headers["HX-Trigger"]) == {
        "showToast": {"message": "Model updated", "type": "success"}
    }
    assert _row_has_model_label(resp.text, "S01", "Claude Sonnet 4.6")


def test_per_step_clear_override_returns_fragment_and_toast_trigger(
    client: TestClient,
    db_session: Session,
    test_project: Project,
    seed_runtime_options: list[AgentRuntimeOption],
) -> None:
    item = _seed_item_with_steps(
        db_session,
        test_project,
        "I00086-PER-STEP-CLEAR",
        statuses=[StepStatus.failed],
        option_by_step={"S01": 2},
    )

    resp = client.patch(
        f"/project/{test_project.id}/api/item/{item.id}/step/S01/runtime-override",
        data={"option_id": ""},
    )

    assert resp.status_code == 200
    assert 'id="item-steps-table"' in resp.text
    assert json.loads(resp.headers["HX-Trigger"]) == {
        "showToast": {"message": "Model updated", "type": "success"}
    }

    db_session.expire_all()
    saved_step = _steps_by_id(db_session, test_project.id, item.id)["S01"]
    assert saved_step.agent_runtime_option_id is None


def test_bulk_apply_with_zero_editable_steps_returns_info_toast(
    client: TestClient,
    db_session: Session,
    test_project: Project,
    seed_runtime_options: list[AgentRuntimeOption],
) -> None:
    item = _seed_item_with_steps(
        db_session,
        test_project,
        "I00086-BULK-ZERO",
        statuses=[StepStatus.in_progress, StepStatus.completed],
        option_by_step={"S01": 1, "S02": 1},
    )

    before_steps = {
        k: v.agent_runtime_option_id
        for k, v in _steps_by_id(db_session, test_project.id, item.id).items()
    }
    before_events = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.project_id == test_project.id,
            DaemonEvent.entity_id == item.id,
            DaemonEvent.event_type == "runtime_override_changed",
        )
        .count()
    )

    resp = client.patch(
        f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
        data={"option_id": "2"},
    )

    assert resp.status_code == 200
    assert 'id="item-steps-table"' in resp.text
    assert json.loads(resp.headers["HX-Trigger"]) == {
        "showToast": {"message": "No editable steps to update", "type": "info"}
    }

    db_session.expire_all()
    after_steps = {
        k: v.agent_runtime_option_id
        for k, v in _steps_by_id(db_session, test_project.id, item.id).items()
    }
    assert after_steps == before_steps

    after_events = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.project_id == test_project.id,
            DaemonEvent.entity_id == item.id,
            DaemonEvent.event_type == "runtime_override_changed",
        )
        .count()
    )
    assert after_events == before_events


def test_per_step_unknown_item_returns_404(
    client: TestClient,
    test_project: Project,
    seed_runtime_options: list[AgentRuntimeOption],
) -> None:
    resp = client.patch(
        f"/project/{test_project.id}/api/item/UNKNOWN-I00086/step/S01/runtime-override",
        data={"option_id": "2"},
    )
    assert resp.status_code == 404
    assert "HX-Trigger" not in resp.headers


def test_bulk_unknown_option_returns_404(
    client: TestClient,
    db_session: Session,
    test_project: Project,
    seed_runtime_options: list[AgentRuntimeOption],
) -> None:
    item = _seed_item_with_steps(
        db_session,
        test_project,
        "I00086-BULK-BAD-OPTION",
        statuses=[StepStatus.pending, StepStatus.failed],
    )

    resp = client.patch(
        f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
        data={"option_id": "999"},
    )

    assert resp.status_code == 404
    assert "HX-Trigger" not in resp.headers


def test_bulk_apply_counts_only_editable_steps(
    client: TestClient,
    db_session: Session,
    test_project: Project,
    seed_runtime_options: list[AgentRuntimeOption],
) -> None:
    item = _seed_item_with_steps(
        db_session,
        test_project,
        "I00086-BULK-COUNT",
        statuses=[
            StepStatus.pending,
            StepStatus.pending,
            StepStatus.pending,
            StepStatus.in_progress,
            StepStatus.completed,
        ],
        option_by_step={"S01": 1, "S02": 1, "S03": 1, "S04": 1, "S05": 1},
    )

    resp = client.patch(
        f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
        data={"option_id": "3"},
    )

    assert resp.status_code == 200
    assert json.loads(resp.headers["HX-Trigger"]) == {
        "showToast": {"message": "Model updated for 3 step(s)", "type": "success"}
    }

    db_session.expire_all()
    steps = _steps_by_id(db_session, test_project.id, item.id)
    assert steps["S01"].agent_runtime_option_id == 3
    assert steps["S02"].agent_runtime_option_id == 3
    assert steps["S03"].agent_runtime_option_id == 3
    assert steps["S04"].agent_runtime_option_id == 1
    assert steps["S05"].agent_runtime_option_id == 1


def test_response_fragment_reflects_updated_options_per_row(
    client: TestClient,
    db_session: Session,
    test_project: Project,
    seed_runtime_options: list[AgentRuntimeOption],
) -> None:
    item = _seed_item_with_steps(
        db_session,
        test_project,
        "I00086-BULK-FRAGMENT",
        statuses=[StepStatus.pending, StepStatus.pending],
        option_by_step={"S01": 2, "S02": 2},
    )

    resp = client.patch(
        f"/project/{test_project.id}/api/item/{item.id}/runtime-override/bulk",
        data={"option_id": "3"},
    )

    assert resp.status_code == 200
    assert _row_has_model_label(resp.text, "S01", "Claude Opus 4.7")
    assert _row_has_model_label(resp.text, "S02", "Claude Opus 4.7")
    assert not _row_has_model_label(resp.text, "S01", "Claude Sonnet 4.6")
    assert not _row_has_model_label(resp.text, "S02", "Claude Sonnet 4.6")
