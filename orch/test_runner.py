"""Background test execution engine.

Launches test commands as subprocesses, captures output, runs allure generate,
parses results, and updates DB state. Designed to run in daemon threads
(same pattern as archive_batch in dashboard/routers/actions.py).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from orch.db.models import DaemonEvent, Project, TestRun, TestRunStatus
from orch.db.session import SessionLocal

logger = logging.getLogger(__name__)

# ANSI escape code pattern for stripping from log output
_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# Default subprocess timeout — overridden per-project via test_config/quality_config.timeout_secs
_DEFAULT_TEST_TIMEOUT_SECS = 3600  # 1 hour


def launch_test_run(run_id: int) -> None:
    """Execute a test run in a background thread.

    Opens its own DB session. Updates status through the lifecycle:
    pending -> running -> passed/failed/error.
    """
    db = SessionLocal()
    try:
        run = db.scalar(select(TestRun).where(TestRun.id == run_id))
        if run is None:
            logger.error("TestRun %d not found", run_id)
            return

        project_id = run.project_id
        event_prefix = "quality" if run.run_type == "quality" else "test"
        execution_dir = _resolve_execution_dir(run, db)
        if execution_dir is None:
            run.status = TestRunStatus.error
            run.finished_at = datetime.now(UTC)
            _emit_event(
                db, project_id, f"{event_prefix}_failed", str(run_id), "No execution_dir configured"
            )
            db.commit()
            return

        # Prepare log directory
        log_dir = Path(execution_dir) / "logs" / "test_runs" / project_id
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{run_id}.log"

        # Resolve per-run allure directories so concurrent runs don't clobber each other.
        # Results use a unique run-scoped name; the persistent HTML report keeps the run_id too.
        allure_results, allure_report = _resolve_allure_dirs(run, db, execution_dir, run_id)
        run.allure_results_dir = allure_results
        run.allure_report_dir = allure_report

        # When the command is a make invocation, override ALLURE_RESULTS so the Makefile
        # target writes to the run-specific directory instead of the shared default.
        command = run.command
        if allure_results and "make " in command:
            results_rel = Path(allure_results).relative_to(execution_dir)
            command = f"ALLURE_RESULTS={results_rel} {command}"

        # Update status to running
        run.status = TestRunStatus.running
        run.started_at = datetime.now(UTC)
        run.log_path = str(log_path)
        db.commit()

        _emit_event(
            db,
            project_id,
            f"{event_prefix}_started",
            str(run_id),
            f"Test run {run_id} started: {run.category}",
        )

        # Launch subprocess
        start_time = time.monotonic()
        test_timeout = _resolve_test_timeout(run, db)
        try:
            with Path(log_path).open("w") as log_file:
                proc = subprocess.Popen(
                    command,
                    shell=True,
                    cwd=execution_dir,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    preexec_fn=os.setsid,
                )

            # Store PID for kill support
            run.pid = proc.pid
            db.commit()

            try:
                exit_code = proc.wait(timeout=test_timeout)
            except subprocess.TimeoutExpired:
                logger.warning(
                    "TestRun %d timed out after %ds — killing process group",
                    run_id,
                    test_timeout,
                )
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                time.sleep(3)
                with contextlib.suppress(ProcessLookupError, PermissionError):
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                proc.wait()
                run.status = TestRunStatus.error
                run.finished_at = datetime.now(UTC)
                run.duration_secs = time.monotonic() - start_time
                run.pid = None
                _emit_event(
                    db,
                    project_id,
                    f"{event_prefix}_failed",
                    str(run_id),
                    f"Test run timed out after {test_timeout}s",
                )
                db.commit()
                return
        except Exception as exc:
            logger.exception("Subprocess error for TestRun %d", run_id)
            run.status = TestRunStatus.error
            run.finished_at = datetime.now(UTC)
            run.duration_secs = time.monotonic() - start_time
            _emit_event(
                db, project_id, f"{event_prefix}_failed", str(run_id), f"Subprocess error: {exc}"
            )
            db.commit()
            return

        elapsed = time.monotonic() - start_time

        # Check if cancelled while running (query without refreshing)
        current_status = db.scalar(select(TestRun.status).where(TestRun.id == run_id))
        if current_status == TestRunStatus.cancelled:
            return

        # Now update the run with results
        run.exit_code = exit_code
        run.finished_at = datetime.now(UTC)
        run.duration_secs = elapsed
        run.pid = None  # Process is done

        # Generate allure report if results directory exists (skipped for quality runs).
        # After generating the HTML report the raw results dir is deleted — it can be large
        # (thousands of JSON files) and everything needed is in the HTML report.
        if run.run_type != "quality" and allure_results and Path(allure_results).is_dir():
            _generate_allure_report(allure_results, allure_report, execution_dir)
            shutil.rmtree(allure_results, ignore_errors=True)
            summary = parse_allure_summary(allure_report)
            if summary:
                run.summary = summary

        # Set final status
        if exit_code == 0:
            run.status = TestRunStatus.passed
            _emit_event(
                db,
                project_id,
                f"{event_prefix}_completed",
                str(run_id),
                f"Tests passed ({run.category})",
            )
        else:
            run.status = TestRunStatus.failed
            _emit_event(
                db,
                project_id,
                f"{event_prefix}_failed",
                str(run_id),
                f"Tests failed ({run.category}, exit code {exit_code})",
            )

        db.commit()
    except Exception:
        logger.exception("Unhandled error in launch_test_run(%d)", run_id)
        try:
            db.rollback()
            run = db.scalar(select(TestRun).where(TestRun.id == run_id))
            if run and run.status not in (
                TestRunStatus.cancelled,
                TestRunStatus.passed,
                TestRunStatus.failed,
            ):
                run.status = TestRunStatus.error
                run.finished_at = datetime.now(UTC)
                db.commit()
        except Exception:
            logger.exception("Failed to mark TestRun %d as error", run_id)
    finally:
        db.close()


def kill_test_run(run_id: int) -> bool:
    """Kill a running test by sending SIGTERM to its process group.

    Returns True if signal was sent successfully.
    """
    db = SessionLocal()
    try:
        run = db.scalar(select(TestRun).where(TestRun.id == run_id))
        if run is None:
            return False
        if run.status != TestRunStatus.running:
            return False
        if run.pid is None:
            run.status = TestRunStatus.cancelled
            run.finished_at = datetime.now(UTC)
            db.commit()
            return True

        with contextlib.suppress(ProcessLookupError, PermissionError):
            os.killpg(os.getpgid(run.pid), signal.SIGTERM)

        run.status = TestRunStatus.cancelled
        run.finished_at = datetime.now(UTC)
        run.pid = None
        _emit_event(
            db, run.project_id, "test_failed", str(run_id), f"Test run {run_id} cancelled by user"
        )
        db.commit()
        return True
    finally:
        db.close()


def parse_allure_summary(report_dir: str | None) -> dict[str, Any] | None:
    """Read and return Allure summary data from the widgets directory.

    Supports both Allure 3.x (widgets/statistic.json) and Allure 2.x (widgets/summary.json).
    Returns a normalized dict with keys: statistic (total/passed/failed/skipped/broken)
    and time (duration).
    """
    if not report_dir:
        return None
    widgets = Path(report_dir) / "widgets"

    # Allure 3.x: statistic.json has flat {total, passed, failed, ...}
    stat_path = widgets / "statistic.json"
    if stat_path.is_file():
        try:
            stat = json.loads(stat_path.read_text(encoding="utf-8"))
            # Normalize to the format our dashboard expects
            return {
                "statistic": {
                    "total": stat.get("total", 0),
                    "passed": stat.get("passed", 0),
                    "failed": stat.get("failed", 0),
                    "skipped": stat.get("skipped", 0),
                    "broken": stat.get("broken", 0),
                },
                "time": {"duration": 0},
            }
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to parse Allure statistic at %s", stat_path)

    # Allure 2.x: summary.json has {statistic: {...}, time: {...}}
    summary_path = widgets / "summary.json"
    if summary_path.is_file():
        try:
            return json.loads(summary_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError):
            logger.warning("Failed to parse Allure summary at %s", summary_path)

    return None


def mark_orphaned_runs() -> int:
    """Mark any 'running' test runs as 'error' (stale PIDs after restart).

    Returns count of orphaned runs found.
    """
    db = SessionLocal()
    try:
        runs = list(db.scalars(select(TestRun).where(TestRun.status == TestRunStatus.running)))
        for run in runs:
            run.status = TestRunStatus.error
            run.finished_at = datetime.now(UTC)
            run.pid = None
        if runs:
            db.commit()
        return len(runs)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _resolve_execution_dir(run: TestRun, db: Any) -> str | None:
    """Get the execution directory from project config."""

    project = db.scalar(select(Project).where(Project.id == run.project_id))
    if project is None:
        return None
    config = project.config or {}
    config_key = "quality_config" if run.run_type == "quality" else "test_config"
    section = config.get(config_key, {})
    return section.get("execution_dir")  # type: ignore[no-any-return]


def _resolve_test_timeout(run: TestRun, db: Any) -> int:
    """Get the subprocess timeout (seconds) from project config, or the platform default."""
    project = db.scalar(select(Project).where(Project.id == run.project_id))
    if project is None:
        return _DEFAULT_TEST_TIMEOUT_SECS
    config = project.config or {}
    config_key = "quality_config" if run.run_type == "quality" else "test_config"
    section = config.get(config_key, {})
    raw = section.get("timeout_secs")
    return int(raw) if raw else _DEFAULT_TEST_TIMEOUT_SECS


def _resolve_allure_dirs(
    run: TestRun, db: Any, execution_dir: str, run_id: int | None = None
) -> tuple[str | None, str | None]:
    """Get per-run allure results and report directories.

    Directory names are scoped by run_id (e.g. ``allure-results-42``,
    ``allure-report-42``) so concurrent test runs never share a directory.
    """
    project = db.scalar(select(Project).where(Project.id == run.project_id))
    if project is None:
        return None, None
    config = project.config or {}
    config_key = "quality_config" if run.run_type == "quality" else "test_config"
    section = config.get(config_key, {})

    results_base = section.get("allure_results_dir", "allure-results")
    report_base = section.get("allure_report_dir", "allure-report")

    # Append run_id suffix for isolation when provided
    suffix = f"-{run_id}" if run_id is not None else ""
    results_abs = str(Path(execution_dir) / f"{results_base}{suffix}")
    report_abs = str(Path(execution_dir) / f"{report_base}{suffix}")
    return results_abs, report_abs


def _generate_allure_report(results_dir: str, report_dir: str | None, cwd: str) -> bool:
    """Run ``allure generate`` to produce the HTML report.

    Passes the results directory explicitly so Allure 3.x doesn't fall back
    to its default glob (``**/*allure-results``) which would pick up results
    from other concurrent runs.
    """
    if not report_dir:
        return False
    try:
        # Allure 3.x doesn't overwrite — delete existing report first
        report_path = Path(report_dir)
        if report_path.is_dir():
            shutil.rmtree(report_path, ignore_errors=True)

        # Allure 3.x: positional arg is the results directory
        result = subprocess.run(
            ["npx", "allure", "generate", results_dir, "-o", report_dir],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.warning("allure generate failed: %s", result.stderr[:500])
            return False
        return True
    except (subprocess.TimeoutExpired, OSError) as exc:
        logger.warning("allure generate error: %s", exc)
        return False


def _emit_event(db: Any, project_id: str, event_type: str, entity_id: str, message: str) -> None:
    """Insert a DaemonEvent for SSE consumption."""
    db.add(
        DaemonEvent(
            project_id=project_id,
            event_type=event_type,
            entity_id=entity_id,
            message=message,
        )
    )
    db.flush()
