"""Unit tests for CR-00066 token extraction in step_monitor."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Fake StepRun — mirrors the pattern from test_step_monitor_session_file.py
# ---------------------------------------------------------------------------


class _FakeStepRun:
    def __init__(
        self,
        *,
        cli_tool: str = "pi",
        session_file: str | None = None,
        context_tokens_peak: int | None = None,
        context_tokens_last: int | None = None,
        started_at: datetime | None = None,
        pid: int | None = 1,
        step_id: int = 1,
        worktree_path: str | None = None,
    ) -> None:
        self.cli_tool = cli_tool
        self.session_file = session_file
        self.context_tokens_peak = context_tokens_peak
        self.context_tokens_last = context_tokens_last
        self.started_at = started_at
        self.pid = pid
        self.id = 1
        self.step_id = step_id
        self.worktree_path = worktree_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _call_extract_latest_tokens(session_file: str) -> int | None:
    """Import and call the module-level helper after patching."""
    from orch.daemon import step_monitor as sm

    return sm._extract_latest_tokens(session_file)


def _call_poll_update(run: _FakeStepRun) -> None:
    """Call the poll-loop token-update block after patching."""
    from orch.daemon import step_monitor as sm

    sm._update_token_counts(run)


# ---------------------------------------------------------------------------
# _extract_latest_tokens
# ---------------------------------------------------------------------------


def test_extract_latest_tokens_from_valid_jsonl(tmp_path: Path) -> None:
    """Returns totalTokens from the most recent assistant message with usage."""
    jsonl = tmp_path / "session.jsonl"
    # Third message is the most recent; second has no usage; first has lower usage
    lines = [
        json.dumps(
            {
                "type": "message",
                "message": {"role": "assistant", "content": [], "usage": {"totalTokens": 45000}},
            }
        ),
        json.dumps({"type": "tool_call", "tool": "bash", "args": {}}),
        json.dumps(
            {
                "type": "message",
                "message": {"role": "assistant", "content": [], "usage": {"totalTokens": 92000}},
            }
        ),
    ]
    jsonl.write_text("\n".join(lines) + "\n")

    result = _call_extract_latest_tokens(str(jsonl))
    assert result == 92000


def test_extract_latest_tokens_ignores_non_assistant_entries(tmp_path: Path) -> None:
    """Skips user/toolResult entries; finds the last assistant entry."""
    jsonl = tmp_path / "session.jsonl"
    lines = [
        json.dumps({"type": "tool_call", "tool": "bash", "args": {}}),
        json.dumps({"type": "tool_result", "result": "output"}),
        json.dumps({"type": "thinking", "text": "reflecting..."}),
        json.dumps(
            {
                "type": "message",
                "message": {"role": "assistant", "content": [], "usage": {"totalTokens": 66000}},
            }
        ),
        # After the assistant message, a tool result
        json.dumps({"type": "tool_result", "result": "done"}),
        # This tool_result would be the "last" line by raw position
        # but the assistant message above should be the last assistant message
    ]
    jsonl.write_text("\n".join(lines) + "\n")

    result = _call_extract_latest_tokens(str(jsonl))
    assert result == 66000


def test_extract_latest_tokens_returns_none_for_missing_usage(tmp_path: Path) -> None:
    """Returns None if no assistant message has a usage field."""
    jsonl = tmp_path / "session.jsonl"
    lines = [
        json.dumps(
            {
                "type": "message",
                "message": {"role": "assistant", "content": []},  # no usage key
            }
        ),
        json.dumps(
            {
                "type": "message",
                "message": {"role": "assistant", "content": [], "usage": {}},  # empty usage
            }
        ),
    ]
    jsonl.write_text("\n".join(lines) + "\n")

    result = _call_extract_latest_tokens(str(jsonl))
    assert result is None


def test_extract_latest_tokens_returns_none_for_empty_file(tmp_path: Path) -> None:
    """Returns None for an empty file without raising."""
    jsonl = tmp_path / "empty.jsonl"
    jsonl.touch()

    result = _call_extract_latest_tokens(str(jsonl))
    assert result is None


def test_extract_latest_tokens_returns_none_for_missing_file() -> None:
    """Returns None for a non-existent path without raising."""
    result = _call_extract_latest_tokens("/nonexistent/path/to/session.jsonl")
    assert result is None


def test_extract_latest_tokens_skips_malformed_json_lines(tmp_path: Path) -> None:
    """Malformed lines are silently skipped; valid last assistant message is found."""
    jsonl = tmp_path / "session.jsonl"
    lines = [
        "not valid json at all",
        json.dumps(
            {
                "type": "message",
                "message": {
                    "role": "assistant",
                    "content": [],
                    "usage": {"totalTokens": 30000},
                },
            }
        ),
        "also broken {",
        json.dumps({"type": "tool_call", "tool": "bash", "args": {}}),
        json.dumps(
            {
                "type": "message",
                "message": {"role": "assistant", "content": [], "usage": {"totalTokens": 77000}},
            }
        ),
    ]
    jsonl.write_text("\n".join(lines) + "\n")

    result = _call_extract_latest_tokens(str(jsonl))
    assert result == 77000


# ---------------------------------------------------------------------------
# _update_token_counts — peak never decreases
# ---------------------------------------------------------------------------


def test_peak_never_decreases(tmp_path: Path) -> None:
    """When context_tokens_last drops (post-compaction), "
    "context_tokens_peak stays at high-water mark."""
    jsonl = tmp_path / "session.jsonl"
    lines = [
        json.dumps(
            {
                "type": "message",
                "message": {"role": "assistant", "content": [], "usage": {"totalTokens": 150000}},
            }
        ),
    ]
    jsonl.write_text("\n".join(lines) + "\n")

    # Run starts with no token values
    run = _FakeStepRun(
        cli_tool="pi",
        session_file=str(jsonl),
        context_tokens_peak=None,
        context_tokens_last=None,
    )
    _call_poll_update(run)
    assert run.context_tokens_last == 150000
    assert run.context_tokens_peak == 150000

    # Simulate the session JSONL now showing a lower token count (post-compaction)
    # The file now reflects compaction to a lower value
    jsonl.write_text(
        json.dumps(
            {
                "type": "compaction",
                "text": "— context compacted —",
            }
        )
        + "\n"
        + json.dumps(
            {
                "type": "message",
                "message": {
                    "role": "assistant",
                    "content": [],
                    "usage": {"totalTokens": 80000},
                },  # lower after compaction
            }
        )
        + "\n"
    )

    _call_poll_update(run)
    # last should reflect the new (lower) value
    assert run.context_tokens_last == 80000
    # peak should remain at the previous high-water mark
    assert run.context_tokens_peak == 150000


