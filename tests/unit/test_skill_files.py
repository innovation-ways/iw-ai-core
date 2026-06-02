"""Unit tests for skill file content and structure.

Validates that skill files contain the correct frontmatter fields,
placeholder patterns, and sync invariants. No DB or network I/O.
"""

from pathlib import Path

import pytest

WORKTREE_ROOT = Path(__file__).resolve().parents[2]  # .worktrees/F-00078

SKILLS_DIR = WORKTREE_ROOT / "skills"
CLAUDE_SKILLS_DIR = WORKTREE_ROOT / ".claude" / "skills"
TEMPLATES_DIR = WORKTREE_ROOT / "templates" / "design"
AI_DEV_TEMPLATES_DIR = WORKTREE_ROOT / "ai-dev" / "templates"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def read_skill(name: str) -> str:
    """Return read skill."""
    return (SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8")


def read_template(name: str) -> str:
    """Return read template."""
    return (TEMPLATES_DIR / name).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# iw-item-analyze: OpenCode migration
# ---------------------------------------------------------------------------


def test_item_analyze_has_no_allowed_tools() -> None:
    """OpenCode skills must NOT have allowed-tools frontmatter field."""
    content = read_skill("iw-item-analyze")
    assert "allowed-tools:" not in content


def test_item_analyze_has_no_argument_hint() -> None:
    """OpenCode skills must NOT have argument-hint frontmatter field."""
    content = read_skill("iw-item-analyze")
    assert "argument-hint:" not in content


def test_item_analyze_uses_iw_item_id() -> None:
    """Skill must read item ID from IW_ITEM_ID env var, not $ARGUMENTS."""
    content = read_skill("iw-item-analyze")
    assert "$IW_ITEM_ID" in content
    assert "$ARGUMENTS" not in content


def test_item_analyze_writes_findings_json() -> None:
    """Skill must reference the _self_assess_findings.json output file."""
    content = read_skill("iw-item-analyze")
    assert "_self_assess_findings.json" in content


def test_item_analyze_has_compatibility_opencode() -> None:
    """Skill must declare compatibility: opencode in frontmatter."""
    content = read_skill("iw-item-analyze")
    assert "compatibility: opencode" in content


def test_item_analyze_phase_0_5_log_inventory() -> None:
    """Skill must have Phase 0.5 for log size inventory."""
    content = read_skill("iw-item-analyze")
    assert "Phase 0.5" in content
    assert "tail -500" in content


# ---------------------------------------------------------------------------
# SelfAssess_Prompt_Template
# ---------------------------------------------------------------------------


def test_self_assess_template_exists() -> None:
    """Template must exist in templates/design/."""
    assert (TEMPLATES_DIR / "SelfAssess_Prompt_Template.md").exists()


def test_self_assess_template_has_id_placeholder() -> None:
    """Template must use {ID} placeholder."""
    content = read_template("SelfAssess_Prompt_Template.md")
    assert "{ID}" in content


def test_self_assess_template_has_nn_placeholder() -> None:
    """Template must use {NN} placeholder."""
    content = read_template("SelfAssess_Prompt_Template.md")
    assert "{NN}" in content


def test_self_assess_template_mentions_iw_item_analyze() -> None:
    """Template must reference the iw-item-analyze skill."""
    content = read_template("SelfAssess_Prompt_Template.md")
    assert "iw-item-analyze" in content


def test_self_assess_template_soft_step_semantics() -> None:
    """Template must document soft-step semantics."""
    content = read_template("SelfAssess_Prompt_Template.md")
    assert "soft" in content.lower()
    assert "block" in content.lower() or "merge" in content.lower()


# ---------------------------------------------------------------------------
# Canonical agent table: self-assess-impl
# ---------------------------------------------------------------------------


def test_workflow_skill_has_self_assess_impl_in_table() -> None:
    """workflow skill canonical table must have self-assess-impl."""
    content = read_skill("iw-workflow")
    assert "self-assess-impl" in content


def test_workflow_skill_soft_step_docs() -> None:
    """workflow skill must document soft-step behavior for self-assess-impl."""
    content = read_skill("iw-workflow")
    assert "soft step" in content.lower()
    assert "block" in content.lower() or "merging" in content.lower()


# ---------------------------------------------------------------------------
# Design skills: conditional self_assess injection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "skill_name",
    ["iw-new-feature", "iw-new-cr", "iw-new-incident"],
)
def test_design_skill_injects_self_assess_when_flag_on(skill_name: str) -> None:
    """Design skills must document the conditional self_assess injection rule."""
    content = read_skill(skill_name)
    assert "self-assess-impl" in content
    assert "projects.toml" in content


@pytest.mark.parametrize(
    "skill_name",
    ["iw-new-feature", "iw-new-cr", "iw-new-incident"],
)
def test_design_skill_constraints_mention_self_assess(skill_name: str) -> None:
    """Design skills Constraints section must mention the injection rule."""
    content = read_skill(skill_name)
    # The constraint about self_assess injection must be in the file
    assert "self_assess" in content


# ---------------------------------------------------------------------------
# Sync invariant: .claude/skills/ == skills/ byte-for-byte
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "skill_name",
    [
        "iw-item-analyze",
        "iw-new-feature",
        "iw-new-cr",
        "iw-new-incident",
        "iw-workflow",
    ],
)
def test_skills_sync_is_byte_identical(skill_name: str) -> None:
    """Master in skills/ and synced copy in .claude/skills/ must match."""
    master = SKILLS_DIR / skill_name / "SKILL.md"
    synced = CLAUDE_SKILLS_DIR / skill_name / "SKILL.md"
    assert master.read_bytes() == synced.read_bytes()


# ---------------------------------------------------------------------------
# ai-dev/templates sync invariant
# ---------------------------------------------------------------------------


def test_ai_dev_templates_self_assess_matches_master() -> None:
    """ai-dev/templates/SelfAssess_Prompt_Template.md must match master."""
    master = TEMPLATES_DIR / "SelfAssess_Prompt_Template.md"
    synced = AI_DEV_TEMPLATES_DIR / "SelfAssess_Prompt_Template.md"
    assert master.read_bytes() == synced.read_bytes()


# ---------------------------------------------------------------------------
# iw-item-analyze: Invariant 4 — never writes outside reports dir
# ---------------------------------------------------------------------------


def test_item_analyze_constraints_mention_no_outside_writes() -> None:
    """Invariant 4: skill body explicitly forbids writes outside ai-dev/work/<ID>/reports/."""
    content = read_skill("iw-item-analyze")
    # The constraint that enforces read-only (Invariant 4) must appear in the body
    assert "MUST NOT" in content
    assert "outside" in content or "reports" in content
    assert "ai-dev/work/" in content


def test_item_analyze_documents_two_file_output_contract() -> None:
    """AC6 / Invariant 4: skill documents the two-file output contract."""
    content = read_skill("iw-item-analyze")
    # Both output files must be mentioned in the skill body
    assert "_self_assess_report.md" in content
    assert "_self_assess_findings.json" in content


@pytest.mark.parametrize(
    "skill_name",
    ["iw-new-feature", "iw-new-cr", "iw-new-incident"],
)
def test_design_skill_injects_self_assess_conditional(skill_name: str) -> None:
    """AC2: design skills document the conditional self_assess step injection."""
    content = read_skill(skill_name)
    # Must mention the conditional nature: when the flag is on, inject the step
    assert "self-assess-impl" in content
    assert "projects.toml" in content or "self_assess" in content
