"""Unit tests for _parse_and_store_fix_summary from orch.daemon.fix_cycle.

Tests JSON parsing, truncation at 20000 chars, and edge cases for malformed input.
"""

from __future__ import annotations

import json
import tempfile
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from pathlib import Path

from orch.daemon.fix_cycle import _parse_and_store_fix_summary


class TestParseAndStoreFixSummary:
    """Test _parse_and_store_fix_summary with various JSON inputs."""

    def _make_cycle_with_log_file(self, content: str) -> tuple[MagicMock, str]:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write(content)
        cycle = MagicMock()
        cycle.fix_metadata = {"log_file": tmp.name}
        cycle.fix_summary = None
        return cycle, tmp.name

    def test_valid_fix_summary_stored(self, tmp_path: Path) -> None:
        log_content = json.dumps({"fix_summary": "Fixed the SQL injection issue"})
        log_file = tmp_path / "fix_cycle.json"
        log_file.write_text(log_content)

        cycle = MagicMock()
        cycle.fix_metadata = {"log_file": str(log_file)}
        cycle.fix_summary = None

        _parse_and_store_fix_summary(cycle)
        assert cycle.fix_summary == "Fixed the SQL injection issue"

    def test_missing_fix_summary_key_stores_none(self, tmp_path: Path) -> None:
        log_content = json.dumps({"other_key": "some_value"})
        log_file = tmp_path / "fix_cycle.json"
        log_file.write_text(log_content)

        cycle = MagicMock()
        cycle.fix_metadata = {"log_file": str(log_file)}
        cycle.fix_summary = "previous_value"

        _parse_and_store_fix_summary(cycle)
        assert cycle.fix_summary is None

    def test_empty_string_fix_summary_stores_none(self, tmp_path: Path) -> None:
        log_content = json.dumps({"fix_summary": ""})
        log_file = tmp_path / "fix_cycle.json"
        log_file.write_text(log_content)

        cycle = MagicMock()
        cycle.fix_metadata = {"log_file": str(log_file)}
        cycle.fix_summary = None

        _parse_and_store_fix_summary(cycle)
        assert cycle.fix_summary is None

    def test_whitespace_only_fix_summary_stores_none(self, tmp_path: Path) -> None:
        log_content = json.dumps({"fix_summary": "   \n\t  "})
        log_file = tmp_path / "fix_cycle.json"
        log_file.write_text(log_content)

        cycle = MagicMock()
        cycle.fix_metadata = {"log_file": str(log_file)}
        cycle.fix_summary = None

        _parse_and_store_fix_summary(cycle)
        assert cycle.fix_summary is None

    def test_content_up_to_20000_chars_stored_verbatim(self, tmp_path: Path) -> None:
        long_content = "x" * 20000
        log_content = json.dumps({"fix_summary": long_content})
        log_file = tmp_path / "fix_cycle.json"
        log_file.write_text(log_content)

        cycle = MagicMock()
        cycle.fix_metadata = {"log_file": str(log_file)}
        cycle.fix_summary = None

        _parse_and_store_fix_summary(cycle)
        assert cycle.fix_summary == long_content

    def test_content_over_20000_chars_truncated(self, tmp_path: Path) -> None:
        long_content = "x" * 25000
        log_content = json.dumps({"fix_summary": long_content})
        log_file = tmp_path / "fix_cycle.json"
        log_file.write_text(log_content)

        cycle = MagicMock()
        cycle.fix_metadata = {"log_file": str(log_file)}
        cycle.fix_summary = None

        _parse_and_store_fix_summary(cycle)
        assert len(cycle.fix_summary) == 20000

    def test_malformed_json_stores_none_no_exception(self, tmp_path: Path) -> None:
        log_content = "not valid json {"
        log_file = tmp_path / "fix_cycle.json"
        log_file.write_text(log_content)

        cycle = MagicMock()
        cycle.fix_metadata = {"log_file": str(log_file)}
        cycle.fix_summary = None

        _parse_and_store_fix_summary(cycle)
        assert cycle.fix_summary is None

    def test_no_log_file_key_no_crash(self) -> None:
        cycle = MagicMock()
        cycle.fix_metadata = {}
        cycle.fix_summary = None

        _parse_and_store_fix_summary(cycle)
        assert cycle.fix_summary is None

    def test_none_fix_metadata_no_crash(self) -> None:
        cycle = MagicMock()
        cycle.fix_metadata = None
        cycle.fix_summary = None

        _parse_and_store_fix_summary(cycle)
        assert cycle.fix_summary is None

    def test_log_file_not_found_no_crash(self) -> None:
        cycle = MagicMock()
        cycle.fix_metadata = {"log_file": "/nonexistent/path/fix.json"}
        cycle.fix_summary = "previous"

        _parse_and_store_fix_summary(cycle)
        assert cycle.fix_summary == "previous"

    def test_fix_summary_not_a_string_no_crash(self, tmp_path: Path) -> None:
        log_content = json.dumps({"fix_summary": 12345})
        log_file = tmp_path / "fix_cycle.json"
        log_file.write_text(log_content)

        cycle = MagicMock()
        cycle.fix_metadata = {"log_file": str(log_file)}
        cycle.fix_summary = None

        _parse_and_store_fix_summary(cycle)
        assert cycle.fix_summary is None

    def test_fix_summary_is_list_no_crash(self, tmp_path: Path) -> None:
        log_content = json.dumps({"fix_summary": ["item1", "item2"]})
        log_file = tmp_path / "fix_cycle.json"
        log_file.write_text(log_content)

        cycle = MagicMock()
        cycle.fix_metadata = {"log_file": str(log_file)}
        cycle.fix_summary = None

        _parse_and_store_fix_summary(cycle)
        assert cycle.fix_summary is None

    def test_existing_fix_summary_preserved_on_error(self, tmp_path: Path) -> None:
        log_content = "invalid json"
        log_file = tmp_path / "fix_cycle.json"
        log_file.write_text(log_content)

        cycle = MagicMock()
        cycle.fix_metadata = {"log_file": str(log_file)}
        cycle.fix_summary = "already_set"

        _parse_and_store_fix_summary(cycle)
        assert cycle.fix_summary == "already_set"


class TestMaxFixSummaryLength:
    """Test the 20000 character limit constant."""

    def test_max_fix_summary_length_constant(self) -> None:
        from orch.daemon.fix_cycle import _MAX_FIX_SUMMARY_LEN

        assert _MAX_FIX_SUMMARY_LEN == 20000

    def test_exactly_20000_chars_not_truncated(self, tmp_path: Path) -> None:
        content = "y" * 20000
        log_content = json.dumps({"fix_summary": content})
        log_file = tmp_path / "fix_cycle.json"
        log_file.write_text(log_content)

        cycle = MagicMock()
        cycle.fix_metadata = {"log_file": str(log_file)}
        cycle.fix_summary = None

        _parse_and_store_fix_summary(cycle)
        assert len(cycle.fix_summary) == 20000

    def test_20001_chars_truncated_to_20000(self, tmp_path: Path) -> None:
        content = "z" * 20001
        log_content = json.dumps({"fix_summary": content})
        log_file = tmp_path / "fix_cycle.json"
        log_file.write_text(log_content)

        cycle = MagicMock()
        cycle.fix_metadata = {"log_file": str(log_file)}
        cycle.fix_summary = None

        _parse_and_store_fix_summary(cycle)
        assert len(cycle.fix_summary) == 20000
        assert cycle.fix_summary == "z" * 20000
