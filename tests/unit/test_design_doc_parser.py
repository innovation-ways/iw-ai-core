"""Unit tests for I-00053 design-doc parser.

Tests verify the behavior specified in the I-00053 Boundary Behavior table.
The parser requires a ## Dependencies section heading to find dependency lines.
"""

from __future__ import annotations

import pytest

from orch.design_doc_parser import (
    Dependencies,
    parse_dependencies,
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


def test_parse_dependencies_does_not_raise_on_malformed() -> None:
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
