"""Session content reader for CR-00065 — Live Agent Session Log Viewer.

Provides ``read_session_content`` which parses pi session .jsonl files or
claude/opencode log files into a list of human-readable segment dicts.

Segment schema (each dict):
    type         : str  — one of the segment type strings below
    text         : str  — rendered content
    collapsible  : bool — True for thinking blocks and long tool results

Segment types:
    assistant  — plain text output from the LLM
    tool_call  — LLM invoked a tool (name + abbreviated args)
    tool_result — output returned from a tool call
    thinking   — LLM internal reasoning (pi only)
    compaction — pi context-compaction marker
    error      — step failed with an error message
    log        — fallback for claude/opencode (full log dump)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from orch.db.models import StepRun

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Segment type constants (kept in sync with docstring above)
# ---------------------------------------------------------------------------

_SEG_ASSISTANT = "assistant"
_SEG_TOOL_CALL = "tool_call"
_SEG_TOOL_RESULT = "tool_result"
_SEG_THINKING = "thinking"
_SEG_COMPACTION = "compaction"
_SEG_ERROR = "error"
_SEG_LOG = "log"
_SEG_USER = "user"  # internal only — pi prompt injections are skipped


# ---------------------------------------------------------------------------
# Pi JSONL helpers
# ---------------------------------------------------------------------------

_MAX_ASSISTANT_TEXT = 2_000
_MAX_THINKING_TEXT = 200
_MAX_TOOL_CALL_ARGS = 200
_MAX_TOOL_RESULT_TEXT = 500


def _parse_pi_line(raw: str) -> dict[str, Any] | None:
    """Parse one line of a pi session .jsonl file.

    Returns the deserialised dict or None if the line is not valid JSON.
    Errors are logged at DEBUG level and swallowed so a corrupt line never
    crashes the entire parse.
    """
    try:
        obj: dict[str, Any] = json.loads(raw)
        return obj
    except json.JSONDecodeError:
        logger.debug("session_reader: skipping unparseable JSONL line: %r", raw)
        return None


def _render_pi_jsonl(session_file: str) -> list[dict[str, Any]]:
    """Parse a pi session .jsonl file and return a list of segment dicts."""
    segments: list[dict[str, Any]] = []

    try:
        with open(session_file, encoding="utf-8") as fh:  # noqa: PTH123
            lines = fh.readlines()
    except OSError as exc:
        logger.debug("session_reader: could not open %s: %s", session_file, exc)
        return []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue

        obj = _parse_pi_line(line)
        if obj is None:
            continue

        _process_pi_object(obj, segments)

    return segments


def _process_pi_object(obj: dict[str, Any], segments: list[dict[str, Any]]) -> None:
    """Classify a parsed JSONL object and append one or more segments to ``segments``."""
    obj_type = obj.get("type", "")

    if obj_type == "compaction":
        segments.append(
            {
                "type": _SEG_COMPACTION,
                "text": "— context compacted —",
                "collapsible": False,
            }
        )
        return

    # --- Top-level event types (pi session JSONL v3) ---
    if obj_type == "thinking":
        thinking_text = str(obj.get("text", ""))
        if len(thinking_text) > _MAX_THINKING_TEXT:
            display_text = thinking_text[:_MAX_THINKING_TEXT] + "…"
        else:
            display_text = thinking_text
        segments.append({"type": _SEG_THINKING, "text": display_text, "collapsible": True})
        return

    if obj_type == "tool_call":
        name = obj.get("tool", "?")
        args = obj.get("args", {})
        args_str = json.dumps(args, ensure_ascii=False)
        summary = args_str[:_MAX_TOOL_CALL_ARGS]
        segments.append(
            {"type": _SEG_TOOL_CALL, "text": f"{name}: {summary}", "collapsible": False}
        )
        return

    if obj_type == "tool_result":
        result_text = str(obj.get("result", ""))[:_MAX_TOOL_RESULT_TEXT]
        segments.append({"type": _SEG_TOOL_RESULT, "text": result_text, "collapsible": True})
        return

    if obj_type != "message":
        return

    message: dict[str, Any] = obj.get("message", {})
    role = message.get("role", "")
    stop_reason = message.get("stopReason", "")

    # Error stop reason
    if stop_reason == "error":
        error_msg = message.get("errorMessage", "Unknown error")
        segments.append(
            {
                "type": _SEG_ERROR,
                "text": error_msg,
                "collapsible": False,
            }
        )
        return

    # Skip user role (original prompt injections — not agent output)
    if role == _SEG_USER:
        return

    # Assistant role: iterate content items
    if role == "assistant":
        for content_item in message.get("content", []):
            _process_assistant_content_item(content_item, segments)

    # toolResult role
    elif role == "toolResult":
        tool_contents = message.get("content", [])
        if tool_contents:
            first = tool_contents[0]
            raw_text = first.get("text", "") if isinstance(first, dict) else str(first)
            text = raw_text[:_MAX_TOOL_RESULT_TEXT]
            segments.append(
                {
                    "type": _SEG_TOOL_RESULT,
                    "text": text,
                    "collapsible": True,
                }
            )


def _process_assistant_content_item(
    item: dict[str, Any],
    segments: list[dict[str, Any]],
) -> None:
    """Process one entry from an assistant message's ``content`` list."""
    item_type = item.get("type", "")

    if item_type == "text":
        text = item.get("text", "")[:_MAX_ASSISTANT_TEXT]
        segments.append(
            {
                "type": _SEG_ASSISTANT,
                "text": text,
                "collapsible": False,
            }
        )

    elif item_type == "thinking":
        thinking_text = item.get("thinking", "")
        # Truncate to 200 chars + "…" per spec
        if len(thinking_text) > _MAX_THINKING_TEXT:
            display_text = thinking_text[:_MAX_THINKING_TEXT] + "…"
        else:
            display_text = thinking_text
        segments.append(
            {
                "type": _SEG_THINKING,
                "text": display_text,
                "collapsible": True,
            }
        )

    elif item_type == "toolCall":
        name = item.get("name", "?")
        arguments = item.get("arguments", {})
        args_str = json.dumps(arguments, ensure_ascii=True)
        summary = args_str[:_MAX_TOOL_CALL_ARGS]
        segments.append(
            {
                "type": _SEG_TOOL_CALL,
                "text": f"{name}: {summary}",
                "collapsible": False,
            }
        )


