"""Contract tests for `iw doc-update` against a real PostgreSQL testcontainer.

Tests the full contract: exit codes, stdout shape, DB row effects.

All tests use the testcontainer db_session fixture — never the live DB.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from sqlalchemy import select

from orch.cli.main import cli
from orch.db.models import (
    Project,
    ProjectDoc,
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


def test_doc_update_new_doc_without_tier_is_clean_usage_error(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """A new-doc doc-update missing --tier/--editorial-category should be a clean
    exit-2 usage error — not a raw TypeError surfaced as exit 3.

    Post-S01 (I-00108): the pre-check in doc_commands.py fires only on the new-doc
    path and exits 2 with a message naming the missing flags.
    """
    runner = CliRunner()
    result = invoke(
        runner,
        ["doc-update", "F-00099", "--doc-type", "module", "--title", "T"],
        cli_get_session,
    )
    assert result.exit_code == 2, f"stdout: {result.output}\nstderr: {result.stderr}"
    assert "tier" in (result.stderr or "").lower()


# ---------------------------------------------------------------------------
# Regression guards — I-00108
# ---------------------------------------------------------------------------


def test_doc_update_existing_doc_update_without_tier_succeeds(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """An update to an existing doc may omit --tier and --editorial-category —
    they are required only when creating a brand-new doc, per upsert semantics.

    Pins the 'update path stays optional' side of I-00108: making --tier /
    --editorial-category required at the Click layer would have broken this
    path; the pre-check in doc_commands.py must fire only when no existing doc
    is found.
    """
    runner = CliRunner()

    # Seed: create the doc with all required flags first.
    first = runner.invoke(
        cli,
        [
            "--project",
            test_project.id,
            "--json",
            "doc-update",
            "F-00200",
            "--doc-type",
            "module",
            "--title",
            "Original title",
            "--tier",
            "human_authored",
            "--editorial-category",
            "technical",
            "--content",
            "# Original body",
        ],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert first.exit_code == 0, f"precondition failed — create call: {first.stderr}"

    # Update WITHOUT --tier/--editorial-category — must succeed (not exit 2/3).
    second = runner.invoke(
        cli,
        [
            "--project",
            test_project.id,
            "--json",
            "doc-update",
            "F-00200",
            "--title",
            "Updated title",
            "--content",
            "# v2 body",
        ],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert second.exit_code == 0, (
        f"update without --tier/--editorial-category should succeed; got exit {second.exit_code}"
    )
    assert second.exit_code == 0, f"stderr: {second.stderr}"

    # Semantic check: the row was updated, not crashed or re-created.
    doc = db_session.execute(
        select(ProjectDoc).where(
            ProjectDoc.id == f"{test_project.id}:F-00200",
        )
    ).scalar_one()
    assert doc.title == "Updated title"
    assert doc.content is not None
    assert "v2 body" in doc.content


def test_doc_update_new_doc_with_tier_and_category_succeeds(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """A new-doc upsert with all required flags creates the ProjectDoc row
    cleanly — the pre-check added for I-00108 must not fire when both
    --tier and --editorial-category are supplied.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project",
            test_project.id,
            "--json",
            "doc-update",
            "F-00201",
            "--doc-type",
            "module",
            "--title",
            "New module doc",
            "--tier",
            "human_authored",
            "--editorial-category",
            "technical",
            "--content",
            "# New doc body",
        ],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )
    assert result.exit_code == 0, (
        f"new-doc with full flags should succeed; got exit {result.exit_code}"
    )
    assert result.exit_code == 0, f"stderr: {result.stderr}"
    data = json.loads(result.output)
    assert data["doc_id"] == f"{test_project.id}:F-00201"
    assert data["project_id"] == test_project.id

    doc = db_session.execute(
        select(ProjectDoc).where(
            ProjectDoc.id == f"{test_project.id}:F-00201",
        )
    ).scalar_one()
    assert doc.title == "New module doc"
    assert doc.tier.value == "human_authored"
    assert doc.editorial_category.value == "technical"
