# CR-00040: CodeReview Templates — Anchor Reviewers to Design Doc Before Code Inspection

**Type**: Change Request
**Priority**: Medium
**Reason**: Self-assess finding from CR-00039 — first-run code review missed test-update obligations because the "Read the design document" instruction was buried inside the `## Context` paragraph, after lengthy Docker / Migration banners. The fix-cycle prompt explicitly anchored on the design doc and immediately caught the issue. We want the first-run review to do the same.
**Created**: 2026-05-09
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt. This CR does not touch any Docker-related code.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This CR does NOT add, modify, or remove any alembic migration. Only markdown prompt-template files are touched.)

## Description

Add a prominent, top-level **"Read the Design Document FIRST"** section to `templates/design/CodeReview_Prompt_Template.md` and `templates/design/CodeReview_Final_Prompt_Template.md`. The new section must instruct the reviewer to read the design doc (especially its TDD section) **before** running lint/format gates and **before** opening any changed files, and to verify implementation+tests both match the design doc's expectations as a first-class checklist item. Then propagate the updated master copies to every project's local mirror via `iw sync-templates`.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and the hard rule that template master copies under `templates/design/` must be re-synced via `iw sync-templates` after editing (see `feedback_templates_sync` memory).

## Current Behavior

Today, the CodeReview prompt template (`templates/design/CodeReview_Prompt_Template.md`, line 87) and the CodeReview_Final prompt template (`templates/design/CodeReview_Final_Prompt_Template.md`, line 90) each contain a single passing reference to "Read the design document" buried at the end of the `## Context` paragraph, after ~70 lines of Docker / Migration banners and Input Files boilerplate. There is no separate, named section for design-doc reading; no explicit instruction to extract the TDD section's expectations; and no checklist item that anchors test-coverage findings to design-doc obligations.

Observed cost (CR-00039 self-assess report, finding [1]): the first-run S02 review missed that the design doc's TDD section mandated updating `tests/dashboard/test_runtime_override_templates.py` alongside the CSS class rename. The fix-cycle prompt — which explicitly anchors on the design doc — caught the issue immediately, costing one wasted review round-trip.

## Desired Behavior

Both `CodeReview_Prompt_Template.md` and `CodeReview_Final_Prompt_Template.md` open with a clearly-named **"## Read the Design Document FIRST"** section placed BEFORE the `## Pre-Review Lint & Format Gate` section. This new section must:

1. Make it impossible to skim past — bold heading, short imperative bullets, no buried prose.
2. Instruct the reviewer to open the design doc and (a) read the **Acceptance Criteria** and **TDD Approach** sections in full, (b) note any test files the design explicitly mentions, and (c) carry those expectations into the review checklist.
3. Add an explicit checklist item under `### 5. Testing` (existing section): "Do test files cover the assertions the design doc's TDD section calls out by name?"
4. For the `CodeReview_Final` variant, mirror the same anchor and add: "Do all test references mentioned in the design doc's TDD section actually appear in the implementation reports' `files_changed`? Missing test updates are a CRITICAL finding."

After the master copies are updated, `iw sync-templates` propagates the change to every project listed in `projects.toml` (writes `ai-dev/templates/CodeReview_Prompt_Template.md` and `ai-dev/templates/CodeReview_Final_Prompt_Template.md` in each project root).

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `templates/design/CodeReview_Prompt_Template.md` | "Read the design document" buried in `## Context` (line 87) | New `## Read the Design Document FIRST` section before `## Pre-Review Lint & Format Gate`; new checklist item under `### 5. Testing` |
| `templates/design/CodeReview_Final_Prompt_Template.md` | "Read the design document" buried in `## Context` (line 90) | New `## Read the Design Document FIRST` section + augmented `### 1. Completeness vs Design Document` checklist with explicit test-file-mention rule |
| Per-project `ai-dev/templates/CodeReview_*_Prompt_Template.md` mirrors | Stale copies of the master | Re-synced via `iw sync-templates` |

### Breaking Changes

None. The change is additive to prompt instructions; it strictly improves review thoroughness and does not alter the result-contract JSON schema, the lint/format gate, or any agent slug.

### Data Migration

None. No DB schema changes. No data transformations.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | template-impl | Edit both `CodeReview_Prompt_Template.md` and `CodeReview_Final_Prompt_Template.md` master copies; run `iw sync-templates` to propagate; commit synced mirrors | — |
| S02 | code-review-impl | Per-step review of S01's template edits and sync output | — |
| S03 | code-review-final-impl | Final cross-step review: consistency between the two CodeReview templates and across all synced mirrors | — |
| S04 | qv-gate (lint) | `make lint` | — |
| S05 | qv-gate (format) | `make format-check` | — |
| S06 | qv-gate (typecheck) | `make type-check` | — |
| S07 | qv-gate (unit-tests) | `make test-unit` | — |
| S08 | self-assess-impl | Item self-assessment via `iw-item-analyze` skill | — |

