"""I-00083 — Branch-base drift regression + coverage tests.

S01 created this file with the AC1 reproduction (RED → GREEN proof for
the missing daemon drift-log-line bug).

S03 extends the file with:
  * AC3 — happy-path solo-item regression (empty-siblings log line)
  * Sibling-scope-check unit coverage (multiple siblings, merged sibling,
    non-matching glob)
  * Chore-commit allow-list coverage (non-design files left out)

Shared module-level helpers used by both S01 and S03 live near the top.
AC1's test body (`TestI00083BranchBaseDrift`) is unchanged.
"""

from __future__ import annotations

import logging
import re
import subprocess
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from orch.active_files import ensure_active_files_committed
from orch.config import DaemonConfig
from orch.daemon.batch_manager import BatchManager
from orch.daemon.project_registry import ProjectConfig
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    Project,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Module-level fake-repo helpers
# Used by AC1 (S01) and the AC3 / unit / chore-commit tests (S03).
# ---------------------------------------------------------------------------


def _make_fake_repo(tmp_path: Path) -> Path:
    """Init a git repo at tmp_path/repo with one README commit on `main`."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
        check=True,
        capture_output=True,
    )
    (repo / "README.md").write_text("initial\n")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "initial"],
        check=True,
        capture_output=True,
    )
    return repo


def _add_file_and_commit(repo: Path, rel_path: str, content: str = "test\n") -> str:
    """Write `rel_path` under `repo`, stage + commit it, return HEAD sha."""
    full = repo / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content)
    subprocess.run(["git", "-C", str(repo), "add", rel_path], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", f"add {rel_path}"],
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _simulate_chore_commit(
    repo: Path,
    item_id: str,
    extra_active_files: dict[str, str] | None = None,
) -> str:
    """Drop a realistic ai-dev/active/<id>/ tree, then run the production
    `ensure_active_files_committed` to land the narrowed chore commit.

    `extra_active_files` maps repo-relative paths (under
    ai-dev/active/<id>/) to file contents — use it to plant non-design
    files such as `notes.txt` that should NOT survive the allow-list.

    Returns the HEAD sha after the chore commit (or the prior HEAD if
    no allow-listed paths were dirty, e.g. only extras present).
    """
    active = repo / "ai-dev" / "active" / item_id
    active.mkdir(parents=True, exist_ok=True)
    # The production allow-list passes each pathspec to `git add --` as a
    # literal; pathspecs that match nothing make `git add` exit non-zero.
    # So always create every allow-listed file the production code expects.
    (active / f"{item_id}_Issue_Design.md").write_text(f"# {item_id} Design\n")
    (active / f"{item_id}_Functional.md").write_text(f"# {item_id} Functional\n")
    (active / "workflow-manifest.json").write_text('{"steps": []}\n')
    prompts = active / "prompts"
    prompts.mkdir(exist_ok=True)
    (prompts / f"{item_id}_S01_Pipeline_prompt.md").write_text(f"# {item_id} S01\n")
    if extra_active_files:
        for rel, content in extra_active_files.items():
            target = active / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)

    ensure_active_files_committed(repo, item_id, f"Test {item_id}")

    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _simulate_in_flight_impl(repo: Path, item_id: str, touches: list[str]) -> str:
    """Land impl-style edits on `main` to mimic a sibling's tests/fixtures
    that arrived via someone else's prior squash merge.

    Each path in `touches` is created and committed under a single
    "impl: <item_id>" commit. Returns the resulting HEAD sha.
    """
    for rel in touches:
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"# {item_id} impl drift\n")
        subprocess.run(["git", "-C", str(repo), "add", rel], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", f"impl: {item_id}"],
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit_contains(repo: Path, sha: str, rel_path: str) -> bool:
    """Return True iff `rel_path` is present in the tree at `sha`."""
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-tree", "-r", "--name-only", sha],
        check=True,
        capture_output=True,
        text=True,
    )
    return rel_path in result.stdout.splitlines()


# ---------------------------------------------------------------------------
# DB row helpers (mirrors the pattern in test_batch_manager_scope_gate.py)
# ---------------------------------------------------------------------------


def _unique_id(prefix: str = "I-00083") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


def _create_work_item(
    db: Session,
    project_id: str,
    item_id: str,
    impacted_paths: list[str] | None = None,
    merge_commit_sha: str | None = None,
) -> WorkItem:
    wi = WorkItem(
        project_id=project_id,
        id=item_id,
        type=WorkItemType.Feature,
        title=f"Test {item_id}",
        status=WorkItemStatus.approved,
        phase=WorkItemPhase.active,
        impacted_paths=impacted_paths or [],
        config={},
        depends_on=[],
        blocks=[],
        merge_commit_sha=merge_commit_sha,
    )
    db.add(wi)
    db.flush()
    return wi


def _create_batch_and_item(
    db: Session,
    project_id: str,
    work_item_id: str,
    batch_item_status: BatchItemStatus = BatchItemStatus.executing,
) -> BatchItem:
    batch = Batch(
        id=_unique_id("B"),
        project_id=project_id,
        status=BatchStatus.executing,
        max_parallel=2,
    )
    db.add(batch)
    db.flush()
    bi = BatchItem(
        project_id=project_id,
        batch_id=batch.id,
        work_item_id=work_item_id,
        execution_group=0,
        status=batch_item_status,
    )
    db.add(bi)
    db.flush()
    return bi


def _make_batch_manager(test_project: Project, db_session: Session, tmp_path: Path) -> BatchManager:
    """Build a BatchManager wired to the test db_session."""
    project_config = ProjectConfig(
        id=test_project.id,
        display_name=test_project.display_name,
        repo_root=str(tmp_path / "repo"),
        enabled=True,
        cli_tool="iw",
        model="minimax",
        worktree_base=str(tmp_path / "worktrees"),
        config={},
    )
    projects_toml = tmp_path / "projects.toml"
    projects_toml.write_text("")
    config = DaemonConfig(
        db_host="localhost",
        db_port=5433,
        db_name="test",
        db_user="test",
        db_password="test",  # noqa: S106
        db_url="postgresql+psycopg://test:test@localhost:5433/test",
        dashboard_host="0.0.0.0",  # noqa: S104
        dashboard_port=9900,
        poll_interval=60,
        stall_threshold=600,
        pid_file=str(tmp_path / "daemon.pid"),
        archive_dir=str(tmp_path / "archive"),
        archive_ttl=90,
        log_level="DEBUG",
        log_file=str(tmp_path / "daemon.log"),
        projects_toml=projects_toml,
    )

    @contextmanager
    def session_factory() -> Generator[Session, None, None]:
        yield db_session

    return BatchManager(
        project_id=test_project.id,
        project_config=project_config,
        session_factory=session_factory,
        config=config,
    )


# ---------------------------------------------------------------------------
# AC1 reproduction test (I-00083) — authored at S01, kept verbatim at S03
# ---------------------------------------------------------------------------


class TestI00083BranchBaseDrift:
    """AC1: When item B's worktree is created while item A is in-flight,
    the daemon must emit an INFO log line with sibling_paths_without_merge > 0
    naming item A as the source of drift.

    RED state: the log line does not exist before the fix.
    GREEN state: the log line is emitted after the fix.
    """

    def test_i00083_b_worktree_does_not_inherit_a_pre_impl_test_drift(
        self,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """When B's worktree is created while A is executing (no merge_commit_sha),
        and the worktree contains files matching A's impacted_paths, the daemon
        MUST emit an INFO log line with:
          - in_flight_siblings containing A's item_id
          - sibling_paths_without_merge >= 1
          - details listing A with a non-zero count

        This test FAILS before I-00083 fix (no log line emitted).
        This test PASSES after the fix (log line emitted as specified).
        """
        # --- Arrange: fake git repo that simulates B's worktree tree -----------
        # The repo represents B's worktree after git worktree add.
        # It contains a file that matches A's impacted_paths glob.
        fake_repo = _make_fake_repo(tmp_path)
        drift_file = "tests/test_drift.py"
        _add_file_and_commit(fake_repo, drift_file, "# A's test file — not yet merged\n")

        # --- DB: item A is in-flight (executing, no merge_commit_sha) ----------
        a_id = _unique_id("A-99001")
        _create_work_item(
            db_session,
            test_project.id,
            a_id,
            impacted_paths=["tests/test_drift.py"],
            merge_commit_sha=None,  # A has NOT merged yet
        )
        _create_batch_and_item(
            db_session, test_project.id, a_id, batch_item_status=BatchItemStatus.executing
        )

        # --- DB: item B being launched (pending) --------------------------------
        b_id = _unique_id("B-99002")
        _create_work_item(
            db_session,
            test_project.id,
            b_id,
            impacted_paths=["orch/something.py"],
            merge_commit_sha=None,
        )
        b_batch = Batch(
            id=_unique_id("B"),
            project_id=test_project.id,
            status=BatchStatus.executing,
            max_parallel=2,
        )
        db_session.add(b_batch)
        db_session.flush()
        b_batch_item = BatchItem(
            project_id=test_project.id,
            batch_id=b_batch.id,
            work_item_id=b_id,
            execution_group=0,
            status=BatchItemStatus.pending,
        )
        db_session.add(b_batch_item)
        db_session.commit()

        # --- Act: call _launch_item with mocked worktree pointing at fake_repo --
        # Mock _setup_worktree to return the fake repo as the worktree path.
        fake_worktree_info = {
            "path": str(fake_repo),
            "branch": f"agent/{b_id}",
            "created_at": "2026-01-01T00:00:00+00:00",
        }

        from orch.db.alembic_guard import GuardStatus

        ok_guard = GuardStatus(
            current_rev="abc",
            head_rev="abc",
            pending=[],
            multiple_heads=[],
            ok=True,
        )

        bm = _make_batch_manager(test_project, db_session, tmp_path)

        with (
            caplog.at_level(logging.INFO, logger="orch.daemon.batch_manager"),
            patch("orch.daemon.batch_manager.check_db_at_head", return_value=ok_guard),
            patch.object(BatchManager, "_setup_worktree", return_value=fake_worktree_info),
            patch("orch.daemon.worktree_compose.has_iw_config", return_value=False),
            patch.object(BatchManager, "_compute_qv_baselines"),
            patch.object(BatchManager, "_launch_next_step"),
        ):
            bm._launch_item(db_session, b_batch_item)

        # --- Assert: the INFO log line must be present --------------------------
        # The line format is:
        #   worktree create: item=<B> base=<sha> in_flight_siblings=[<A>]
        #   sibling_paths_without_merge=<N> details=[<A>:<N>]
        drift_log_lines = [
            r.message
            for r in caplog.records
            if "worktree create:" in r.message and "sibling_paths_without_merge" in r.message
        ]
        assert drift_log_lines, (
            "Expected INFO log line with 'worktree create:' and 'sibling_paths_without_merge' "
            "but none found. All batch_manager INFO records:\n"
            + "\n".join(r.message for r in caplog.records if r.name == "orch.daemon.batch_manager")
        )

        log_line = drift_log_lines[0]

        # The line must name item A as an in-flight sibling
        assert a_id in log_line, (
            f"Expected sibling '{a_id}' to appear in drift log line but got: {log_line!r}"
        )

        # The line must report sibling_paths_without_merge >= 1
        assert "sibling_paths_without_merge=0" not in log_line, (
            f"Expected sibling_paths_without_merge >= 1 (A's drift files exist in B's tree) "
            f"but got: {log_line!r}"
        )

        # The line must include item B's id
        assert f"item={b_id}" in log_line, (
            f"Expected 'item={b_id}' in drift log line but got: {log_line!r}"
        )


# ---------------------------------------------------------------------------
# AC3 — Happy-path / solo-item regression (S03)
# ---------------------------------------------------------------------------


class TestI00083HappyPathSoloItem:
    """AC3: When only item B is in-flight (no siblings), the daemon's
    worktree-create log line must report empty siblings and zero drift,
    and B's batch_item must transition to `executing` just like today.

    This pins the "no behavioural change vs today" half of the contract
    so we don't regress the solo-item flow when refining the sibling
    detection in the future.
    """

    def test_solo_item_emits_empty_sibling_log_and_transitions_to_executing(
        self,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # --- Arrange: only B exists; no other in-flight items in the project ---
        fake_repo = _make_fake_repo(tmp_path)
        # A plain file unrelated to any sibling glob; should never cause drift.
        _add_file_and_commit(fake_repo, "orch/something.py", "# unrelated\n")

        b_id = _unique_id("B-SOLO")
        _create_work_item(
            db_session,
            test_project.id,
            b_id,
            impacted_paths=["orch/something.py"],
            merge_commit_sha=None,
        )
        b_batch = Batch(
            id=_unique_id("B"),
            project_id=test_project.id,
            status=BatchStatus.executing,
            max_parallel=2,
        )
        db_session.add(b_batch)
        db_session.flush()
        b_batch_item = BatchItem(
            project_id=test_project.id,
            batch_id=b_batch.id,
            work_item_id=b_id,
            execution_group=0,
            status=BatchItemStatus.pending,
        )
        db_session.add(b_batch_item)
        db_session.commit()

        fake_worktree_info = {
            "path": str(fake_repo),
            "branch": f"agent/{b_id}",
            "created_at": "2026-01-01T00:00:00+00:00",
        }

        from orch.db.alembic_guard import GuardStatus

        ok_guard = GuardStatus(
            current_rev="abc",
            head_rev="abc",
            pending=[],
            multiple_heads=[],
            ok=True,
        )

        bm = _make_batch_manager(test_project, db_session, tmp_path)

        with (
            caplog.at_level(logging.INFO, logger="orch.daemon.batch_manager"),
            patch("orch.daemon.batch_manager.check_db_at_head", return_value=ok_guard),
            patch.object(BatchManager, "_setup_worktree", return_value=fake_worktree_info),
            patch("orch.daemon.worktree_compose.has_iw_config", return_value=False),
            patch.object(BatchManager, "_compute_qv_baselines"),
            patch.object(BatchManager, "_launch_next_step"),
        ):
            bm._launch_item(db_session, b_batch_item)

        # --- Assert: exactly one drift-log line, in the empty-siblings shape ---
        drift_lines = [
            r.message
            for r in caplog.records
            if "worktree create:" in r.message and "sibling_paths_without_merge" in r.message
        ]
        assert len(drift_lines) == 1, (
            f"Expected exactly one drift log line on solo-item launch; got {len(drift_lines)}: "
            f"{drift_lines!r}"
        )

        log_line = drift_lines[0]
        assert f"item={b_id}" in log_line, f"Solo-item log must reference B's id; got: {log_line!r}"
        assert "in_flight_siblings=[]" in log_line, (
            f"Solo-item log must contain empty siblings list literally; got: {log_line!r}"
        )
        assert "sibling_paths_without_merge=0" in log_line, (
            f"Solo-item log must report zero drift; got: {log_line!r}"
        )

        # No WARNING line should be emitted in the happy path (drift warning
        # is the operator-visible alarm and must stay silent on solo runs).
        warn_records = [
            r
            for r in caplog.records
            if r.name == "orch.daemon.batch_manager" and r.levelno >= logging.WARNING
        ]
        assert warn_records == [], (
            "Solo-item launch must not emit any WARNING from batch_manager; got: "
            + ", ".join(r.message for r in warn_records)
        )

        # Behavioural equivalence vs today: B's batch_item must reach `executing`
        # and worktree_info must be persisted.
        db_session.refresh(b_batch_item)
        assert b_batch_item.status == BatchItemStatus.executing, (
            f"Solo-item launch must transition to executing; got {b_batch_item.status!r}"
        )
        assert b_batch_item.worktree_info is not None, "Solo-item launch must persist worktree_info"
        assert b_batch_item.worktree_info.get("path") == str(fake_repo), (
            f"worktree_info.path must round-trip; got {b_batch_item.worktree_info!r}"
        )
        assert b_batch_item.started_at is not None, "Solo-item launch must stamp started_at"


# ---------------------------------------------------------------------------
# Sibling-scope-check unit coverage (S03)
# Exercises BatchManager._emit_sibling_drift_log directly across the three
# branches that determine each sibling's contribution to the drift count.
# ---------------------------------------------------------------------------


class TestI00083SiblingScopeUnit:
    """Direct coverage of `_emit_sibling_drift_log` aggregation logic.

    Each test builds a fake B-worktree with a known file set, creates the
    sibling rows directly, calls `_emit_sibling_drift_log`, and asserts on
    the exact `details=[...]` portion of the emitted log line.
    """

    def _capture_drift_line(
        self,
        bm: BatchManager,
        db_session: Session,
        item_id: str,
        worktree_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> str:
        with caplog.at_level(logging.INFO, logger="orch.daemon.batch_manager"):
            bm._emit_sibling_drift_log(db_session, item_id, worktree_path)
        lines = [
            r.message
            for r in caplog.records
            if "worktree create:" in r.message and "sibling_paths_without_merge" in r.message
        ]
        assert len(lines) == 1, f"Expected exactly one drift log line; got {len(lines)}: {lines!r}"
        return lines[0]

    def test_multiple_in_flight_siblings_non_overlapping_globs_sum_counts(
        self,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Two in-flight siblings with disjoint impacted_paths that each match
        exactly one file in B's tree → per-sibling counts each = 1 and total = 2.
        """
        fake_repo = _make_fake_repo(tmp_path)
        _add_file_and_commit(fake_repo, "src/a1.py", "# A1's pending impl\n")
        _add_file_and_commit(fake_repo, "src/a2.py", "# A2's pending impl\n")

        a1_id = _unique_id("A1")
        _create_work_item(
            db_session,
            test_project.id,
            a1_id,
            impacted_paths=["src/a1.py"],
            merge_commit_sha=None,
        )
        _create_batch_and_item(
            db_session, test_project.id, a1_id, batch_item_status=BatchItemStatus.executing
        )

        a2_id = _unique_id("A2")
        _create_work_item(
            db_session,
            test_project.id,
            a2_id,
            impacted_paths=["src/a2.py"],
            merge_commit_sha=None,
        )
        _create_batch_and_item(
            db_session, test_project.id, a2_id, batch_item_status=BatchItemStatus.executing
        )

        b_id = _unique_id("B")
        bm = _make_batch_manager(test_project, db_session, tmp_path)
        db_session.commit()

        log_line = self._capture_drift_line(bm, db_session, b_id, fake_repo, caplog)

        # Extract the total via regex and compare with equality — must equal
        # the sum of per-sibling counts (1 + 1 = 2).
        total_match = re.search(r"sibling_paths_without_merge=(\d+)", log_line)
        assert total_match is not None, (
            f"Log line missing sibling_paths_without_merge=N; got: {log_line!r}"
        )
        total = int(total_match.group(1))
        assert total == 2, (
            f"Expected total drift = 2 (1 per sibling), got total={total}: {log_line!r}"
        )
        # Both siblings must appear in in_flight_siblings list
        assert a1_id in log_line, (
            f"Sibling A1 ({a1_id}) must appear in the log line; got: {log_line!r}"
        )
        assert a2_id in log_line, (
            f"Sibling A2 ({a2_id}) must appear in the log line; got: {log_line!r}"
        )
        # Per-sibling detail entries are present in details=[...]
        assert f"{a1_id}:1" in log_line, f"Expected '{a1_id}:1' in details; got: {log_line!r}"
        assert f"{a2_id}:1" in log_line, f"Expected '{a2_id}:1' in details; got: {log_line!r}"

        # Drift > 0 must fire exactly one WARN line naming both siblings —
        # this is the operator-visible alarm the design contract requires.
        warn_records = [
            r
            for r in caplog.records
            if r.name == "orch.daemon.batch_manager" and r.levelno >= logging.WARNING
        ]
        assert len(warn_records) == 1, (
            f"Expected exactly one WARN line for total_drift>0; got {len(warn_records)}: "
            + ", ".join(r.message for r in warn_records)
        )
        warn_message = warn_records[0].getMessage()
        assert a1_id in warn_message, f"Drift WARN must name sibling a1; got: {warn_message!r}"
        assert a2_id in warn_message, f"Drift WARN must name sibling a2; got: {warn_message!r}"

    def test_sibling_with_merge_commit_contributes_zero(
        self,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Sibling whose squash commit already landed on main (merge_commit_sha
        not NULL) contributes zero to the drift count even when its impacted
        paths are present in B's worktree.
        """
        fake_repo = _make_fake_repo(tmp_path)
        _add_file_and_commit(fake_repo, "src/merged_sibling.py", "# legitimately on main\n")

        merged_id = _unique_id("MERGED")
        _create_work_item(
            db_session,
            test_project.id,
            merged_id,
            impacted_paths=["src/merged_sibling.py"],
            merge_commit_sha="deadbeef" * 5,  # already merged
        )
        # BatchItem still appears "in-flight" briefly while the merge queue
        # transitions it from merging → merged; that is exactly the window
        # where merge_commit_sha is set but BatchItem.status is still active.
        _create_batch_and_item(
            db_session, test_project.id, merged_id, batch_item_status=BatchItemStatus.merging
        )

        b_id = _unique_id("B")
        bm = _make_batch_manager(test_project, db_session, tmp_path)
        db_session.commit()

        log_line = self._capture_drift_line(bm, db_session, b_id, fake_repo, caplog)

        assert "sibling_paths_without_merge=0" in log_line, (
            f"Merged sibling must contribute zero drift; got: {log_line!r}"
        )
        # The sibling is still surfaced in the in_flight_siblings list (it has
        # an active BatchItem), but its merge_commit_sha shields it from the
        # drift count.
        assert merged_id in log_line, (
            f"Merged sibling id must still appear in in_flight_siblings; got: {log_line!r}"
        )
        # And no WARNING line should fire — the alarm is only for true drift.
        warn_records = [
            r
            for r in caplog.records
            if r.name == "orch.daemon.batch_manager" and r.levelno >= logging.WARNING
        ]
        assert warn_records == [], (
            "Merged sibling must not trigger a drift WARNING; got: "
            + ", ".join(r.message for r in warn_records)
        )

    def test_sibling_glob_matches_nothing_contributes_zero(
        self,
        db_session: Session,
        test_project: Project,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Sibling with no merge_commit_sha but whose impacted_paths globs
        match no file in B's worktree → count is zero and no WARNING fires.
        """
        fake_repo = _make_fake_repo(tmp_path)
        # B's tree has only README.md from _make_fake_repo — nothing else.
        no_match_id = _unique_id("NOMATCH")
        _create_work_item(
            db_session,
            test_project.id,
            no_match_id,
            impacted_paths=["src/never_present.py", "lib/also_missing/*.py"],
            merge_commit_sha=None,
        )
        _create_batch_and_item(
            db_session, test_project.id, no_match_id, batch_item_status=BatchItemStatus.executing
        )

        b_id = _unique_id("B")
        bm = _make_batch_manager(test_project, db_session, tmp_path)
        db_session.commit()

        log_line = self._capture_drift_line(bm, db_session, b_id, fake_repo, caplog)

        assert "sibling_paths_without_merge=0" in log_line, (
            f"Non-matching sibling must produce zero drift; got: {log_line!r}"
        )
        assert no_match_id in log_line, (
            f"Sibling id must still appear in in_flight_siblings; got: {log_line!r}"
        )
        warn_records = [
            r
            for r in caplog.records
            if r.name == "orch.daemon.batch_manager" and r.levelno >= logging.WARNING
        ]
        assert warn_records == [], (
            "Non-matching sibling must not emit a WARNING; got: "
            + ", ".join(r.message for r in warn_records)
        )


# ---------------------------------------------------------------------------
# Chore-commit allow-list coverage (S03)
# Exercises the narrowed `ensure_active_files_committed` and asserts that
# non-design files placed under ai-dev/active/<ID>/ are NOT promoted to main.
# ---------------------------------------------------------------------------


class TestI00083ChoreCommitAllowList:
    """The chore commit at approval time must ship only the allow-listed
    design/manifest/prompt files. Test fixtures, scripts, evidences, and
    ad-hoc notes placed under `ai-dev/active/<ID>/` must remain untracked
    so they travel with the squash merge instead — closing the half-state
    branch-base drift documented in I-00083.
    """

    def test_chore_commit_excludes_non_design_files(
        self,
        tmp_path: Path,
    ) -> None:
        """`notes.txt` placed under ai-dev/active/<ID>/ must NOT appear in
        the chore commit's tree, while the design/manifest/prompt files MUST.
        """
        repo = _make_fake_repo(tmp_path)
        item_id = "I-99999"

        sha = _simulate_chore_commit(
            repo,
            item_id,
            extra_active_files={
                # Non-design files that should be filtered out:
                "notes.txt": "operator scratch notes — should not reach main\n",
                "tests/fixtures/sample.json": '{"smoke": true}\n',
                "evidences/screenshot.png": "fake-png-bytes\n",
            },
        )

        # --- Allow-listed files MUST be in the chore commit's tree -----------
        assert _commit_contains(repo, sha, f"ai-dev/active/{item_id}/{item_id}_Issue_Design.md"), (
            "Design doc must be committed by the chore step"
        )
        assert _commit_contains(repo, sha, f"ai-dev/active/{item_id}/{item_id}_Functional.md"), (
            "Functional design doc must be committed by the chore step"
        )
        assert _commit_contains(repo, sha, f"ai-dev/active/{item_id}/workflow-manifest.json"), (
            "workflow-manifest.json must be committed by the chore step"
        )
        assert _commit_contains(
            repo, sha, f"ai-dev/active/{item_id}/prompts/{item_id}_S01_Pipeline_prompt.md"
        ), "Prompt files under prompts/ must be committed by the chore step"

        # --- Non-design files MUST NOT be in the chore commit's tree --------
        assert not _commit_contains(repo, sha, f"ai-dev/active/{item_id}/notes.txt"), (
            "notes.txt was committed by the chore step — allow-list leak (I-00083)"
        )
        assert not _commit_contains(
            repo, sha, f"ai-dev/active/{item_id}/tests/fixtures/sample.json"
        ), "Test fixture under ai-dev/active/ was committed — allow-list leak (I-00083)"
        assert not _commit_contains(
            repo, sha, f"ai-dev/active/{item_id}/evidences/screenshot.png"
        ), "Evidence under ai-dev/active/ was committed — allow-list leak (I-00083)"

        # --- And the excluded files must still exist on disk (untracked) ----
        # They are intentionally left for the squash merge to pick up.
        assert (repo / "ai-dev" / "active" / item_id / "notes.txt").exists()
        assert (
            repo / "ai-dev" / "active" / item_id / "tests" / "fixtures" / "sample.json"
        ).exists()

    def test_chore_commit_with_only_non_design_files_skips_commit(
        self,
        tmp_path: Path,
    ) -> None:
        """If only non-design files are dirty under ai-dev/active/<ID>/,
        `ensure_active_files_committed` must NOT create an empty / mis-scoped
        commit — it must skip cleanly so the noise stays out of main.
        """
        repo = _make_fake_repo(tmp_path)
        item_id = "I-88888"

        # Seed the active dir with the design files and land them in an
        # initial chore commit so subsequent calls find no allow-listed dirt.
        first_sha = _simulate_chore_commit(repo, item_id)

        # Now place ONLY non-design files in the active dir.
        active = repo / "ai-dev" / "active" / item_id
        (active / "scratch.txt").write_text("scribbles\n")
        (active / "logs").mkdir()
        (active / "logs" / "run.log").write_text("agent output\n")

        ensure_active_files_committed(repo, item_id, f"Test {item_id}")

        head_sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        assert head_sha == first_sha, (
            "Expected no new chore commit when only non-design files are dirty; "
            f"first_sha={first_sha!r} but HEAD moved to {head_sha!r}"
        )
        # Scratch file must remain on disk (untracked) so the squash merge
        # — or a later operator clean-up — handles it.
        assert (active / "scratch.txt").exists()
        assert (active / "logs" / "run.log").exists()
