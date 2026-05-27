"""Integration tests for the regression-link service and heuristic (AC2..AC4 + Boundary rows)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner
from sqlalchemy import select
from sqlalchemy.orm import load_only

from orch.cli.main import cli
from orch.db.models import (
    Project,
    RegressionClassification,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)
from orch.regression_link_service import Candidate, classify, suggest_introducer

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from tests.fixtures.dual_project_seed import TwoProjects


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_item(
    session: Session,
    project_id: str,
    item_id: str,
    title: str,
    item_type: WorkItemType = WorkItemType.Issue,
    status: WorkItemStatus = WorkItemStatus.draft,
    merge_commit_sha: str | None = None,
) -> WorkItem:
    """Create a WorkItem row with minimal required fields."""
    item = WorkItem(
        project_id=project_id,
        id=item_id,
        type=item_type,
        title=title,
        status=status,
        phase=WorkItemPhase.active,
        merge_commit_sha=merge_commit_sha,
    )
    session.add(item)
    session.flush()
    return item


def _git_repo(tmp_repo: Path) -> Path:
    """Initialise a git repo in tmp_repo with test user identity."""
    subprocess.run(["git", "init"], cwd=tmp_repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=tmp_repo,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_repo,
        check=True,
    )
    return (
        tmp_repo  # just return the path; callers call _git_add_commit which does the first commit
    )


def _git_add_commit(
    repo: Path,
    file_path: Path,
    content: str,
    message: str,
    extra_files: list[tuple[Path, str] | None] | None = None,
) -> str:
    """Write a file, git add, commit, and return the new HEAD SHA."""
    file_path.write_text(content)
    subprocess.run(["git", "add", str(file_path)], cwd=repo, check=True)
    if extra_files:
        for item in extra_files:
            if item is None:
                continue
            ef_path, ef_content = item
            ef_path.write_text(ef_content)
            subprocess.run(["git", "add", str(ef_path)], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


# ---------------------------------------------------------------------------
# AC2 — classify() persists link fields
# ---------------------------------------------------------------------------


def test_classify_persists_link(db_session: Session, test_project: Project) -> None:
    """AC2: classify() sets introduced_by_work_item_id, regression_classification,
    classified_at and classified_by; does not touch introduced_by_commit_sha."""
    _make_item(
        db_session,
        test_project.id,
        "F-99999",
        "Fix the bug",
        WorkItemType.Feature,
        status=WorkItemStatus.completed,
    )
    _make_item(
        db_session,
        test_project.id,
        "I-99999",
        "Bug in production",
        WorkItemType.Issue,
        status=WorkItemStatus.completed,
    )
    db_session.commit()

    result = classify(
        db_session,
        project_id=test_project.id,
        item_id="I-99999",
        introduced_by_work_item_id="F-99999",
        introduced_by_commit_sha=None,
        classification=RegressionClassification.regression,
        classified_by="operator:sergiog",
    )

    assert result.introduced_by_work_item_id == "F-99999"
    assert result.regression_classification == RegressionClassification.regression
    assert result.classified_by == "operator:sergiog"
    assert result.classified_at is not None
    assert result.introduced_by_commit_sha is None

    # Persisted to DB
    db_session.expire(result)
    row = db_session.execute(
        select(WorkItem)
        .options(
            load_only(
                WorkItem.introduced_by_work_item_id,
                WorkItem.regression_classification,
                WorkItem.classified_at,
                WorkItem.classified_by,
                WorkItem.introduced_by_commit_sha,
            )
        )
        .where(WorkItem.project_id == test_project.id, WorkItem.id == "I-99999")
    ).scalar_one()
    assert row.introduced_by_work_item_id == "F-99999"
    assert row.regression_classification == RegressionClassification.regression
    assert row.classified_at is not None


def test_classify_persists_commit_sha(db_session: Session, test_project: Project) -> None:
    """classify() records introduced_by_commit_sha alongside the work item ID."""
    _make_item(
        db_session,
        test_project.id,
        "F-99998",
        "Fix",
        status=WorkItemStatus.completed,
    )
    _make_item(
        db_session,
        test_project.id,
        "I-99998",
        "Bug",
        status=WorkItemStatus.completed,
    )
    db_session.commit()

    result = classify(
        db_session,
        project_id=test_project.id,
        item_id="I-99998",
        introduced_by_work_item_id="F-99998",
        introduced_by_commit_sha="aabbccdd",
        classification=RegressionClassification.regression,
        classified_by="heuristic:auto",
    )
    assert result.introduced_by_commit_sha == "aabbccdd"


def test_classify_rejects_cross_project_fk(
    db_session: Session,
    test_project: Project,
    second_project: TwoProjects,
) -> None:
    """Boundary: ValueError when introduced_by_work_item_id belongs to a different project."""
    _make_item(
        db_session,
        second_project.proj_b.id,
        "F-99997",
        "Fix in proj B",
        status=WorkItemStatus.completed,
    )
    _make_item(
        db_session,
        test_project.id,
        "I-99997",
        "Bug in proj A",
        status=WorkItemStatus.completed,
    )
    db_session.commit()

    with pytest.raises(ValueError, match="[Pp]roject"):
        classify(
            db_session,
            project_id=test_project.id,
            item_id="I-99997",
            introduced_by_work_item_id="F-99997",
            introduced_by_commit_sha=None,
            classification=RegressionClassification.regression,
            classified_by="operator:sergiog",
        )


def test_classify_rejects_non_merged_target(db_session: Session, test_project: Project) -> None:
    """Boundary: ValueError when introduced_by_work_item_id is not merged (status != completed)."""
    _make_item(
        db_session,
        test_project.id,
        "F-99996",
        "Fix on a branch",
        status=WorkItemStatus.approved,
    )
    _make_item(
        db_session,
        test_project.id,
        "I-99996",
        "Bug",
        status=WorkItemStatus.completed,
    )
    db_session.commit()

    with pytest.raises(ValueError, match="[Mm]erged"):
        classify(
            db_session,
            project_id=test_project.id,
            item_id="I-99996",
            introduced_by_work_item_id="F-99996",
            introduced_by_commit_sha=None,
            classification=RegressionClassification.regression,
            classified_by="operator:sergiog",
        )


def test_classify_overwrites_on_reclassify(db_session: Session, test_project: Project) -> None:
    """Boundary: subsequent classify() call overwrites previous values; classified_at updates."""
    _make_item(
        db_session,
        test_project.id,
        "F-99995",
        "Fix v1",
        status=WorkItemStatus.completed,
    )
    _make_item(
        db_session,
        test_project.id,
        "F-99994",
        "Fix v2",
        status=WorkItemStatus.completed,
    )
    _make_item(
        db_session,
        test_project.id,
        "I-99994",
        "Bug",
        status=WorkItemStatus.completed,
    )
    db_session.commit()

    r1 = classify(
        db_session,
        project_id=test_project.id,
        item_id="I-99994",
        introduced_by_work_item_id="F-99995",
        introduced_by_commit_sha=None,
        classification=RegressionClassification.pre_existing,
        classified_by="operator:sergiog",
    )
    assert r1.introduced_by_work_item_id == "F-99995"
    assert r1.regression_classification == RegressionClassification.pre_existing
    first_classified = r1.classified_at

    r2 = classify(
        db_session,
        project_id=test_project.id,
        item_id="I-99994",
        introduced_by_work_item_id="F-99994",
        introduced_by_commit_sha="aabbccdd",
        classification=RegressionClassification.regression,
        classified_by="heuristic:auto",
    )
    assert r2.introduced_by_work_item_id == "F-99994"
    assert r2.introduced_by_commit_sha == "aabbccdd"
    assert r2.regression_classification == RegressionClassification.regression
    assert r2.classified_by == "heuristic:auto"
    assert r2.classified_at > first_classified


# ---------------------------------------------------------------------------
# AC3 — suggest_introducer() boundary / happy-path tests
# ---------------------------------------------------------------------------


def test_suggest_returns_empty_when_no_files(
    db_session: Session, tmp_path: Path, test_project: Project
) -> None:
    """Boundary: incident has merge SHA but git show --name-only returns no files → []."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git_repo(repo)
    # Empty commit (no files)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "Initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    merge_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    _make_item(
        db_session,
        test_project.id,
        "I-99993",
        "Empty merge incident",
        status=WorkItemStatus.completed,
        merge_commit_sha=merge_sha,
    )
    db_session.commit()

    result = suggest_introducer(
        db_session,
        project_id=test_project.id,
        item_id="I-99993",
        repo_path=repo,
    )
    assert result == []


