"""CR-00045: assert TDD RED-run evidence contract strings in agent/template files.

Pure file-content assertions — no DB, no fixtures. This test fails before the
agent/template edits land (RED phase) and passes after (GREEN phase). It pins
the contract that `backend-impl` agents must run the new failing test, confirm
the failure is for the expected reason, and record `tdd_red_evidence`.

AC3 / Design §TDD Approach.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# Files that MUST contain the literal marker "tdd_red_evidence" and a phrase
# from the mandatory-RED language ("run the new failing test").
IN_SCOPE_FILES = [
    "agents/claude/backend-impl.md",
    "agents/opencode/backend-impl.md",
    "templates/design/Implementation_Prompt_Template.md",
    "ai-dev/templates/Implementation_Prompt_Template.md",
    "templates/design/SelfAssess_Prompt_Template.md",
    "ai-dev/templates/SelfAssess_Prompt_Template.md",
    "templates/design/CodeReview_Prompt_Template.md",
    "ai-dev/templates/CodeReview_Prompt_Template.md",
]

# The stable phrase from the mandatory-RED language introduced in the
# agent edits.  Both "run the new failing test" and "run the new test" are
# acceptable — we check for the shorter anchor so either form passes.
RED_PHRASE = "run the new failing test"


@pytest.mark.parametrize("rel_path", IN_SCOPE_FILES)
def test_file_contains_tdd_red_evidence_marker(rel_path: str) -> None:
    """AC3: every in-scope file contains the literal marker string."""
    content = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    assert "tdd_red_evidence" in content, f"{rel_path}: missing 'tdd_red_evidence' contract marker"


@pytest.mark.parametrize("rel_path", IN_SCOPE_FILES)
def test_file_contains_red_run_phrase(rel_path: str) -> None:
    """AC3: every in-scope file contains the mandatory-RED run phrase."""
    content = (REPO_ROOT / rel_path).read_text(encoding="utf-8")
    assert RED_PHRASE in content, f"{rel_path}: missing '{RED_PHRASE}' — the mandatory-RED run step"


# The three template pairs must be byte-identical after the edits.
IDENTICAL_PAIRS = [
    (
        "templates/design/Implementation_Prompt_Template.md",
        "ai-dev/templates/Implementation_Prompt_Template.md",
    ),
    (
        "templates/design/SelfAssess_Prompt_Template.md",
        "ai-dev/templates/SelfAssess_Prompt_Template.md",
    ),
    (
        "templates/design/CodeReview_Prompt_Template.md",
        "ai-dev/templates/CodeReview_Prompt_Template.md",
    ),
]


@pytest.mark.parametrize(("master_path", "copy_path"), IDENTICAL_PAIRS)
def test_template_pair_is_byte_identical(master_path: str, copy_path: str) -> None:
    """AC2: templates/design/X.md and ai-dev/templates/X.md are byte-identical."""
    master = (REPO_ROOT / master_path).read_bytes()
    copy = (REPO_ROOT / copy_path).read_bytes()
    assert master == copy, (
        f"{master_path} and {copy_path} differ — "
        "CR-00045 requires both copies to be identical after edits"
    )
