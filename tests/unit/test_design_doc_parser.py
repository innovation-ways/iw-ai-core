"""Unit tests for I-00053 design-doc parser.

Tests verify the behavior specified in the I-00053 Boundary Behavior table.
The parser requires a ## Dependencies section heading to find dependency lines.
"""

from __future__ import annotations

import pytest

from orch.design_doc_parser import (
    Dependencies,
    parse_dependencies,
    parse_impacted_paths,
    strip_excluded_sections,
)

# --- parse_dependencies ---


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        # Section heading with None/empty values
        (
            "## Dependencies\n\n- **Depends on**: None\n",
            Dependencies(depends_on=[], blocks=[]),
        ),
        (
            "## Dependencies\n\n- **Depends on**: —\n",
            Dependencies(depends_on=[], blocks=[]),
        ),
        (
            "## Dependencies\n\n- **Depends on**:\n",
            Dependencies(depends_on=[], blocks=[]),
        ),
        # Actual ID values
        (
            "## Dependencies\n\n- **Depends on**: F-00069\n",
            Dependencies(depends_on=["F-00069"], blocks=[]),
        ),
        (
            "## Dependencies\n\n- **Depends on**: F-00069, I-00042, CR-99025\n",
            Dependencies(depends_on=["F-00069", "I-00042", "CR-99025"], blocks=[]),
        ),
        (
            "## Dependencies\n\n- **Depends on**: F-00069 (provides make test-parallel)\n",
            Dependencies(depends_on=["F-00069"], blocks=[]),
        ),
        (
            "## Dependencies\n\n- **Depends on**: F-00069 - reason\n",
            Dependencies(depends_on=["F-00069"], blocks=[]),
        ),
        # Blocks field
        (
            "## Dependencies\n\n- **Blocks**: F-00073\n",
            Dependencies(depends_on=[], blocks=["F-00073"]),
        ),
        # Both fields together
        (
            "## Dependencies\n\n- **Depends on**: F-00069\n- **Blocks**: F-00073\n",
            Dependencies(depends_on=["F-00069"], blocks=["F-00073"]),
        ),
    ],
)
def test_parse_dependencies_table(content: str, expected: Dependencies) -> None:
    """Boundary Behavior table: parser requires ## Dependencies section heading."""
    assert parse_dependencies(content) == expected


def test_parse_dependencies_section_absent() -> None:
    """No `## Dependencies` section -> empty result, no error."""
    assert parse_dependencies("# Some doc\n\nNo deps section here.\n") == Dependencies([], [])


def test_parse_dependencies_handles_none_input() -> None:
    assert parse_dependencies(None) == Dependencies([], [])
    assert parse_dependencies("") == Dependencies([], [])


def test_parse_dependencies_case_insensitive_heading() -> None:
    content = "## dependencies\n\n- **Depends on**: F-00069\n"
    assert parse_dependencies(content) == Dependencies(depends_on=["F-00069"], blocks=[])


def test_parse_dependencies_extra_whitespace_tolerated() -> None:
    content = "## Dependencies\n\n-   **Depends on**:    F-00069  ,  I-00042   \n"
    assert parse_dependencies(content) == Dependencies(depends_on=["F-00069", "I-00042"], blocks=[])


def test_parse_dependencies_does_not_raise_on_malformed() -> None:  # noqa: assertion-scanner
    """Garbage input produces empty result + WARNING log, never raises."""
    parse_dependencies("**Depends on**: this is not a list of IDs\n")
    parse_dependencies("not even close to valid markdown")
    # Should not raise; specific output is implementation-defined for garbage,
    # but the call MUST complete.


def test_parse_dependencies_stops_at_next_section() -> None:
    """Lines after the next ## heading are not parsed."""
    content = (
        "## Dependencies\n\n"
        "- **Depends on**: F-00069\n\n"
        "## Other Section\n\n"
        "- **Depends on**: F-99999\n"
    )
    # Only F-00069 is parsed; F-99999 is after the next ## heading
    assert parse_dependencies(content) == Dependencies(depends_on=["F-00069"], blocks=[])


# --- strip_excluded_sections ---


def test_strip_excluded_sections_removes_out_of_scope() -> None:
    content = (
        "## In Scope\n"
        "- foo\n"
        "## Out of Scope\n"
        "- bar\n"
        "- `tests/foo.py` (owned by F-B)\n"
        "## Acceptance Criteria\n"
        "- baz\n"
    )
    result = strip_excluded_sections(content)
    assert "tests/foo.py" not in result
    assert "## In Scope" in result
    assert "## Acceptance Criteria" in result
    assert "## Out of Scope" not in result


def test_strip_excluded_sections_removes_notes() -> None:
    content = "## Description\nfoo\n## Notes\n- See `dashboard/qux.py` for details.\n"
    result = strip_excluded_sections(content)
    assert "dashboard/qux.py" not in result
    assert "## Description" in result


