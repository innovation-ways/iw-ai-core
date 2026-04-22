# CR-00016 S05 — Tests Report

## What was done

Created `tests/integration/test_agent_constraints_coverage.py` — a drift-catcher that fails if the Docker rule is ever silently removed from any tracked agent-instruction file.

## Enforcement set covered

| File group | Test |
|---|---|
| 11 prompt templates (`ai-dev/templates/*.md`) | `test_prompt_template_contains_docker_rule` (parametrized) |
| 5 CLAUDE.md files | `test_claude_md_references_policy` (parametrized) |
| `skills/iw-workflow/SKILL.md` | `test_iw_workflow_skill_surfaces_rule` |
| `docs/IW_AI_Core_Agent_Constraints.md` | `test_policy_doc_exists_and_includes_rule` |
| Template count guard | `test_number_of_templates_covered` |

## Test results

```
19 passed, 0 failed in 0.03s
```

## Mutation test (monkeypatch verification)

Simulated marker removal from `Implementation_Prompt_Template.md` via `monkeypatch.setattr(Path, "read_text", ...)` — test correctly failed with:

```
AssertionError: Implementation_Prompt_Template.md is missing the Docker rule marker ('⛔ Docker is off-limits').
See docs/IW_AI_Core_Agent_Constraints.md for the required text.
```

No actual files were mutated.

## Lint

All ruff checks pass after auto-format.

## Notes

- `@pytest.mark.integration` used (filesystem-only I/O, no DB) — consistent with how other integration tests in this repo handle non-DB I/O.
- Warnings about `pytest.mark.integration` being unknown are pre-existing for the whole file and not introduced by this test (verified by running the full suite).
- No docker, no DB, no subprocess calls — test is pure and runs in ~30ms.