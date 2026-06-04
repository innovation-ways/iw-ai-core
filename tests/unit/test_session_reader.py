"""Unit tests for group_into_turns_newest_first (I-00106 regression tests)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from orch.daemon.session_reader import (
    group_into_turns_newest_first,
    read_session_content,
)


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
# AC1 / AC3: Two turns reversed + within-turn order preserved
# ---------------------------------------------------------------------------


def test_group_turns_reverses_turn_order(tmp_path: Path) -> None:
    """The helper must return turns with the newest turn at index 0."""
    # Build a session .jsonl with TWO distinct turns:
    #   Turn 1 (oldest): thinking → assistant "OLDEST_TURN_MARKER"
    #   Turn 2 (newest): thinking → tool_call → tool_result → assistant "NEWEST_TURN_MARKER"
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(
        "\n".join(
            json.dumps(line)
            for line in [
                # Turn 1 (oldest)
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": None,
                        "content": [
                            {"type": "thinking", "thinking": "Old thinking"},
                            {"type": "text", "text": "OLDEST_TURN_MARKER"},
                        ],
                    },
                },
                # Turn 2 (newest)
                {
                    "type": "thinking",
                    "text": "New thinking block",
                },
                {
                    "type": "tool_call",
                    "tool": "Bash",
                    "args": {"command": "echo new"},
                },
                {
                    "type": "tool_result",
                    "result": "new output",
                },
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": None,
                        "content": [{"type": "text", "text": "NEWEST_TURN_MARKER"}],
                    },
                },
            ]
        )
        + "\n"
    )

    run = _FakeStepRun(cli_tool="pi", session_file=str(session_file))
    segments = read_session_content(run)
    turns = group_into_turns_newest_first(segments)

    # Must be exactly 2 turns
    assert len(turns) == 2, f"Expected 2 turns, got {len(turns)}"

    # Turn 0 must be the NEWEST turn (contains NEWEST_TURN_MARKER)
    newest_turn = turns[0]
    newest_texts = [s["text"] for s in newest_turn if s["type"] == "assistant"]
    assert any("NEWEST_TURN_MARKER" in t for t in newest_texts), (
        f"Turn 0 should be the newest turn. Texts found: {newest_texts}"
    )

    # Turn 1 must be the OLDEST turn (contains OLDEST_TURN_MARKER)
    oldest_turn = turns[1]
    oldest_texts = [s["text"] for s in oldest_turn if s["type"] == "assistant"]
    assert any("OLDEST_TURN_MARKER" in t for t in oldest_texts), (
        f"Turn 1 should be the oldest turn. Texts found: {oldest_texts}"
    )

    # Absolute ordering assertion: newest marker appears BEFORE oldest marker
    all_text = "\n".join(s["text"] for turn in turns for s in turn)
    assert all_text.index("NEWEST_TURN_MARKER") < all_text.index("OLDEST_TURN_MARKER"), (
        "I-00106 regression: newest turn must appear before the oldest turn"
    )


def test_group_turns_preserves_within_turn_order(tmp_path: Path) -> None:
    """AC3: Within a single turn the segment order is unchanged."""
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(
        "\n".join(
            json.dumps(line)
            for line in [
                # Single turn: thinking → tool_call → tool_result → assistant
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": None,
                        "content": [
                            {"type": "thinking", "thinking": "Reasoning step"},
                            {
                                "type": "toolCall",
                                "name": "Bash",
                                "arguments": {"command": "echo done"},
                            },
                        ],
                    },
                },
                {
                    "type": "tool_result",
                    "result": "done output",
                },
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": None,
                        "content": [{"type": "text", "text": "Final assistant reply."}],
                    },
                },
            ]
        )
        + "\n"
    )

    run = _FakeStepRun(cli_tool="pi", session_file=str(session_file))
    segments = read_session_content(run)
    turns = group_into_turns_newest_first(segments)

    assert len(turns) == 1, f"Expected 1 turn, got {len(turns)}"
    turn = turns[0]
    seg_types = [s["type"] for s in turn]

    # Exact AC3 assertion: order must be thinking → tool_call → tool_result → assistant
    assert seg_types == [
        "thinking",
        "tool_call",
        "tool_result",
        "assistant",
    ], f"Within-turn segment order must be preserved exactly. Got: {seg_types}"


# ---------------------------------------------------------------------------
# AC4: In-progress trailing turn (no assistant reply) is first
# ---------------------------------------------------------------------------


def test_group_turns_in_progress_trailing_turn_first(tmp_path: Path) -> None:
    """Segments ending with thinking + tool_call (no assistant reply) form a trailing
    in-progress turn shown at index 0 (newest position)."""
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(
        "\n".join(
            json.dumps(line)
            for line in [
                # Turn 1 (complete): thinking + assistant → terminated
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": None,
                        "content": [
                            {"type": "thinking", "thinking": "First turn reasoning"},
                            {"type": "text", "text": "FIRST_TURN_MARKER"},
                        ],
                    },
                },
                # Turn 2 (in-progress, no assistant yet): thinking + tool_call
                {
                    "type": "thinking",
                    "text": "Still running reasoning",
                },
                {
                    "type": "tool_call",
                    "tool": "Bash",
                    "args": {"command": "echo running"},
                },
            ]
        )
        + "\n"
    )

    run = _FakeStepRun(cli_tool="pi", session_file=str(session_file))
    segments = read_session_content(run)
    turns = group_into_turns_newest_first(segments)

    # Must be exactly 2 turns
    assert len(turns) == 2, f"Expected 2 turns, got {len(turns)}"

    # Turn 0: the in-progress trailing turn (contains "Still running reasoning")
    in_progress = turns[0]
    in_progress_types = [s["type"] for s in in_progress]
    assert "thinking" in in_progress_types, "Turn 0 should be the in-progress turn"
    assert "tool_call" in in_progress_types, "Turn 0 should be the in-progress turn"
    assert "assistant" not in in_progress_types, (
        "In-progress turn must NOT contain an assistant segment"
    )

    # Turn 1: the complete first turn
    first_turn = turns[1]
    first_turn_texts = [s["text"] for s in first_turn if s["type"] == "assistant"]
    assert any("FIRST_TURN_MARKER" in t for t in first_turn_texts), (
        "Turn 1 should be the first (oldest) complete turn"
    )


# ---------------------------------------------------------------------------
# AC4: compaction is a standalone turn at correct position
# ---------------------------------------------------------------------------


def test_group_turns_compaction_is_standalone_turn(tmp_path: Path) -> None:
    """A compaction segment must be its own single-segment turn in the correct
    chronological position relative to the newest and oldest turns."""
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(
        "\n".join(
            json.dumps(line)
            for line in [
                # Turn 1 (oldest): assistant → terminated
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": None,
                        "content": [{"type": "text", "text": "OLDEST_TURN_MARKER"}],
                    },
                },
                # compaction: its own standalone turn
                {"type": "compaction"},
                # Turn 2 (newest): assistant → terminated
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": None,
                        "content": [{"type": "text", "text": "NEWEST_TURN_MARKER"}],
                    },
                },
            ]
        )
        + "\n"
    )

    run = _FakeStepRun(cli_tool="pi", session_file=str(session_file))
    segments = read_session_content(run)
    turns = group_into_turns_newest_first(segments)

    assert len(turns) == 3, f"Expected 3 turns (newest, compaction, oldest), got {len(turns)}"

    # Turn 0 must be the newest complete turn
    newest_texts = [s["text"] for s in turns[0] if s["type"] == "assistant"]
    assert any("NEWEST_TURN_MARKER" in t for t in newest_texts), (
        f"Turn 0 should be the newest turn. Texts: {newest_texts}"
    )

    # Turn 1 must be the compaction turn (single segment, type=compaction)
    compaction_turn = turns[1]
    assert len(compaction_turn) == 1, "Compaction must be a single-segment turn"
    assert compaction_turn[0]["type"] == "compaction", (
        "Compaction turn's segment must have type 'compaction'"
    )

    # Turn 2 must be the oldest complete turn
    oldest_texts = [s["text"] for s in turns[2] if s["type"] == "assistant"]
    assert any("OLDEST_TURN_MARKER" in t for t in oldest_texts), (
        f"Turn 2 should be the oldest turn. Texts: {oldest_texts}"
    )


# ---------------------------------------------------------------------------
# AC4: error terminates its turn, later turns are separate
# ---------------------------------------------------------------------------


def test_group_turns_error_terminates_turn(tmp_path: Path) -> None:
    """An error segment closes the current turn and any following segments form
    a new separate turn."""
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(
        "\n".join(
            json.dumps(line)
            for line in [
                # Turn 1 (oldest): thinking + assistant → terminated
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": None,
                        "content": [
                            {"type": "thinking", "thinking": "First reasoning"},
                            {"type": "text", "text": "OLDEST_TURN_MARKER"},
                        ],
                    },
                },
                # Turn 2 (terminated by error): thinking + error
                {
                    "type": "thinking",
                    "text": "Trying something risky",
                },
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": "error",
                        "errorMessage": "Something went wrong ERROR_MARKER",
                    },
                },
                # Turn 3 (newest, separate): assistant → terminated
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": None,
                        "content": [{"type": "text", "text": "NEWEST_TURN_MARKER"}],
                    },
                },
            ]
        )
        + "\n"
    )

    run = _FakeStepRun(cli_tool="pi", session_file=str(session_file))
    segments = read_session_content(run)
    turns = group_into_turns_newest_first(segments)

    assert len(turns) == 3, f"Expected 3 turns, got {len(turns)}"

    # Turn 0 must be the newest turn
    newest_texts = [s["text"] for s in turns[0] if s["type"] == "assistant"]
    assert any("NEWEST_TURN_MARKER" in t for t in newest_texts), (
        f"Turn 0 should be the newest turn. Texts: {newest_texts}"
    )

    # Turn 1 must be the error turn — contains both thinking and error types
    error_turn = turns[1]
    error_turn_types = {s["type"] for s in error_turn}
    assert "error" in error_turn_types, "Turn 1 should contain the error segment"
    assert "thinking" in error_turn_types, "Error turn should also contain preceding thinking"

    # Turn 2 must be the oldest turn
    oldest_texts = [s["text"] for s in turns[2] if s["type"] == "assistant"]
    assert any("OLDEST_TURN_MARKER" in t for t in oldest_texts), (
        f"Turn 2 should be the oldest turn. Texts: {oldest_texts}"
    )


# ---------------------------------------------------------------------------
# AC3: Consecutive assistant segments stay in the same turn
# ---------------------------------------------------------------------------


def test_group_turns_consecutive_assistant_segments_stay_in_one_turn(tmp_path: Path) -> None:
    """Two adjacent 'assistant' segments must land in the same turn, not two."""
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(
        "\n".join(
            json.dumps(line)
            for line in [
                # Two consecutive assistant text blocks in one message
                # (pi emits multiple text items in one content list)
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": None,
                        "content": [
                            {"type": "text", "text": "FIRST_ASSISTANT_BLOCK"},
                            {"type": "text", "text": "SECOND_ASSISTANT_BLOCK"},
                        ],
                    },
                },
            ]
        )
        + "\n"
    )

    run = _FakeStepRun(cli_tool="pi", session_file=str(session_file))
    segments = read_session_content(run)
    turns = group_into_turns_newest_first(segments)

    # Must be exactly 1 turn (not 2)
    assert len(turns) == 1, f"Expected 1 turn for consecutive assistant segments, got {len(turns)}"

    # Both assistant blocks must be in the same turn
    turn = turns[0]
    assistant_texts = [s["text"] for s in turn if s["type"] == "assistant"]
    assert "FIRST_ASSISTANT_BLOCK" in assistant_texts, "First assistant block should be in the turn"
    assert "SECOND_ASSISTANT_BLOCK" in assistant_texts, (
        "Second assistant block should be in the same turn"
    )


# ---------------------------------------------------------------------------
# AC4: log segment text lines are reversed; input dict is not mutated
# ---------------------------------------------------------------------------


def test_group_turns_log_segment_lines_reversed() -> None:
    """A single 'log' segment's text lines must be reversed (newest line on top),
    and the original input dict must NOT be mutated."""
    # Build segments the way read_session_content would for a claude run
    original_text = "line 1\nline 2\nline 3"
    segments = [{"type": "log", "text": original_text, "collapsible": False}]

    # Capture the original dict's id so we can verify it's not mutated
    original_dict_id = id(segments[0])
    original_dict_text = segments[0]["text"]

    turns = group_into_turns_newest_first(segments)

    # Must be exactly 1 turn
    assert len(turns) == 1, f"Expected 1 turn for a log segment, got {len(turns)}"

    # The returned segment must have lines in reversed order
    returned_seg = turns[0][0]
    expected_reversed = "line 3\nline 2\nline 1"
    assert returned_seg["text"] == expected_reversed, (
        f"Log segment text lines must be reversed. "
        f"Expected: {expected_reversed!r}, Got: {returned_seg['text']!r}"
    )

    # The original dict must NOT be mutated
    assert segments[0]["text"] == original_dict_text, (
        "group_into_turns_newest_first must NOT mutate the input dict's text field"
    )
    assert id(segments[0]) == original_dict_id, (
        "group_into_turns_newest_first must NOT replace the input dict"
    )


# ---------------------------------------------------------------------------
# Empty input returns empty list
# ---------------------------------------------------------------------------


def test_group_turns_empty_input_returns_empty_list() -> None:
    """Empty segment list returns an empty turns list."""
    turns = group_into_turns_newest_first([])
    assert turns == [], f"Expected [], got {turns!r}"


# ---------------------------------------------------------------------------
# Purity: input segments are not mutated across normal turns
# ---------------------------------------------------------------------------


def test_group_turns_does_not_mutate_input_segments(tmp_path: Path) -> None:
    """The helper must not mutate the text of the input segment dicts."""
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(
        "\n".join(
            json.dumps(line)
            for line in [
                {
                    "type": "message",
                    "message": {
                        "role": "assistant",
                        "stopReason": None,
                        "content": [
                            {"type": "thinking", "thinking": "Thinking content"},
                            {"type": "text", "text": "Assistant reply"},
                        ],
                    },
                },
            ]
        )
        + "\n"
    )

    run = _FakeStepRun(cli_tool="pi", session_file=str(session_file))
    segments = read_session_content(run)
    original_segment_dicts = [{**s} for s in segments]  # deep copy of original state

    # Call the helper
    group_into_turns_newest_first(segments)

    # All original segment dicts must be unchanged
    for original, current in zip(original_segment_dicts, segments, strict=True):
        assert original == current, (
            f"group_into_turns_newest_first must not mutate input segments. "
            f"Original: {original}, Current: {current}"
        )
