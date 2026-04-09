"""Integration tests for SQLAlchemy models against a real PostgreSQL testcontainer.

Tests verify:
- All models can be inserted and queried back
- ENUM constraints reject invalid values
- Composite PKs enforce isolation across projects
- Cascade deletes propagate correctly
- FTS trigger updates tsvector when design_doc_content changes
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DataError, IntegrityError

from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    FixCycle,
    FixStatus,
    FixTrigger,
    IdSequence,
    MigrationLock,
    Project,
    RunStatus,
    StepRun,
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


# ---------------------------------------------------------------------------
# Helpers / factories
# ---------------------------------------------------------------------------


def make_project(project_id: str = "test-proj") -> Project:
    return Project(
        id=project_id,
        display_name="Test Project",
        repo_root="/repos/test",
    )


def make_work_item(
    project_id: str = "test-proj",
    item_id: str = "F-00001",
    title: str = "My Feature",
) -> WorkItem:
    return WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Feature,
        title=title,
    )


def make_workflow_step(
    project_id: str = "test-proj",
    work_item_id: str = "F-00001",
    step_number: int = 1,
) -> WorkflowStep:
    return WorkflowStep(
        project_id=project_id,
        work_item_id=work_item_id,
        step_number=step_number,
        step_id="S01",
        agent_label="Backend",
        step_type=StepType.implementation,
    )


# ---------------------------------------------------------------------------
# Test: all models can be created and queried back
# ---------------------------------------------------------------------------


def test_project_insert_and_query(db_session: Session) -> None:
    project = make_project()
    db_session.add(project)
    db_session.flush()

    result = db_session.get(Project, "test-proj")
    assert result is not None
    assert result.display_name == "Test Project"
    assert result.enabled is True
    assert result.config == {}


def test_id_sequence_insert_and_query(db_session: Session) -> None:
    project = make_project()
    db_session.add(project)
    db_session.flush()

    seq = IdSequence(project_id="test-proj", prefix="F", next_number=1)
    db_session.add(seq)
    db_session.flush()

    result = db_session.get(IdSequence, ("test-proj", "F"))
    assert result is not None
    assert result.next_number == 1


def test_work_item_insert_and_query(db_session: Session) -> None:
    db_session.add(make_project())
    db_session.flush()

    item = make_work_item()
    db_session.add(item)
    db_session.flush()

    result = db_session.get(WorkItem, ("test-proj", "F-00001"))
    assert result is not None
    assert result.type == WorkItemType.Feature
    assert result.status == WorkItemStatus.draft
    assert result.phase == WorkItemPhase.active
    assert result.depends_on == []
    assert result.blocks == []


def test_workflow_step_insert_and_query(db_session: Session) -> None:
    db_session.add(make_project())
    db_session.flush()
    db_session.add(make_work_item())
    db_session.flush()

    step = make_workflow_step()
    db_session.add(step)
    db_session.flush()

    result = (
        db_session.query(WorkflowStep)
        .filter_by(project_id="test-proj", work_item_id="F-00001", step_number=1)
        .one()
    )
    assert result.step_type == StepType.implementation
    assert result.status == StepStatus.pending


def test_step_run_insert_and_query(db_session: Session) -> None:
    db_session.add(make_project())
    db_session.flush()
    db_session.add(make_work_item())
    db_session.flush()
    step = make_workflow_step()
    db_session.add(step)
    db_session.flush()

    run = StepRun(step_id=step.id, run_number=1, status=RunStatus.pending)
    db_session.add(run)
    db_session.flush()

    result = db_session.query(StepRun).filter_by(step_id=step.id, run_number=1).one()
    assert result.status == RunStatus.pending
    assert result.pid is None
    assert result.pid_alive is False


def test_fix_cycle_insert_and_query(db_session: Session) -> None:
    db_session.add(make_project())
    db_session.flush()
    db_session.add(make_work_item())
    db_session.flush()
    step = make_workflow_step()
    db_session.add(step)
    db_session.flush()

    fc = FixCycle(
        step_id=step.id,
        cycle_number=1,
        trigger_type=FixTrigger.code_review,
    )
    db_session.add(fc)
    db_session.flush()

    result = db_session.query(FixCycle).filter_by(step_id=step.id).one()
    assert result.status == FixStatus.pending
    assert result.trigger_type == FixTrigger.code_review


def test_batch_insert_and_query(db_session: Session) -> None:
    db_session.add(make_project())
    db_session.flush()

    batch = Batch(project_id="test-proj", id="BATCH-00001")
    db_session.add(batch)
    db_session.flush()

    result = db_session.get(Batch, ("test-proj", "BATCH-00001"))
    assert result is not None
    assert result.status == BatchStatus.planning
    assert result.max_parallel == 4
    assert result.auto_publish is False


def test_batch_item_insert_and_query(db_session: Session) -> None:
    db_session.add(make_project())
    db_session.flush()
    db_session.add(make_work_item())
    db_session.flush()
    batch = Batch(project_id="test-proj", id="BATCH-00001")
    db_session.add(batch)
    db_session.flush()

    bi = BatchItem(
        project_id="test-proj",
        batch_id="BATCH-00001",
        work_item_id="F-00001",
    )
    db_session.add(bi)
    db_session.flush()

    result = (
        db_session.query(BatchItem)
        .filter_by(project_id="test-proj", batch_id="BATCH-00001", work_item_id="F-00001")
        .one()
    )
    assert result.status == BatchItemStatus.pending
    assert result.execution_group == 0
    assert result.worktree_info == {}


def test_migration_lock_insert_and_query(db_session: Session) -> None:
    db_session.add(make_project())
    db_session.flush()

    lock = MigrationLock(project_id="test-proj")
    db_session.add(lock)
    db_session.flush()

    result = db_session.get(MigrationLock, "test-proj")
    assert result is not None
    assert result.current_holder is None


def test_daemon_event_insert_and_query(db_session: Session) -> None:
    event = DaemonEvent(event_type="daemon_started", message="Daemon is up")
    db_session.add(event)
    db_session.flush()

    result = db_session.query(DaemonEvent).filter_by(event_type="daemon_started").one()
    assert result.message == "Daemon is up"
    assert result.project_id is None
    assert result.event_metadata == {}


# ---------------------------------------------------------------------------
# Test: ENUM constraints reject invalid values
# ---------------------------------------------------------------------------


def test_invalid_work_item_type_rejected(db_session: Session) -> None:
    """The DB must reject an invalid work_item_type value."""
    db_session.add(make_project())
    db_session.flush()

    with pytest.raises(DataError):
        db_session.execute(
            text(
                "INSERT INTO work_items (project_id, id, type, title, status, phase) "
                "VALUES ('test-proj', 'BAD001', 'InvalidType', 'Bad', 'draft', 'active')"
            )
        )


def test_invalid_work_item_status_rejected(db_session: Session) -> None:
    """The DB must reject an invalid work_item_status value."""
    db_session.add(make_project())
    db_session.flush()

    with pytest.raises(DataError):
        db_session.execute(
            text(
                "INSERT INTO work_items (project_id, id, type, title, status, phase) "
                "VALUES ('test-proj', 'BAD001', 'Feature', 'Bad', 'not_a_status', 'active')"
            )
        )


# ---------------------------------------------------------------------------
# Test: composite PKs enforce isolation across projects
# ---------------------------------------------------------------------------


def test_same_item_id_in_different_projects(db_session: Session) -> None:
    """The same work item ID must be allowed in different projects."""
    for proj_id in ("proj-a", "proj-b"):
        db_session.add(Project(id=proj_id, display_name=proj_id, repo_root=f"/repos/{proj_id}"))
    db_session.flush()

    for proj_id in ("proj-a", "proj-b"):
        db_session.add(
            WorkItem(
                project_id=proj_id,
                id="F-00001",  # same ID in both projects — must be allowed
                type=WorkItemType.Feature,
                title="Shared ID Feature",
            )
        )
    db_session.flush()

    item_a = db_session.get(WorkItem, ("proj-a", "F-00001"))
    item_b = db_session.get(WorkItem, ("proj-b", "F-00001"))
    assert item_a is not None
    assert item_b is not None
    assert item_a is not item_b


def test_duplicate_item_id_in_same_project_rejected(db_session: Session) -> None:
    """Duplicate (project_id, id) must be rejected by the composite PK."""
    db_session.add(make_project())
    db_session.flush()
    db_session.add(make_work_item(item_id="F-00001"))
    db_session.flush()

    db_session.add(make_work_item(item_id="F-00001"))
    with pytest.raises((IntegrityError, Exception)):  # noqa: B017
        db_session.flush()


# ---------------------------------------------------------------------------
# Test: cascade deletes
# ---------------------------------------------------------------------------


def test_delete_project_cascades_to_work_items(db_session: Session) -> None:
    """Deleting a project must delete all its work items (ON DELETE CASCADE)."""
    db_session.add(make_project())
    db_session.flush()
    db_session.add(make_work_item(item_id="F-00001"))
    db_session.add(make_work_item(item_id="F-00002"))
    db_session.flush()

    project = db_session.get(Project, "test-proj")
    assert project is not None
    db_session.delete(project)
    db_session.flush()

    items = db_session.query(WorkItem).filter_by(project_id="test-proj").all()
    assert items == []


def test_delete_project_cascades_to_id_sequences(db_session: Session) -> None:
    """Deleting a project must delete its id_sequences."""
    db_session.add(make_project())
    db_session.flush()
    db_session.add(IdSequence(project_id="test-proj", prefix="F"))
    db_session.flush()

    project = db_session.get(Project, "test-proj")
    assert project is not None
    db_session.delete(project)
    db_session.flush()

    seqs = db_session.query(IdSequence).filter_by(project_id="test-proj").all()
    assert seqs == []


def test_delete_project_cascades_to_batches(db_session: Session) -> None:
    """Deleting a project must delete its batches."""
    db_session.add(make_project())
    db_session.flush()
    db_session.add(Batch(project_id="test-proj", id="BATCH-00001"))
    db_session.flush()

    project = db_session.get(Project, "test-proj")
    assert project is not None
    db_session.delete(project)
    db_session.flush()

    batches = db_session.query(Batch).filter_by(project_id="test-proj").all()
    assert batches == []


def test_delete_work_item_cascades_to_workflow_steps(db_session: Session) -> None:
    """Deleting a work item must delete its workflow steps."""
    db_session.add(make_project())
    db_session.flush()
    db_session.add(make_work_item())
    db_session.flush()
    db_session.add(make_workflow_step())
    db_session.flush()

    item = db_session.get(WorkItem, ("test-proj", "F-00001"))
    assert item is not None
    db_session.delete(item)
    db_session.flush()

    steps = (
        db_session.query(WorkflowStep).filter_by(project_id="test-proj", work_item_id="F-00001").all()
    )
    assert steps == []


def test_delete_workflow_step_cascades_to_step_runs(db_session: Session) -> None:
    """Deleting a workflow step must delete its step runs."""
    db_session.add(make_project())
    db_session.flush()
    db_session.add(make_work_item())
    db_session.flush()
    step = make_workflow_step()
    db_session.add(step)
    db_session.flush()
    step_id = step.id

    run = StepRun(step_id=step_id, run_number=1)
    db_session.add(run)
    db_session.flush()

    db_session.delete(step)
    db_session.flush()

    runs = db_session.query(StepRun).filter_by(step_id=step_id).all()
    assert runs == []


# ---------------------------------------------------------------------------
# Test: FTS trigger updates tsvector
# ---------------------------------------------------------------------------


def test_fts_trigger_sets_tsvector_on_insert(db_session: Session) -> None:
    """Inserting a work item must auto-populate design_doc_search via the trigger."""
    db_session.add(make_project())
    db_session.flush()

    item = WorkItem(
        project_id="test-proj",
        id="F-00001",
        type=WorkItemType.Feature,
        title="Authentication System",
        design_doc_content="Implement login with session management",
    )
    db_session.add(item)
    db_session.flush()
    db_session.refresh(item)

    # The trigger should have set design_doc_search to a non-null tsvector
    assert item.design_doc_search is not None
    assert item.design_doc_search != ""


def test_fts_trigger_updates_tsvector_when_content_changes(db_session: Session) -> None:
    """Updating design_doc_content must refresh design_doc_search via the trigger."""
    db_session.add(make_project())
    db_session.flush()

    item = WorkItem(
        project_id="test-proj",
        id="F-00001",
        type=WorkItemType.Feature,
        title="Auth",
    )
    db_session.add(item)
    db_session.flush()
    db_session.refresh(item)
    old_search = item.design_doc_search

    # Update with content that should produce a richer tsvector
    item.design_doc_content = "bearer tokens refresh rotation session"
    db_session.flush()
    db_session.refresh(item)

    assert item.design_doc_search != old_search
    assert item.design_doc_search is not None


def test_fts_trigger_title_only_when_no_content(db_session: Session) -> None:
    """Without design_doc_content, tsvector should still be set from title."""
    db_session.add(make_project())
    db_session.flush()

    item = WorkItem(
        project_id="test-proj",
        id="F-00001",
        type=WorkItemType.Feature,
        title="Unique Title Keywords",
    )
    db_session.add(item)
    db_session.flush()
    db_session.refresh(item)

    # Trigger fires on INSERT even without content
    assert item.design_doc_search is not None


def test_fts_full_text_search_query(db_session: Session) -> None:
    """FTS search using plainto_tsquery must find items by content keywords."""
    db_session.add(make_project())
    db_session.flush()

    # Use clear English words that the 'english' stemmer handles well
    for item_id, title, content in [
        ("F-00001", "Authentication", "user login session management"),
        ("F-00002", "Database", "schema migration database upgrade"),
        ("F-00003", "Frontend", "visual interface components"),
    ]:
        db_session.add(
            WorkItem(
                project_id="test-proj",
                id=item_id,
                type=WorkItemType.Feature,
                title=title,
                design_doc_content=content,
            )
        )
    db_session.flush()

    # Search for "session" — should find only F-00001
    results = (
        db_session.query(WorkItem)
        .filter(WorkItem.design_doc_search.op("@@")(text("plainto_tsquery('english', 'session')")))
        .all()
    )
    assert len(results) == 1
    assert results[0].id == "F-00001"

    # Search for "migration" — should find only F-00002
    results = (
        db_session.query(WorkItem)
        .filter(
            WorkItem.design_doc_search.op("@@")(text("plainto_tsquery('english', 'migration')"))
        )
        .all()
    )
    assert len(results) == 1
    assert results[0].id == "F-00002"
