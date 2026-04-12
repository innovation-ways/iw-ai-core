"""Integration tests for CLI core commands against a real PostgreSQL testcontainer."""

import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from click.testing import CliRunner
from sqlalchemy.orm import Session as SASession

from orch.cli.id_commands import allocate_next_id
from orch.cli.main import cli
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    IdSequence,
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

    ids = []
    for _ in range(3):
        result = invoke(runner, ["next-id", "--type", "incident"], cli_get_session)
        assert result.exit_code == 0, result.output
        ids.append(result.output.strip())

    # Must be sequential (gapless, ascending)
    numbers = [int(i.split("-")[1]) for i in ids]
    assert numbers == [numbers[0], numbers[0] + 1, numbers[0] + 2]


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
    assert data["id"].startswith("I-")
    assert data["project_id"] == "test-proj"
    assert data["prefix"] == "I"
    assert isinstance(data["number"], int)


def test_next_id_all_types(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
) -> None:
    runner = CliRunner()
    expected_prefixes = {
        "feature": "F-",
        "incident": "I-",
        "cr": "CR-",
        "batch": "BATCH-",
    }

    for item_type, prefix in expected_prefixes.items():
        result = invoke(runner, ["next-id", "--type", item_type], cli_get_session)
        assert result.exit_code == 0, f"{item_type}: {result.output}"
        assert result.output.strip().startswith(prefix)


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

    # Cleanup — delete project and the global sequence row
    with _session() as s, s.begin():
        p = s.get(Project, project_id)
        if p:
            s.delete(p)
        seq = s.get(IdSequence, "I")
        if seq:
            s.delete(seq)

    assert len(set(results)) == 10
    # IDs must be unique and gapless (exact start depends on prior state)
    numbers = sorted(int(r.split("-")[1]) for r in results)
    assert numbers == list(range(numbers[0], numbers[0] + 10))


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


def test_register_loads_design_doc_content_from_disk(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Any,
    monkeypatch: Any,
) -> None:
    """Regression: `register` previously stored only `design_doc_path`,
    leaving `design_doc_content` NULL. That meant the batch planner's
    file-overlap detection saw an empty string for every item and always
    reported "no overlaps", which caused BATCH-00011's F-00004 / F-00005
    collision on DesignerShell.tsx to slip through."""
    design_doc = tmp_path / "F-00001_Design.md"
    design_doc.write_text(
        "# F-00001\n\n"
        "| File | Role |\n"
        "| `frontend/src/components/editor/DesignerShell.tsx` | Editor shell |\n"
    )
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = invoke(
        runner,
        [
            "register",
            "F-00001",
            "Test",
            "--type",
            "feature",
            "--design-doc",
            "F-00001_Design.md",
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output

    item = db_session.get(WorkItem, ("test-proj", "F-00001"))
    assert item is not None
    assert item.design_doc_path == "F-00001_Design.md"
    assert item.design_doc_content is not None
    assert "DesignerShell.tsx" in item.design_doc_content


def test_register_tolerates_missing_design_doc_file(
    db_session: Any,
    test_project: Project,
    cli_get_session: Any,
    tmp_path: Any,
    monkeypatch: Any,
) -> None:
    """If the --design-doc file does not exist the item still registers,
    but a warning is emitted and design_doc_content is NULL."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = invoke(
        runner,
        [
            "register",
            "F-00002",
            "Test",
            "--type",
            "feature",
            "--design-doc",
            "does-not-exist.md",
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, result.output
    assert "Warning" in result.output or "not found" in result.output

    item = db_session.get(WorkItem, ("test-proj", "F-00002"))
    assert item is not None
    assert item.design_doc_path == "does-not-exist.md"
    assert item.design_doc_content is None


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
    assert item_id.startswith("I-")

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
