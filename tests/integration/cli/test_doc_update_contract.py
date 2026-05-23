"""Contract tests for `iw doc-update` against a real PostgreSQL testcontainer.

Tests the full contract: exit codes, stdout shape, DB row effects.

All tests use the testcontainer db_session fixture — never the live DB.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from orch.cli.main import cli
from orch.db.models import (
    Project,
    WorkItem,
    WorkItemPhase,
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


def seed_work_item(
    db_session: Session,
    project_id: str,
    item_id: str,
    item_type: WorkItemType = WorkItemType.Feature,
    status: WorkItemStatus = WorkItemStatus.draft,
) -> WorkItem:
    """Seed a work item in the given state."""
    # Idempotent: skip if project already exists (e.g. from test_project fixture)
    existing = db_session.get(Project, project_id)
    if not existing:
        db_session.add(
            Project(id=project_id, display_name="Test", repo_root="/repos/test", config={})
        )
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=item_type,
        title=f"Test {item_id}",
        status=status,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    db_session.add(item)
    db_session.flush()
    return item


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


def test_doc_update_new_research_item_autocomplete(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: doc-update on a draft research item auto-completes it (completed phase)."""
    # Register a research item first
    seed_work_item(
        db_session, test_project.id, "R-00001", WorkItemType.Research, WorkItemStatus.draft
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project",
            test_project.id,
            "--json",
            "doc-update",
            "R-00001",
            "--doc-type",
            "research",
            "--title",
            "My Research",
            "--tier",
            "human_authored",
            "--editorial-category",
            "technical",
            "--content",
            "# Research content",
        ],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}\nstdout: {result.output}"
    data = json.loads(result.output)
    assert data.get("work_item_auto_completed") is True

    item = db_session.get(WorkItem, (test_project.id, "R-00001"))
    assert item is not None
    assert item.status == WorkItemStatus.completed
    assert item.phase == WorkItemPhase.done


def test_doc_update_second_call_on_completed_research(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: second doc-update on already-completed research returns auto_completed=false."""
    seed_work_item(
        db_session, test_project.id, "R-00002", WorkItemType.Research, WorkItemStatus.draft
    )

    runner = CliRunner()

    # First update: auto-completes
    first = runner.invoke(
        cli,
        [
            "--project",
            test_project.id,
            "--json",
            "doc-update",
            "R-00002",
            "--doc-type",
            "research",
            "--title",
            "Research",
            "--tier",
            "human_authored",
            "--editorial-category",
            "technical",
            "--content",
            "# V1",
        ],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert first.exit_code == 0
    assert json.loads(first.output).get("work_item_auto_completed") is True

    # Second update: already completed
    second = runner.invoke(
        cli,
        [
            "--project",
            test_project.id,
            "--json",
            "doc-update",
            "R-00002",
            "--title",
            "Research",
            "--content",
            "# V2",
        ],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert second.exit_code == 0
    assert json.loads(second.output).get("work_item_auto_completed") is False


def test_doc_update_non_research_does_not_autocomplete(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: doc-update on a non-research item does not change status."""
    seed_work_item(
        db_session, test_project.id, "F-00001", WorkItemType.Feature, WorkItemStatus.draft
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project",
            test_project.id,
            "--json",
            "doc-update",
            "F-00001",
            "--doc-type",
            "module",
            "--title",
            "Tech Design",
            "--tier",
            "human_authored",
            "--editorial-category",
            "technical",
            "--content",
            "# Tech Design",
        ],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    data = json.loads(result.output)
    assert data.get("work_item_auto_completed") is False

    item = db_session.get(WorkItem, (test_project.id, "F-00001"))
    assert item is not None
    assert item.status == WorkItemStatus.draft


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_doc_update_content_and_content_file_mutually_exclusive_exit_2(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 2 + clear stderr: --content and --content-file cannot be combined."""
    runner = CliRunner()
    result = invoke(
        runner,
        [
            "doc-update",
            "F-00001",
            "--doc-type",
            "module",
            "--title",
            "T",
            "--content",
            "inline body",
            "--content-file",
            "some-file.md",
        ],
        cli_get_session,
    )
    assert result.exit_code == 2, f"stdout: {result.output}\nstderr: {result.stderr}"
    assert "mutually exclusive" in (result.stderr or "").lower()


def test_doc_update_unknown_project_exit_1(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 1 + clear stderr: the --project does not exist."""
    runner = CliRunner()
    result = invoke(
        runner,
        ["doc-update", "F-00001", "--doc-type", "module", "--title", "T"],
        cli_get_session,
        project_id="nonexistent-project",
    )
    assert result.exit_code == 1, f"stdout: {result.output}\nstderr: {result.stderr}"
    assert "not found" in (result.stderr or "").lower()


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TODO(file-incident): doc-update accepts a new-doc upsert that omits "
        "--tier/--editorial-category, then crashes with a raw TypeError from "
        "DocService.create_doc() surfaced as exit 3 'Database error'. The "
        "contract should be a clean exit 2 usage error naming the missing "
        "options. Operator follow-up: file an Incident; the orch/cli fix is "
        "out of scope for this test-only CR."
    ),
)
def test_doc_update_new_doc_without_tier_is_clean_usage_error(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """A new-doc doc-update missing --tier/--editorial-category should be a clean
    exit-2 usage error — not a raw TypeError surfaced as exit 3.

    Currently the CLI exits 3 ("Database error: ... missing ... arguments"), so
    this test is a strict xfail pinning the desired contract until the bug is
    fixed (see the xfail reason — operator to file an Incident).
    """
    runner = CliRunner()
    result = invoke(
        runner,
        ["doc-update", "F-00099", "--doc-type", "module", "--title", "T"],
        cli_get_session,
    )
    assert result.exit_code == 2, f"stdout: {result.output}\nstderr: {result.stderr}"
    assert "tier" in (result.stderr or "").lower()
