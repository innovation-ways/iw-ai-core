"""Unit tests for session_reader — CR-00065."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from orch.daemon.session_reader import read_session_content


class _FakeStepRun:
    """Minimal stand-in for StepRun for unit tests (no DB needed)."""

    def __init__(
        self,
        *,
        cli_tool: str = "pi",
        session_file: str | None = None,
        log_file: str | None = None,
        log_content: str | None = None,
        started_at: datetime | None = None,
    ) -> None:
        self.cli_tool = cli_tool
        self.session_file = session_file
        self.log_file = log_file
        self.log_content = log_content
        self.started_at = started_at


# ---------------------------------------------------------------------------
# Pi JSONL — assistant message with text
# ---------------------------------------------------------------------------


def test_pi_jsonl_parses_assistant_message(tmp_path: Path) -> None:
    """Given a JSONL with one assistant text entry, returns one 'assistant' segment."""
    line = json.dumps(
        {
            "type": "message",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Hello world"}],
            },
        }
    )
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(line + "\n")

    run = _FakeStepRun(cli_tool="pi", session_file=str(session_file))
    segments = read_session_content(run)

    assert len(segments) == 1
    assert segments[0]["type"] == "assistant"
    assert segments[0]["text"] == "Hello world"
    assert segments[0]["collapsible"] is False


# ---------------------------------------------------------------------------
# Pi JSONL — thinking block
# ---------------------------------------------------------------------------


def test_pi_jsonl_thinking_is_collapsible(tmp_path: Path) -> None:
    """Given a thinking block, segment has collapsible=True and text is truncated."""
    long_thinking = (
        "This is a very long thinking block that exceeds the two hundred character limit. " * 3
    )
    line = json.dumps(
        {
            "type": "message",
            "message": {
                "role": "assistant",
                "content": [{"type": "thinking", "thinking": long_thinking}],
            },
        }
    )
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(line + "\n")

    run = _FakeStepRun(cli_tool="pi", session_file=str(session_file))
    segments = read_session_content(run)

    assert len(segments) == 1
    assert segments[0]["type"] == "thinking"
    assert segments[0]["collapsible"] is True
    # Text is truncated to 200 chars + "…"
    assert len(segments[0]["text"]) == 201
    assert segments[0]["text"].endswith("…")


# ---------------------------------------------------------------------------
# Pi JSONL — tool call
# ---------------------------------------------------------------------------


def test_pi_jsonl_tool_call_segment(tmp_path: Path) -> None:
    """Given a toolCall entry, segment type is 'tool_call' with name:args summary."""
    line = json.dumps(
        {
            "type": "message",
            "message": {
                "role": "assistant",
                "content": [
                    {
                        "type": "toolCall",
                        "name": "Bash",
                        "arguments": {"command": "ls -la", "path": "/tmp"},
                    }
                ],
            },
        }
    )
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(line + "\n")

    run = _FakeStepRun(cli_tool="pi", session_file=str(session_file))
    segments = read_session_content(run)

    assert len(segments) == 1
    assert segments[0]["type"] == "tool_call"
    assert segments[0]["collapsible"] is False
    assert "Bash" in segments[0]["text"]
    assert "ls -la" in segments[0]["text"]


# ---------------------------------------------------------------------------
# Pi JSONL — compaction marker
# ---------------------------------------------------------------------------


def test_pi_jsonl_compaction_marker(tmp_path: Path) -> None:
    """Given a compaction entry, segment type is 'compaction'."""
    line = json.dumps({"type": "compaction"})
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(line + "\n")

    run = _FakeStepRun(cli_tool="pi", session_file=str(session_file))
    segments = read_session_content(run)

    assert len(segments) == 1
    assert segments[0]["type"] == "compaction"
    assert "—" in segments[0]["text"]


# ---------------------------------------------------------------------------
# Pi JSONL — error entry
# ---------------------------------------------------------------------------


def test_pi_jsonl_error_entry(tmp_path: Path) -> None:
    """Given a message with stopReason=error and errorMessage, segment type is 'error'."""
    line = json.dumps(
        {
            "type": "message",
            "message": {
                "role": "assistant",
                "stopReason": "error",
                "errorMessage": "Context window exceeded",
            },
        }
    )
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(line + "\n")

    run = _FakeStepRun(cli_tool="pi", session_file=str(session_file))
    segments = read_session_content(run)

    assert len(segments) == 1
    assert segments[0]["type"] == "error"
    assert "Context window exceeded" in segments[0]["text"]


# ---------------------------------------------------------------------------
# Claude/OpenCode — log_content
# ---------------------------------------------------------------------------


def test_claude_run_uses_log_content() -> None:
    """Given cli_tool='claude' and log_content set, returns single 'log' segment."""
    run = _FakeStepRun(
        cli_tool="claude",
        log_content="Build complete. 42 files changed.",
    )
    segments = read_session_content(run)

    assert len(segments) == 1
    assert segments[0]["type"] == "log"
    assert segments[0]["text"] == "Build complete. 42 files changed."
    assert segments[0]["collapsible"] is False


# ---------------------------------------------------------------------------
# Empty / no content
# ---------------------------------------------------------------------------


def test_empty_run_returns_empty_list() -> None:
    """Given no session_file, no log_file, no log_content, returns []."""
    run = _FakeStepRun(cli_tool="pi")
    segments = read_session_content(run)
    assert segments == []


def test_opencode_with_log_file(tmp_path: Path) -> None:
    """Given cli_tool='opencode' with a log_file on disk, returns one 'log' segment."""
    log = tmp_path / "run.log"
    log.write_text("opencode output line 1\nopencode output line 2\n")

    run = _FakeStepRun(cli_tool="opencode", log_file=str(log))
    segments = read_session_content(run)

    assert len(segments) == 1
    assert segments[0]["type"] == "log"
    assert "opencode output line 1" in segments[0]["text"]
    assert segments[0]["collapsible"] is False


# ---------------------------------------------------------------------------
# Malformed JSONL lines are skipped
# ---------------------------------------------------------------------------


def test_malformed_jsonl_line_is_skipped(tmp_path: Path) -> None:
    """A line that isn't valid JSON is logged at debug and skipped."""
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(
        '{"type": "message", "message": {"role": "assistant", '
        '"content": [{"type": "text", "text": "OK"}]}}\n'
        "not valid json at all\n"
        '{"type": "compaction"}\n'
    )

    run = _FakeStepRun(cli_tool="pi", session_file=str(session_file))
    segments = read_session_content(run)

    # Two valid entries survive; bad line is skipped
    assert len(segments) == 2
    types = [s["type"] for s in segments]
    assert "assistant" in types
    assert "compaction" in types


