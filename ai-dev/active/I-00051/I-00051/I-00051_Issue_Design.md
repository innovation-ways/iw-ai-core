# I-00051: Code review steps do not run linters — ARG and format errors reach QV gates

**Type**: Issue
**Severity**: Medium
**Created**: 2026-04-29
**Reported By**: iw-item-analyze (post-execution analysis of F-00067, finding [4])
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No database changes required for this fix.

## Description

Code review steps (code-review-impl, code-review-final-impl) perform only textual inspection of changed files. They do not run `make lint` or `make format`, so lint violations (e.g., `ARG001` unused function arguments) and formatting drift (e.g., unformatted test files) pass silently through code review into QV gates, where each one burns a fix cycle. In F-00067, this produced 2 unnecessary fix cycles: S12 caught `ARG001` on `dashboard/routers/code_qa.py:67,70` and S13 caught an unformatted `tests/dashboard/test_docs_callouts.py` — neither was flagged by the 4 preceding code review steps.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. This fix is entirely in template files (`ai-dev/templates/` and `templates/design/`). No Python code changes. Per project convention, template edits must also be applied to the master copies under `templates/design/` and synced via `iw skills sync`.

## Steps to Reproduce

1. A feature adds Python files with an unused function argument (e.g., a fallback stub `def render_mermaid(dsl: str) -> str | None: return None`).
2. Code review steps (S04, S05, S08, S11) review the changed files textually. They check naming, logic, and architecture — but do not run `make lint`.
3. The ARG001 violation passes undetected through all code review steps.
4. QV gate S12 (`make lint`) catches it and fails. A fix cycle is triggered.

**Expected**: Code review steps run `make lint` and `make format` on changed files before beginning textual review. Any new violations are reported as CRITICAL findings in the review result.

**Actual**: Code review steps skip the linters. The "Test Verification" section of the template says "Run lint and type checking" in a single vague line that agents interpret as part of the test run, not as a mandatory pre-review gate.

## Root Cause Analysis

`ai-dev/templates/CodeReview_Prompt_Template.md` (line 132) contains:

```
## Test Verification (NON-NEGOTIABLE)
Before submitting your review:
1. Run the project's unit test command to verify no regressions
2. Run lint and type checking
3. Report test results accurately in the result contract
```

The "Run lint and type checking" instruction at line 132 is:
- Buried inside the "Test Verification" section (agents read it as part of running tests)
- Not actionable — no command given, no pass/fail criteria
- Not labelled NON-NEGOTIABLE on its own line
- Missing classification: no instruction to treat violations as CRITICAL findings

The same gap exists in `ai-dev/templates/CodeReview_Final_Prompt_Template.md` (line 139).

The master copies in `templates/design/CodeReview_Prompt_Template.md` and `templates/design/CodeReview_Final_Prompt_Template.md` have the same gap and must be updated in sync.

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Code review prompt template | `ai-dev/templates/CodeReview_Prompt_Template.md` | No lint/format gate in per-agent reviews |
| Code review final template | `ai-dev/templates/CodeReview_Final_Prompt_Template.md` | No lint/format gate in global review |
| Master template copies | `templates/design/CodeReview_Prompt_Template.md` | Master copy out of sync |
| Master template copies | `templates/design/CodeReview_Final_Prompt_Template.md` | Master copy out of sync |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Template | Add mandatory "Pre-Review Lint & Format Gate" section to both templates + master copies; run `iw skills sync` | — |
| S02 | CodeReview_Template | Review S01 | — |
| S03 | CodeReview_Final | Global review | — |
| S04 | QvGate lint | `make lint` | — |
| S05 | QvGate format | `make format` | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None

### Code Changes

- **Files to modify**:
  - `ai-dev/templates/CodeReview_Prompt_Template.md`
  - `ai-dev/templates/CodeReview_Final_Prompt_Template.md`
  - `templates/design/CodeReview_Prompt_Template.md`
  - `templates/design/CodeReview_Final_Prompt_Template.md`
