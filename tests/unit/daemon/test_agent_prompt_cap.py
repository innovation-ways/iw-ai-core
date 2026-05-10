"""Unit tests for batch_manager.write_agent_prompt — I-00074 execve argv cap.

A fix-cycle / step prompt is consumed as ``"$(cat <file>)"`` on a shell command
line. Linux caps a single argv element at MAX_ARG_STRLEN (128 KiB); a larger
prompt makes ``execve`` fail with E2BIG ("Argument list too long") and the agent
never starts. ``write_agent_prompt`` truncates the middle to keep the file under
``MAX_PROMPT_BYTES`` while preserving the head (task framing) and tail (summary).
"""

from __future__ import annotations

from pathlib import Path

from orch.daemon.batch_manager import MAX_PROMPT_BYTES, write_agent_prompt


def test_small_prompt_written_verbatim(tmp_path: Path) -> None:
    p = tmp_path / "small.prompt"
    text = "fix the failing test\n" * 10
    write_agent_prompt(p, text)
    assert p.read_text() == text


def test_prompt_at_limit_written_verbatim(tmp_path: Path) -> None:
    p = tmp_path / "atlimit.prompt"
    text = "x" * MAX_PROMPT_BYTES
    write_agent_prompt(p, text)
    assert p.read_bytes() == text.encode("utf-8")


def test_oversized_prompt_is_truncated_below_limit(tmp_path: Path) -> None:
    p = tmp_path / "huge.prompt"
    # Mimic the I-00074 case: a ~350 KB prompt (a full `pytest -v` dump spliced in).
    text = "\n".join(f"tests/unit/x.py::test_{i} PASSED [ 50%]" for i in range(10000))
    assert len(text.encode("utf-8")) > MAX_PROMPT_BYTES
    write_agent_prompt(p, text)
    written = p.read_bytes()
    assert len(written) <= MAX_PROMPT_BYTES
    assert "truncated" in written.decode("utf-8", errors="ignore")


def test_truncation_keeps_head_and_tail(tmp_path: Path) -> None:
    p = tmp_path / "huge2.prompt"
    text = "HEAD-MARKER\n" + ("y" * (MAX_PROMPT_BYTES * 3)) + "\nTAIL-MARKER"
    write_agent_prompt(p, text)
    written = p.read_text(encoding="utf-8", errors="ignore")
    assert written.startswith("HEAD-MARKER")
    assert written.endswith("TAIL-MARKER")
    assert len(written.encode("utf-8")) <= MAX_PROMPT_BYTES
