# CR-00016_S05_Tests_prompt

**Work Item**: CR-00016 — Agent prompt hardening
**Step**: S05
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/CR-00016/CR-00016_CR_Design.md` — Design (AC2, AC3, AC5)
- S01/S03 reports
- Enforcement set (input to the test):
  - All files matching `ai-dev/templates/*.md`
  - `.claude/skills/iw-workflow/SKILL.md`
  - `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`, `executor/CLAUDE.md`, `tests/CLAUDE.md`
  - `docs/IW_AI_Core_Agent_Constraints.md`

## Output Files

- `ai-dev/active/CR-00016/reports/CR-00016_S05_Tests_report.md`
- `tests/integration/test_agent_constraints_coverage.py` — new coverage test

## Context

Write a test that fails whenever the Docker rule is removed from any tracked file. This is the drift-catcher — it ensures future edits can't silently remove the rule from a subset of files.

Read `tests/CLAUDE.md` first for test conventions.

## Requirements

### 1. Test file structure

Create `tests/integration/test_agent_constraints_coverage.py`:

```python
"""Agent-constraints coverage — enforce that the Docker rule text is present
in every file where agents read instructions. See CR-00016."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
MARKER = "⛔ Docker is off-limits"

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
    assert MARKER in content, (
        f"{template.relative_to(PROJECT_ROOT)} is missing the Docker rule marker "
        f"({MARKER!r}). See docs/IW_AI_Core_Agent_Constraints.md for the required text."
    )


@pytest.mark.integration
@pytest.mark.parametrize("claude_md", CLAUDE_MD_FILES, ids=lambda p: str(p.relative_to(PROJECT_ROOT)))
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
def test_iw_workflow_skill_surfaces_rule() -> None:
    assert IW_WORKFLOW_SKILL.exists(), f"iw-workflow SKILL.md missing: {IW_WORKFLOW_SKILL}"
    content = IW_WORKFLOW_SKILL.read_text()
    assert "IW_AI_Core_Agent_Constraints" in content or "Docker is off-limits" in content


@pytest.mark.integration
def test_policy_doc_exists_and_includes_rule() -> None:
    assert POLICY_DOC.exists()
    content = POLICY_DOC.read_text()
    assert MARKER in content
    # The policy doc must reference the 2026-04-22 incident so the rationale
    # survives. Cross-referenced from docs/IW_AI_Core_DB_Setup.md.
    assert "2026-04-22" in content or "IW_AI_Core_DB_Setup" in content


@pytest.mark.integration
def test_number_of_templates_covered() -> None:
    # Guards against accidentally moving templates out of ai-dev/templates/,
    # which would silently shrink the enforcement set.
    assert len(PROMPT_TEMPLATES) >= 10, (
        f"Expected >=10 prompt templates, found {len(PROMPT_TEMPLATES)}. "
        "If you moved templates, update this test's enforcement set."
    )
```

### 2. Mutation test (manual verification, documented in report)

Before signing off, temporarily mutate ONE file (e.g. remove the marker from `ai-dev/templates/Implementation_Prompt_Template.md` by running `sed -i 's/⛔ Docker is off-limits/Docker section/' ai-dev/templates/Implementation_Prompt_Template.md` in a scratch copy, NOT the real file — or just run the test against a temp copy of the file with the marker removed). Confirm the test fails with a clear message naming the offending file. Restore the file. Document this in the S05 report as "Mutation test: FAILED as expected → {filename}".

**Safer alternative**: use `monkeypatch.setattr` with `Path.read_text` returning a string without the marker, and assert the test raises. This keeps the actual file untouched.

### 3. No side effects

- Test is pure: reads files, makes assertions.
- No docker calls, no DB calls, no subprocess.
- Runs fast (well under 1 second for the whole suite).

### 4. Parametrization gives clear failure output

Using `@pytest.mark.parametrize` with `ids=` means a failing test names the specific template or CLAUDE.md — no hunting. Preserve that.

### 5. Integration marker

All tests are `@pytest.mark.integration` so they run in `make test-integration` but can also be included under `make test-unit` if the Makefile's selector picks them up (this is filesystem-only, no docker — could arguably be a unit test). Pick per what the existing split does in this repo; if unit-tests-only mode is strictly "no filesystem I/O", keep `integration`.

### 6. Documentation

Include a top-of-file docstring pointing to CR-00016 so future readers understand the test's purpose.

## Project Conventions

- pytest parametrize style consistent with `tests/integration/`.
- `PROJECT_ROOT` resolved from `__file__`.
- No hardcoded paths outside of `PROJECT_ROOT`.

## TDD Verification

Tests must fail against pre-CR-00016 state. You've already seen that S01 + S03 landed the marker in the enforcement set, so the tests pass now. The mutation test proves they also fail correctly when the marker is missing. Document both in the report.

## Test Verification (NON-NEGOTIABLE)

1. `make test-integration` — all new tests pass.
2. `make lint` — pass.
3. Mutation test documented (marker removal triggers correct failure).

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "tests-impl",
  "work_item": "CR-00016",
  "completion_status": "complete",
  "files_changed": ["tests/integration/test_agent_constraints_coverage.py"],
  "tests_passed": true,
  "test_summary": "N passed, 0 failed; mutation test: FAILED as expected when marker removed from {filename}",
  "blockers": [],
  "notes": ""
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00016 --step S05
# write test ...
uv run iw step-done CR-00016 --step S05 --report ai-dev/active/CR-00016/reports/CR-00016_S05_Tests_report.md
```