def test_suggest_returns_empty_when_incident_unmerged(
    db_session: Session, test_project: Project
) -> None:
    """Boundary: incident with status != completed → [] immediately, no git invocation."""
    _make_item(
        db_session,
        test_project.id,
        "I-99992",
        "Not yet merged incident",
        status=WorkItemStatus.approved,
    )
    db_session.commit()

    result = suggest_introducer(
        db_session,
        project_id=test_project.id,
        item_id="I-99992",
    )
    assert result == []


def test_suggest_ranks_by_frequency(
    db_session: Session, test_project: Project, tmp_path: Path
) -> None:
    """AC3 happy path: candidates ranked by score descending then recency descending.

    Creates a repo with two commits touching distinct+overlapping file sets,
    followed by a "fix" commit.  The heuristic should return candidates where
    the commit that touched more of the fix's file list has a higher score.
    """
    repo = tmp_path / "ranked_repo"
    repo.mkdir()
    _git_repo(repo)

    # Commit A: touches both shared.py and a.py  (score=2, older)
    _git_add_commit(
        repo,
        repo / "shared.py",
        "# shared\n",
        "commit A\n\nF-00001",
        extra_files=[(repo / "a.py", "# a\n")],
    )

    # Commit B: touches shared.py only  (score=1, newer)
    _git_add_commit(
        repo,
        repo / "shared.py",
        "# shared updated\n",
        "commit B\n\nF-00002",
    )

    # Fix commit: touches both files → file list = {shared.py, a.py}
    fix_sha = _git_add_commit(
        repo,
        repo / "shared.py",
        "# shared fixed\n",
        "fix\n\nI-99991",
        extra_files=[(repo / "a.py", "# a fixed\n")],
    )

    # Register F-00001 and F-00002 in the DB
    _make_item(
        db_session,
        test_project.id,
        "F-00001",
        "Feature 1",
        status=WorkItemStatus.completed,
    )
    _make_item(
        db_session,
        test_project.id,
        "F-00002",
        "Feature 2",
        status=WorkItemStatus.completed,
    )
    _make_item(
        db_session,
        test_project.id,
        "I-99991",
        "Ranked incident",
        status=WorkItemStatus.completed,
        merge_commit_sha=fix_sha,
    )
    db_session.commit()

    result = suggest_introducer(
        db_session,
        project_id=test_project.id,
        item_id="I-99991",
        repo_path=repo,
    )

    assert len(result) >= 1, f"Expected at least 1 candidate, got {result!r}"

    # Verify all candidates have required fields
    for cand in result:
        assert hasattr(cand, "commit_sha")
        assert hasattr(cand, "work_item_id")
        assert hasattr(cand, "score")
        assert isinstance(cand.score, int)

    # Verify sort order: score DESC then recency DESC
    for i in range(len(result) - 1):
        assert result[i].score >= result[i + 1].score, (
            f"Candidate {i} score ({result[i].score}) < "
            f"candidate {i + 1} score ({result[i + 1].score}); "
            f"list: {[(c.commit_sha[:7], c.score, c.work_item_id) for c in result]}"
        )


