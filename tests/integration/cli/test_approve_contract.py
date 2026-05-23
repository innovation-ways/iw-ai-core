"""Contract tests for `iw approve` against a real PostgreSQL testcontainer.

Tests the full contract: exit codes, stdout shape, DB row effects, and
the evidence-ingestion hook (pre-phase) triggered on approve.

All tests use the testcontainer db_session fixture — never the live DB.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from orch.cli.main import cli
from orch.db.models import (
    EvidencePhase,
    Project,
    WorkItem,
    WorkItemEvidence,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from subprocess import CompletedProcess

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


def seed_draft_item(
    db_session: Session,
    project_id: str,
    item_id: str,
    item_type: WorkItemType = WorkItemType.Feature,
) -> None:
    """Seed a draft work item."""
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
        status=WorkItemStatus.draft,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        impacted_paths=[],
    )
    db_session.add(item)
    db_session.flush()


# ---------------------------------------------------------------------------
# Success paths
# ---------------------------------------------------------------------------


def test_approve_draft_to_approved_transitions_status(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: approving a draft item transitions status → approved, phase unchanged."""
    seed_draft_item(db_session, test_project.id, "F-00001")

    runner = CliRunner()
    result = invoke(runner, ["approve", "F-00001"], cli_get_session)

    assert result.exit_code == 0, f"stderr: {result.stderr}\nstdout: {result.output}"

    item = db_session.get(WorkItem, (test_project.id, "F-00001"))
    assert item is not None
    assert item.status == WorkItemStatus.approved


def test_approve_json_output_shape(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0 with --json: stdout is valid JSON with documented fields."""
    seed_draft_item(db_session, test_project.id, "F-00002")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project", test_project.id, "--json", "approve", "F-00002"],
        obj={"get_session": cli_get_session},
        catch_exceptions=False,
    )

    assert result.exit_code == 0, f"stderr: {result.stderr}"
    data = json.loads(result.output)
    assert data["project_id"] == test_project.id
    assert data["id"] == "F-00002"
    assert data["status"] == "approved"


def test_approve_updates_updated_at(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 0: updated_at is refreshed on approve."""

    seed_draft_item(db_session, test_project.id, "F-00003")
    item_before = db_session.get(WorkItem, (test_project.id, "F-00003"))
    old_updated = item_before.updated_at

    runner = CliRunner()
    result = invoke(runner, ["approve", "F-00003"], cli_get_session)
    assert result.exit_code == 0

    db_session.expire(item_before)
    item_after = db_session.get(WorkItem, (test_project.id, "F-00003"))
    assert item_after.updated_at > old_updated


# ---------------------------------------------------------------------------
# Evidence-ingestion hook (approve → pre-phase)
# ---------------------------------------------------------------------------


def test_approve_evidence_ingestion_pre_phase_subprocess(
    db_engine: object,
    pg_container: object,
    tmp_path: Path,
    iw_subprocess: Callable[..., CompletedProcess[str]],
) -> None:
    """Approve ingests evidence files from ai-dev/active/<id>/evidences/pre/
    into work_item_evidences (EvidencePhase.pre).

    This test runs the CLI as a subprocess to exercise the full evidence pipeline.
    Deliberately does NOT take the ``test_project`` fixture — that fixture inserts
    ``test-proj`` inside the still-open ``db_session`` transaction, and this test
    re-seeds the same project id on a separate ``db_engine`` connection; the
    duplicate primary key would block forever on the unresolved transaction.
    """
    project_id = "test-proj"
    item_id = "F-00004"

    # Build pre-evidence tree
    pre_dir = tmp_path / "ai-dev" / "active" / item_id / "evidences" / "pre"
    pre_dir.mkdir(parents=True)

    evidence_file = pre_dir / "pre-check.txt"
    evidence_file.write_text("Pre-approval evidence content")

    # Seed DB
    from orch.db.models import WorkItemPhase, WorkItemStatus, WorkItemType

    sm = sessionmaker(bind=db_engine)

    with sm() as session:
        session.add(Project(id=project_id, display_name="Test", repo_root=str(tmp_path), config={}))
        session.flush()
        session.add(
            WorkItem(
                project_id=project_id,
                id=item_id,
                type=WorkItemType.Feature,
                title=f"Test {item_id}",
                status=WorkItemStatus.draft,
                phase=WorkItemPhase.active,
                config={},
                depends_on=[],
                blocks=[],
                impacted_paths=[],
            )
        )
        session.commit()

    result = iw_subprocess(["approve", item_id], project_id, tmp_path)

    assert result.returncode == 0, (
        f"approve failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # Verify pre-evidence was ingested
    with sm() as session:
        ev = session.execute(
            select(WorkItemEvidence).where(
                WorkItemEvidence.project_id == project_id,
                WorkItemEvidence.work_item_id == item_id,
                WorkItemEvidence.phase == EvidencePhase.pre,
            )
        ).scalar_one_or_none()
        assert ev is not None, "pre-phase evidence was not ingested"
        assert ev.filename == "pre-check.txt"
        assert b"Pre-approval" in ev.content


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_approve_unknown_item_exit_1(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 1 + clear stderr: item not found."""
    runner = CliRunner()
    result = invoke(runner, ["approve", "I-DOES-NOT-EXIST"], cli_get_session)
    assert result.exit_code == 1
    assert "not found" in (result.stderr or "").lower()


def test_approve_non_draft_item_exit_1(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 1 + clear stderr: cannot approve a non-draft item."""
    seed_draft_item(db_session, test_project.id, "F-00005")
    # First approve it
    runner = CliRunner()
    first = invoke(runner, ["approve", "F-00005"], cli_get_session)
    assert first.exit_code == 0

    # Try approve again
    second = invoke(runner, ["approve", "F-00005"], cli_get_session)
    assert second.exit_code == 1
    assert "cannot approve" in (second.stderr or "").lower()


def test_approve_research_item_exit_1(
    db_session: Session,
    test_project: ProjectModel,
    cli_get_session: object,
) -> None:
    """Exit 1 + clear stderr: research items cannot be approved."""
    seed_draft_item(db_session, test_project.id, "R-00001", WorkItemType.Research)

    runner = CliRunner()
    result = invoke(runner, ["approve", "R-00001"], cli_get_session)
    assert result.exit_code != 0
    output = result.stderr or result.output
    assert "research" in output.lower()
