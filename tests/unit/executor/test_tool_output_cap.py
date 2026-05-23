"""Unit tests for executor/tool_output_cap.py — AC2 / I-00105.

These tests cover the tool-output cap helper:

* oversized input → spill file created with the FULL content + a preview returned with the path
* under-cap input → returned unchanged
* specific values asserted: file exists, file content equals the original, preview
  contains head and tail

Per the TDD contract, tests assert specific values, not just shape.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from executor.tool_output_cap import (
    DEFAULT_TOOL_OUTPUT_CAP_BYTES,
    CapResult,
    _count_lines,
    _hash_path,
    apply_tool_output_cap,
    parse_step_from_path,
)


class TestCountLines:
    """Line-counting helper edge cases."""

    def test_empty_string_zero_lines(self) -> None:
        assert _count_lines("") == 0

    def test_single_line_no_newline(self) -> None:
        assert _count_lines("hello") == 1

    def test_single_line_with_newline(self) -> None:
        assert _count_lines("hello\n") == 1

    def test_two_lines(self) -> None:
        assert _count_lines("line1\nline2") == 2
        assert _count_lines("line1\nline2\n") == 2

    def test_many_lines(self) -> None:
        text = "\n".join([f"line{i}" for i in range(100)])
        assert _count_lines(text) == 100


class TestHashPath:
    """Stable spill-path generation from content hash."""

    def test_same_content_same_path(self) -> None:
        d = Path(tempfile.mkdtemp())
        p1 = _hash_path(d, "hello world", "I-00105", "S07")
        p2 = _hash_path(d, "hello world", "I-00105", "S07")
        assert p1 == p2, "Identical (content, item, step) must produce identical path"

    def test_different_content_different_path(self) -> None:
        d = Path(tempfile.mkdtemp())
        p1 = _hash_path(d, "hello", "I-00105", "S07")
        p2 = _hash_path(d, "world", "I-00105", "S07")
        assert p1 != p2, "Different content must produce different path"

    def test_path_is_within_cache_dir(self) -> None:
        d = Path(tempfile.mkdtemp())
        path = _hash_path(d, "x" * 1000, "I-00105", "S07")
        assert path.parent == d

    def test_filename_contains_item_and_step(self) -> None:
        d = Path(tempfile.mkdtemp())
        path = _hash_path(d, "data", "I-00105", "S07")
        assert "I-00105" in path.name
        assert "S07" in path.name
        # Format assertion: filename must have at least 3 underscore-separated parts.
        assert path.name.count("_") >= 2, (
            f"Filename must follow item_step_hash.txt format, got: {path.name}"
        )


class TestApplyToolOutputCap:
    """AC2 tests: cap + spill, or passthrough."""

    @pytest.fixture
    def cache_dir(self) -> Path:
        return Path(tempfile.mkdtemp())

    # ── 1: Under-cap passthrough ──────────────────────────────────────────

    def test_under_cap_returns_unchanged(self, cache_dir: Path) -> None:
        """Result within cap budget → returned unchanged; no spill file."""
        content = "small output\n" * 10
        result = apply_tool_output_cap(
            content,
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=cache_dir,
        )
        assert result.capped is False
        assert result.preview == content
        assert result.spill_path is None
        assert result.total_bytes == len(content.encode("utf-8"))

    def test_under_cap_at_exact_boundary(self, cache_dir: Path) -> None:
        """Content exactly at max_bytes → capped=False (boundary: strict >)."""
        content = "x" * DEFAULT_TOOL_OUTPUT_CAP_BYTES
        result = apply_tool_output_cap(
            content,
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=cache_dir,
        )
        assert result.capped is False, "Exact-boundary content should NOT be capped"

    def test_under_cap_returns_correct_total_bytes(self, cache_dir: Path) -> None:
        """total_bytes reflects actual UTF-8 byte count."""
        content = "é" * 1000  # 2 bytes each in UTF-8 → 2000 bytes
        result = apply_tool_output_cap(
            content,
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=cache_dir,
        )
        assert result.total_bytes == 2000

    # ── 2: Over-cap → spill ───────────────────────────────────────────────

    def test_over_cap_capped_true(self, cache_dir: Path) -> None:
        """Result larger than cap → capped=True."""
        content = "x" * (DEFAULT_TOOL_OUTPUT_CAP_BYTES + 1)
        result = apply_tool_output_cap(
            content,
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=cache_dir,
        )
        assert result.capped is True

    def test_over_cap_spill_file_created_with_full_content(self, cache_dir: Path) -> None:
        """Spill file contains the FULL unmodified content."""
        # "FULL CONTENT LINE DATA x\n" = 26 bytes/line × 3000 = 78,000 bytes — well over 25 KB cap
        content = "FULL CONTENT LINE DATA x\n" * 3000
        result = apply_tool_output_cap(
            content,
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=cache_dir,
        )
        assert result.capped is True, (
            f"{len(content)} bytes should exceed cap {DEFAULT_TOOL_OUTPUT_CAP_BYTES}"
        )
        assert result.spill_path is not None
        spill = Path(result.spill_path)
        assert spill.exists(), "Spill file must be created"
        assert spill.read_text("utf-8") == content, (
            "Spill file must contain full unmodified content"
        )

    def test_over_cap_preview_contains_head_and_tail(self, cache_dir: Path) -> None:
        """Preview contains first and last lines (recoverability)."""
        lines = [f"LINE_{i:04d}_THE_QUICK_BROWN_FOX_JUMPS_OVER" for i in range(200)]
        content = "\n".join(lines)
        # ~50 bytes/line × 200 ≈ 10,000 bytes — still under cap; pad it
        content = content + ("X" * (DEFAULT_TOOL_OUTPUT_CAP_BYTES + 1000))
        result = apply_tool_output_cap(
            content,
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=cache_dir,
        )
        assert result.capped is True, (
            f"{len(content)} bytes should exceed cap {DEFAULT_TOOL_OUTPUT_CAP_BYTES}"
        )
        assert "LINE_0000" in result.preview, "Preview must contain first line"
        assert "LINE_0199" in result.preview, "Preview must contain last line"

    def test_over_cap_preview_contains_file_path(self, cache_dir: Path) -> None:
        """Preview tells the agent where to find the full output."""
        content = "x" * (DEFAULT_TOOL_OUTPUT_CAP_BYTES + 1)
        result = apply_tool_output_cap(
            content,
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=cache_dir,
        )
        assert result.spill_path is not None
        assert result.spill_path in result.preview, "Preview must list the spill path"
        # Format assertion: the spill file must have a .txt extension.
        assert result.spill_path.endswith(".txt"), (
            f"Spill path must end with .txt, got: {result.spill_path}"
        )

    def test_over_cap_preview_contains_total_size(self, cache_dir: Path) -> None:
        """Preview tells the agent how large the full output is."""
        content = "y" * (DEFAULT_TOOL_OUTPUT_CAP_BYTES + 1)
        result = apply_tool_output_cap(
            content,
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=cache_dir,
        )
        # Preview uses formatted bytes (comma separator): "25,601 bytes"
        formatted = f"{result.total_bytes:,}"
        assert formatted in result.preview, (
            f"Preview must include formatted total byte count ({formatted})",
        )
        # Concrete: the total_bytes must exceed the cap.
        assert result.total_bytes > DEFAULT_TOOL_OUTPUT_CAP_BYTES, (
            f"total_bytes ({result.total_bytes}) must exceed cap ({DEFAULT_TOOL_OUTPUT_CAP_BYTES})"
        )

    def test_over_cap_preview_contains_truncated_marker(self, cache_dir: Path) -> None:
        """Preview includes the '... intermediate lines truncated ...' marker."""
        lines = [f"LINE_{i}_THIS_IS_A_MEDIUM_SIZED_DATA_LINE" for i in range(500)]
        content = "\n".join(lines)
        # ~44 bytes/line × 500 ≈ 22,000 bytes — still under 25 KB; pad it
        content = content + ("Z" * (DEFAULT_TOOL_OUTPUT_CAP_BYTES + 1000))
        result = apply_tool_output_cap(
            content,
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=cache_dir,
        )
        assert result.capped is True, (
            f"{len(content)} bytes should exceed cap {DEFAULT_TOOL_OUTPUT_CAP_BYTES}"
        )
        assert "truncated" in result.preview.lower()

    def test_over_cap_total_bytes_reflects_original(self, cache_dir: Path) -> None:
        """total_bytes is the original content byte size, not the preview byte size."""
        content = "z" * 100_000  # 100,000 chars × 1 byte each in ASCII = 100,000 bytes > 25 KB cap
        result = apply_tool_output_cap(
            content,
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=cache_dir,
        )
        assert result.total_bytes == 100_000, (
            f"total_bytes should be the original byte count (100,000), got {result.total_bytes}"
        )
        assert result.total_bytes > DEFAULT_TOOL_OUTPUT_CAP_BYTES

    def test_over_cap_total_lines_reflects_original(self, cache_dir: Path) -> None:
        """total_lines is the original line count."""
        lines = [f"line{i}" for i in range(1000)]
        content = "\n".join(lines)
        result = apply_tool_output_cap(
            content,
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=cache_dir,
        )
        assert result.total_lines == 1000

    def test_over_cap_cache_dir_created_if_missing(self, cache_dir: Path) -> None:
        """cache_dir is created if it does not exist (mkdir parents=True)."""
        subdir = cache_dir / "nested" / "deep"
        content = "x" * (DEFAULT_TOOL_OUTPUT_CAP_BYTES + 1)
        result = apply_tool_output_cap(
            content,
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=subdir,
        )
        assert result.capped is True
        assert subdir.exists()
        assert Path(result.spill_path).parent == subdir

    def test_over_cap_idempotent_path(self, cache_dir: Path) -> None:
        """Same (content, item_id, step_id) always produces the same spill_path."""
        content = ("repeatable content line of data here\n" * 1000) + (
            "X" * (DEFAULT_TOOL_OUTPUT_CAP_BYTES + 1000)
        )
        result1 = apply_tool_output_cap(
            content,
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=cache_dir,
        )
        result2 = apply_tool_output_cap(
            content,
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=cache_dir,
        )
        assert result1.capped is True, (
            f"{len(content)} bytes should exceed cap {DEFAULT_TOOL_OUTPUT_CAP_BYTES}"
        )
        assert result2.capped is True
        assert result1.spill_path == result2.spill_path

    # ── 3: Return type / schema ───────────────────────────────────────────

    def test_returns_capresult_dataclass(self, cache_dir: Path) -> None:
        """Result is a CapResult with all required fields."""
        result = apply_tool_output_cap(
            "tiny output",
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=cache_dir,
        )
        assert isinstance(result, CapResult)
        assert isinstance(result.capped, bool)
        assert isinstance(result.preview, str)
        assert isinstance(result.spill_path, (str, type(None)))
        assert isinstance(result.total_bytes, int)
        assert isinstance(result.total_lines, int)
        # Concrete value assertions.
        assert result.capped is False, "tiny output must not be capped"
        assert result.preview == "tiny output", (
            "preview must equal original content when not capped"
        )
        assert result.spill_path is None, "spill_path must be None when not capped"
        assert result.total_bytes == len(b"tiny output")
        assert result.total_lines == 1

    def test_preview_is_string(self, cache_dir: Path) -> None:
        """preview field is always a str (never bytes, never None)."""
        result = apply_tool_output_cap(
            "small output",
            item_id="I-00105",
            step_id="S07",
            max_bytes=DEFAULT_TOOL_OUTPUT_CAP_BYTES,
            cache_dir=cache_dir,
        )
        assert isinstance(result.preview, str)
        # Content assertion: preview must contain the actual content string.
        assert result.preview == "small output", (
            f"preview must equal original content, got: {result.preview!r}"
        )


class TestParseStepFromPath:
    """Spill-path → (item_id, step_id) parser for downstream tools."""

    def test_parses_stable_hash_format(self) -> None:
        path = "/some/cache/I-00105_S07_a1b2c3d4e5f6abcd.txt"
        result = parse_step_from_path(path)
        assert result == ("I-00105", "S07"), f"Expected (I-00105, S07), got {result}"

    def test_parses_step_only_format(self) -> None:
        path = "/some/cache/S07-1.txt"
        result = parse_step_from_path(path)
        assert result == ("<unknown>", "S07")

    def test_returns_none_for_unknown_format(self) -> None:
        result = parse_step_from_path("not_a_spill_path.txt")
        assert result is None

    def test_returns_none_for_empty_path(self) -> None:
        result = parse_step_from_path("")
        assert result is None