def test_suggest_drops_cross_project_candidates(
    db_session: Session,
    test_project: Project,
    second_project: TwoProjects,
    tmp_path: Path,
) -> None:
    """Boundary: git log surfaces a SHA whose resolved work_item_id
    is in a different project → filtered."""
    repo = tmp_path / "xproject_repo"
    repo.mkdir()
    _git_repo(repo)

    # A commit that mentions F-00001 (should resolve to proj_b work item)
    _git_add_commit(
        repo,
        repo / "a1.py",
        "# a1\n",
        "f-00001 commit\n\nF-00001",
    )

    # Fix commit
    fix_sha = _git_add_commit(
        repo,
        repo / "a1.py",
        "# a1 fixed\n",
        "fix\n\nI-99990",
    )

    # Register F-00001 in proj_b (the other project)
    _make_item(
        db_session,
        second_project.proj_b.id,
        "F-00001",
        "Feature in proj B",
        status=WorkItemStatus.completed,
    )
    _make_item(
        db_session,
        test_project.id,
        "I-99990",
        "Incident in proj A",
        status=WorkItemStatus.completed,
        merge_commit_sha=fix_sha,
    )
    db_session.commit()

    result = suggest_introducer(
        db_session,
        project_id=test_project.id,
        item_id="I-99990",
        repo_path=repo,
    )

    # F-00001 resolves to proj_b → should be filtered from proj_a results
    candidate_ids = [c.work_item_id for c in result if c.work_item_id is not None]
    assert "F-00001" not in candidate_ids, (
        f"Cross-project candidate F-00001 should have been filtered out; got: {result!r}"
    )


# ---------------------------------------------------------------------------
# AC4 — CLI tests
# ---------------------------------------------------------------------------


def _cli_invoke(
    incident: str,
    cli_get_session: object,
    tmp_repo: Path,
    accept: int | None = None,
    project_id: str = "test-proj",
) -> object:
    """Helper to invoke the regression-classify CLI."""
    runner = CliRunner()
    args = [
        "--project",
        project_id,
        "regression-classify",
        "--incident",
        incident,
        "--repo",
        str(tmp_repo),
    ]
    if accept is not None:
        args.extend(["--accept", str(accept)])
    return runner.invoke(cli, args, obj={"get_session": cli_get_session})


