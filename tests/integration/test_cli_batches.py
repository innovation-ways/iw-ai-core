"""Integration tests for batch management CLI commands against a real PostgreSQL testcontainer."""

import json
from typing import Any

from click.testing import CliRunner

from orch.cli.main import cli
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    DaemonEvent,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def invoke(
    runner: CliRunner,
    args: list[str],
    get_session: Any,
    project_id: str = "test-proj",
) -> Any:
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


def make_item(
    db_session: Any,
    item_id: str,
    status: WorkItemStatus = WorkItemStatus.approved,
    depends_on: list[str] | None = None,
) -> WorkItem:
    item = WorkItem(
        project_id="test-proj",
        id=item_id,
        type=WorkItemType.Issue,
        title=f"Test item {item_id}",
        status=status,
        phase=WorkItemPhase.active,
        config={},
        depends_on=depends_on or [],
        blocks=[],
    )
    db_session.add(item)
    db_session.flush()
    return item


def make_batch(
    db_session: Any,
    batch_id: str,
    status: BatchStatus = BatchStatus.executing,
) -> Batch:
    batch = Batch(
        project_id="test-proj",
        id=batch_id,
        status=status,
        cli_tool="opencode",
    )
    db_session.add(batch)
    db_session.flush()
    return batch


# ---------------------------------------------------------------------------
# batch-create
# ---------------------------------------------------------------------------


def test_batch_create_independent_items_all_group_0(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session, "I-00001")
    make_item(db_session, "I-00002")
    make_item(db_session, "I-00003")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", "test-proj", "--json", "batch-create", "I-00001", "I-00002", "I-00003"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)

    assert data["status"] == "planning"
    assert len(data["groups"]) == 1
    assert data["groups"][0]["group"] == 0
    assert sorted(data["groups"][0]["items"]) == ["I-00001", "I-00002", "I-00003"]


