"""Integration tests for CLI core commands against a real PostgreSQL testcontainer."""

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from click.testing import CliRunner
from sqlalchemy.orm import Session as SASession

from orch.cli.id_commands import allocate_next_id
from orch.cli.main import cli
from orch.cli.utils import format_id
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    Project,
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
)

if __name__ == "__main__":
    pass  # pragma: no cover


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def invoke(
    runner: CliRunner,
    args: list[str],
    get_session: Any,
    project_id: str = "test-proj",
) -> Any:
    """Invoke the CLI with a pre-injected session factory."""
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# next-id
# ---------------------------------------------------------------------------


def test_next_id_sequential(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()

    for i in range(1, 4):
        result = invoke(runner, ["next-id", "--type", "incident"], cli_get_session)
        assert result.exit_code == 0, result.output
        assert result.output.strip() == f"I-{i:05d}"


def test_next_id_json_output(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", "test-proj", "--json", "next-id", "--type", "incident"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["id"] == "I-00001"
    assert data["project_id"] == "test-proj"
    assert data["prefix"] == "I"
    assert data["number"] == 1


def test_next_id_all_types(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()
    expected = {
        "feature": "F-00001",
        "incident": "I-00001",
        "cr": "CR-00001",
        "batch": "BATCH-00001",
    }

    for item_type, expected_id in expected.items():
        result = invoke(runner, ["next-id", "--type", item_type], cli_get_session)
        assert result.exit_code == 0, f"{item_type}: {result.output}"
        assert result.output.strip() == expected_id


def test_next_id_concurrent_no_duplicates(db_engine: Any) -> None:
    """10 concurrent allocations must produce 10 unique, gapless IDs."""
    project_id = "concurrent-test"

    def _session() -> SASession:
        return SASession(db_engine)

    # Ensure clean state
    with _session() as s, s.begin():
        existing = s.get(Project, project_id)
        if existing:
            s.delete(existing)

    with _session() as s, s.begin():
        s.add(
            Project(
                id=project_id,
                display_name="Concurrent Test",
                repo_root="/repos/concurrent",
                config={},
            )
        )

    def allocate() -> str:
        with _session() as s, s.begin():
            _number, formatted = allocate_next_id(s, project_id, "I")
            return formatted

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda _: allocate(), range(10)))

    # Cleanup
    with _session() as s, s.begin():
        p = s.get(Project, project_id)
        if p:
            s.delete(p)

    assert len(set(results)) == 10
    assert sorted(results) == [format_id("I", i) for i in range(1, 11)]


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


def test_register_creates_work_item(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()
    result = invoke(
        runner,
        ["register", "I-00001", "Fix timeout", "--type", "incident"],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output
    assert "I-00001" in result.output

    item = db_session.get(WorkItem, ("test-proj", "I-00001"))
    assert item is not None
    assert item.title == "Fix timeout"
    assert item.status == WorkItemStatus.draft


def test_register_json_output(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project",
            "test-proj",
            "--json",
            "register",
            "I-00001",
            "My title",
            "--type",
            "incident",
        ],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["id"] == "I-00001"
    assert data["created"] is True
    assert data["status"] == "draft"


def test_register_idempotent(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()
    invoke(runner, ["register", "I-00001", "Title", "--type", "incident"], cli_get_session)

    result = runner.invoke(
        cli,
        ["--project", "test-proj", "--json", "register", "I-00001", "Other", "--type", "incident"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["created"] is False
    assert data["message"] == "Already registered"


def test_register_wrong_prefix_exits_2(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()
    result = invoke(
        runner,
        ["register", "I-00001", "Title", "--type", "feature"],
        cli_get_session,
    )
    assert result.exit_code == 2


def test_register_steps_from_manifest(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Any,
) -> None:
    manifest = tmp_path / "workflow-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "steps": [
                    {"step": "S01", "agent": "backend-impl"},
                    {"step": "S02", "agent": "code-review-impl"},
                    {"step": "S03", "agent": "code-review-final-impl"},
                ]
            }
        )
    )

    runner = CliRunner()
    result = invoke(
        runner,
        [
            "register",
            "I-00001",
            "With steps",
            "--type",
            "incident",
            "--steps-from",
            str(manifest),
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    steps = (
        db_session.query(WorkflowStep)
        .filter(WorkflowStep.project_id == "test-proj", WorkflowStep.work_item_id == "I-00001")
        .order_by(WorkflowStep.step_number)
        .all()
    )
    assert len(steps) == 3
    assert steps[0].step_id == "S01"
    assert steps[0].opencode_agent == "backend-impl"
    assert steps[1].step_id == "S02"
    assert steps[2].step_id == "S03"


# ---------------------------------------------------------------------------
# approve
# ---------------------------------------------------------------------------


def test_approve_draft_to_approved(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()
    invoke(runner, ["register", "I-00001", "Test", "--type", "incident"], cli_get_session)

    result = invoke(runner, ["approve", "I-00001"], cli_get_session)
    assert result.exit_code == 0, result.output

    item = db_session.get(WorkItem, ("test-proj", "I-00001"))
    assert item is not None
    assert item.status == WorkItemStatus.approved


def test_approve_json_output(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()
    invoke(runner, ["register", "I-00001", "Test", "--type", "incident"], cli_get_session)

    result = runner.invoke(
        cli,
        ["--project", "test-proj", "--json", "approve", "I-00001"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["status"] == "approved"


def test_approve_not_found_exits_1(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()
    result = invoke(runner, ["approve", "I-00999"], cli_get_session)
    assert result.exit_code == 1


def test_approve_already_approved_exits_1(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()
    invoke(runner, ["register", "I-00001", "Test", "--type", "incident"], cli_get_session)
    invoke(runner, ["approve", "I-00001"], cli_get_session)

    result = invoke(runner, ["approve", "I-00001"], cli_get_session)
    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# unapprove
# ---------------------------------------------------------------------------


def test_unapprove_approved_to_draft(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()
    invoke(runner, ["register", "I-00001", "Test", "--type", "incident"], cli_get_session)
    invoke(runner, ["approve", "I-00001"], cli_get_session)

    result = invoke(runner, ["unapprove", "I-00001"], cli_get_session)
    assert result.exit_code == 0, result.output

    item = db_session.get(WorkItem, ("test-proj", "I-00001"))
    assert item is not None
    assert item.status == WorkItemStatus.draft


def test_unapprove_rejects_active_batch_exits_4(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()
    invoke(runner, ["register", "I-00001", "Test", "--type", "incident"], cli_get_session)
    invoke(runner, ["approve", "I-00001"], cli_get_session)

    batch = Batch(
        project_id="test-proj",
        id="BATCH-00001",
        status=BatchStatus.executing,
        cli_tool="opencode",
    )
    db_session.add(batch)
    db_session.flush()

    db_session.add(
        BatchItem(
            project_id="test-proj",
            batch_id="BATCH-00001",
            work_item_id="I-00001",
            status=BatchItemStatus.executing,
        )
    )
    db_session.flush()

    result = invoke(runner, ["unapprove", "I-00001"], cli_get_session)
    assert result.exit_code == 4


def test_unapprove_completed_batch_is_ok(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()
    invoke(runner, ["register", "I-00001", "Test", "--type", "incident"], cli_get_session)
    invoke(runner, ["approve", "I-00001"], cli_get_session)

    batch = Batch(
        project_id="test-proj",
        id="BATCH-00001",
        status=BatchStatus.completed,
        cli_tool="opencode",
    )
    db_session.add(batch)
    db_session.flush()

    db_session.add(
        BatchItem(
            project_id="test-proj",
            batch_id="BATCH-00001",
            work_item_id="I-00001",
            status=BatchItemStatus.merged,
        )
    )
    db_session.flush()

    result = invoke(runner, ["unapprove", "I-00001"], cli_get_session)
    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Full flow: next-id → register → approve
# ---------------------------------------------------------------------------


def test_full_flow_next_id_register_approve(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["--project", "test-proj", "--json", "next-id", "--type", "incident"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    item_id = json.loads(result.output)["id"]
    assert item_id == "I-00001"

    result = runner.invoke(
        cli,
        [
            "--project",
            "test-proj",
            "--json",
            "register",
            item_id,
            "Full flow test",
            "--type",
            "incident",
        ],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert json.loads(result.output)["created"] is True

    result = runner.invoke(
        cli,
        ["--project", "test-proj", "--json", "approve", item_id],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    assert json.loads(result.output)["status"] == "approved"

    item = db_session.get(WorkItem, ("test-proj", "I-00001"))
    assert item is not None
    assert item.status == WorkItemStatus.approved
    assert item.title == "Full flow test"