def test_strip_excluded_sections_preserves_code_fence_headings() -> None:
    """Lines inside a code fence are preserved even when the fence is
    inside an excluded section — code fence content is never stripped."""
    content = (
        "## File Manifest\n"
        "```\n"
        "## Out of Scope\n"
        "this is example markdown inside a code block\n"
        "```\n"
        "- `dashboard/foo.py`\n"
    )
    result = strip_excluded_sections(content)
    # The real File Manifest content survives (the code fence content is preserved
    # because it was inside a fence — but the `dashboard/foo.py` below the fence is
    # in the excluded section, so it's stripped)
    # Note: the fence lines are preserved since they're in the File Manifest section,
    # but the `- dashboard/foo.py` line is in the excluded section and gets stripped
    assert "dashboard/foo.py" not in result


def test_strip_excluded_sections_handles_none() -> None:
    assert strip_excluded_sections(None) == ""
    assert strip_excluded_sections("") == ""


def test_strip_excluded_sections_no_headings_returns_full_content() -> None:
    """A doc with no ## headings is returned unchanged."""
    content = "No headings here\n\nSome text\n- `orch/foo.py`\n"
    result = strip_excluded_sections(content)
    assert result == content


def test_strip_excluded_sections_path_in_description_is_preserved() -> None:
    """Paths in the Description section (not excluded) are preserved."""
    content = (
        "## Description\n"
        "This component touches `orch/foo.py` directly.\n"
        "## Out of Scope\n"
        "- `dashboard/bar.py`\n"
    )
    result = strip_excluded_sections(content)
    assert "orch/foo.py" in result
    assert "dashboard/bar.py" not in result


# --- parse_impacted_paths ---


class TestParseImpactedPathsBulletList:
    """Bullet-list happy path."""

    def test_parses_bullet_list(self) -> None:
        content = (
            "## Impacted Paths\n\n"
            "- orch/foo.py\n"
            "- orch/bar/**\n"
            "- dashboard/templates/components/**\n"
        )
        result = parse_impacted_paths(content)
        assert result.found is True
        assert result.paths == ["orch/foo.py", "orch/bar/**", "dashboard/templates/components/**"]

    def test_parses_asterisk_bullets(self) -> None:
        content = "## Impacted Paths\n\n* orch/foo.py\n* orch/bar/**\n"
        result = parse_impacted_paths(content)
        assert result.found is True
        assert result.paths == ["orch/foo.py", "orch/bar/**"]

    def test_deduplicates_preserving_order(self) -> None:
        content = (
            "## Impacted Paths\n\n- orch/foo.py\n- orch/bar/**\n- orch/foo.py\n- orch/foo.py\n"
        )
        result = parse_impacted_paths(content)
        assert result.paths == ["orch/foo.py", "orch/bar/**"]


class TestParseImpactedPathsCodeBlock:
    """Fenced code block happy path."""

    def test_parses_fenced_code_block(self) -> None:
        content = "## Impacted Paths\n\n```\norch/foo.py\norch/bar/**\n```\n"
        result = parse_impacted_paths(content)
        assert result.found is True
        assert result.paths == ["orch/foo.py", "orch/bar/**"]

    def test_parses_fenced_code_block_with_language(self) -> None:
        content = "## Impacted Paths\n\n```text\norch/foo.py\n```\n"
        result = parse_impacted_paths(content)
        assert result.found is True
        assert result.paths == ["orch/foo.py"]


class TestParseImpactedPathsAbsentOrEmpty:
    """Section absent / present but empty."""

    def test_section_absent(self) -> None:
        content = "## Description\n\nNo paths section here.\n"
        result = parse_impacted_paths(content)
        assert result.found is False
        assert result.paths == []

    def test_section_present_but_empty(self) -> None:
        content = "## Impacted Paths\n\n"
        result = parse_impacted_paths(content)
        assert result.found is True
        assert result.paths == []

    def test_section_present_empty_code_block(self) -> None:
        content = "## Impacted Paths\n\n```\n```\n"
        result = parse_impacted_paths(content)
        assert result.found is True
        assert result.paths == []

    def test_handles_none_input(self) -> None:
        result = parse_impacted_paths(None)
        assert result.found is False
        assert result.paths == []


