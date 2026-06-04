"""Integration tests for the archive system.

Uses a real PostgreSQL testcontainer. Verifies full Tier 1 + Tier 2 archive flow,
FTS search on archived content, and the iw archive CLI command.
"""

from __future__ import annotations

import json as json_mod
import tarfile
from contextlib import contextmanager
from typing import TYPE_CHECKING

import pytest
import zstandard as zstd
from click.testing import CliRunner
from sqlalchemy import text

from orch.archive.archiver import archive_all_completed, archive_work_item
from orch.cli.main import cli
from orch.db.models import (
    Project,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path

    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    return tmp_path / "repo"


@pytest.fixture
def archive_dir(tmp_path: Path) -> Path:
    return tmp_path / "archives"


@pytest.fixture
def test_project_with_root(db_session: Session, repo_root: Path) -> Project:  # noqa: assertion-scanner
    """A project row pointing at a real tmp directory."""
    repo_root.mkdir(parents=True)
    project = Project(
        id="test-proj",
        display_name="Test Project",
        repo_root=str(repo_root),
        config={},
    )
    db_session.add(project)
    db_session.flush()
    return project


def _make_completed_item(
    session: Session,
    project_id: str,
    item_id: str,
    *,
    design_doc_path: str | None = None,
) -> WorkItem:
    wi = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Issue,
        title=f"Work item {item_id}",
        status=WorkItemStatus.completed,
        phase=WorkItemPhase.active,
        config={},
        depends_on=[],
        blocks=[],
        design_doc_path=design_doc_path,
    )
    session.add(wi)
    session.flush()
    return wi


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_full_archive_flow(
    db_session: Session,
    test_project_with_root: Project,
    repo_root: Path,
    archive_dir: Path,
) -> None:
    """Full flow: create work item with files, archive it, verify DB + .tar.zst."""
    project_id = test_project_with_root.id

    doc_path = repo_root / "I001_Design.md"
    doc_path.write_text("# Design Doc\nThis fixes the timeout.", encoding="utf-8")

    work_item_dir = repo_root / "ai-dev" / "design" / "active" / "I-00001"
    work_item_dir.mkdir(parents=True)
    (work_item_dir / "I001_Design.md").write_text("# Design Doc", encoding="utf-8")
    prompts_dir = work_item_dir / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "S01_prompt.md").write_text("Do the work", encoding="utf-8")

    wi = _make_completed_item(db_session, project_id, "I-00001", design_doc_path="I001_Design.md")

    archive_work_item(db_session, project_id, "I-00001", archive_dir=archive_dir, cleanup=True)

    db_session.refresh(wi)
    assert wi.design_doc_content == "# Design Doc\nThis fixes the timeout."
    assert wi.phase == WorkItemPhase.done
    assert wi.archived_at is not None

    assert wi.archive_path == f"{project_id}/I-00001.tar.zst"
    assert wi.archive_size_bytes is not None
    assert wi.archive_size_bytes > 0

    expected_archive = archive_dir / project_id / "I-00001.tar.zst"
    assert expected_archive.exists()

    dctx = zstd.ZstdDecompressor()
    with (
        expected_archive.open("rb") as f_in,
        dctx.stream_reader(f_in) as reader,
        tarfile.open(fileobj=reader, mode="r|") as tar,  # type: ignore[arg-type]
    ):
        names = tar.getnames()
    assert any("I001_Design.md" in n for n in names)
    assert any("S01_prompt.md" in n for n in names)

    assert not work_item_dir.exists()


def test_archive_stores_step_reports(
    db_session: Session,
    test_project_with_root: Project,
    repo_root: Path,
    archive_dir: Path,
) -> None:
    """archive_work_item stores step report_content in DB (Tier 1)."""
    project_id = test_project_with_root.id

    _make_completed_item(db_session, project_id, "I-00001")

    report_path = repo_root / "reports" / "S01_report.md"
    report_path.parent.mkdir(parents=True)
    report_path.write_text("## Step 1 Report\nAll good.", encoding="utf-8")

    step = WorkflowStep(
        project_id=project_id,
        work_item_id="I-00001",
        step_number=1,
        step_id="S01",
        agent_label="Backend",
        step_type=StepType.implementation,
        status=StepStatus.completed,
        report_file="reports/S01_report.md",
    )
    db_session.add(step)
    db_session.flush()

    archive_work_item(db_session, project_id, "I-00001", archive_dir=None)

    db_session.refresh(step)
    assert step.report_content == "## Step 1 Report\nAll good."


def test_archive_all_completed(
    db_session: Session,
    test_project_with_root: Project,
    repo_root: Path,
    archive_dir: Path,
) -> None:
    """archive_all_completed archives every completed+unarchived item."""
    project_id = test_project_with_root.id

    for item_id in ("I-00001", "I-00002"):
        _make_completed_item(db_session, project_id, item_id)

    archived = archive_all_completed(db_session, project_id, archive_dir=None)

    assert set(archived) == {"I-00001", "I-00002"}

    wi1 = db_session.get(WorkItem, (project_id, "I-00001"))
    wi2 = db_session.get(WorkItem, (project_id, "I-00002"))
    assert wi1 is not None
    assert wi1.archived_at is not None
    assert wi2 is not None
    assert wi2.archived_at is not None


