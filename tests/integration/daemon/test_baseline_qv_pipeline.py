"""Integration tests for the QV baseline pipeline.

Covers AC1–AC6 against the real BatchManager._compute_qv_baselines and
_get_qv_findings integration points, using a testcontainer PostgreSQL DB.

AC1: Pre-existing failures excluded from fix-cycle
AC2: Genuine regressions surfaced cleanly
AC3: Baselines created at setup
AC4: Rebase invalidates baseline
AC5: Kill switch disables all new behaviour
AC6: Legacy items fall back gracefully
Boundary: timeout, empty passing gate
N+1: query count bounded in _compute_qv_baselines
"""

from __future__ import annotations

import json
import logging
import subprocess
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import event, select

from orch.daemon.batch_manager import BatchManager
from orch.daemon.fix_cycle import _get_qv_findings
from orch.db.models import (
    Batch,
    BatchItem,
    BatchItemStatus,
    BatchStatus,
    Project,
    QvBaseline,
    RunStatus,
    StepRun,
    StepStatus,
    StepType,
    WorkflowStep,
    WorkItem,
    WorkItemPhase,
    WorkItemStatus,
    WorkItemType,
)

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Unique ID helpers
# ---------------------------------------------------------------------------


def _unique_id(prefix: str = "F-00061") -> str:
    """Generate a unique ID using a UUID suffix to guarantee no collisions."""
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"


# ---------------------------------------------------------------------------
# Manifest helpers
# ---------------------------------------------------------------------------


def make_manifest(item_id: str, steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "id": item_id,
        "steps": [
            {
                "step": f"{item_id}-S10",
                "gate": "lint",
                "command": "echo lint-output",
            },
            {
                "step": f"{item_id}-S13",
                "gate": "unit-tests",
                "command": "echo unit-tests-output",
            },
            {
                "step": f"{item_id}-S14",
                "gate": "integration-tests",
                "command": "echo integration-tests-output",
            },
            *steps,
        ],
    }


def write_manifest(worktree_path: Path, item_id: str, steps: list[dict[str, Any]]) -> None:
    manifest = make_manifest(item_id, steps)
    manifest_dir = worktree_path / "ai-dev" / "active" / item_id
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "workflow-manifest.json").write_text(json.dumps(manifest))


# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_worktree(tmp_path: Path, test_project: Project) -> tuple[Path, str]:
    """Create a worktree with a guaranteed-unique item ID."""
    item_id = _unique_id()
    worktree = tmp_path / "worktrees" / item_id
    worktree.mkdir(parents=True, exist_ok=True)

    (worktree / ".git").mkdir()
    (worktree / ".git").chmod(0o755)

    write_manifest(worktree, item_id, [])

    return worktree, item_id


# ---------------------------------------------------------------------------
# Helper: create a work item + QV step in DB
# ---------------------------------------------------------------------------


def _create_item_and_step(
    db: Session,
    project_id: str,
    item_id: str,
    step_id: str,
    gate_name: str,
    step_number: int = 13,
) -> tuple[WorkItem, WorkflowStep]:
    """Create a WorkItem + QV WorkflowStep in the DB.

    If the WorkItem already exists in the session (e.g. from a previous flush
    that didn't commit), use the in-session copy.
    """
    # Check if item already exists in the current session
    existing_item = db.execute(
        select(WorkItem).where(
            WorkItem.project_id == project_id,
            WorkItem.id == item_id,
        )
    ).scalar_one_or_none()

    if existing_item is not None:
        item = existing_item
    else:
        item = WorkItem(
            project_id=project_id,
            id=item_id,
            type=WorkItemType.Feature,
            title=f"Test item {item_id}",
            status=WorkItemStatus.in_progress,
            phase=WorkItemPhase.active,
            config={},
            depends_on=[],
            blocks=[],
        )
        db.add(item)
        db.flush()

    # Check if step already exists (from a previous failed test with same item_id)
    existing_step = db.execute(
        select(WorkflowStep).where(
            WorkflowStep.project_id == project_id,
            WorkflowStep.work_item_id == item_id,
            WorkflowStep.step_number == step_number,
        )
    ).scalar_one_or_none()

    if existing_step is not None:
        step = existing_step
    else:
        step = WorkflowStep(
            project_id=project_id,
            work_item_id=item_id,
            step_number=step_number,
            step_id=step_id,
            agent_label=f"Test_{step_id}",
            step_type=StepType.quality_validation,
            status=StepStatus.pending,
        )
        db.add(step)
        db.flush()
    return item, step