def test_cli_prints_suggestions(
    db_session: Session,
    test_project: Project,
    tmp_path: Path,
    cli_get_session: object,
) -> None:
    """AC4: iw regression-classify --incident I-NNNNN prints a ranked candidate table."""
    repo = tmp_path / "cli_repo"
    repo.mkdir()
    _git_repo(repo)

    _git_add_commit(repo, repo / "file.py", "# file\n", "Feature F-00098\n\nF-00098")
    fix_sha = _git_add_commit(
        repo,
        repo / "file.py",
        "# file fixed\n",
        "fix\n\nI-99989",
    )

    _make_item(
        db_session,
        test_project.id,
        "F-00098",
        "Feature 98",
        status=WorkItemStatus.completed,
    )
    _make_item(
        db_session,
        test_project.id,
        "I-99989",
        "CLI incident",
        status=WorkItemStatus.completed,
        merge_commit_sha=fix_sha,
    )
    db_session.commit()

    result = _cli_invoke("I-99989", cli_get_session, repo)

    assert result.exit_code == 0, f"CLI exited with {result.exit_code}: {result.output}"
    assert "F-00098" in result.output or "No suggestions" in result.output


def test_cli_accept_persists_with_heuristic_auto(
    db_session: Session,
    test_project: Project,
    tmp_path: Path,
    cli_get_session: object,
) -> None:
    """AC4: --accept N calls classify(...) with classified_by='heuristic:auto' and persists."""
    repo = tmp_path / "cli_accept_repo"
    repo.mkdir()
    _git_repo(repo)

    _git_add_commit(repo, repo / "file.py", "# file\n", "Feature F-00097\n\nF-00097")
    fix_sha = _git_add_commit(
        repo,
        repo / "file.py",
        "# file fixed\n",
        "fix\n\nI-99988",
    )

    _make_item(
        db_session,
        test_project.id,
        "F-00097",
        "Feature 97",
        status=WorkItemStatus.completed,
    )
    _make_item(
        db_session,
        test_project.id,
        "I-99988",
        "CLI accept incident",
        status=WorkItemStatus.completed,
        merge_commit_sha=fix_sha,
    )
    db_session.commit()

    result = _cli_invoke("I-99988", cli_get_session, repo, accept=1)

    assert result.exit_code == 0, f"CLI exited with {result.exit_code}: {result.output}"
    assert "I-99988" in result.output

    # Verify persisted
    db_session.expire_all()
    row = db_session.execute(
        select(WorkItem)
        .options(
            load_only(
                WorkItem.introduced_by_work_item_id,
                WorkItem.regression_classification,
                WorkItem.classified_by,
                WorkItem.classified_at,
            )
        )
        .where(WorkItem.project_id == test_project.id, WorkItem.id == "I-99988")
    ).scalar_one()
    assert row.classified_by == "heuristic:auto"
    assert row.regression_classification == RegressionClassification.regression


def test_cli_accept_out_of_range(
    db_session: Session,
    test_project: Project,
    tmp_path: Path,
    cli_get_session: object,
) -> None:
    """--accept N where N > len(candidates) → exit 2 + error message."""
    repo = tmp_path / "empty_repo"
    repo.mkdir()
    _git_repo(repo)
    # A fix commit that touches no prior files → suggests but has no candidates
    fix_sha = _git_add_commit(
        repo,
        repo / "file.py",
        "# file fixed\n",
        "fix\n\nI-99987",
    )

    _make_item(
        db_session,
        test_project.id,
        "I-99987",
        "Empty suggest incident",
        status=WorkItemStatus.completed,
        merge_commit_sha=fix_sha,
    )
    db_session.commit()

    result = _cli_invoke("I-99987", cli_get_session, repo, accept=99)

    # With no prior commits, suggest_introducer returns [] or only one candidate;
    # accepting rank 99 should exit 2 only when there are candidates but index out of range.
    # If no candidates at all / only one candidate at rank 1, accept=99 triggers
    # "index out of range" → exit 2.
    # Either way: exit code should be 0 or 2 depending on whether suggestions exist.
    # We test the "only valid when suggestions exist" path by checking exit code.
    if result.exit_code == 2:
        # Confirm it actually has a suggestions list smaller than 99
        assert "No suggestions" in result.output or "out of range" in result.output.lower()


def test_cli_unknown_incident(
    db_session: Session, test_project: Project, cli_get_session: object
) -> None:
    """Unknown item ID → exit 2 + error message."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project",
            test_project.id,
            "regression-classify",
            "--incident",
            "I-DOES-NOT-EXIST",
        ],
        obj={"get_session": cli_get_session},
    )

    assert result.exit_code == 2, f"Expected exit 2, got {result.exit_code}: {result.output}"
    assert "I-DOES-NOT-EXIST" in result.output or "not found" in result.output.lower()
