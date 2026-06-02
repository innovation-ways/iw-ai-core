"""CR-00023: assert prompt-template hints + Implementation pre-flight section.

Pure file-content tests — no DB, no fixtures. Covers AC5 and AC7.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Templates that must mention iw item-status (AC5).
IN_SCOPE_TEMPLATES = [
    "templates/design/Implementation_Prompt_Template.md",
    "templates/design/CodeReview_Prompt_Template.md",
    "templates/design/CodeReview_Final_Prompt_Template.md",
    "templates/design/QualityValidation_Template.md",
    "ai-dev/templates/Implementation_Prompt_Template.md",
    "ai-dev/templates/CodeReview_Prompt_Template.md",
    "ai-dev/templates/CodeReview_Final_Prompt_Template.md",
    "ai-dev/templates/QualityValidation_Template.md",
]

# Templates that must NOT contain the hint (defensive — they were excluded
# from CR-00023's S07 because they read design-time fields like
# `scope.allowed_paths` that don't drift).
OUT_OF_SCOPE_TEMPLATES = [
    "templates/design/QualityValidation_FIX_Prompt_Template.md",
    "templates/design/CodeReview_FIX_Prompt_Template.md",
    "templates/design/CodeReview_FIX_Final_Prompt_Template.md",
    "templates/design/QVBrowser_Prompt_Template.md",
    "ai-dev/templates/QualityValidation_FIX_Prompt_Template.md",
    "ai-dev/templates/CodeReview_FIX_Prompt_Template.md",
    "ai-dev/templates/CodeReview_FIX_Final_Prompt_Template.md",
    "ai-dev/templates/QVBrowser_Prompt_Template.md",
]

IMPLEMENTATION_TEMPLATES = [
    "templates/design/Implementation_Prompt_Template.md",
    "ai-dev/templates/Implementation_Prompt_Template.md",
]

# In-scope templates that are NOT Implementation — they get the iw item-status
# hint but must NOT have the Pre-flight section (those agents do not write code).
NON_IMPLEMENTATION_IN_SCOPE = [
    "templates/design/CodeReview_Prompt_Template.md",
    "templates/design/CodeReview_Final_Prompt_Template.md",
    "templates/design/QualityValidation_Template.md",
    "ai-dev/templates/CodeReview_Prompt_Template.md",
    "ai-dev/templates/CodeReview_Final_Prompt_Template.md",
    "ai-dev/templates/QualityValidation_Template.md",
]


@pytest.mark.parametrize("template_rel", IN_SCOPE_TEMPLATES)
def test_in_scope_template_mentions_iw_item_status(template_rel: str) -> None:
    """AC5: every in-scope template directs agents to iw item-status."""
    content = (REPO_ROOT / template_rel).read_text(encoding="utf-8")
    assert "iw item-status" in content, f"{template_rel}: missing iw item-status hint"
    assert "CR-00023" in content, f"{template_rel}: missing CR-00023 reference in hint"
    assert "design-time snapshot" in content, (
        f"{template_rel}: hint must reference 'design-time snapshot' (AC5 wording)"
    )


@pytest.mark.parametrize("template_rel", OUT_OF_SCOPE_TEMPLATES)
def test_out_of_scope_template_unchanged(template_rel: str) -> None:
    """AC5 defensive: FIX / Browser templates must not be touched."""
    content = (REPO_ROOT / template_rel).read_text(encoding="utf-8")
    assert "iw item-status" not in content, (
        f"{template_rel}: FIX/Browser templates must not mention iw item-status"
    )
    assert "Pre-flight Quality Gates" not in content, (
        f"{template_rel}: FIX/Browser templates must not contain Pre-flight Quality Gates"
    )


@pytest.mark.parametrize("template_rel", IMPLEMENTATION_TEMPLATES)
def test_implementation_template_has_preflight_section(template_rel: str) -> None:
    """AC7: Implementation template gets Pre-flight Quality Gates section."""
    content = (REPO_ROOT / template_rel).read_text(encoding="utf-8")
    assert "## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023" in content, (
        f"{template_rel}: missing exact Pre-flight heading"
    )
    assert "make format" in content, f"{template_rel}: Pre-flight must list make format"
    assert "make typecheck" in content, f"{template_rel}: Pre-flight must list make typecheck"
    assert "make lint" in content, f"{template_rel}: Pre-flight must list make lint"

    preflight_idx = content.find("## Pre-flight Quality Gates")
    test_verif_idx = content.find("## Test Verification (NON-NEGOTIABLE)")
    assert preflight_idx != -1
    assert test_verif_idx != -1
    assert preflight_idx < test_verif_idx, (
        f"{template_rel}: Pre-flight section must appear BEFORE Test Verification"
    )


@pytest.mark.parametrize("template_rel", IMPLEMENTATION_TEMPLATES)
def test_implementation_template_contract_has_preflight_object(template_rel: str) -> None:
    """AC7: Subagent Result Contract example must include preflight."""
    content = (REPO_ROOT / template_rel).read_text(encoding="utf-8")
    assert '"preflight":' in content, (
        f"{template_rel}: Subagent Result Contract must include preflight object"
    )
    contract_idx = content.find('"preflight":')
    snippet = content[contract_idx : contract_idx + 400]
    for key in ("format", "typecheck", "lint"):
        assert f'"{key}":' in snippet, f"{template_rel}: preflight object must contain key {key!r}"


@pytest.mark.parametrize("template_rel", NON_IMPLEMENTATION_IN_SCOPE)
def test_non_implementation_template_lacks_preflight(template_rel: str) -> None:
    """AC7 defensive: only Implementation gets Pre-flight."""
    content = (REPO_ROOT / template_rel).read_text(encoding="utf-8")
    assert "Pre-flight Quality Gates" not in content, (
        f"{template_rel}: only Implementation templates should have Pre-flight"
    )
    assert '"preflight":' not in content, (
        f"{template_rel}: only Implementation templates should have preflight contract field"
    )


def test_implementation_pair_pre_flight_blocks_match() -> None:
    """AC7: the Pre-flight section + preflight contract must be byte-identical
    between the two Implementation_Prompt_Template.md copies.

    Note: the full files are NOT byte-identical pre-existing — the
    `ai-dev/templates/` copy has a prepended Docker/migrations boilerplate
    block that the master in `templates/design/` lacks. That drift predates
    CR-00023; reconciling it is out of scope. We instead assert that the
    sections this CR adds are identical, which is what the AC7 spirit
    intends ("the new sections appear in lockstep in both copies").
    """
    a = (REPO_ROOT / IMPLEMENTATION_TEMPLATES[0]).read_text(encoding="utf-8")
    b = (REPO_ROOT / IMPLEMENTATION_TEMPLATES[1]).read_text(encoding="utf-8")

    def extract_block(text: str, start_marker: str, end_marker: str) -> str:
        """Return extract block."""
        s = text.find(start_marker)
        e = text.find(end_marker, s)
        assert s != -1, f"start marker not found: {start_marker!r}"
        assert e != -1, f"end marker not found: {end_marker!r}"
        return text[s:e]

    pre_a = extract_block(
        a,
        "## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023",
        "## Test Verification (NON-NEGOTIABLE)",
    )
    pre_b = extract_block(
        b,
        "## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023",
        "## Test Verification (NON-NEGOTIABLE)",
    )
    assert pre_a == pre_b, "Pre-flight section drifted between Implementation template copies"

    contract_a = extract_block(a, '"preflight":', '"tests_passed":')
    contract_b = extract_block(b, '"preflight":', '"tests_passed":')
    assert contract_a == contract_b, (
        "preflight contract block drifted between Implementation template copies"
    )


@pytest.mark.parametrize("template_rel", IMPLEMENTATION_TEMPLATES)
def test_implementation_template_has_css_rename_checklist(template_rel: str) -> None:
    """CR-00041: assert CSS-class-rename checklist line is present in Test Verification.

    When the design renames a CSS class name, the agent must grep the test suite
    for the old class name and update every assertion to match the new name before
    reporting tests_passed: true. Stale CSS class assertions are a code-review
    failure mode (see CR-00039 self-assess finding [3]).
    """
    content = (REPO_ROOT / template_rel).read_text(encoding="utf-8")

    # Extract the Test Verification section
    tv_start = content.find("## Test Verification (NON-NEGOTIABLE)")
    assert tv_start != -1, f"{template_rel}: missing Test Verification section"

    # End marker: next top-level heading or end-of-file
    next_heading = content.find("\n## ", tv_start + 1)
    tv_section = content[tv_start:] if next_heading == -1 else content[tv_start:next_heading]

    assert "CSS class" in tv_section, (
        f"{template_rel}: Test Verification section missing 'CSS class' substring"
    )
    assert "CR-00039" in tv_section, (
        f"{template_rel}: Test Verification section missing 'CR-00039' reference"
    )
