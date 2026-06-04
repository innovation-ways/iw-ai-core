# SPDX-License-Identifier: MIT
"""Tool-output cap with disk spill for IW AI Core step execution.

Cap each tool result the executor mediates at a configurable byte budget.
When a result exceeds the cap:

* Write the full, unmodified result to a file under the step work directory
  (e.g. ai-dev/work/<ITEM>/.tool-cache/<step>-<n>.txt).
* Return to the agent a HEAD + TAIL preview PLUS the file path and total size,
  so the agent can grep / read the rest on demand.

This is AC2 / R-00078 Primary Recommendation: "cap + spill to file, not
in-place truncation".  R-00078 §Codex #14206: an in-place head/tail snippet
with an inline "...truncated..." marker and no spill file "preserves neither
exactness nor recoverability" and is FORBIDDEN.

Under-cap results pass through completely unchanged.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

# ------------------------------------------------------------------
# Default cap — order of magnitude of Claude Code's 30 KB Bash tool cap
# (R-00078 / arXiv 2511.22729 cross-harness survey).
# ------------------------------------------------------------------
DEFAULT_TOOL_OUTPUT_CAP_BYTES: int = 25 * 1024  # 25 KB

# How many lines to show in the head and tail previews (deterministic, testable).
_PREVIEW_LINES: int = 30


@dataclass(frozen=True)
class CapResult:
    """Result of applying the tool-output cap to a single tool result.

    Attributes
    ----------
    capped : bool
        True when the result was larger than the cap and a spill file was created.
    preview : str
        The capped variant the agent should see: either the unchanged input
        (when capped==False) or a head+tail preview with file path (capped==True).
    spill_path : str | None
        Absolute path to the spill file when capped==True; None when capped==False.
    total_bytes : int
        Total byte size of the original content (for the agent to know how large).
    total_lines : int
        Total line count of the original content.
    """

    capped: bool
    preview: str
    spill_path: str | None
    total_bytes: int
    total_lines: int


def _count_lines(text: str) -> int:
    """Return the number of lines in ``text`` (trailing \n does not create a blank line)."""
    if not text:
        return 0
    return text.count("\n") + (0 if text.endswith("\n") else 1)


def _hash_path(cache_dir: Path, content: str, item_id: str, step_id: str) -> Path:
    """Build a stable, collision-free spill filename from a hash of the content."""
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{item_id}_{step_id}_{digest}.txt"


def apply_tool_output_cap(
    content: str,
    *,
    item_id: str,
    step_id: str,
    max_bytes: int = DEFAULT_TOOL_OUTPUT_CAP_BYTES,
    cache_dir: Path | None = None,
) -> CapResult:
    """Apply the per-tool-output cap, spilling to disk when the budget is exceeded.

    Parameters
    ----------
    content:
        The raw tool output as a string (UTF-8 bytes).
    item_id:
        Work item ID — used to build the spill filename and parent directory.
    step_id:
        Step ID — used to build the spill filename.
    max_bytes:
        Byte budget.  A result whose UTF-8 byte length exceeds this is spilled.
        Defaults to 25 KB (~25,600 bytes), the order of magnitude of Claude
        Code's Bash cap (R-00078).  Tunable per runtime via ``IW_CORE_TOOL_OUTPUT_CAP``.
    cache_dir:
        Directory where spill files are written.  Defaults to
        ``ai-dev/work/<item_id>/.tool-cache`` relative to the repo root.
        Created automatically if it does not exist.

    Returns
    -------
    CapResult
        ``capped=True`` when overflow occurred: ``preview`` is the head+tail
        snippet with spill path; ``spill_path`` is the absolute path of the
        full content.
        ``capped=False`` when the result was within budget: ``preview`` is
        the original content unchanged; ``spill_path`` is None.

    Notes
    -----
    - The spill file contains the **full, unmodified** content — not a
      transformed version.  The agent can read it with its file tool.
    - The preview format is deliberately simple: it lists head lines, a
      "...N bytes truncated..." marker, tail lines, and the spill path.
      No summarisation or re-encoding is applied.
    - The function is deterministic: the same (content, item_id, step_id)
      triple always produces the same spill_path, so pre-existing spill files
      are never duplicated.
    - Thread-safety: the function writes atomically (write-then-rename) so
      concurrent callers cannot read a partial spill file.
    """
    total_bytes = len(content.encode("utf-8"))
    total_lines = _count_lines(content)

    # Fast path: under-cap — return unchanged.
    if total_bytes <= max_bytes:
        return CapResult(
            capped=False,
            preview=content,
            spill_path=None,
            total_bytes=total_bytes,
            total_lines=total_lines,
        )

    # Overflow path: cap + spill.
    if cache_dir is None:
        # Default: ai-dev/work/<item_id>/.tool-cache  (worktree-local).
        repo_root = Path(__file__).resolve().parent.parent
        cache_dir = repo_root / "ai-dev" / "work" / item_id / ".tool-cache"

    cache_dir = cache_dir.resolve()
    cache_dir.mkdir(parents=True, exist_ok=True)

    spill_path = _hash_path(cache_dir, content, item_id, step_id)

    # Write atomically — write to a temp file, then rename over the target.
    # This prevents a concurrent reader from seeing a partial file.
    tmp_path = spill_path.with_suffix(".tmp")
    tmp_path.write_bytes(content.encode("utf-8"))
    tmp_path.rename(spill_path)

    # Build head + tail preview.
    lines = content.splitlines(keepends=True)
    head_lines = lines[:_PREVIEW_LINES]
    tail_lines = lines[-_PREVIEW_LINES:] if len(lines) > _PREVIEW_LINES else []

    head_text = "".join(head_lines)
    tail_text = "".join(tail_lines)

    marker_lines = len(lines) - 2 * _PREVIEW_LINES
    if marker_lines > 0:
        marker_block = f"\n... {marker_lines:,} intermediate lines truncated ...\n"
    else:
        marker_block = "\n... output truncated ...\n"

    preview_lines = [
        "===== TOOL OUTPUT EXCEEDED CAP — FULL OUTPUT SPILLED TO FILE =====\n",
        f"Original size: {total_bytes:,} bytes ({total_lines:,} lines)\n",
        f"Cap budget:    {max_bytes:,} bytes\n",
        f"\n--- First {_PREVIEW_LINES} lines ---\n",
        head_text.rstrip("\n"),
        marker_block,
        f"--- Last {_PREVIEW_LINES} lines ---\n",
        tail_text.lstrip("\n"),
        "\n===== RECOVER FULL OUTPUT FROM FILE =====\n",
        f"Path: {spill_path}\n",
        f"Lines: {total_lines} | Bytes: {total_bytes:,}\n",
        "\nRead the full output with your file tool to see all intermediate results.\n",
    ]

    preview = "".join(preview_lines)

    return CapResult(
        capped=True,
        preview=preview,
        spill_path=str(spill_path),
        total_bytes=total_bytes,
        total_lines=total_lines,
    )


def parse_step_from_path(path: str) -> tuple[str, str] | None:
    """Parse (item_id, step_id) from a spill-path filename, or None.

    Used by downstream tools to map a spill file back to the work item / step
    it came from.  Handles both the stable-hash path format and the older
    sequential format (``<step>-<n>.txt``).
    """
    # Match: <item_id>_<step_id>_<16-char-hash>.txt
    m = re.search(r"^([A-Z]-\d+)_([A-Z]\d+)_[a-f0-9]+\.txt$", Path(path).name)
    if m:
        return m.group(1), m.group(2)

    # Fallback: <step>-<n>.txt  (sequential format, no item_id)
    m2 = re.search(r"^([A-Z]\d+)-\d+\.txt$", Path(path).name)
    if m2:
        return ("<unknown>", m2.group(1))

    return None