def test_batch_create_with_dependencies_correct_groups(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    # I-00002 depends on I-00001 → I-00001 in group 0, I-00002 in group 1
    make_item(db_session, "I-00001")
    make_item(db_session, "I-00002", depends_on=["I-00001"])

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", "test-proj", "--json", "batch-create", "I-00001", "I-00002"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)

    groups_by_number = {g["group"]: g["items"] for g in data["groups"]}
    assert groups_by_number[0] == ["I-00001"]
    assert groups_by_number[1] == ["I-00002"]


def test_batch_create_rejects_non_approved_item(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session, "I-00001", status=WorkItemStatus.draft)

    runner = CliRunner()
    result = invoke(runner, ["batch-create", "I-00001"], cli_get_session)
    assert result.exit_code == 1


def test_batch_create_rejects_item_in_active_batch(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session, "I-00001")
    make_batch(db_session, "BATCH-00001", status=BatchStatus.executing)
    db_session.add(
        BatchItem(
            project_id="test-proj",
            batch_id="BATCH-00001",
            work_item_id="I-00001",
            status=BatchItemStatus.executing,
        )
    )
    db_session.flush()

    runner = CliRunner()
    result = invoke(runner, ["batch-create", "I-00001"], cli_get_session)
    assert result.exit_code == 4


def test_batch_create_item_in_completed_batch_is_ok(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session, "I-00001")
    # Manually create a completed batch — use a higher ID to avoid conflicting with
    # the auto-allocated sequence (which starts at BATCH-00001).
    make_batch(db_session, "BATCH-00099", status=BatchStatus.completed)
    db_session.add(
        BatchItem(
            project_id="test-proj",
            batch_id="BATCH-00099",
            work_item_id="I-00001",
            status=BatchItemStatus.merged,
        )
    )
    db_session.flush()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", "test-proj", "--json", "batch-create", "I-00001"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["status"] == "planning"


def test_batch_create_persists_to_db(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session, "I-00001")
    make_item(db_session, "I-00002")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", "test-proj", "--json", "batch-create", "I-00001", "I-00002"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    batch_id = data["batch_id"]

    batch = db_session.get(Batch, ("test-proj", batch_id))
    assert batch is not None
    assert batch.status == BatchStatus.planning

    items = (
        db_session.query(BatchItem)
        .filter(
            BatchItem.project_id == "test-proj",
            BatchItem.batch_id == batch_id,
        )
        .all()
    )
    assert len(items) == 2
    work_item_ids = {bi.work_item_id for bi in items}
    assert work_item_ids == {"I-00001", "I-00002"}


def test_batch_create_human_output(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session, "I-00001")
    make_item(db_session, "I-00002")

    runner = CliRunner()
    result = invoke(runner, ["batch-create", "I-00001", "I-00002"], cli_get_session)
    assert result.exit_code == 0
    assert "Group 0" in result.output
    assert "planning" in result.output


# ---------------------------------------------------------------------------
# batch-approve
# ---------------------------------------------------------------------------


def test_batch_approve_planning_to_approved(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    batch = make_batch(db_session, "BATCH-00001", status=BatchStatus.planning)

    runner = CliRunner()
    result = invoke(runner, ["batch-approve", "BATCH-00001"], cli_get_session)
    assert result.exit_code == 0, result.output

    db_session.refresh(batch)
    assert batch.status == BatchStatus.approved


def test_batch_approve_emits_daemon_event(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_batch(db_session, "BATCH-00001", status=BatchStatus.planning)

    runner = CliRunner()
    result = invoke(runner, ["batch-approve", "BATCH-00001"], cli_get_session)
    assert result.exit_code == 0

    event = (
        db_session.query(DaemonEvent)
        .filter(
            DaemonEvent.project_id == "test-proj",
            DaemonEvent.event_type == "batch_approved",
            DaemonEvent.entity_id == "BATCH-00001",
        )
        .first()
    )
    assert event is not None


def test_batch_approve_json_output(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_batch(db_session, "BATCH-00001", status=BatchStatus.planning)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", "test-proj", "--json", "batch-approve", "BATCH-00001"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "approved"


def test_batch_approve_rejects_non_planning(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_batch(db_session, "BATCH-00001", status=BatchStatus.executing)

    runner = CliRunner()
    result = invoke(runner, ["batch-approve", "BATCH-00001"], cli_get_session)
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# batch-status
# ---------------------------------------------------------------------------


def test_batch_status_json_output(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session, "I-00001")
    make_batch(db_session, "BATCH-00001", status=BatchStatus.planning)
    db_session.add(
        BatchItem(
            project_id="test-proj",
            batch_id="BATCH-00001",
            work_item_id="I-00001",
            execution_group=0,
            status=BatchItemStatus.pending,
        )
    )
    db_session.flush()

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", "test-proj", "--json", "batch-status", "BATCH-00001"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["batch_id"] == "BATCH-00001"
    assert data["status"] == "planning"
    assert len(data["items"]) == 1
    assert data["items"][0]["work_item_id"] == "I-00001"
    assert data["items"][0]["execution_group"] == 0


def test_batch_status_not_found_exits_1(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()
    result = invoke(runner, ["batch-status", "BATCH-00999"], cli_get_session)
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# batch-pause and batch-resume
# ---------------------------------------------------------------------------


def test_batch_pause_executing_to_paused(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    batch = make_batch(db_session, "BATCH-00001", status=BatchStatus.executing)

    runner = CliRunner()
    result = invoke(runner, ["batch-pause", "BATCH-00001"], cli_get_session)
    assert result.exit_code == 0, result.output

    db_session.refresh(batch)
    assert batch.status == BatchStatus.paused


def test_batch_pause_rejects_non_executing(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_batch(db_session, "BATCH-00001", status=BatchStatus.planning)

    runner = CliRunner()
    result = invoke(runner, ["batch-pause", "BATCH-00001"], cli_get_session)
    assert result.exit_code == 1


def test_batch_resume_paused_to_executing(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    batch = make_batch(db_session, "BATCH-00001", status=BatchStatus.paused)

    runner = CliRunner()
    result = invoke(runner, ["batch-resume", "BATCH-00001"], cli_get_session)
    assert result.exit_code == 0, result.output

    db_session.refresh(batch)
    assert batch.status == BatchStatus.executing


def test_batch_resume_rejects_non_paused(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_batch(db_session, "BATCH-00001", status=BatchStatus.executing)

    runner = CliRunner()
    result = invoke(runner, ["batch-resume", "BATCH-00001"], cli_get_session)
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Full batch lifecycle: create → approve → pause → resume
# ---------------------------------------------------------------------------


def test_batch_full_lifecycle(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    make_item(db_session, "I-00001")
    make_item(db_session, "I-00002")
    make_item(db_session, "I-00003")

    runner = CliRunner()

    # Create
    result = runner.invoke(
        cli,
        ["--project", "test-proj", "--json", "batch-create", "I-00001", "I-00002", "I-00003"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    batch_id = json.loads(result.output)["batch_id"]

    # Approve
    result = invoke(runner, ["batch-approve", batch_id], cli_get_session)
    assert result.exit_code == 0

    batch = db_session.get(Batch, ("test-proj", batch_id))
    assert batch is not None
    assert batch.status == BatchStatus.approved

    # Simulate daemon transition to executing
    batch.status = BatchStatus.executing
    db_session.flush()

    # Pause
    result = invoke(runner, ["batch-pause", batch_id], cli_get_session)
    assert result.exit_code == 0

    db_session.refresh(batch)
    assert batch.status == BatchStatus.paused

    # Resume
    result = invoke(runner, ["batch-resume", batch_id], cli_get_session)
    assert result.exit_code == 0

    db_session.refresh(batch)
    assert batch.status == BatchStatus.executing
