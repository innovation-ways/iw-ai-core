"""Integration tests for the iw search command.

Verifies full-text search with ranking, project filtering, and type filtering.
"""

from __future__ import annotations

import json as json_mod
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from orch.cli.main import cli
from orch.db.models import Project, WorkItem, WorkItemPhase, WorkItemStatus, WorkItemType

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def two_projects(db_session: Session) -> tuple[Project, Project]:
    """Two projects for cross-project filtering tests."""
    p1 = Project(id="proj-alpha", display_name="Alpha", repo_root="/repos/alpha", config={})
    p2 = Project(id="proj-beta", display_name="Beta", repo_root="/repos/beta", config={})
    db_session.add(p1)
    db_session.add(p2)
    db_session.flush()
    return p1, p2


def _insert_item(
    session: Session,
    *,
    project_id: str,
    item_id: str,
    title: str,
    content: str,
    item_type: WorkItemType = WorkItemType.Issue,
    status: WorkItemStatus = WorkItemStatus.completed,
) -> WorkItem:
    """Insert a WorkItem and flush (FTS trigger updates design_doc_search)."""
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=item_type,
        title=title,
        status=status,
        phase=WorkItemPhase.done,
        config={},
        depends_on=[],
        blocks=[],
        design_doc_content=content,
    )
    session.add(item)
    session.flush()
    return item


def _make_runner(db_session: Session) -> tuple[CliRunner, Callable[[], contextmanager]]:  # type: ignore[type-arg]
    @contextmanager  # type: ignore[arg-type]
    def get_session() -> Generator[Session, None, None]:
        yield db_session

    return CliRunner(), get_session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_search_returns_matching_items(
    two_projects: tuple[Project, Project], db_session: Session
) -> None:
    """Insert 3 items; searching by keyword returns the relevant ones."""
    p1, p2 = two_projects
    _insert_item(
        db_session,
        project_id="proj-alpha",
        item_id="I-00001",
        title="Fix template rendering timeout",
        content="WeasyPrint times out when rendering large templates with many zones.",
    )
    _insert_item(
        db_session,
        project_id="proj-alpha",
        item_id="I-00002",
        title="Template rendering fails on large invoices",
        content="Rendering pipeline crashes on invoices with nested zone hierarchies.",
    )
    _insert_item(
        db_session,
        project_id="proj-alpha",
        item_id="F-00001",
        title="Add dark mode support",
        content="Users want a dark mode toggle in the settings page.",
        item_type=WorkItemType.Feature,
    )

    runner, get_session = _make_runner(db_session)
    result = runner.invoke(
        cli,
        ["--json", "search", "template"],
        obj={"get_session": get_session},
    )
    assert result.exit_code == 0, result.output
    data = json_mod.loads(result.output)
    assert data["count"] == 2
    ids = {r["id"] for r in data["results"]}
    assert ids == {"I-00001", "I-00002"}


def test_search_ranking_by_relevance(
    two_projects: tuple[Project, Project], db_session: Session
) -> None:
    """Item with keyword in both title and content ranks higher."""
    p1, _ = two_projects
    _insert_item(
        db_session,
        project_id="proj-alpha",
        item_id="I-00001",
        title="Fix rendering timeout",
        content="WeasyPrint rendering times out on large templates.",
    )
    _insert_item(
        db_session,
        project_id="proj-alpha",
        item_id="I-00002",
        title="Unrelated issue",
        content="Some note about rendering in passing.",
    )

    runner, get_session = _make_runner(db_session)
    result = runner.invoke(
        cli,
        ["--json", "search", "rendering"],
        obj={"get_session": get_session},
    )
    assert result.exit_code == 0, result.output
    data = json_mod.loads(result.output)
    assert data["count"] == 2
    # I-00001 has rendering in both title and content — should rank first
    assert data["results"][0]["id"] == "I-00001"


def test_search_project_filter(two_projects: tuple[Project, Project], db_session: Session) -> None:
    """--project option restricts results to a single project."""
    p1, p2 = two_projects
    _insert_item(
        db_session,
        project_id="proj-alpha",
        item_id="I-00001",
        title="Timeout issue alpha",
        content="timeout rendering in alpha project pipeline",
    )
    _insert_item(
        db_session,
        project_id="proj-beta",
        item_id="I-00001",
        title="Timeout issue beta",
        content="timeout rendering in beta project pipeline",
    )

    runner, get_session = _make_runner(db_session)

    # Filter to proj-alpha only via global --project flag
    result = runner.invoke(
        cli,
        ["--json", "--project", "proj-alpha", "search", "timeout"],
        obj={"get_session": get_session},
    )
    assert result.exit_code == 0, result.output
    data = json_mod.loads(result.output)
    assert data["count"] == 1
    assert data["results"][0]["project_id"] == "proj-alpha"


def test_search_type_filter(two_projects: tuple[Project, Project], db_session: Session) -> None:
    """--type option restricts results to the specified work item type."""
    p1, _ = two_projects
    _insert_item(
        db_session,
        project_id="proj-alpha",
        item_id="I-00001",
        title="Incident with timeout",
        content="rendering timeout in issue",
        item_type=WorkItemType.Issue,
    )
    _insert_item(
        db_session,
        project_id="proj-alpha",
        item_id="F-00001",
        title="Feature with timeout",
        content="rendering timeout in feature",
        item_type=WorkItemType.Feature,
    )

    runner, get_session = _make_runner(db_session)

    result = runner.invoke(
        cli,
        ["--json", "search", "timeout", "--type", "incident"],
        obj={"get_session": get_session},
    )
    assert result.exit_code == 0, result.output
    data = json_mod.loads(result.output)
    assert data["count"] == 1
    assert data["results"][0]["id"] == "I-00001"


def test_search_returns_empty_for_no_match(
    two_projects: tuple[Project, Project], db_session: Session
) -> None:
    """Search returns 0 results when no items match the query."""
    _insert_item(
        db_session,
        project_id="proj-alpha",
        item_id="I-00001",
        title="Completely unrelated title",
        content="Nothing here matches the search query at all.",
    )

    runner, get_session = _make_runner(db_session)
    result = runner.invoke(
        cli,
        ["--json", "search", "xylophone"],
        obj={"get_session": get_session},
    )
    assert result.exit_code == 0, result.output
    data = json_mod.loads(result.output)
    assert data["count"] == 0
    assert data["results"] == []


def test_search_human_output(two_projects: tuple[Project, Project], db_session: Session) -> None:
    """Human output includes item ID and title."""
    _insert_item(
        db_session,
        project_id="proj-alpha",
        item_id="I-00001",
        title="Template timeout issue",
        content="timeout when rendering large templates",
    )

    runner, get_session = _make_runner(db_session)
    result = runner.invoke(
        cli,
        ["search", "timeout"],
        obj={"get_session": get_session},
    )
    assert result.exit_code == 0, result.output
    assert "I-00001" in result.output
    assert "Template timeout issue" in result.output