No `qv-browser` step (browser_verification=false — markdown-only change with no UI surface). No `make test-integration` gate (no DB/orch paths touched, no models, no migrations). Lint/format/typecheck/unit-tests gates are kept for uniformity even though they will pass trivially on a markdown-only change.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — no migration is added, modified, or removed.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00040/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00040_CR_Design.md` | Design | This document |
| `CR-00040_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00040_S01_Template_prompt.md` | Prompt | S01 template-impl instructions |
| `prompts/CR-00040_S02_CodeReview_prompt.md` | Prompt | S02 per-step review instructions |
| `prompts/CR-00040_S03_CodeReviewFinal_prompt.md` | Prompt | S03 final cross-step review instructions |
| `prompts/CR-00040_S08_SelfAssess_prompt.md` | Prompt | S08 self-assessment instructions |

Reports are created during execution under `ai-dev/work/CR-00040/reports/`.

## Acceptance Criteria

### AC1: New "Read the Design Document FIRST" section present in CodeReview_Prompt_Template.md

```
Given the master template `templates/design/CodeReview_Prompt_Template.md` after S01
When I read the file from top to bottom
Then I find a section titled exactly `## Read the Design Document FIRST`
And the section appears BEFORE `## Pre-Review Lint & Format Gate`
And the section contains imperative bullets instructing the reviewer to read the design doc's Acceptance Criteria and TDD Approach sections before opening any code files
```

### AC2: New "Read the Design Document FIRST" section present in CodeReview_Final_Prompt_Template.md

```
Given the master template `templates/design/CodeReview_Final_Prompt_Template.md` after S01
When I read the file from top to bottom
Then I find a section titled exactly `## Read the Design Document FIRST`
And the section appears BEFORE `## Pre-Review Lint & Format Gate`
And the section instructs the reviewer to extract every test file mentioned in the design doc's TDD section and check those references appear in the implementation reports' `files_changed` arrays
```

### AC3: Existing review checklist augmented with design-doc anchor

```
Given `templates/design/CodeReview_Prompt_Template.md` after S01
When I read `### 5. Testing`
Then there is a bullet item phrased substantially as "Do test files cover the assertions the design doc's TDD section calls out by name?"

And given `templates/design/CodeReview_Final_Prompt_Template.md` after S01
When I read `### 1. Completeness vs Design Document`
Then there is a bullet item that flags missing test-file references from the design doc's TDD section as CRITICAL
```

### AC4: Per-project mirrors are in sync after `iw sync-templates`

```
Given S01 has run `iw sync-templates` to completion
When I diff every project's `ai-dev/templates/CodeReview_Prompt_Template.md` against `templates/design/CodeReview_Prompt_Template.md`
Then the diff is empty for every project listed in `projects.toml`
And the same is true for `CodeReview_Final_Prompt_Template.md`
```

### AC5: Banner sections preserved verbatim

```
Given both edited master templates after S01
When I diff their `## ⛔ Docker is off-limits` and `## ⛔ Migrations: agents generate, daemon applies` sections against the previous main-branch versions
Then the diff is empty
And no other existing section (Input Files, Output Files, Pre-Review Lint & Format Gate, Severity Levels, Review Result Contract) has been removed or had its semantics altered
```

## Rollback Plan

- **Database**: N/A — no migration in this CR.
- **Code**: Revert the merge commit. `templates/design/` and `ai-dev/templates/` master copies will return to their pre-CR state in a single revert. Re-running `iw sync-templates` after the revert restores per-project mirrors automatically.
- **Data**: No data loss possible — markdown content edits only.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `templates/design/CodeReview_Prompt_Template.md`
- `templates/design/CodeReview_Final_Prompt_Template.md`
- `ai-dev/templates/CodeReview_Prompt_Template.md`
- `ai-dev/templates/CodeReview_Final_Prompt_Template.md`
- `ai-dev/active/CR-00040/**`

## TDD Approach

- **Unit tests**: None — markdown prompt files are not exercised by the Python test suite. Test changes would be vacuous.
- **Integration tests**: None — `iw sync-templates` already has coverage in the existing test suite (smoke-tested by `tests/integration/test_templates_sync.py` if present, or by execution during S01). This CR does not change the sync behavior.
- **Updated tests**: None — no existing test asserts the contents of the CodeReview prompt templates.
- **Verification**: AC1–AC5 above are verified by reading the resulting files directly. AC4 is additionally verifiable via `git diff --no-index templates/design/CodeReview_Prompt_Template.md ai-dev/templates/CodeReview_Prompt_Template.md` (must be empty after sync). The S02/S03 code reviews are the human-loop check that the new instruction is actually clear and imperative — they exercise the very pattern this CR is improving.

## Notes

- **Why no test updates**: Markdown prompt templates are configuration content for downstream agents, not exercised by any Python unit/integration test. Adding a test that string-matches the new heading would be brittle (it would have to be updated every time the prompt copy is tweaked) and would not catch the underlying failure mode (a reviewer skimming past a buried instruction). The acceptance criteria above are the right-shaped check for this kind of change.
- **Self-referential risk**: The S02 reviewer of THIS CR is using the OLD CodeReview template (the new one only takes effect for items launched after this CR merges). That's expected and fine — S02's job here is to verify the edits are correct and the sync ran cleanly, which is well-defined regardless of the reviewer's own prompt.
- **Effort estimate**: S — roughly ~10–15 lines added to each of the two master templates, plus one `iw sync-templates` invocation. The bulk of the change is in this design doc, not the implementation.
- **Source**: `ai-dev/active/CR-00039/reports/CR-00039_self_assess_report.md`, finding [1] (severity MED, class prompt, frequency systemic).