def _insert_step_run(
    db: Session,
    step: WorkflowStep,
    log_content: str,
    status: RunStatus = RunStatus.failed,
) -> None:
    """Insert a StepRun record that _get_qv_findings will find."""
    run = StepRun(
        step_id=step.id,
        run_number=1,
        status=status,
        log_content=log_content,
        log_file=None,
        error_message=None,
    )
    db.add(run)
    db.flush()


# ---------------------------------------------------------------------------
# AC1: Pre-existing failures excluded from fix-cycle
# ---------------------------------------------------------------------------


class TestAC1:
    def test_ac1_pre_existing_failure_excluded_from_fix_cycle(
        self,
        db_session: Session,
        test_project: Project,
        fake_worktree: tuple[Path, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        worktree, item_id = fake_worktree
        step_id = f"{item_id}-S13"

        _, step = _create_item_and_step(db_session, test_project.id, item_id, step_id, "unit-tests")

        # Seed a QvBaseline row with test_flaky as a pre-existing failure
        baseline_fp: dict[str, Any] = {
            "failures": [{"kind": "test", "key": "tests/unit/foo.py::test_flaky"}],
            "unparseable": [],
        }
        baseline_row = QvBaseline(
            step_id=step.id,
            gate_name="unit-tests",
            base_sha="abc123",
            fingerprint=baseline_fp,
        )
        db_session.add(baseline_row)

        # Insert a StepRun that the _get_qv_findings query will find
        _insert_step_run(
            db_session,
            step,
            log_content="FAILED tests/unit/foo.py::test_flaky - AssertionError",
        )
        db_session.commit()

        # Patch _resolve_worktree_base_sha so no rebase is detected
        monkeypatch.setenv("IW_CORE_BASELINE_QV", "true")

        with patch(
            "orch.daemon.fix_cycle._resolve_worktree_base_sha",
            return_value="abc123",
        ):
            findings = _get_qv_findings(
                db_session, step, str(worktree), MagicMock(baseline_qv_enabled=True)
            )

        # test_flaky was in baseline → baseline subtraction removes it → no findings
        assert "test_flaky" not in findings
        assert findings == ""


# ---------------------------------------------------------------------------
# AC2: Genuine regressions surfaced cleanly
# ---------------------------------------------------------------------------


class TestAC2:
    def test_ac2_regression_surfaced_cleanly(
        self,
        db_session: Session,
        test_project: Project,
        fake_worktree: tuple[Path, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        worktree, item_id = fake_worktree
        step_id = f"{item_id}-S13"

        _, step = _create_item_and_step(db_session, test_project.id, item_id, step_id, "unit-tests")

        # Baseline only knows about test_flaky (pre-existing)
        baseline_fp: dict[str, Any] = {
            "failures": [{"kind": "test", "key": "tests/unit/foo.py::test_flaky"}],
            "unparseable": [],
        }
        baseline_row = QvBaseline(
            step_id=step.id,
            gate_name="unit-tests",
            base_sha="abc123",
            fingerprint=baseline_fp,
        )
        db_session.add(baseline_row)

        # Current output contains BOTH test_flaky (pre-existing) and test_new_regression (new)
        current_output = (
            "FAILED tests/unit/foo.py::test_flaky - AssertionError\n"
            "FAILED tests/unit/bar.py::test_new_regression - AssertionError"
        )
        _insert_step_run(db_session, step, log_content=current_output)
        db_session.flush()

        monkeypatch.setenv("IW_CORE_BASELINE_QV", "true")

        with patch(
            "orch.daemon.fix_cycle._resolve_worktree_base_sha",
            return_value="abc123",
        ):
            findings = _get_qv_findings(
                db_session, step, str(worktree), MagicMock(baseline_qv_enabled=True)
            )

        # test_new_regression is genuine → must surface; test_flaky is baseline-subtracted
        assert "test_new_regression" in findings
        assert "test_flaky" not in findings


# ---------------------------------------------------------------------------
# AC3: Baselines created at setup
# ---------------------------------------------------------------------------


class TestAC3:
    def test_ac3_baselines_created_at_setup(
        self,
        db_session: Session,
        db_engine: Engine,
        test_project: Project,
        fake_worktree: tuple[Path, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        worktree, item_id = fake_worktree

        for sn, suffix, gate in [
            (10, "S10", "lint"),
            (13, "S13", "unit-tests"),
            (14, "S14", "integration-tests"),
        ]:
            _create_item_and_step(
                db_session, test_project.id, item_id, f"{item_id}-{suffix}", gate, step_number=sn
            )
        db_session.flush()

        write_manifest(
            worktree,
            item_id,
            [
                {"step": f"{item_id}-S10", "gate": "lint", "command": "make lint"},
                {
                    "step": f"{item_id}-S13",
                    "gate": "unit-tests",
                    "command": "make test-unit",
                },
                {
                    "step": f"{item_id}-S14",
                    "gate": "integration-tests",
                    "command": "make test-integration",
                },
            ],
        )

        batch = Batch(
            project_id=test_project.id,
            id=f"B-{item_id[:8]}",
            status=BatchStatus.executing,
            max_parallel=4,
            cli_tool="opencode",
            auto_publish=False,
        )
        db_session.add(batch)
        db_session.flush()

        batch_item = BatchItem(
            project_id=test_project.id,
            batch_id=batch.id,
            work_item_id=item_id,
            status=BatchItemStatus.pending,
        )
        db_session.add(batch_item)
        db_session.commit()

        monkeypatch.setenv("IW_CORE_BASELINE_QV", "true")

        def subprocess_side_effect(cmd: list[str], **kwargs: Any) -> MagicMock:
            if isinstance(cmd, list) and "merge-base" in cmd:
                return MagicMock(stdout="abc123\n", stderr="", returncode=0)
            return MagicMock(stdout="", stderr="", returncode=0)

        with (
            patch("orch.daemon.batch_manager.subprocess.run", side_effect=subprocess_side_effect),
            patch("orch.daemon.batch_manager.subprocess.Popen") as mock_popen,
        ):
            mock_proc = MagicMock()
            mock_proc.communicate.return_value = (b"", b"")
            mock_proc.pid = 12345
            mock_popen.return_value.__enter__.return_value = mock_proc
            bm = BatchManager(
                project_id=test_project.id,
                project_config=MagicMock(
                    id=test_project.id,
                    worktree_base=".worktrees",
                    working_dir=str(worktree.parent.parent),
                ),
                session_factory=lambda: db_session,
                config=MagicMock(baseline_qv_enabled=True),
            )

            with (
                patch.object(bm, "_setup_worktree", return_value={"path": str(worktree)}),
                patch.object(bm, "_launch_next_step"),
            ):
                bm._compute_qv_baselines(db_session, batch_item, {"path": str(worktree)})

        rows = db_session.query(QvBaseline).all()
        assert len(rows) == 3
        base_shas = {r.base_sha for r in rows}
        assert len(base_shas) == 1
        assert "abc123" in base_shas


# ---------------------------------------------------------------------------
# AC4: Rebase invalidates baseline
# ---------------------------------------------------------------------------


class TestAC4:
    def test_ac4_rebase_invalidates_baseline(
        self,
        db_session: Session,
        test_project: Project,
        fake_worktree: tuple[Path, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        worktree, item_id = fake_worktree
        step_id = f"{item_id}-S13"

        _, step = _create_item_and_step(db_session, test_project.id, item_id, step_id, "unit-tests")

        old_sha = "aaa000"
        baseline_fp: dict[str, Any] = {
            "failures": [{"kind": "test", "key": "tests/unit/foo.py::test_flaky"}],
            "unparseable": [],
        }
        old_row = QvBaseline(
            step_id=step.id,
            gate_name="unit-tests",
            base_sha=old_sha,
            fingerprint=baseline_fp,
        )
        db_session.add(old_row)
        _insert_step_run(
            db_session,
            step,
            log_content="FAILED tests/unit/foo.py::test_flaky - AssertionError\n",
        )
        db_session.commit()

        call_count = 0

        def fake_git_merge_base(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            nonlocal call_count
            call_count += 1
            sha = "bbb111" if call_count == 1 else old_sha
            return MagicMock(stdout=f"{sha}\n", stderr="", returncode=0)

        monkeypatch.setenv("IW_CORE_BASELINE_QV", "true")

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = fake_git_merge_base
            _get_qv_findings(db_session, step, str(worktree), MagicMock(baseline_qv_enabled=True))

        # Old baseline should have been invalidated/deleted
        remaining = db_session.query(QvBaseline).filter(QvBaseline.base_sha == old_sha).all()
        assert len(remaining) == 0


# ---------------------------------------------------------------------------
# AC5: Kill switch disables
# ---------------------------------------------------------------------------


class TestAC5:
    def test_ac5_kill_switch_disables(
        self,
        db_session: Session,
        db_engine: Engine,
        test_project: Project,
        fake_worktree: tuple[Path, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        worktree, item_id = fake_worktree
        step_id = f"{item_id}-S13"

        _, step = _create_item_and_step(db_session, test_project.id, item_id, step_id, "unit-tests")

        write_manifest(worktree, item_id, [])

        batch = Batch(
            project_id=test_project.id,
            id=f"B-{item_id[:8]}",
            status=BatchStatus.executing,
            max_parallel=4,
            cli_tool="opencode",
            auto_publish=False,
        )
        db_session.add(batch)
        db_session.flush()

        batch_item = BatchItem(
            project_id=test_project.id,
            batch_id=batch.id,
            work_item_id=item_id,
            status=BatchItemStatus.pending,
        )
        db_session.add(batch_item)
        db_session.commit()

        monkeypatch.setenv("IW_CORE_BASELINE_QV", "false")

        bm = BatchManager(
            project_id=test_project.id,
            project_config=MagicMock(
                id=test_project.id,
                worktree_base=".worktrees",
                working_dir=str(worktree.parent.parent),
            ),
            session_factory=lambda: db_session,
            config=MagicMock(baseline_qv_enabled=False),
        )

        # When baseline_qv_enabled=False, _compute_qv_baselines should return early
        with patch.object(
            bm, "_compute_qv_baselines", wraps=bm._compute_qv_baselines
        ) as mock_compute:
            bm._compute_qv_baselines(db_session, batch_item, {"path": str(worktree)})
            mock_compute.assert_called_once()

        baseline_count = db_session.query(QvBaseline).count()
        assert baseline_count == 0


# ---------------------------------------------------------------------------
# AC6: Legacy item graceful
# ---------------------------------------------------------------------------


class TestAC6:
    def test_ac6_legacy_item_graceful(
        self,
        db_session: Session,
        test_project: Project,
        fake_worktree: tuple[Path, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        worktree, item_id = fake_worktree
        step_id = f"{item_id}-S13"

        _, step = _create_item_and_step(db_session, test_project.id, item_id, step_id, "unit-tests")

        _insert_step_run(
            db_session,
            step,
            log_content="FAILED tests/unit/foo.py::test_flaky - AssertionError",
        )
        db_session.commit()

        # No baseline row exists → falls back to legacy path, test_flaky surfaces
        monkeypatch.setenv("IW_CORE_BASELINE_QV", "true")

        with patch(
            "orch.daemon.fix_cycle._resolve_worktree_base_sha",
            return_value="abc123",
        ):
            findings = _get_qv_findings(
                db_session, step, str(worktree), MagicMock(baseline_qv_enabled=True)
            )

        assert "test_flaky" in findings


# ---------------------------------------------------------------------------
# Boundary Behaviour
# ---------------------------------------------------------------------------


class TestBaselineBoundary:
    def test_baseline_compute_timeout_is_contained(
        self,
        db_session: Session,
        test_project: Project,
        fake_worktree: tuple[Path, str],
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        worktree, item_id = fake_worktree
        step_id = f"{item_id}-S10"

        _, step = _create_item_and_step(db_session, test_project.id, item_id, step_id, "lint")

        write_manifest(
            worktree, item_id, [{"step": f"{item_id}-S10", "gate": "lint", "command": "sleep 999"}]
        )

        batch = Batch(
            project_id=test_project.id,
            id=f"B-{item_id[:8]}",
            status=BatchStatus.executing,
            max_parallel=4,
            cli_tool="opencode",
            auto_publish=False,
        )
        db_session.add(batch)
        db_session.flush()

        batch_item = BatchItem(
            project_id=test_project.id,
            batch_id=batch.id,
            work_item_id=item_id,
            status=BatchItemStatus.pending,
        )
        db_session.add(batch_item)
        db_session.commit()

        monkeypatch.setenv("IW_CORE_BASELINE_QV", "true")

        def fake_timeout_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            raise subprocess.TimeoutExpired("sleep 999", 1)

        with (
            caplog.at_level(logging.WARNING),
            patch("subprocess.run", side_effect=fake_timeout_run),
        ):
            bm = BatchManager(
                project_id=test_project.id,
                project_config=MagicMock(
                    id=test_project.id,
                    worktree_base=".worktrees",
                    working_dir=str(worktree.parent.parent),
                ),
                session_factory=lambda: db_session,
                config=MagicMock(baseline_qv_enabled=True),
            )
            bm._compute_qv_baselines(db_session, batch_item, {"path": str(worktree)})

        assert any("[F-00061]" in r.message for r in caplog.records)
        rows_after = db_session.query(QvBaseline).filter(QvBaseline.step_id == step.id).all()
        assert len(rows_after) == 0

    def test_baseline_empty_passing_gate_persists_sentinel_row(
        self,
        db_session: Session,
        db_engine: Engine,
        test_project: Project,
        fake_worktree: tuple[Path, str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        worktree, item_id = fake_worktree
        step_id = f"{item_id}-S13"

        _, step = _create_item_and_step(db_session, test_project.id, item_id, step_id, "unit-tests")

        write_manifest(
            worktree,
            item_id,
            [{"step": f"{item_id}-S13", "gate": "unit-tests", "command": "make test-unit"}],
        )

        batch = Batch(
            project_id=test_project.id,
            id=f"B-{item_id[:8]}",
            status=BatchStatus.executing,
            max_parallel=4,
            cli_tool="opencode",
            auto_publish=False,
        )
        db_session.add(batch)
        db_session.flush()

        batch_item = BatchItem(
            project_id=test_project.id,
            batch_id=batch.id,
            work_item_id=item_id,
            status=BatchItemStatus.pending,
        )
        db_session.add(batch_item)
        db_session.commit()

        monkeypatch.setenv("IW_CORE_BASELINE_QV", "true")

        class MockPopen:
            def __init__(self, cmd: str, **kwargs: Any) -> None:
                self.cmd = cmd
                self.kwargs = kwargs

            def communicate(self, **kwargs: Any) -> tuple[bytes, bytes]:
                if "merge-base" in self.cmd:
                    return (b"abc123\n", b"")
                return (b"", b"")

            def __enter__(self) -> MockPopen:
                return self

            def __exit__(self, *args: Any) -> None:
                pass

        def subprocess_side_effect(cmd: list[str], **kwargs: Any) -> MagicMock:
            if isinstance(cmd, list) and "merge-base" in cmd:
                return MagicMock(stdout="abc123\n", stderr="", returncode=0)
            return MagicMock(stdout="", stderr="", returncode=0)

        with (
            patch("orch.daemon.batch_manager.subprocess.run", side_effect=subprocess_side_effect),
            patch("orch.daemon.batch_manager.subprocess.Popen", side_effect=MockPopen),
        ):
            bm = BatchManager(
                project_id=test_project.id,
                project_config=MagicMock(
                    id=test_project.id,
                    worktree_base=".worktrees",
                    working_dir=str(worktree.parent.parent),
                ),
                session_factory=lambda: db_session,
                config=MagicMock(baseline_qv_enabled=True),
            )
            bm._compute_qv_baselines(db_session, batch_item, {"path": str(worktree)})

        rows = db_session.query(QvBaseline).filter(QvBaseline.step_id == step.id).all()
        assert len(rows) == 1
        assert rows[0].fingerprint == {"failures": [], "unparseable": []}


# ---------------------------------------------------------------------------
# N+1 query discipline
# ---------------------------------------------------------------------------


class TestN1QueryCount:
    def test_no_n_plus_one_in_compute_qv_baselines(
        self,
        db_session: Session,
        db_engine: Engine,
        test_project: Project,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Create a fresh unique worktree for this test (not using fake_worktree fixture
        # to avoid counter state issues with N+1 test)
        item_id_n1 = _unique_id()
        n1_worktree = Path(f"/tmp/{uuid.uuid4().hex[:8]}")
        n1_worktree.mkdir(parents=True, exist_ok=True)
        worktree = n1_worktree / "worktrees" / item_id_n1
        worktree.mkdir(parents=True, exist_ok=True)
        (worktree / ".git").mkdir()
        (worktree / ".git").chmod(0o755)

        for i, gate in enumerate(["lint", "unit-tests", "integration-tests"]):
            step_id = f"{item_id_n1}-S{10 + i}"
            _create_item_and_step(
                db_session,
                test_project.id,
                item_id_n1,
                step_id,
                gate,
            )
        db_session.flush()

        write_manifest(
            worktree,
            item_id_n1,
            [
                {"step": f"{item_id_n1}-S{i:02d}", "gate": gate, "command": f"echo {gate}"}
                for i, gate in enumerate(["lint", "unit-tests", "integration-tests"])
            ],
        )

        batch = Batch(
            project_id=test_project.id,
            id=f"B-N1-{item_id_n1[:8]}",
            status=BatchStatus.executing,
            max_parallel=4,
            cli_tool="opencode",
            auto_publish=False,
        )
        db_session.add(batch)
        db_session.flush()

        batch_item = BatchItem(
            project_id=test_project.id,
            batch_id=batch.id,
            work_item_id=item_id_n1,
            status=BatchItemStatus.pending,
        )
        db_session.add(batch_item)
        db_session.commit()

        monkeypatch.setenv("IW_CORE_BASELINE_QV", "true")

        k_gates = 3
        query_count = 0

        @event.listens_for(db_engine, "before_cursor_execute")
        def count_queries(*args: Any, **kwargs: Any) -> None:
            nonlocal query_count
            query_count += 1

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="abc123\n", stderr="", returncode=0)
            bm = BatchManager(
                project_id=test_project.id,
                project_config=MagicMock(
                    id=test_project.id,
                    worktree_base=".worktrees",
                    working_dir=str(worktree.parent.parent),
                ),
                session_factory=lambda: db_session,
                config=MagicMock(baseline_qv_enabled=True),
            )
            bm._compute_qv_baselines(db_session, batch_item, {"path": str(worktree)})

        event.remove(db_engine, "before_cursor_execute", count_queries)

        assert query_count <= k_gates + 5