def test_peak_increments_on_higher_tokens(tmp_path: Path) -> None:
    """When a new token count exceeds the existing peak, peak is updated."""
    jsonl = tmp_path / "session.jsonl"

    run = _FakeStepRun(
        cli_tool="pi",
        session_file=str(jsonl),
        context_tokens_peak=50000,
        context_tokens_last=50000,
    )

    # First poll: token count = 80000
    jsonl.write_text(
        json.dumps(
            {
                "type": "message",
                "message": {"role": "assistant", "content": [], "usage": {"totalTokens": 80000}},
            }
        )
        + "\n"
    )
    _call_poll_update(run)
    assert run.context_tokens_last == 80000
    assert run.context_tokens_peak == 80000  # 50K → 80K

    # Second poll: token count = 95000
    jsonl.write_text(
        json.dumps(
            {
                "type": "message",
                "message": {"role": "assistant", "content": [], "usage": {"totalTokens": 95000}},
            }
        )
        + "\n"
    )
    _call_poll_update(run)
    assert run.context_tokens_last == 95000
    assert run.context_tokens_peak == 95000  # 80K → 95K

    # Third poll: tokens drop to 60000 (compaction)
    jsonl.write_text(
        json.dumps(
            {
                "type": "message",
                "message": {"role": "assistant", "content": [], "usage": {"totalTokens": 60000}},
            }
        )
        + "\n"
    )
    _call_poll_update(run)
    assert run.context_tokens_last == 60000
    assert run.context_tokens_peak == 95000  # peak preserved


def test_non_pi_runs_are_not_touched() -> None:
    """Non-pi runs should not have their token counts updated."""
    run = _FakeStepRun(
        cli_tool="claude",
        session_file="/some/path/session.jsonl",
        context_tokens_peak=None,
        context_tokens_last=None,
    )
    _call_poll_update(run)

    # Should remain None — non-pi runs are skipped
    assert run.context_tokens_peak is None
    assert run.context_tokens_last is None


def test_null_session_file_is_handled() -> None:
    """A pi run with session_file=None should be handled gracefully."""
    run = _FakeStepRun(
        cli_tool="pi",
        session_file=None,
        context_tokens_peak=None,
        context_tokens_last=None,
    )
    # Should not raise
    _call_poll_update(run)

    assert run.context_tokens_peak is None
    assert run.context_tokens_last is None


def test_extract_finds_last_assistant_even_when_file_has_trailing_newlines(
    tmp_path: Path,
) -> None:
    """Files ending with blank lines still yield the correct totalTokens."""
    jsonl = tmp_path / "session.jsonl"
    content = (
        json.dumps(
            {
                "type": "message",
                "message": {"role": "assistant", "content": [], "usage": {"totalTokens": 123456}},
            }
        )
        + "\n\n\n"
    )
    jsonl.write_text(content)

    result = _call_extract_latest_tokens(str(jsonl))
    assert result == 123456