# ---------------------------------------------------------------------------
# Claude / OpenCode log rendering
# ---------------------------------------------------------------------------


def _read_log_file(log_file: str, max_chars: int) -> str:
    """Read the last ``max_chars`` bytes of ``log_file``.

    Seeking to a negative offset from the end reads from that position
    relative to EOF, which is supported by Python's buffered I/O.
    Returns an empty string if the file does not exist or cannot be read.
    """
    try:
        size = Path(log_file).stat().st_size
        read_start = max(0, size - max_chars)
        with open(log_file, encoding="utf-8", errors="replace") as fh:  # noqa: PTH123
            fh.seek(read_start)
            return fh.read()
    except OSError:
        return ""


def _render_claude_opencode(run: StepRun, max_chars: int) -> list[dict[str, Any]]:
    """Render content for a claude or opencode StepRun.

    Priority: log_content (DB field) > log_file (on-disk file) > error segment.
    """
    # 1. log_content from DB
    if run.log_content is not None:
        text = run.log_content[:max_chars]
        return [{"type": _SEG_LOG, "text": text, "collapsible": False}]

    # 2. log_file on disk
    if run.log_file is not None:
        text = _read_log_file(run.log_file, max_chars)
        if text:
            return [{"type": _SEG_LOG, "text": text, "collapsible": False}]

    # 3. Nothing available
    return [{"type": _SEG_ERROR, "text": "No log content available", "collapsible": False}]


# ---------------------------------------------------------------------------
# Turn grouping helpers
# ---------------------------------------------------------------------------


def _reverse_log_lines(text: str) -> str:
    """Reverse the lines of ``text`` so the newest line is on top."""
    return "\n".join(text.splitlines()[::-1])


