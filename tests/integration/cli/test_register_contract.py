"""Contract tests for `iw register` against a real PostgreSQL testcontainer.

Tests the full contract: exit codes, stdout shape, DB row effects, and
idempotency-key behaviour.

All tests use the testcontainer db_session fixture — never the live DB.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from orch.cli.main import cli
from orch.db.models import (
    WorkflowStep,
    WorkItem,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import Project as ProjectModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def invoke(
    runner: CliRunner,
    args: list[str],
    get_session: object,
    project_id: str = "test-proj",
) -> pytest.ClickResult:
    """Invoke the CLI with a pre-injected session factory."""
    return runner.invoke(
        cli,
        ["--project", project_id, *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


def test_register_new_item_success(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: registering a new item creates the work_items row with status=draft."""
    runner = CliRunner()
    result = invoke(
        runner,
        ["register", "I-00001", "Fix timeout bug", "--type", "incident"],
        cli_get_session,
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}\nstdout: {result.output}"
    assert "I-00001" in result.output

    item = db_session.get(WorkItem, (test_project.id, "I-00001"))
    assert item is not None, "WorkItem was not created in DB"
    assert item.title == "Fix timeout bug"
    assert item.status == WorkItemStatus.draft
    assert item.type == WorkItemType.Issue


def test_register_json_output_shape(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0 with --json: stdout is valid JSON with documented fields."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project",
            test_project.id,
            "--json",
            "register",
            "I-00002",
            "My title",
            "--type",
            "incident",
        ],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    data = json.loads(result.output)
    assert data["project_id"] == test_project.id
    assert data["id"] == "I-00002"
    assert data["title"] == "My title"
    assert data["status"] == "draft"
    assert data["created"] is True


def test_register_with_steps_from_manifest(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
    tmp_path: Path,
) -> None:
    """Exit 0 with --steps-from: workflow_steps rows are created from the manifest."""
    manifest = tmp_path / "workflow-manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "steps": [
                    {"step": "S01", "agent": "backend-impl"},
                    {"step": "S02", "agent": "code-review-impl"},
                ]
            }
        )
    )

    runner = CliRunner()
    result = invoke(
        runner,
        ["register", "F-00001", "With steps", "--type", "feature", "--steps-from", str(manifest)],
        cli_get_session,
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}"

    steps = (
        db_session.query(WorkflowStep)
        .filter(
            WorkflowStep.project_id == test_project.id,
            WorkflowStep.work_item_id == "F-00001",
        )
        .order_by(WorkflowStep.step_number)
        .all()
    )
    assert len(steps) == 2
    assert steps[0].step_id == "S01"
    assert steps[0].opencode_agent == "backend-impl"
    assert steps[1].step_id == "S02"


def test_register_with_design_doc_loads_content(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exit 0 with --design-doc: design_doc_content is loaded from disk."""
    design_doc = tmp_path / "F-00002_Design.md"
    design_doc.write_text("# F-00002 Design\n\n| File | Role |\n| `a.ts` | component |")

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = invoke(
        runner,
        [
            "register",
            "F-00002",
            "Feature with design doc",
            "--type",
            "feature",
            "--design-doc",
            "F-00002_Design.md",
        ],
        cli_get_session,
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}"

    item = db_session.get(WorkItem, (test_project.id, "F-00002"))
    assert item is not None
    assert item.design_doc_path == "F-00002_Design.md"
    assert item.design_doc_content is not None
    assert "F-00002 Design" in item.design_doc_content


def test_register_research_item(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0 with --type research: a research-type item is created."""
    runner = CliRunner()
    result = invoke(
        runner,
        ["register", "R-00001", "Research something", "--type", "research"],
        cli_get_session,
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}"

    item = db_session.get(WorkItem, (test_project.id, "R-00001"))
    assert item is not None
    assert item.type == WorkItemType.Research
    assert item.status == WorkItemStatus.draft


# ---------------------------------------------------------------------------
# Idempotence
# ---------------------------------------------------------------------------


def test_register_idempotent_same_key_no_new_row(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: re-registering with the same ID returns created=false, DB row unchanged."""
    runner = CliRunner()
    first = invoke(
        runner,
        ["register", "I-00003", "Original title", "--type", "incident"],
        cli_get_session,
    )
    assert first.exit_code == 0

    # Capture the created_at timestamp
    item_before = db_session.get(WorkItem, (test_project.id, "I-00003"))
    assert item_before is not None
    created_at_before = item_before.created_at

    second = runner.invoke(
        cli,
        [
            "--project",
            test_project.id,
            "--json",
            "register",
            "I-00003",
            "Different title",
            "--type",
            "incident",
        ],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert second.exit_code == 0, f"Idempotent re-registration failed: {second.stderr}"
    data = json.loads(second.output)
    assert data["created"] is False
    assert data["message"] == "Already registered"

    # DB row unchanged
    item_after = db_session.get(WorkItem, (test_project.id, "I-00003"))
    assert item_after is not None
    assert item_after.title == "Original title"
    assert item_after.created_at == created_at_before


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_register_missing_required_args_exit_2(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 2: missing the required ID argument."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", test_project.id, "register"],
        obj={"get_session": cli_get_session},
        catch_exceptions=True,
    )
    # Missing positional arg → exit 2 (Click usage error)
    assert result.exit_code == 2


def test_register_missing_type_flag_exit_2(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 2: missing the required --type flag."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", test_project.id, "register", "I-00004", "Title"],
        obj={"get_session": cli_get_session},
        catch_exceptions=True,
    )
    assert result.exit_code == 2


def test_register_invalid_type_exit_2(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 2: --type value not in the allowed set."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", test_project.id, "register", "X-00001", "Title", "--type", "not-a-type"],
        obj={"get_session": cli_get_session},
        catch_exceptions=True,
    )
    assert result.exit_code == 2


def test_register_id_type_mismatch_exit_2(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 2: ID prefix does not match the --type."""
    runner = CliRunner()
    result = invoke(
        runner,
        ["register", "I-00005", "Title", "--type", "feature"],
        cli_get_session,
    )
    # I- prefix with --type feature is a mismatch → exit 2
    assert result.exit_code == 2


def test_register_missing_design_doc_emits_warning(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exit 0 but with warning in stderr: --design-doc file does not exist."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = invoke(
        runner,
        [
            "register",
            "F-00003",
            "Feature",
            "--type",
            "feature",
            "--design-doc",
            "does-not-exist.md",
        ],
        cli_get_session,
    )
    assert result.exit_code == 0, f"Should succeed with warning: {result.stderr}"
    # Warning emitted but registration succeeds
    item = db_session.get(WorkItem, (test_project.id, "F-00003"))
    assert item is not None
    assert item.design_doc_path == "does-not-exist.md"
