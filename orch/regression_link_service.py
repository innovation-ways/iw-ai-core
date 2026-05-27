"""Regression-link service and heuristic suggester for F-00090.

Single write path for regression classification.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session  # noqa: TC002  needed at runtime for type annotations

from orch.db.models import RegressionClassification, WorkItem, WorkItemStatus

log = logging.getLogger(__name__)

# Pattern matching work-item IDs in git commit messages (daemon squash-merge stamps)
_WORK_ITEM_ID_PATTERN = re.compile(r"\b(F-\d{5}|I-\d{5}|CR-\d{5})\b", re.IGNORECASE)


@dataclass
class Candidate:
    """A candidate work item that may have introduced a regression.

    Attributes
    ----------
    commit_sha:
        The full SHA of the candidate commit.
    work_item_id:
        The work-item ID resolved from the commit message, or None if no
        F-NNNNN / I-NNNNN / CR-NNNNN pattern was found.
    score:
        Number of files that the incident's fix touched AND that this candidate
        also touched (aggregate across the fix's file list).
    """

    commit_sha: str
    work_item_id: str | None
    score: int


def classify(
    session: Session,
    *,
    project_id: str,
    item_id: str,
    introduced_by_work_item_id: str | None,
    introduced_by_commit_sha: str | None,
    classification: RegressionClassification,
    classified_by: str,
) -> WorkItem:
    """Classify an Incident against the work item (or SHA) that introduced the regression.

    Validates:
    - The target Incident exists in the given project.
    - ``introduced_by_work_item_id`` is not a cross-project reference.
    - ``introduced_by_work_item_id`` references a merged (done) work item
      when one is supplied.

    Persists the five regression-link columns on the WorkItem row and returns
    the refreshed row so the caller can inspect the post-commit values.

    Raises
    ------
    ValueError
        When cross-project FK or unmerged target is detected.
    LookupError
        When the incident does not exist in the named project.
    """
    item = session.execute(
        select(WorkItem).where(WorkItem.project_id == project_id, WorkItem.id == item_id)
    ).scalar_one_or_none()
    if item is None:
        raise LookupError(f"Work item {item_id} not found in project {project_id}")

    if introduced_by_work_item_id is not None:
        target = session.execute(
            select(WorkItem).where(
                WorkItem.project_id == project_id,
                WorkItem.id == introduced_by_work_item_id,
            )
        ).scalar_one_or_none()
        if target is None:
            raise ValueError(
                f"introduced_by_work_item_id '{introduced_by_work_item_id}' "
                f"does not exist in project {project_id}"
            )
        if target.status != WorkItemStatus.completed:
            raise ValueError(
                f"introduced_by_work_item_id '{introduced_by_work_item_id}' "
                f"has status '{target.status.value}'; only merged (completed) "
                f"work items may be regression sources"
            )

    item.introduced_by_work_item_id = introduced_by_work_item_id
    item.introduced_by_commit_sha = introduced_by_commit_sha
    item.regression_classification = classification
    item.classified_at = datetime.now(UTC)
    item.classified_by = classified_by

    session.flush()
    session.refresh(item)
    return item


def suggest_introducer(
    session: Session,
    *,
    project_id: str,
    item_id: str,
    repo_path: Path | None = None,
) -> list[Candidate]:
    """Suggest the most-likely work items that introduced a regression for an Incident.

    File-discovery contract (non-negotiable):
    1. Load the Incident row.  If ``status != 'done'`` or there is no merge SHA,
       return ``[]`` immediately and log at INFO level (no git invocation).
    2. Given the merge SHA, derive the fix's file list via
       ``git show --name-only --pretty=format: <sha>``.  Filter out empty
       lines.  If the command fails or returns no files, return ``[]``.
    3. For each file, run ``git log -n 50 --pretty=format:%H -- <file>`` to
       enumerate the 50 most-recent commits that touched it (excluding the
       Incident's own merge SHA).  Aggregate counts across files — the score
       for a candidate SHA is the number of fix-files it touched.
    4. For each candidate SHA, resolve to a work_item_id by scanning the commit
       message for ``F-NNNNN`` / ``I-NNNNN`` / ``CR-NNNNN`` patterns (this is
       how the daemon's squash merges are stamped).  Candidates resolving to a
       work item in a *different* project are dropped (cross-project FKs are
       rejected at write time anyway).
    5. Return the top-10 candidates sorted by ``(score DESC, recency DESC)``.
    """
    repo = repo_path or Path.cwd()

    item = session.execute(
        select(WorkItem).where(WorkItem.project_id == project_id, WorkItem.id == item_id)
    ).scalar_one_or_none()

    if item is None:
        return []

    if item.status != WorkItemStatus.completed:
        log.info("suggest_introducer: %s not merged yet; no file list available", item_id)
        return []

    merge_sha = item.merge_commit_sha
    if not merge_sha:
        log.info(
            "suggest_introducer: %s has no merge_commit_sha recorded; no file list available",
            item_id,
        )
        return []

    # Step 2: get fix file list from merge commit
    try:
        fix_files_out = subprocess.run(
            ["git", "show", "--name-only", f"--pretty=format:{merge_sha}", merge_sha],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    fix_files = [line.strip() for line in fix_files_out.stdout.splitlines() if line.strip()]
    if not fix_files:
        return []

    # Step 3: enumerate candidate SHAs across fix files
    file_counts: dict[str, int] = {}
    for file in fix_files:
        try:
            log_out = subprocess.run(
                ["git", "log", "-n", "50", "--pretty=format:%H", "--", file],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue

        for sha in log_out.stdout.splitlines():
            sha = sha.strip()
            if sha and sha != merge_sha:
                file_counts[sha] = file_counts.get(sha, 0) + 1

    if not file_counts:
        return []

    # Step 4: resolve work_item_id per candidate and filter cross-project ones
    candidates: list[Candidate] = []
    for sha, score in file_counts.items():
        work_item_id: str | None = None
        try:
            msg_out = subprocess.run(
                ["git", "show", "-s", "--pretty=format:%B", sha],
                cwd=repo,
                capture_output=True,
                text=True,
                check=True,
            )
            match = _WORK_ITEM_ID_PATTERN.search(msg_out.stdout)
            if match:
                work_item_id = match.group(0)
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass

        if work_item_id is not None:
            # Check if the resolved work item belongs to this project
            resolved = session.execute(
                select(WorkItem).where(
                    WorkItem.project_id == project_id,
                    WorkItem.id == work_item_id,
                )
            ).scalar_one_or_none()
            if resolved is None:
                # Cross-project or non-existent → skip
                continue

        candidates.append(Candidate(commit_sha=sha, work_item_id=work_item_id, score=score))

    # Step 5: sort and truncate
    candidates.sort(key=lambda c: (c.score, c.commit_sha), reverse=True)
    return candidates[:10]
