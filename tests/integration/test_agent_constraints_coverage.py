"""Agent-constraints coverage — enforce that Docker rule text is present
in every file where agents read instructions. See CR-00016."""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
MARKER_R1 = "⛔ Docker is off-limits"
MARKER_R2 = "⛔ Migrations: agents generate, daemon applies"

PROMPT_TEMPLATES = sorted((PROJECT_ROOT / "ai-dev" / "templates").glob("*.md"))

CLAUDE_MD_FILES = [
    PROJECT_ROOT / "CLAUDE.md",
    PROJECT_ROOT / "orch" / "CLAUDE.md",
    PROJECT_ROOT / "dashboard" / "CLAUDE.md",
    PROJECT_ROOT / "executor" / "CLAUDE.md",
    PROJECT_ROOT / "tests" / "CLAUDE.md",
]

IW_WORKFLOW_SKILL = PROJECT_ROOT / ".claude" / "skills" / "iw-workflow" / "SKILL.md"
POLICY_DOC = PROJECT_ROOT / "docs" / "IW_AI_Core_Agent_Constraints.md"


@pytest.mark.integration
@pytest.mark.parametrize("template", PROMPT_TEMPLATES, ids=lambda p: p.name)
def test_prompt_template_contains_docker_rule(template: Path) -> None:
    assert template.exists(), f"Template missing: {template}"
    content = template.read_text()
    assert MARKER_R1 in content, (
        f"{template.relative_to(PROJECT_ROOT)} is missing the Docker rule marker "
        f"({MARKER_R1!r}). See docs/IW_AI_Core_Agent_Constraints.md for the required text."
    )


@pytest.mark.integration
@pytest.mark.parametrize("template", PROMPT_TEMPLATES, ids=lambda p: p.name)
def test_prompt_template_contains_migrations_rule(template: Path) -> None:
    assert template.exists(), f"Template missing: {template}"
    content = template.read_text()
    assert MARKER_R2 in content, (
        f"{template.relative_to(PROJECT_ROOT)} is missing the Migrations rule marker "
        f"({MARKER_R2!r}). See docs/IW_AI_Core_Agent_Constraints.md for the required text."
    )


@pytest.mark.integration
@pytest.mark.parametrize(
    "claude_md", CLAUDE_MD_FILES, ids=lambda p: str(p.relative_to(PROJECT_ROOT))
)
def test_claude_md_references_policy(claude_md: Path) -> None:
    assert claude_md.exists(), f"CLAUDE.md missing: {claude_md}"
    content = claude_md.read_text()
    assert "docker" in content.lower(), (
        f"{claude_md.relative_to(PROJECT_ROOT)} does not mention docker in any rule."
    )
    assert "IW_AI_Core_Agent_Constraints" in content, (
        f"{claude_md.relative_to(PROJECT_ROOT)} does not link to the policy doc."
    )


@pytest.mark.integration
def test_claude_md_references_migrations_policy() -> None:
    for claude_md in CLAUDE_MD_FILES:
        assert claude_md.exists(), f"CLAUDE.md missing: {claude_md}"
        content = claude_md.read_text()
        assert "alembic" in content.lower(), (
            f"{claude_md.relative_to(PROJECT_ROOT)} does not mention alembic."
        )
        assert "IW_AI_Core_Agent_Constraints" in content, (
            f"{claude_md.relative_to(PROJECT_ROOT)} does not link to the policy doc."
        )


@pytest.mark.integration
def test_iw_workflow_skill_surfaces_rule() -> None:
    assert IW_WORKFLOW_SKILL.exists(), f"iw-workflow SKILL.md missing: {IW_WORKFLOW_SKILL}"
    content = IW_WORKFLOW_SKILL.read_text()
    assert "IW_AI_Core_Agent_Constraints" in content or "Docker is off-limits" in content


@pytest.mark.integration
def test_policy_doc_exists_and_includes_rule() -> None:
    assert POLICY_DOC.exists()
    content = POLICY_DOC.read_text()
    assert MARKER_R1 in content
    assert MARKER_R2 in content
    assert "2026-04-22" in content or "IW_AI_Core_DB_Setup" in content


@pytest.mark.integration
def test_number_of_templates_covered() -> None:
    assert len(PROMPT_TEMPLATES) >= 10, (
        f"Expected >=10 prompt templates, found {len(PROMPT_TEMPLATES)}. "
        "If you moved templates, update this test's enforcement set."
    )