def group_into_turns_newest_first(
    segments: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    """Group a chronological flat segment list into agent turns, newest turn first.

    A *turn* is a contiguous run of segments ending with an ``assistant`` segment
    that is **not** immediately followed by another ``assistant`` segment, or with
    an ``error`` segment (which always terminates its turn).  Consecutive
    ``assistant`` segments (e.g. a pi message whose ``content`` list carries
    multiple ``text`` items) stay in the same turn — only the last of a consecutive
    run terminates the turn.

    A ``compaction`` segment is emitted as its **own single-segment turn** after
    flushing any in-progress turn, so the marker acts as a visual separator.

    A ``log`` segment (claude/opencode whole-dump fallback) is emitted as its own
    turn with its ``text`` lines reversed (newest line on top), consistent with
    the ``_reverse_log`` behaviour used by the Logs tab.

    Segments accumulated after the last terminator (no assistant reply yet —
    common while a step is still running) form a **final in-progress turn**.

    The list of turns is ordered **newest turn first**; segments **inside** each
    turn keep their original chronological order.  The input list is not mutated.

    Args:
        segments: Flat chronological list of segment dicts produced by
            ``read_session_content``.

    Returns:
        A list of turns, each turn being a list of segment dicts.  Empty input
        returns an empty list.
    """
    if not segments:
        return []

    turns: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    i = 0
    n = len(segments)

    while i < n:
        seg = segments[i]
        seg_type = seg["type"]

        # ── Special: compaction ──────────────────────────────────────────────
        if seg_type == _SEG_COMPACTION:
            # Flush in-progress turn first, then emit compaction as its own turn
            if current:
                turns.append(current)
                current = []
            turns.append([seg])
            i += 1
            continue

        # ── Special: log ─────────────────────────────────────────────────────
        if seg_type == _SEG_LOG:
            # Emit log as its own turn with reversed lines
            # (do NOT mutate the original dict)
            reversed_text = _reverse_log_lines(seg.get("text", ""))
            reversed_seg = {**seg, "text": reversed_text}
            if current:
                turns.append(current)
                current = []
            turns.append([reversed_seg])
            i += 1
            continue

        # ── Normal segment ────────────────────────────────────────────────────
        current.append(seg)

        # Turn terminates on an `error` segment
        if seg_type == _SEG_ERROR:
            turns.append(current)
            current = []
            i += 1
            continue

        # Turn terminates on an `assistant` segment that is NOT immediately
        # followed by another `assistant` segment
        if seg_type == _SEG_ASSISTANT:
            next_is_assistant = (i + 1 < n) and (segments[i + 1]["type"] == _SEG_ASSISTANT)
            if not next_is_assistant:
                turns.append(current)
                current = []

        i += 1

    # Final in-progress turn (no terminating assistant/error yet)
    if current:
        turns.append(current)

    # Reverse the list of turns so newest turn is first
    turns.reverse()

    return turns


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_session_content(run: StepRun, max_chars: int = 50_000) -> list[dict[str, Any]]:
    """Return a list of rendered segment dicts for the given StepRun.

    For ``pi`` runs: parses the session_file JSONL.
    For ``claude`` / ``opencode`` runs: reads log_file or log_content.

    Args:
        run: A StepRun model instance (or a compatible duck-type object).
        max_chars: Maximum characters to return per segment.
                   Defaults to 50 000 (claude/opencode log fallback only).

    Returns:
        A list of segment dicts. Empty list when no content is available
        (pi with no session_file yet).
    """
    cli_tool = getattr(run, "cli_tool", None)
    session_file = getattr(run, "session_file", None)

    if cli_tool == "pi" and session_file:
        return _render_pi_jsonl(session_file)

    # CR-00065: pi runs without a session_file fall back to log_content (JSONL in DB)
    log_content: str | None = getattr(run, "log_content", None)
    if cli_tool == "pi" and not session_file and log_content:
        segments: list[dict[str, Any]] = []
        for line in log_content.splitlines():
            obj = _parse_pi_line(line.strip())
            if obj is not None:
                _process_pi_object(obj, segments)
        return segments

    if cli_tool in ("claude", "opencode"):
        return _render_claude_opencode(run, max_chars)

    # Unknown or unset cli_tool — nothing to render
    return []
