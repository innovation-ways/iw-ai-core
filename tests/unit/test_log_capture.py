"""Unit tests for orch.utils.log_capture."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

from orch.utils.log_capture import DEFAULT_MAX_BYTES, capture_log_content, strip_ansi

if TYPE_CHECKING:
    from pathlib import Path


class TestStripAnsi:
    def test_removes_color_codes(self) -> None:
        assert strip_ansi("\x1b[31mERROR\x1b[0m") == "ERROR"

    def test_removes_cursor_codes(self) -> None:
        assert strip_ansi("\x1b[2Jhello\x1b[H") == "hello"

    def test_preserves_plain_text(self) -> None:
        text = "no ansi here\njust text"
        assert strip_ansi(text) == text

    def test_removes_bold_and_underline(self) -> None:
        assert strip_ansi("\x1b[1mbold\x1b[4munderline\x1b[0m") == "boldunderline"


class TestCaptureLogContent:
    def _make_step_run(
        self, log_file: str | None = None, log_content: str | None = None
    ) -> MagicMock:
        run = MagicMock()
        run.log_file = log_file
        run.log_content = log_content
        return run

    def test_noop_when_log_file_is_none(self) -> None:
        run = self._make_step_run(log_file=None, log_content=None)
        capture_log_content(run)
        # log_content should remain None — no file to read
        assert run.log_content is None

    def test_capture_from_existing_file(self, tmp_path: Path) -> None:
        log = tmp_path / "test.log"
        log.write_text("line 1\nline 2\nline 3\n")
        run = self._make_step_run(log_file=str(log))
        capture_log_content(run)
        assert run.log_content == "line 1\nline 2\nline 3\n"

    def test_capture_strips_ansi(self, tmp_path: Path) -> None:
        log = tmp_path / "test.log"
        log.write_text("\x1b[32mOK\x1b[0m step done\n")
        run = self._make_step_run(log_file=str(log))
        capture_log_content(run)
        assert run.log_content == "OK step done\n"

    def test_capture_missing_file(self, tmp_path: Path) -> None:
        run = self._make_step_run(log_file=str(tmp_path / "nonexistent.log"))
        capture_log_content(run)
        assert run.log_content is not None
        assert "[Log file not found:" in run.log_content

    def test_capture_truncates_large_file(self, tmp_path: Path) -> None:
        log = tmp_path / "big.log"
        # Write >2MB of content
        line = "A" * 200 + "\n"
        num_lines = (DEFAULT_MAX_BYTES // len(line)) + 1000
        log.write_text(line * num_lines)

        run = self._make_step_run(log_file=str(log))
        capture_log_content(run)

        assert run.log_content is not None
        assert run.log_content.startswith("[truncated:")
        # Content should be under the limit (plus header)
        assert len(run.log_content.encode("utf-8")) < DEFAULT_MAX_BYTES + 500

    def test_capture_empty_file(self, tmp_path: Path) -> None:
        log = tmp_path / "empty.log"
        log.write_text("")
        run = self._make_step_run(log_file=str(log))
        capture_log_content(run)
        assert run.log_content == ""