- **Nature of change**: Add a new `## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)` section immediately before the existing `## Review Checklist` section. The section must:
  1. Instruct the agent to run `make lint` on all files listed in `files_changed`
  2. Instruct the agent to run `make format` on all Python/JS files in `files_changed` (runs `ruff format --check` — check-only, does NOT auto-fix)
  3. State that any new violations (i.e., not present in `main` before this step) must be reported as **CRITICAL** findings in the review result contract
  4. State that the agent must NOT proceed to textual review if lint/format cannot be run (raise a blocker instead)

**Exact section to add** (insert before `## Review Checklist`):

```markdown
## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run these two commands on the files listed in the
implementation report's `files_changed`. Fix nothing yourself — only report.

```bash
make lint          # ruff check — catches ARG001, F811, unused imports, etc.
make format  # ruff format --check — catches formatting drift (does NOT auto-fix)
```

If either command reports NEW violations in the changed files (i.e., violations
that do not appear on the `main` branch before this step), classify each one as
a **CRITICAL** finding in your review result contract with:
- `"category": "conventions"`
- `"file"` and `"line"` from the tool output
- `"description"` quoting the exact violation code and message

If a command is unavailable (e.g., `make` not found), STOP and raise a blocker.
Do NOT skip this step or mark it as optional.
```

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00051_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00051_S01_Template_prompt.md` | Prompt | Template edits |
| `prompts/I-00051_S02_CodeReview_Template_prompt.md` | Prompt | Review S01 |
| `prompts/I-00051_S03_CodeReview_Final_prompt.md` | Prompt | Global review |

Reports are created during execution in `ai-dev/active/I-00051/reports/`.

## Test to Reproduce

This is a pure template change — there is no executable test for the template content itself. The QV gates (`make lint` + `make format`) serve as the verification that the template edits do not introduce their own violations. The fix is verified functionally by the next feature/incident that uses code-review steps: lint and format errors will now appear as CRITICAL findings in the review report rather than in the QV gate.

For this reason, no Tests step is included. The regression prevention is the template change itself.

## Acceptance Criteria

### AC1: Lint gate is explicit in code review template

```
Given the updated CodeReview_Prompt_Template.md
When a code-review-impl agent uses it
Then the agent runs `make lint` before beginning textual review
 AND any ARG001 / F811 violations in changed files appear as CRITICAL findings
```

### AC2: Format gate is explicit in code review template

```
Given the updated CodeReview_Prompt_Template.md
When a code-review-impl agent uses it
Then the agent runs `make format` before beginning textual review (check-only, does NOT auto-fix)
 AND any format violations in changed files appear as CRITICAL findings
```

### AC3: Final review template updated consistently

```
Given the updated CodeReview_Final_Prompt_Template.md
When a code-review-final-impl agent uses it
Then the same Pre-Review Lint & Format Gate section is present and NON-NEGOTIABLE
```

### AC4: Master copies in sync

```
Given templates/design/CodeReview_Prompt_Template.md
 AND templates/design/CodeReview_Final_Prompt_Template.md
When compared to their ai-dev/templates/ counterparts
Then both master copies contain the new Pre-Review Lint & Format Gate section
```

## Regression Prevention

- The `Pre-Review Lint & Format Gate` section is placed before the review checklist and marked NON-NEGOTIABLE so agents cannot treat it as optional.
- Future template edits should be applied to both `ai-dev/templates/` and `templates/design/` in the same commit.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## TDD Approach

Not applicable — this is a template-only change. QV gates (`make lint` + `make format`) serve as the verification.

## Notes

- The `iw skills sync` command should be run after updating the templates to propagate the change to managed projects. The template-impl agent must run this as the final action of S01.
- The new section uses `make format` — the Makefile `format` target already runs `ruff format --check .` (check-only, does NOT auto-fix files).
- Do not add lint/format commands to the implementation prompt template — implementations already have a "Pre-flight Quality Gates (NON-NEGOTIABLE)" section that handles this. The gap is only in review templates.