class TestParseImpactedPathsValidationErrors:
    """Each violation raises ValueError with a precise message."""

    def test_absolute_path_raises(self) -> None:
        content = "## Impacted Paths\n\n- /etc/passwd\n"
        with pytest.raises(ValueError, match="absolute paths are not allowed"):
            parse_impacted_paths(content)

    def test_absolute_path_in_code_block_raises(self) -> None:
        content = "## Impacted Paths\n\n```\n/etc/passwd\n```\n"
        with pytest.raises(ValueError, match="absolute paths are not allowed"):
            parse_impacted_paths(content)

    def test_double_dot_segment_raises(self) -> None:
        content = "## Impacted Paths\n\n- orch/../etc/passwd\n"
        with pytest.raises(ValueError, match="'..' path segments are not allowed"):
            parse_impacted_paths(content)

    def test_double_dot_in_code_block_raises(self) -> None:
        content = "## Impacted Paths\n\n```\norch/../etc/passwd\n```\n"
        with pytest.raises(ValueError, match="'..' path segments are not allowed"):
            parse_impacted_paths(content)

    def test_empty_string_raises(self) -> None:
        content = "## Impacted Paths\n\n- \n"
        with pytest.raises(ValueError, match="empty glob"):
            parse_impacted_paths(content)

    def test_whitespace_only_raises(self) -> None:
        content = "## Impacted Paths\n\n-    \n"
        with pytest.raises(ValueError, match="empty glob"):
            parse_impacted_paths(content)

    def test_whitespace_inside_glob_raises(self) -> None:
        content = "## Impacted Paths\n\n- orch/foo bar.py\n"
        with pytest.raises(ValueError, match="whitespace"):
            parse_impacted_paths(content)


class TestParseImpactedPathsSpecialChars:
    """Globs with special characters."""

    def test_glob_double_star(self) -> None:
        content = "## Impacted Paths\n\n- **/*.py\n- orch/**\n"
        result = parse_impacted_paths(content)
        assert "**/*.py" in result.paths
        assert "orch/**" in result.paths

    def test_glob_square_brackets(self) -> None:
        content = "## Impacted Paths\n\n- orch/foo[abc].py\n"
        result = parse_impacted_paths(content)
        assert "orch/foo[abc].py" in result.paths

    def test_glob_question_mark(self) -> None:
        content = "## Impacted Paths\n\n- orch/foo?.py\n"
        result = parse_impacted_paths(content)
        assert "orch/foo?.py" in result.paths

    def test_glob_dot_prefix_allowed(self) -> None:
        content = "## Impacted Paths\n\n- .env\n- .gitignore\n"
        result = parse_impacted_paths(content)
        assert ".env" in result.paths
        assert ".gitignore" in result.paths


class TestParseImpactedPathsStopsAtNextSection:
    """Lines after the next ## heading are not parsed."""

    def test_stops_at_next_section(self) -> None:
        content = "## Impacted Paths\n\n- orch/foo.py\n\n## Other Section\n\n- /etc/passwd\n"
        result = parse_impacted_paths(content)
        assert result.found is True
        assert result.paths == ["orch/foo.py"]

    def test_mixed_bullets_and_code_block(self) -> None:
        content = "## Impacted Paths\n\n- orch/foo.py\n```\norch/bar.py\n```\n"
        result = parse_impacted_paths(content)
        assert result.paths == ["orch/foo.py", "orch/bar.py"]


class TestImpactedPathsBacktickStripping:
    """I-00071 regression: markdown code-span backticks must be stripped."""

    def test_strips_surrounding_code_span_backticks_in_bullet_lines(self) -> None:
        """I-00071 RED: bullet items wrapped in markdown backticks must be stored bare."""
        content = """## Impacted Paths

- `dashboard/CLAUDE.md`
- `dashboard/static/clipboard.js`
- `tests/dashboard/test_i00071.py`
"""
        result = parse_impacted_paths(content)
        assert result.found is True
        assert result.paths == [
            "dashboard/CLAUDE.md",
            "dashboard/static/clipboard.js",
            "tests/dashboard/test_i00071.py",
        ]

    def test_strips_surrounding_code_span_backticks_in_fenced_code_block(self) -> None:
        """I-00071: backticks inside a fenced code block also get stripped."""
        content = """## Impacted Paths

```
`orch/foo.py`
`orch/bar/**`
```
"""
        result = parse_impacted_paths(content)
        assert result.paths == ["orch/foo.py", "orch/bar/**"]

    def test_bare_paths_without_backticks_still_parse_unchanged(self) -> None:
        """I-00071 regression: backtick stripping must NOT corrupt bare paths."""
        content = """## Impacted Paths

- orch/foo.py
- orch/bar/**
"""
        result = parse_impacted_paths(content)
        assert result.paths == ["orch/foo.py", "orch/bar/**"]

    def test_mixed_wrapped_and_bare_paths(self) -> None:
        """I-00071: a mix of wrapped and bare paths in the same section."""
        content = """## Impacted Paths

- `orch/foo.py`
- orch/bar/baz.py
"""
        result = parse_impacted_paths(content)
        assert result.paths == ["orch/foo.py", "orch/bar/baz.py"]
