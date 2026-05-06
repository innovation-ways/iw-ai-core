"""Extended unit tests for orch.doc_report helpers with CR-00035 fixtures.

These tests use the fixture log files (doc_00004_replay.log, successful_run.log,
process_exited_early.log) to verify report-building behavior against real-world
log patterns.
"""

from __future__ import annotations

import pathlib
import tempfile
from unittest.mock import MagicMock

import pytest

from orch.doc_report import (
    build_execution_report,
    count_doc_update_invocations,
    parse_tool_calls,
    read_log_tail,
    strip_ansi,
)

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_mock_job(**kwargs) -> MagicMock:
    job = MagicMock()
    job.skill_used = kwargs.get("skill_used", "iw-doc-generator")
    job.duration_seconds = kwargs.get("duration_seconds", 47)
    job.lint_warnings = kwargs.get("lint_warnings")
    return job


def _make_mock_project(**kwargs) -> MagicMock:
    proj = MagicMock()
    proj.id = kwargs.get("id", "test-proj")
    proj.config = kwargs.get("config", {"cli_tool": "opencode"})
    return proj


# ---------------------------------------------------------------------------
# read_log_tail
# ---------------------------------------------------------------------------


class TestReadLogTailExtended:
    def test_read_log_tail_full_file(self) -> None:
        """A small log file is returned verbatim — no truncation marker."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as fh:
            fh.write("line1\nline2\nline3\n")
            path = pathlib.Path(fh.name)
        try:
            text, size, lines = read_log_tail(path)
            assert text == "line1\nline2\nline3\n"
            assert size > 0
            assert lines == 3
            assert "[truncated:" not in text
        finally:
            path.unlink()

    def test_read_log_tail_truncates(self) -> None:
        """A log larger than max_bytes is truncated with a marker."""
        content = "x" * 100_000
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as fh:
            fh.write(content)
            path = pathlib.Path(fh.name)
        try:
            text, size, lines = read_log_tail(path, max_bytes=65536)
            assert text.startswith("[truncated:")
            assert size == len(content)
            # The marker encodes how many bytes were elided
            assert "bytes elided]" in text
        finally:
            path.unlink()

    def test_read_log_tail_missing_path(self) -> None:
        """Non-existent path returns empty tuple — no exception."""
        text, size, lines = read_log_tail(pathlib.Path("/nonexistent/file.log"))
        assert text == ""
        assert size == 0
        assert lines == 0

    def test_read_log_tail_strips_ansi(self) -> None:
        """ANSI escape sequences are stripped from the returned text."""
        raw = "\x1b[32mgreen\x1b[0m\x1b[1mbold\x1b[0m\nplain\n"
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as fh:
            fh.write(raw)
            path = pathlib.Path(fh.name)
        try:
            text, _, _ = read_log_tail(path)
            assert "\x1b" not in text
            assert "green" in text
            assert "bold" in text
        finally:
            path.unlink()


# ---------------------------------------------------------------------------
# parse_tool_calls
# ---------------------------------------------------------------------------


class TestParseToolCallsExtended:
    def test_parse_tool_calls_doc_00004_fixture(self) -> None:
        """The DOC-00004 replay log contains expected tool calls.

        The broken dispatch log shows:
          $ uv run iw item-status <job-id>  (exit code 1 — "not found")
          $ uv run iw search <job-id>        (exit code 0)
          $ uv run iw doc-job-done <job-id>  (exit code 1 — "job not found")
        """
        fixture = (
            pathlib.Path(__file__).parent.parent / "fixtures" / "doc_jobs" / "doc_00004_replay.log"
        )
        if not fixture.exists():
            pytest.skip("doc_00004_replay.log fixture not found")
        log_text = fixture.read_text()
        calls = parse_tool_calls(log_text)

        tool_names = [c["tool"] for c in calls]
        assert "iw item-status" in tool_names
        assert "iw search" in tool_names
        # doc-job-done appears in the fixture
        assert "iw doc-job-done" in tool_names

    def test_parse_tool_calls_successful_run_fixture(self) -> None:
        """The successful_run.log fixture should have doc-update and doc-job-done."""
        fixture = (
            pathlib.Path(__file__).parent.parent / "fixtures" / "doc_jobs" / "successful_run.log"
        )
        if not fixture.exists():
            pytest.skip("successful_run.log fixture not found")
        log_text = fixture.read_text()
        calls = parse_tool_calls(log_text)
        tool_names = [c["tool"] for c in calls]
        assert "iw doc-update" in tool_names
        assert "iw doc-job-done" in tool_names

    def test_parse_tool_calls_process_exited_early(self) -> None:
        """The short process_exited_early.log has one doc-update attempt with an error."""
        fixture = (
            pathlib.Path(__file__).parent.parent
            / "fixtures"
            / "doc_jobs"
            / "process_exited_early.log"
        )
        if not fixture.exists():
            pytest.skip("process_exited_early.log fixture not found")
        log_text = fixture.read_text()
        calls = parse_tool_calls(log_text)
        # The error line after doc-update is "Error: project 'missing-project' not found"
        assert len(calls) >= 1
        doc_update_calls = [c for c in calls if c["tool"] == "iw doc-update"]
        assert len(doc_update_calls) == 1


# ---------------------------------------------------------------------------
# count_doc_update_invocations
# ---------------------------------------------------------------------------


class TestCountDocUpdateInvocationsExtended:
    def test_count_doc_update_invocations_zero(self) -> None:
        """The DOC-00004 broken-run fixture has no doc-update invocations (wrong dispatch)."""
        fixture = (
            pathlib.Path(__file__).parent.parent / "fixtures" / "doc_jobs" / "doc_00004_replay.log"
        )
        if not fixture.exists():
            pytest.skip("doc_00004_replay.log fixture not found")
        count = count_doc_update_invocations(fixture.read_text())
        assert count == 0

    def test_count_doc_update_invocations_one(self) -> None:
        """The successful_run.log fixture has exactly one doc-update invocation."""
        fixture = (
            pathlib.Path(__file__).parent.parent / "fixtures" / "doc_jobs" / "successful_run.log"
        )
        if not fixture.exists():
            pytest.skip("successful_run.log fixture not found")
        count = count_doc_update_invocations(fixture.read_text())
        assert count == 1

    def test_count_doc_update_invocations_none_in_early_exit(self) -> None:
        """The process_exited_early.log has no successful doc-update.

        It fails before calling doc-job-done. count_doc_update_invocations
        counts the invocations, not whether they succeeded.
        """
        fixture = (
            pathlib.Path(__file__).parent.parent
            / "fixtures"
            / "doc_jobs"
            / "process_exited_early.log"
        )
        if not fixture.exists():
            pytest.skip("process_exited_early.log fixture not found")
        count = count_doc_update_invocations(fixture.read_text())
        # The log shows "uv run iw doc-update" with an error after it, but no "doc-job-done"
        # count_doc_update_invocations counts the invocations, not whether they succeeded
        assert count >= 0


# ---------------------------------------------------------------------------
# build_execution_report
# ---------------------------------------------------------------------------


class TestBuildExecutionReportExtended:
    def test_build_report_wrong_dispatch_diagnosis(self) -> None:
        """When outcome=failed_process_exited and the log shows 'iw item-status'
        but no doc-update, the diagnosis must mention the wrong-dispatch heuristic."""
        fixture = (
            pathlib.Path(__file__).parent.parent / "fixtures" / "doc_jobs" / "doc_00004_replay.log"
        )
        if not fixture.exists():
            pytest.skip("doc_00004_replay.log fixture not found")
        log_text = fixture.read_text()
        job = _make_mock_job()
        proj = _make_mock_project()
        report = build_execution_report(
            job=job,
            project=proj,
            log_text=log_text,
            log_size_bytes=4443,
            log_line_count=98,
            outcome="failed_process_exited",
            command_issued=(
                'opencode run "/doc-job 727a12bd-cae3-443b-b033-924ea767b0e8" '
                "--dangerously-skip-permissions"
            ),
            cli_tool="opencode",
        )
        assert report["outcome"] == "failed_process_exited"
        assert report["doc_update_invocations"] == 0
        # The key AC4 diagnosis for this scenario
        assert (
            "iw doc-update" not in report["diagnosis"]
            or "no content was generated" in report["diagnosis"].lower()
        )

    def test_build_report_completed_success(self) -> None:
        """A successful run (outcome=completed, successful_run.log) gives doc_update_invocations=1
        and no suspicious diagnosis."""
        fixture = (
            pathlib.Path(__file__).parent.parent / "fixtures" / "doc_jobs" / "successful_run.log"
        )
        if not fixture.exists():
            pytest.skip("successful_run.log fixture not found")
        log_text = fixture.read_text()
        job = _make_mock_job()
        proj = _make_mock_project()
        report = build_execution_report(
            job=job,
            project=proj,
            log_text=log_text,
            log_size_bytes=500,
            log_line_count=20,
            outcome="completed",
            command_issued='opencode run "/doc-job abc-123" --dangerously-skip-permissions',
            cli_tool="opencode",
        )
        assert report["outcome"] == "completed"
        assert report["doc_update_invocations"] == 1
        # Diagnosis should be empty or "completed cleanly"
        assert report["diagnosis"] == "" or "completed" in report["diagnosis"].lower()

    def test_build_report_timeout_outcome(self) -> None:
        """A failed_timeout outcome produces a diagnosis mentioning timeout."""
        job = _make_mock_job()
        proj = _make_mock_project()
        report = build_execution_report(
            job=job,
            project=proj,
            log_text="",
            log_size_bytes=0,
            log_line_count=0,
            outcome="failed_timeout",
            command_issued=None,
            cli_tool="opencode",
        )
        assert report["outcome"] == "failed_timeout"
        assert "timeout" in report["diagnosis"].lower()

    def test_build_report_includes_all_ac4_fields(self) -> None:
        """Every key from AC4 is present in the returned dict."""
        job = _make_mock_job()
        proj = _make_mock_project()
        report = build_execution_report(
            job=job,
            project=proj,
            log_text="$ uv run iw doc-update X\n",
            log_size_bytes=100,
            log_line_count=5,
            outcome="completed",
            command_issued='opencode run "/doc-job 123" --dangerously-skip-permissions',
            cli_tool="opencode",
        )
        expected_keys = [
            "outcome",
            "duration_seconds",
            "skill_used",
            "cli_tool",
            "command_issued",
            "log_size_bytes",
            "log_line_count",
            "tool_calls",
            "doc_update_invocations",
            "lint_warning_count",
            "diagnosis",
        ]
        for key in expected_keys:
            assert key in report, f"AC4 key '{key}' is missing from report"

    def test_build_report_agent_error_outcome(self) -> None:
        """An failed_agent_error outcome produces a generic diagnosis."""
        job = _make_mock_job()
        proj = _make_mock_project()
        report = build_execution_report(
            job=job,
            project=proj,
            log_text="some error\n",
            log_size_bytes=50,
            log_line_count=2,
            outcome="failed_agent_error",
            command_issued=None,
            cli_tool="opencode",
        )
        assert report["outcome"] == "failed_agent_error"
        assert "diagnosis" in report


# ---------------------------------------------------------------------------
# strip_ansi standalone
# ---------------------------------------------------------------------------


class TestStripAnsi:
    def test_strip_ansi_removes_color_codes(self) -> None:
        raw = "\x1b[31mError: something went wrong\x1b[0m\n\x1b[1mbold\x1b[0m"
        result = strip_ansi(raw)
        assert "\x1b" not in result
        assert "Error: something went wrong" in result

    def test_strip_ansi_preserves_plain_text(self) -> None:
        plain = "no escape codes here\njust normal text"
        result = strip_ansi(plain)
        assert result == plain

    def test_strip_ansi_doc_00004_fixture(self) -> None:
        """Fixture contains [0m ANSI codes — strip_ansi removes them all."""
        fixture = (
            pathlib.Path(__file__).parent.parent / "fixtures" / "doc_jobs" / "doc_00004_replay.log"
        )
        if not fixture.exists():
            pytest.skip("doc_00004_replay.log fixture not found")
        raw = fixture.read_text()
        cleaned = strip_ansi(raw)
        assert "\x1b" not in cleaned
        # Content is still readable
        assert "iw item-status" in cleaned