def test_archive_idempotent(
    db_session: Session,
    test_project_with_root: Project,
    repo_root: Path,
    archive_dir: Path,
) -> None:
    """Calling archive_work_item twice does not raise and only Tier 2-archives once."""
    project_id = test_project_with_root.id
    work_item_dir = repo_root / "ai-dev" / "design" / "active" / "I-00001"
    work_item_dir.mkdir(parents=True)
    (work_item_dir / "f.txt").write_text("x")

    _make_completed_item(db_session, project_id, "I-00001")

    archive_work_item(db_session, project_id, "I-00001", archive_dir=archive_dir, cleanup=False)
    wi = db_session.get(WorkItem, (project_id, "I-00001"))
    assert wi is not None
    first_path = wi.archive_path

    archive_work_item(db_session, project_id, "I-00001", archive_dir=archive_dir, cleanup=False)
    db_session.refresh(wi)

    assert wi.archive_path == first_path


def test_archive_includes_and_removes_work_folder(
    db_session: Session,
    test_project_with_root: Project,
    repo_root: Path,
    archive_dir: Path,
) -> None:
    """archive_work_item compresses and removes ai-dev/work/<id>/ (reports, self-assess)."""
    project_id = test_project_with_root.id

    active_dir = repo_root / "ai-dev" / "active" / "I-00001"
    active_dir.mkdir(parents=True)
    (active_dir / "I-00001_design.md").write_text("# Design", encoding="utf-8")

    work_reports = repo_root / "ai-dev" / "work" / "I-00001" / "reports"
    work_reports.mkdir(parents=True)
    (work_reports / "I-00001_S08_SelfAssess_findings.json").write_text("{}", encoding="utf-8")

    _make_completed_item(
        db_session,
        project_id,
        "I-00001",
        design_doc_path="ai-dev/active/I-00001/I-00001_design.md",
    )

    archive_work_item(db_session, project_id, "I-00001", archive_dir=archive_dir, cleanup=True)

    work_dir = repo_root / "ai-dev" / "work" / "I-00001"
    assert not active_dir.exists()
    assert not work_dir.exists()

    archive_path = archive_dir / project_id / "I-00001.tar.zst"
    dctx = zstd.ZstdDecompressor()
    with (
        archive_path.open("rb") as f_in,
        dctx.stream_reader(f_in) as reader,
        tarfile.open(fileobj=reader, mode="r|") as tar,  # type: ignore[arg-type]
    ):
        names = tar.getnames()
    assert any(n.endswith("I-00001_S08_SelfAssess_findings.json") for n in names)


def test_fts_finds_archived_item(
    db_session: Session,
    test_project_with_root: Project,
    repo_root: Path,
    archive_dir: Path,
) -> None:
    """After archiving, FTS search finds items by content stored in Tier 1."""
    project_id = test_project_with_root.id

    doc = repo_root / "I001_Design.md"
    doc.write_text("The WeasyPrint timeout issue causes slow invoice rendering.", encoding="utf-8")

    _make_completed_item(db_session, project_id, "I-00001", design_doc_path="I001_Design.md")
    archive_work_item(db_session, project_id, "I-00001", archive_dir=None)
    db_session.flush()

    results = db_session.execute(
        text(
            "SELECT id FROM work_items "
            "WHERE project_id = :pid "
            "AND to_tsvector('english', coalesce(design_doc_content, '')) "
            "@@ to_tsquery('english', 'WeasyPrint')"
        ),
        {"pid": project_id},
    ).fetchall()

    assert len(results) == 1
    assert results[0][0] == "I-00001"


def test_cli_archive_command(
    db_session: Session,
    test_project_with_root: Project,
    repo_root: Path,
    archive_dir: Path,
) -> None:
    """iw archive <item_id> archives via CLI with Tier 1 + Tier 2."""
    project_id = test_project_with_root.id

    work_item_dir = repo_root / "ai-dev" / "design" / "active" / "I-00001"
    work_item_dir.mkdir(parents=True)
    (work_item_dir / "design.md").write_text("content", encoding="utf-8")

    _make_completed_item(db_session, project_id, "I-00001")

    @contextmanager  # type: ignore[arg-type]
    def get_session() -> Generator[Session, None, None]:
        yield db_session

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--json",
            "--project",
            project_id,
            "archive",
            "I-00001",
            "--archive-dir",
            str(archive_dir),
        ],
        obj={"get_session": get_session},
    )

    assert result.exit_code == 0, result.output
    data = json_mod.loads(result.output)
    assert data["archived"] == ["I-00001"]
    assert data["count"] == 1

    wi = db_session.get(WorkItem, (project_id, "I-00001"))
    assert wi is not None
    assert wi.archived_at is not None
    assert wi.phase == WorkItemPhase.done