# ---------------------------------------------------------------------------
# Tool result segments
# ---------------------------------------------------------------------------


def test_pi_jsonl_tool_result_is_collapsible(tmp_path: Path) -> None:
    """Given a toolResult entry, segment type is 'tool_result' and collapsible is True."""
    line = json.dumps(
        {
            "type": "message",
            "message": {
                "role": "toolResult",
                "content": [{"type": "output", "text": "A" * 600}],
            },
        }
    )
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(line + "\n")

    run = _FakeStepRun(cli_tool="pi", session_file=str(session_file))
    segments = read_session_content(run)

    assert len(segments) == 1
    assert segments[0]["type"] == "tool_result"
    assert segments[0]["collapsible"] is True
    # Content truncated to 500 chars
    assert len(segments[0]["text"]) == 500


# ---------------------------------------------------------------------------
# User messages are skipped
# ---------------------------------------------------------------------------


def test_pi_jsonl_user_message_skipped(tmp_path: Path) -> None:
    """A 'user' role message is skipped (original prompt injection, not agent output)."""
    line = json.dumps(
        {
            "type": "message",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": "The user's prompt"}],
            },
        }
    )
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(line + "\n")

    run = _FakeStepRun(cli_tool="pi", session_file=str(session_file))
    segments = read_session_content(run)

    assert segments == []


# ---------------------------------------------------------------------------
# max_chars truncation on log content
# ---------------------------------------------------------------------------


def test_log_content_truncated_to_max_chars(tmp_path: Path) -> None:
    """Log content longer than max_chars is truncated."""
    long_log = "x" * 100_000
    run = _FakeStepRun(cli_tool="claude", log_content=long_log)
    segments = read_session_content(run, max_chars=50_000)

    assert len(segments) == 1
    assert len(segments[0]["text"]) == 50_000


def test_log_file_content_truncated_to_max_chars(tmp_path: Path) -> None:
    """log_file content longer than max_chars is truncated to the last max_chars bytes."""
    log = tmp_path / "run.log"
    log.write_text("y" * 100_000)

    run = _FakeStepRun(cli_tool="opencode", log_file=str(log))
    segments = read_session_content(run, max_chars=50_000)

    assert len(segments) == 1
    assert len(segments[0]["text"]) == 50_000


# ---------------------------------------------------------------------------
# No log available fallback
# ---------------------------------------------------------------------------


def test_no_content_available_returns_error_segment() -> None:
    """A run with cli_tool='claude' but no log_content and no log_file returns error segment."""
    run = _FakeStepRun(cli_tool="claude")
    segments = read_session_content(run)

    assert len(segments) == 1
    assert segments[0]["type"] == "error"
    assert "No log content available" in segments[0]["text"]
