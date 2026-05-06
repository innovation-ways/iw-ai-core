"""Doc-generation execution report assembly.

Pure functions: no DB, no I/O except reading the log file whose path is
passed by the caller.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Literal

from orch.utils.log_capture import strip_ansi

if TYPE_CHECKING:
    import pathlib

    from orch.db.models import DocGenerationJob, Project

__all__ = [
    "read_log_tail",
    "parse_tool_calls",
    "count_doc_update_invocations",
    "build_execution_report",
    "strip_ansi",
]

_MAX_LOG_TAIL_BYTES = 65536


def read_log_tail(path: pathlib.Path, max_bytes: int = _MAX_LOG_TAIL_BYTES) -> tuple[str, int, int]:
    """Read the last max_bytes of the file at *path*, stripping ANSI.

    Returns ``(text, original_size_bytes, line_count)`` where:
      - text is the ANSI-stripped tail (full file if <= max_bytes)
      - original_size_bytes is the full file size before truncation
      - line_count is the number of lines in the returned text

    When the file is larger than max_bytes, prepends
    ``"[truncated: N bytes elided]\\n"``.

    Empty or missing file → ``("", 0, 0)``.
    """
    if not path.is_file():
        return "", 0, 0

    try:
        raw_bytes = path.read_bytes()
    except OSError:
        return "", 0, 0

    original_size = len(raw_bytes)

    try:
        raw_text = raw_bytes.decode("utf-8", errors="replace")
    except OSError:
        return "", original_size, 0

    text = strip_ansi(raw_text)

    if len(text.encode("utf-8")) > max_bytes:
        total_size = len(text.encode("utf-8"))
        header = f"[truncated: {total_size - max_bytes} bytes elided]\n"
        tail = text[-max_bytes:]
        # Align to next newline to avoid a partial first line in the tail
        nl = tail.find("\n")
        if nl != -1:
            tail = tail[nl + 1 :]
        text = header + tail

    lines = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
    return text, original_size, lines


# Heuristic for exit_code in parse_tool_calls:
#   - 0 by default (the log records shell prompts, not exit codes)
#   - 1 when a line starting with "Error:" appears after the command block,
#     or when the output contains a known failure phrase such as
#     "command not found", "No such file", "Permission denied", "not found in project"
#   These phrases indicate the tool call failed at the shell level before
#   producing useful output.

_TOOL_CALL_RE = re.compile(r"^\$ \S+.*?iw\s+(\S+)(?:\s+.*)?$", re.MULTILINE)
_FAILURE_PHRASES = frozenset(
    [
        "Error:",
        "command not found",
        "No such file",
        "Permission denied",
        "not found in project",
    ]
)


def parse_tool_calls(log_text: str) -> list[dict[str, Any]]:
    """Extract ``iw <subcommand>`` invocations and their estimated exit code.

    Parses log lines of the form::

        $ uv run iw <subcommand> [args...]

    exit_code is 0 by default and 1 when a subsequent line starts with
    "Error:" or contains a known failure phrase — the captured logs use
    plain shell prompts, so no real exit code is recorded.

    Returns ``[{"tool": "iw <subcommand>", "exit_code": 0|1}, ...]``.
    """
    calls = []
    lines = log_text.splitlines()
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        match = _TOOL_CALL_RE.match(line)
        if match:
            tool_name = match.group(1)
            # Look ahead for failure indicators in the next few lines
            exit_code = 0
            for j in range(i + 1, min(i + 8, n)):
                nxt = lines[j].strip()
                if nxt.startswith("Error:"):
                    exit_code = 1
                    break
                if any(phrase.lower() in nxt.lower() for phrase in _FAILURE_PHRASES):
                    exit_code = 1
                    break
                # Empty or continuation line — keep scanning
                if nxt and not nxt.startswith("$") and not nxt.startswith(">"):
                    # Non-prompt, non-empty line after the command
                    pass
                else:
                    # Hit another prompt — stop scanning
                    break

            calls.append({"tool": f"iw {tool_name}", "exit_code": exit_code})
        i += 1

    return calls


_DOC_UPDATE_RE = re.compile(r"^\$ .*?iw doc-update\s", re.MULTILINE)


def count_doc_update_invocations(log_text: str) -> int:
    """Count ``iw doc-update `` invocations preceded by a ``$`` shell prompt.

    Matches lines of the form::

        $ <anything>iw doc-update <args>

    Returns the number of matches (0 if none).
    """
    return len(_DOC_UPDATE_RE.findall(log_text))


def build_execution_report(
    *,
    job: DocGenerationJob,
    project: Project | None,  # noqa: ARG001
    log_text: str,
    log_size_bytes: int,
    log_line_count: int,
    outcome: Literal["completed", "failed_timeout", "failed_process_exited", "failed_agent_error"],
    command_issued: str | None,
    cli_tool: str,
) -> dict[str, Any]:
    """Assemble the AC4 execution report dict.

    Includes a one-line ``diagnosis`` derived from heuristic rules:
      - outcome=failed_process_exited AND doc_update_invocations==0
        AND tool_calls contains 'iw item-status' → wrong-dispatch diagnosis
      - outcome=failed_process_exited AND doc_update_invocations==0 → "agent
        ran but produced no document content"
      - outcome=failed_timeout → "agent ran for the full timeout without completing"
      - outcome=completed AND lint_warning_count>0 → "completed with lint warnings"
      - outcome=completed AND doc_update_invocations==0 → suspicious; flag
      - default → ""
    """
    tool_calls = parse_tool_calls(log_text)
    doc_update_invocations = count_doc_update_invocations(log_text)

    lint_warning_count = 0
    if job.lint_warnings is not None:
        lint_warning_count = len(job.lint_warnings)

    skill_used = job.skill_used or ""

    # Diagnosis heuristic
    diagnosis = ""
    if outcome == "failed_process_exited":
        tool_names = {c["tool"] for c in tool_calls}
        if doc_update_invocations == 0 and "iw item-status" in tool_names:
            diagnosis = (
                "Skill never called `iw doc-update` — no content was generated. "
                "Likely cause: dispatcher invoked /execute (work-item path) instead "
                "of doc-generation skill."
            )
        else:
            diagnosis = "agent ran but produced no document content"
    elif outcome == "failed_timeout":
        diagnosis = "agent ran for the full timeout without completing"
    elif outcome == "completed":
        if lint_warning_count > 0:
            diagnosis = "completed with lint warnings"
        elif doc_update_invocations == 0:
            diagnosis = "completed but skill never called `iw doc-update`"

    return {
        "outcome": outcome,
        "duration_seconds": job.duration_seconds or 0,
        "skill_used": skill_used,
        "cli_tool": cli_tool,
        "command_issued": command_issued,
        "log_size_bytes": log_size_bytes,
        "log_line_count": log_line_count,
        "tool_calls": tool_calls,
        "doc_update_invocations": doc_update_invocations,
        "lint_warning_count": lint_warning_count,
        "diagnosis": diagnosis,
    }
