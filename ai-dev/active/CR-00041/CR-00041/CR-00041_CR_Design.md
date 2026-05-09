# CR-00041: Implementation prompt — test-update checklist for renamed CSS classes

**Type**: Change Request
**Priority**: Low
**Reason**: Process improvement surfaced by CR-00039's self-assessment (finding [3]). Implementation steps that rename CSS classes have been shipping correct templates while leaving stale class names in tests, costing one extra code-review fix-cycle per occurrence. A short checklist line in the Implementation prompt template closes the gap.
**Created**: 2026-05-09
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This item adds no migrations and modifies no existing migrations.)

## Description

Add a one-line checklist item to `Implementation_Prompt_Template.md` instructing the agent to confirm that any test file asserting old CSS class names has been updated to reflect the new class names from the design doc TDD section. The change is applied to both copies (master under `templates/design/`, synced copy under `ai-dev/templates/`) and is enforced by a new assertion in `tests/unit/test_template_hints.py`.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Note in particular the existing template parity rules in `tests/unit/test_template_hints.py` (CR-00023): the two copies of `Implementation_Prompt_Template.md` must stay in lockstep for sections covered by parity tests.

## Current Behavior

`Implementation_Prompt_Template.md` (both copies) instructs implementation agents (Frontend, Backend, API, Database, Pipeline, Template) to follow TDD and run targeted tests after their changes (`## TDD Requirement` and `## Test Verification (NON-NEGOTIABLE)` sections). Neither section explicitly tells the agent to grep for old CSS class names that the implementation just renamed and update test assertions accordingly.

Result observed in CR-00039:
- S01 correctly renamed `iw-step-strip` → `iw-pipeline-strip` and `iw-step-seg` → `iw-pipeline-pill` in templates and CSS.
- The test file `tests/dashboard/test_runtime_override_templates.py` (line 278–284) was left asserting the old class names.
- S02 (code-review) caught the drift on the second pass after a fix-cycle prompt explicitly named the design doc's TDD section as authoritative — wasting one fix-cycle slot.

## Desired Behavior

The Implementation prompt template (both copies) carries a short, explicit checklist item that the agent must satisfy before reporting `tests_passed: true`:

> When the design renames or changes any CSS class name, grep the test suite for the old class name and update every assertion to match the new name. Stale CSS-class assertions in tests are a code-review failure mode (see CR-00039 self-assess finding [3]).

The line lives inside the existing `## Test Verification (NON-NEGOTIABLE)` section so the agent reads it in the same pass it considers test correctness. Both copies are kept byte-identical for the new line. A unit test asserts that both copies contain the new line.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `templates/design/Implementation_Prompt_Template.md` | Test Verification section silent on renamed identifiers | Adds CSS-class-rename checklist item to Test Verification section |
| `ai-dev/templates/Implementation_Prompt_Template.md` | Same as master | Same edit applied byte-identically |
| `tests/unit/test_template_hints.py` | Asserts existing parity + Pre-flight headings | Adds assertion that the new CSS-class-rename line appears in both copies |

### Breaking Changes

- None. Additive prompt-template line.

### Data Migration

- None. No DB schema or data changes.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | template-impl | Add checklist line to both `Implementation_Prompt_Template.md` copies; add new assertion to `tests/unit/test_template_hints.py` | — |
| S02 | code-review-impl | Per-agent review of S01 (wording, parity, test correctness) | — |
| S03 | code-review-final-impl | Cross-agent final review: AC trace, no scope creep | — |
| S04 | qv-gate | `make lint` | — |
| S05 | qv-gate | `make format-check` | — |
| S06 | qv-gate | `make type-check` | — |
| S07 | qv-gate | `make test-unit` | — |
| S08 | self-assess-impl | Self-assessment via iw-item-analyze | — |

Agent slug for S01 is `template-impl` (the file under change is a prompt template, not application code; `template-impl` is the canonical agent for non-code template assets per the iw-workflow agent table).

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — this CR does not touch `orch/db/migrations/versions/**`.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00041_CR_Design.md` | Design | This document |
| `CR-00041_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves) |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00041_S01_Template_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00041_S02_CodeReview_prompt.md` | Prompt | S02 per-agent review |
| `prompts/CR-00041_S03_CodeReviewFinal_prompt.md` | Prompt | S03 final cross-agent review |
| `prompts/CR-00041_S08_SelfAssess_prompt.md` | Prompt | S08 self-assessment |

## Acceptance Criteria

### AC1: Both Implementation_Prompt_Template.md copies contain the CSS-class-rename checklist line

```
Given the repository contains two parity-tested copies of Implementation_Prompt_Template.md
  (one at templates/design/, one at ai-dev/templates/)
When the CR-00041 changes are applied
Then both files contain a checklist line inside the "Test Verification (NON-NEGOTIABLE)"
  section that names CSS-class renames as a required test-update trigger
And the wording references the design doc TDD section as authoritative
And the line cites CR-00039 finding [3] as the rationale
```

### AC2: Parity test enforces presence of the new line in both copies

```
Given tests/unit/test_template_hints.py asserts template parity
When the test is extended with a new assertion under CR-00041
Then running `uv run pytest tests/unit/test_template_hints.py -v` passes with the new
  assertion green for both Implementation_Prompt_Template.md copies
And removing the new line from either copy causes the new assertion to fail
```

### AC3: New checklist line lives inside the existing Test Verification section, not a new section

```
Given the prompt template's existing structure
When the new line is added
Then it appears within the "## Test Verification (NON-NEGOTIABLE)" section
And no new top-level "##" heading is introduced
And the existing Pre-flight section (CR-00023) is left byte-identical between copies
  (the existing parity test for Pre-flight continues to pass)
```

## Rollback Plan

- **Database**: Not applicable — no DB changes.
- **Code**: Revert the merge commit. The prompt-template change has no runtime side effects; reverting only undoes the prompt guidance and the corresponding assertion. Already-running agents in flight are unaffected (the prompt is read at step launch).
- **Data**: No data loss on rollback.

## Dependencies

- **Depends on**: None (CR-00023 already shipped the parity-test scaffold this CR extends).
- **Blocks**: None.

## Impacted Paths

- `templates/design/Implementation_Prompt_Template.md`
- `ai-dev/templates/Implementation_Prompt_Template.md`
- `tests/unit/test_template_hints.py`

## TDD Approach

- **Unit tests**: Extend `tests/unit/test_template_hints.py` with a parametrized assertion (over `IMPLEMENTATION_TEMPLATES`) that the new checklist line is present in both copies. Use a stable marker substring (e.g. `"CSS class name"` and `"CR-00039"` together) so the assertion is robust to minor wording tweaks but breaks if the line is removed.
- **Integration tests**: None — this is a prompt-template + unit-test change.
- **Updated tests**: None — existing tests in `test_template_hints.py` continue to pass unchanged (Pre-flight parity, iw item-status hint, etc.).

## Notes

- The `Implementation_Prompt_Template.md` file under `ai-dev/templates/` is the synced copy; downstream projects pull the master from `templates/design/` via `iw sync-templates`. Editing both in this CR is required to keep the iw-ai-core project itself current and to satisfy the existing parity test.
- This CR deliberately scopes the rule to **CSS class names** (not "all renamed identifiers") so the wording stays close to the analyzed CR-00039 incident. Broader generalization (renamed routes, function names) is a candidate for a follow-up CR if data shows recurrence in non-CSS renames.
- The checklist line is intentionally short (one to two sentences). Longer prompts dilute every other line in the template; the goal is a sharp trigger the agent hits while reading Test Verification.
