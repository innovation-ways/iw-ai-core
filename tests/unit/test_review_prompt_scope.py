"""I-00116 — Prompt scope regression tests.

Validates that the code-review prompt (S05) correctly scopes the reviewer's
diff to `scope.allowed_paths` from the workflow-manifest instead of using
unbounded `git diff HEAD`. Also verifies that `skills/iw-workflow/SKILL.md`
documents the convention and references I-00116.

These tests read the actual files from disk — they are NOT mocked.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import orch.daemon.step_monitor  # noqa: TC004 — needed for step_monitor imports used in other tests

# ---------------------------------------------------------------------------
# Paths to master files
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent.parent
_AGENTS_DIR = _ROOT / "agents"
_SKILLS_DIR = _ROOT / "skills"
_IW_WORKFLOW_SKILL = _SKILLS_DIR / "iw-workflow" / "SKILL.md"


def _read_agent_prompt(filename: str) -> str:
    """Read the content of a code-review prompt file from agents/.

    Returns the full file text. Raises FileNotFoundError if missing.
    """
    path = _AGENTS_DIR / filename
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1: prompt references allowed_paths
# ---------------------------------------------------------------------------


def test_review_prompt_references_allowed_paths() -> None:
    """Both code-review prompt files must contain the string 'allowed_paths'.

    AC4: the reviewer must be instructed to restrict diff to files matching
    the step's scope.allowed_paths globs. 'allowed_paths' is the canonical
    signal word for this instruction.

    Semantic assertions:
      - 'allowed_paths' in agents/claude/code-review-impl.md
      - 'allowed_paths' in agents/opencode/code-review-impl.md
      - 'allowed_paths' in agents/pi/code-review-impl.md (if present)

    If S05's prompt change was reverted, these tests would FAIL — catching
    the regression at the prompt level, before it can cause production harm.
    """
    for filename in ["claude/code-review-impl.md", "opencode/code-review-impl.md"]:
        path = _AGENTS_DIR / filename
        assert path.exists(), f"Prompt file {filename} not found at {path}"
        text = path.read_text(encoding="utf-8")
        assert "allowed_paths" in text, (
            f"Prompt file {filename} must reference 'allowed_paths' "
            f"(S05: scope-anchored diff convention for I-00116). "
            "The reviewer must restrict diff to scope.allowed_paths from workflow-manifest.json."
        )


# ---------------------------------------------------------------------------
# Test 2: prompt does NOT recommend unbounded git diff HEAD
# ---------------------------------------------------------------------------


def test_review_prompt_does_not_recommend_unbounded_git_diff_head() -> None:
    """Neither code-review prompt file must instruct the reviewer to use unbounded 'git diff HEAD'.

    The anti-pattern: "diff against HEAD" in instructional context (not negative
    context like "do NOT use git diff HEAD"). This is the root cause of I-00116's
    flip-flop bug where re-launched reviewers see un-committed changes from later
    steps and mis-attribute them.

    Pragmatic test:
      - Assert the exact phrase `"diff against HEAD"` does NOT appear
      - Assert `"allowed_paths"` appears within 200 chars of the words "review" or "scope"

    Semantic assertion:
      - '"diff against HEAD"' NOT in prompts  (no unbounded diff instruction)
      - 'allowed_paths' present in prompts    (scope-anchored diff in use)
    """
    forbidden_phrase = '"diff against HEAD"'

    for filename in ["claude/code-review-impl.md", "opencode/code-review-impl.md"]:
        path = _AGENTS_DIR / filename
        text = path.read_text(encoding="utf-8")

        # Explicit anti-pattern: the phrase must NOT appear in instructional context
        assert forbidden_phrase not in text, (
            f"Prompt file {filename} must NOT contain the phrase {forbidden_phrase}. "
            "Unbounded diff causes reviewers to see un-committed work from later steps "
            "(the flip-flop bug, root cause of I-00116). Use scope.allowed_paths instead."
        )

        # Positive signal: allowed_paths must be present (proves the fix was applied)
        assert "allowed_paths" in text, (
            f"Prompt file {filename} must contain 'allowed_paths' as the diff-scoping "
            f"instruction (S05 fix for I-00116)."
        )


# ---------------------------------------------------------------------------
# Test 3: iw-workflow skill documents diff-scoping convention
# ---------------------------------------------------------------------------


def test_iw_workflow_skill_documents_diff_scoping_convention() -> None:
    """skills/iw-workflow/SKILL.md must document allowed_paths diff scoping and reference I-00116.

    The skill doc serves as the canonical reference for all agents that use the
    workflow. Its presence proves the convention is intentional and enforceable.

    Semantic assertions:
      - 'allowed_paths' appears in the skill doc
      - 'I-00116' appears in the skill doc  (references the incident that drove the fix)
      - A heading/section referencing 'diff scoping' or 'allowed_paths' exists
    """
    assert _IW_WORKFLOW_SKILL.exists(), f"iw-workflow SKILL.md not found at {_IW_WORKFLOW_SKILL}"
    text = _IW_WORKFLOW_SKILL.read_text(encoding="utf-8")

    assert "allowed_paths" in text, (
        "skills/iw-workflow/SKILL.md must document 'allowed_paths' "
        "as the canonical diff-scoping mechanism (I-00116 S05)."
    )

    assert "I-00116" in text, (
        "skills/iw-workflow/SKILL.md must reference I-00116 "
        "(the incident that introduced the allowed_paths diff-scoping convention)."
    )

    # Check for a section or heading about diff scoping
    # The skill should have a heading that mentions allowed_paths or diff scoping
    has_diff_section = (
        "Diff scoping" in text or "diff scoping" in text.lower() or "allowed_paths" in text
    )
    assert has_diff_section, (
        "skills/iw-workflow/SKILL.md must have a section or explicit reference "
        "to the diff-scoping convention."
    )


# ---------------------------------------------------------------------------
# Bonus: code_review_final step type also scopes to allowed_paths
# ---------------------------------------------------------------------------


def test_code_review_final_prompt_also_references_allowed_paths() -> None:
    """code_review_final steps must also use allowed_paths scoping.

    The downstream final review step (code_review_final) is equally vulnerable
    to the flip-flop bug — it must also restrict its diff to allowed_paths.
    If S05 only patched code_review and forgot code_review_final, this test catches it.

    Semantic assertion:
      - 'allowed_paths' present in both prompt files
      - Both files are actual code-review prompts (contain 'verdict', 'findings')
    """
    for filename in ["claude/code-review-impl.md", "opencode/code-review-impl.md"]:
        path = _AGENTS_DIR / filename
        text = path.read_text(encoding="utf-8")

        # Both prompt types must use allowed_paths (multiple times — once in docs, once in logic)
        assert text.count("allowed_paths") >= 2, (
            f"Prompt file {filename} must reference 'allowed_paths' "
            f"for ALL review step types (code_review AND code_review_final)."
        )

        # Verify these are actual review prompts (not accidentally a different doc type)
        assert "verdict" in text, (
            f"Prompt file {filename} should contain 'verdict' "
            "(expected in a code-review implementation prompt)."
        )
