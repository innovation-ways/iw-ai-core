"""Unit tests for orch/test_runner.py run_type-aware behavior.

Tests the following:
- _resolve_execution_dir uses "quality_config" when run_type == "quality"
- _resolve_execution_dir uses "test_config" when run_type == "test"
- _resolve_allure_dirs uses "quality_config" when run_type == "quality"
- _resolve_allure_dirs uses "test_config" when run_type == "test"
- launch_test_run skips allure cleanup for quality runs
- launch_test_run skips allure report generation for quality runs
- launch_test_run emits "quality_started" / "quality_completed" / "quality_failed" for quality runs
- launch_test_run emits "test_started" / "test_completed" / "test_failed" for test runs
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from orch.db.models import TestRunStatus
from orch.test_runner import _resolve_allure_dirs, _resolve_execution_dir

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(run_type: str = "test") -> Any:
    """Build a minimal mock TestRun (avoids SQLAlchemy instrumentation issues)."""
    run = MagicMock()
    run.id = 1
    run.project_id = "proj-x"
    run.category = "unit"
    run.status = TestRunStatus.pending
    run.command = "make test"
    run.exit_code = None
    run.started_at = None
    run.finished_at = None
    run.duration_secs = None
    run.pid = None
    run.log_path = None
    run.allure_results_dir = None
    run.allure_report_dir = None
    run.summary = None
    run.run_type = run_type
    return run


def _make_project_with_config(config: dict[str, Any]) -> Any:
    """Build a minimal mock Project with the given config."""
    proj = MagicMock()
    proj.id = "proj-x"
    proj.config = config
    return proj


def _make_db_scalar(project: Any) -> MagicMock:
    """Build a mock db whose scalar() returns the given project."""
    db = MagicMock()
    db.scalar.return_value = project
    return db


# ---------------------------------------------------------------------------
# _resolve_execution_dir
# ---------------------------------------------------------------------------


class TestResolveExecutionDir:
    def test_uses_test_config_for_test_run_type(self) -> None:
        config = {
            "test_config": {"execution_dir": "/app/test"},
            "quality_config": {"execution_dir": "/app/quality"},
        }
        project = _make_project_with_config(config)
        db = _make_db_scalar(project)
        run = _make_run(run_type="test")

        result = _resolve_execution_dir(run, db)

        assert result == "/app/test"

    def test_uses_quality_config_for_quality_run_type(self) -> None:
        config = {
            "test_config": {"execution_dir": "/app/test"},
            "quality_config": {"execution_dir": "/app/quality"},
        }
        project = _make_project_with_config(config)
        db = _make_db_scalar(project)
        run = _make_run(run_type="quality")

        result = _resolve_execution_dir(run, db)

        assert result == "/app/quality"

    def test_returns_none_when_project_not_found(self) -> None:
        db = MagicMock()
        db.scalar.return_value = None
        run = _make_run(run_type="test")

        result = _resolve_execution_dir(run, db)

        assert result is None

    def test_returns_none_when_execution_dir_missing_in_config(self) -> None:
        project = _make_project_with_config({"test_config": {}})
        db = _make_db_scalar(project)
        run = _make_run(run_type="test")

        result = _resolve_execution_dir(run, db)

        assert result is None

    def test_quality_returns_none_when_quality_config_missing(self) -> None:
        project = _make_project_with_config({"test_config": {"execution_dir": "/app/test"}})
        db = _make_db_scalar(project)
        run = _make_run(run_type="quality")

        # quality_config not present — should return None
        result = _resolve_execution_dir(run, db)

        assert result is None


# ---------------------------------------------------------------------------
# _resolve_allure_dirs
# ---------------------------------------------------------------------------


class TestResolveAllureDirs:
    def test_uses_test_config_for_test_run_type(self) -> None:
        config = {
            "test_config": {
                "allure_results_dir": "test-results",
                "allure_report_dir": "test-report",
            },
            "quality_config": {
                "allure_results_dir": "quality-results",
                "allure_report_dir": "quality-report",
            },
        }
        project = _make_project_with_config(config)
        db = _make_db_scalar(project)
        run = _make_run(run_type="test")

        results, report = _resolve_allure_dirs(run, db, "/exec")

        assert results == "/exec/test-results"
        assert report == "/exec/test-report"

    def test_uses_quality_config_for_quality_run_type(self) -> None:
        config = {
            "test_config": {
                "allure_results_dir": "test-results",
                "allure_report_dir": "test-report",
            },
            "quality_config": {
                "allure_results_dir": "quality-results",
                "allure_report_dir": "quality-report",
            },
        }
        project = _make_project_with_config(config)
        db = _make_db_scalar(project)
        run = _make_run(run_type="quality")

        results, report = _resolve_allure_dirs(run, db, "/exec")

        assert results == "/exec/quality-results"
        assert report == "/exec/quality-report"

    def test_falls_back_to_defaults_for_test_run_type(self) -> None:
        project = _make_project_with_config({"test_config": {}})
        db = _make_db_scalar(project)
        run = _make_run(run_type="test")

        results, report = _resolve_allure_dirs(run, db, "/exec")

        assert results == "/exec/allure-results"
        assert report == "/exec/allure-report"

    def test_falls_back_to_defaults_for_quality_run_type(self) -> None:
        project = _make_project_with_config({"quality_config": {}})
        db = _make_db_scalar(project)
        run = _make_run(run_type="quality")

        results, report = _resolve_allure_dirs(run, db, "/exec")

        assert results == "/exec/allure-results"
        assert report == "/exec/allure-report"

    def test_returns_none_when_project_not_found(self) -> None:
        db = MagicMock()
        db.scalar.return_value = None
        run = _make_run(run_type="test")

        results, report = _resolve_allure_dirs(run, db, "/exec")

        assert results is None
        assert report is None


# ---------------------------------------------------------------------------
# launch_test_run — event type and allure skip behavior
# ---------------------------------------------------------------------------


class TestLaunchTestRunEventTypes:
    """Verify that launch_test_run emits correct event_type based on run_type."""

    def _run_launch(
        self,
        run_type: str,
        exit_code: int,
        tmp_path: Path,
    ) -> list[str]:
        """Execute launch_test_run with a mocked subprocess and collect emitted event types."""
        from orch.test_runner import launch_test_run

        emitted_event_types: list[str] = []

        # Capture calls to _emit_event
        def fake_emit(
            db: Any, project_id: str, event_type: str, entity_id: str, message: str
        ) -> None:
            emitted_event_types.append(event_type)

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.wait.return_value = exit_code

        project_config = {
            "test_config": {"execution_dir": str(tmp_path)},
            "quality_config": {"execution_dir": str(tmp_path)},
        }
        mock_project = MagicMock()
        mock_project.id = "proj-x"
        mock_project.config = project_config

        mock_run = _make_run(run_type=run_type)

        mock_db = MagicMock()

        # scalar call order in launch_test_run (current, pre-fix):
        #   1. select(TestRun) — get the run
        #   2. select(Project) — allure-results cleanup (only for run_type=="test" post-fix)
        #   3. select(Project) — inside _resolve_execution_dir
        #   4. select(TestRun.status) — cancelled check (after subprocess)
        #   5. select(Project) — inside _resolve_allure_dirs (only for run_type=="test" post-fix)
        # Use a function that always returns the right type based on the argument.
        def _scalar_dispatch(stmt: Any) -> Any:
            # Introspect what entity is being selected
            entity = getattr(stmt, "entity", None) or getattr(stmt, "columns_clause_froms", None)
            txt = str(stmt)
            if "test_runs" in txt and "status" in txt and "WHERE" in txt:
                return TestRunStatus.running
            if "test_runs" in txt:
                return mock_run
            # default: project
            return mock_project

        mock_db.scalar.side_effect = _scalar_dispatch

        with (
            patch("orch.test_runner.SessionLocal", return_value=mock_db),
            patch("orch.test_runner._emit_event", side_effect=fake_emit),
            patch("orch.test_runner.subprocess.Popen", return_value=mock_proc),
            patch("orch.test_runner.shutil.rmtree"),
            patch("orch.test_runner._generate_allure_report", return_value=True),
            patch("orch.test_runner.parse_allure_summary", return_value=None),
            patch.object(Path, "mkdir"),
            patch.object(Path, "is_dir", return_value=False),  # allure dir doesn't exist
            patch("builtins.open", MagicMock()),
        ):
            launch_test_run(1)

        return emitted_event_types

    def test_test_run_emits_test_started_on_begin(self, tmp_path: Path) -> None:
        events = self._run_launch(run_type="test", exit_code=0, tmp_path=tmp_path)
        assert "test_started" in events

    def test_test_run_emits_test_completed_on_success(self, tmp_path: Path) -> None:
        events = self._run_launch(run_type="test", exit_code=0, tmp_path=tmp_path)
        assert "test_completed" in events

    def test_test_run_emits_test_failed_on_failure(self, tmp_path: Path) -> None:
        events = self._run_launch(run_type="test", exit_code=1, tmp_path=tmp_path)
        assert "test_failed" in events

    def test_test_run_does_not_emit_quality_events(self, tmp_path: Path) -> None:
        events = self._run_launch(run_type="test", exit_code=0, tmp_path=tmp_path)
        assert not any(e.startswith("quality_") for e in events)

    def test_quality_run_emits_quality_started_on_begin(self, tmp_path: Path) -> None:
        events = self._run_launch(run_type="quality", exit_code=0, tmp_path=tmp_path)
        assert "quality_started" in events

    def test_quality_run_emits_quality_completed_on_success(self, tmp_path: Path) -> None:
        events = self._run_launch(run_type="quality", exit_code=0, tmp_path=tmp_path)
        assert "quality_completed" in events

    def test_quality_run_emits_quality_failed_on_failure(self, tmp_path: Path) -> None:
        events = self._run_launch(run_type="quality", exit_code=1, tmp_path=tmp_path)
        assert "quality_failed" in events

    def test_quality_run_does_not_emit_test_events(self, tmp_path: Path) -> None:
        events = self._run_launch(run_type="quality", exit_code=0, tmp_path=tmp_path)
        assert not any(e.startswith("test_") for e in events)


class TestLaunchTestRunAllureSkip:
    """Verify that allure cleanup and report generation are skipped for quality runs."""

    def _run_launch_track_allure(
        self,
        run_type: str,
        tmp_path: Path,
    ) -> tuple[bool, bool]:
        """Returns (rmtree_called, generate_allure_called)."""
        from orch.test_runner import launch_test_run

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.wait.return_value = 0

        project_config = {
            "test_config": {"execution_dir": str(tmp_path)},
            "quality_config": {"execution_dir": str(tmp_path)},
        }
        mock_project = MagicMock()
        mock_project.id = "proj-x"
        mock_project.config = project_config

        mock_run = _make_run(run_type=run_type)

        mock_db = MagicMock()

        def _scalar_dispatch(stmt: Any) -> Any:
            txt = str(stmt)
            if "test_runs" in txt and "status" in txt and "WHERE" in txt:
                return TestRunStatus.running
            if "test_runs" in txt:
                return mock_run
            return mock_project

        mock_db.scalar.side_effect = _scalar_dispatch

        rmtree_called = False
        generate_allure_called = False

        def fake_rmtree(*args: Any, **kwargs: Any) -> None:
            nonlocal rmtree_called
            rmtree_called = True

        def fake_generate(*args: Any, **kwargs: Any) -> bool:
            nonlocal generate_allure_called
            generate_allure_called = True
            return True

        with (
            patch("orch.test_runner.SessionLocal", return_value=mock_db),
            patch("orch.test_runner._emit_event"),
            patch("orch.test_runner.subprocess.Popen", return_value=mock_proc),
            patch("orch.test_runner.shutil.rmtree", side_effect=fake_rmtree),
            patch("orch.test_runner._generate_allure_report", side_effect=fake_generate),
            patch("orch.test_runner.parse_allure_summary", return_value=None),
            patch.object(Path, "mkdir"),
            # Make allure dir appear to exist so cleanup/generate would trigger if not guarded
            patch.object(Path, "is_dir", return_value=True),
            patch("builtins.open", MagicMock()),
        ):
            launch_test_run(1)

        return rmtree_called, generate_allure_called

    def test_test_run_cleans_allure_results(self, tmp_path: Path) -> None:
        rmtree_called, _ = self._run_launch_track_allure(run_type="test", tmp_path=tmp_path)
        assert rmtree_called is True

    def test_test_run_generates_allure_report(self, tmp_path: Path) -> None:
        _, generate_called = self._run_launch_track_allure(run_type="test", tmp_path=tmp_path)
        assert generate_called is True

    def test_quality_run_skips_allure_cleanup(self, tmp_path: Path) -> None:
        rmtree_called, _ = self._run_launch_track_allure(run_type="quality", tmp_path=tmp_path)
        assert rmtree_called is False

    def test_quality_run_skips_allure_report_generation(self, tmp_path: Path) -> None:
        _, generate_called = self._run_launch_track_allure(run_type="quality", tmp_path=tmp_path)
        assert generate_called is False
