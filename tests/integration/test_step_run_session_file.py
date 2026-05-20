"""CR-00065 S01: Integration tests for step_runs.session_file column.

Verifies the column can be set and retrieved via the ORM, and that it
correctly defaults to NULL for a StepRun created without it.

Uses the standard testcontainer fixture (db_session) which runs all
alembic migrations from head — this is a green-path test that validates
the migration was correctly applied.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from orch.db.models import (
    Project,
    RunStatus,
    StepRun,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _seed_work_item(session: Session) -> WorkflowStep:
    """Create a minimal project + work_item + step so we can insert StepRun rows."""
    project = Project(id="test-cr00065", display_name="CR-00065 Test", repo_root="/repos/test")
    session.add(project)
    session.flush()
    # WorkItem uses composite PK (project_id, id) — pass id= not work_item_id=
    work_item = WorkItem(
        project_id=project.id,
        id="CR-00065",
        title="Test Work Item",
        type=WorkItemType.Feature,
        status=WorkItemStatus.approved,
        phase="active",
        design_doc_content="",
        impacted_paths=[],
    )
    session.add(work_item)
    session.flush()
    # WorkflowStep.work_item_id is a plain column referencing WorkItem.id
    step = WorkflowStep(
        project_id=project.id,
        work_item_id=work_item.id,
        step_number=1,
        step_id="S01",
        agent_label="test-agent",
        step_type=StepType.implementation,
    )
    session.add(step)
    session.flush()
    return step


def test_session_file_column_readable_writable(db_session: Session) -> None:
    """session_file column can be set and retrieved via the ORM."""
    step = _seed_work_item(db_session)
    session_path = "/home/agents/sessions/session-abc123.jsonl"

    run = StepRun(step_id=step.id, run_number=1, status=RunStatus.pending)
    run.session_file = session_path
    db_session.add(run)
    db_session.flush()

    result = db_session.query(StepRun).filter_by(id=run.id).one()
    assert result.session_file == session_path


def test_session_file_column_nullable(db_session: Session) -> None:
    """session_file defaults to NULL for a StepRun created without it."""
    step = _seed_work_item(db_session)

    run = StepRun(step_id=step.id, run_number=1, status=RunStatus.pending)
    db_session.add(run)
    db_session.flush()

    result = db_session.query(StepRun).filter_by(id=run.id).one()
    assert result.session_file is None
