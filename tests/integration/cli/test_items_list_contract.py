"""Contract tests for `iw items-list` against a real PostgreSQL testcontainer.

Covers the JSON contract (keys, pagination fields), status/type/phase filtering,
invalid-filter error handling, and the human-readable summary line. All tests
use the testcontainer ``db_session`` fixture — never the live DB.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from click.testing import CliRunner

from orch.cli.main import cli
from orch.db.models import WorkItem, WorkItemPhase, WorkItemStatus, WorkItemType

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from orch.db.models import Project as ProjectModel


def _make_item(
    session: Session,
    project_id: str,
    item_id: str,
    *,
    title: str,
    status: WorkItemStatus,
    item_type: WorkItemType = WorkItemType.Issue,
    phase: WorkItemPhase = WorkItemPhase.active,
) -> None:
    """Insert a minimal WorkItem row for list assertions.

    Args:
        session: Active testcontainer session.
        project_id: Owning project.
        item_id: Work item identifier (prefix must match ``item_type``).
        title: Human-readable title.
        status: Work item status enum.
        item_type: Work item type enum.
        phase: Work item phase enum.
    """
    session.add(
        WorkItem(
            project_id=project_id,
            id=item_id,
            type=item_type,
            title=title,
            status=status,
            phase=phase,
        )
    )
    session.flush()


def _invoke_json(
    runner: CliRunner, args: list[str], get_session: object, project_id: str
) -> object:
    """Invoke the CLI in --json mode with an injected session factory.

    Args:
        runner: Click test runner.
        args: CLI argument list (after the global options).
        get_session: Injected session-factory context manager.
        project_id: Project scope passed via ``--project``.

    Returns:
        The parsed Click result object.
    """
    return runner.invoke(
        cli,
        ["--project", project_id, "--json", *args],
        obj={"get_session": get_session},
        catch_exceptions=False,
    )


def test_items_list_empty_project_returns_empty_contract(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: an empty project yields the documented empty-list JSON contract."""
    runner = CliRunner()
    result = _invoke_json(runner, ["items-list"], cli_get_session, test_project.id)

    assert result.exit_code == 0, f"stderr: {result.stderr}\nstdout: {result.output}"
    data = json.loads(result.output)
    assert data == {"items": [], "next_cursor": None, "has_more": False, "total": 0}


def test_items_list_returns_registered_items(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: registered items appear in the JSON payload with id/status/title."""
    _make_item(
        db_session, test_project.id, "I-00001", title="First bug", status=WorkItemStatus.draft
    )
    _make_item(
        db_session,
        test_project.id,
        "I-00002",
        title="Second bug",
        status=WorkItemStatus.approved,
    )

    runner = CliRunner()
    result = _invoke_json(runner, ["items-list"], cli_get_session, test_project.id)

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    data = json.loads(result.output)
    assert data["total"] == 2
    ids = {it["id"] for it in data["items"]}
    assert ids == {"I-00001", "I-00002"}


def test_items_list_status_filter_narrows_results(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: --status returns only items in that status."""
    _make_item(db_session, test_project.id, "I-00001", title="d", status=WorkItemStatus.draft)
    _make_item(db_session, test_project.id, "I-00002", title="a", status=WorkItemStatus.approved)

    runner = CliRunner()
    result = _invoke_json(
        runner, ["items-list", "--status", "approved"], cli_get_session, test_project.id
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    data = json.loads(result.output)
    assert data["total"] == 1
    assert data["items"][0]["id"] == "I-00002"


def test_items_list_invalid_status_filter_errors(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Non-zero exit: an unrecognised --status value reports a clear error, not all items."""
    _make_item(db_session, test_project.id, "I-00001", title="d", status=WorkItemStatus.draft)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", test_project.id, "--json", "items-list", "--status", "not-a-status"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )

    assert result.exit_code != 0
    assert result.output.lower().find("invalid status") != -1, result.output


def test_items_list_human_output_summary_line(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: human mode prints a 'Work items (N of M)' summary header."""
    _make_item(
        db_session, test_project.id, "I-00001", title="Only one", status=WorkItemStatus.draft
    )

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", test_project.id, "items-list"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    assert result.output.find("Work items (1 of 1)") != -1, result.output
    assert result.output.find("I-00001") != -1, result.output
