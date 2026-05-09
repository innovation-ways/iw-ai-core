# CR-00039: Step Pipeline — Labeled Pill Redesign with Fix-Cycle Expansion

**Type**: Change Request
**Priority**: Medium
**Reason**: UX — current 6×14 px squares are unreadable; broken duration row; fix-cycle reruns invisible
**Created**: 2026-05-09
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This item does NOT add or modify any database migration. Schema is unchanged.

---

## Description

The Step Pipeline section on the item-detail overview renders each workflow step as a 6×14 px coloured square — too small to show any label. A separate duration row below uses mismatched column widths so all timing strings collide into unreadable concatenations (e.g. `684m12s684m12s…`). Fix-cycle reruns are invisible because the macro iterates one entry per `WorkflowStep` regardless of `run_count`. This CR replaces the entire visual component with a horizontal row of fixed-width labeled pills, expands fix-cycle reruns as separate amber `↺SXX` pills, and integrates duration labels inside each pill, eliminating the broken separate row.

## Project Context

Read `CLAUDE.md` (root) and `dashboard/CLAUDE.md` for architecture, Tailwind build rules, htmx patterns, and hard constraints. Plain CSS must be appended directly to `dashboard/static/styles.css` because `make css` may report "Nothing to be done" in worktrees (see I-00067 note in CLAUDE.md).

---

## Current Behavior

`dashboard/templates/components/step_pipeline.html` renders a `<div class="iw-step-strip">` containing one `<div class="iw-step-seg">` (6 px × 14 px) per `WorkflowStep`. No step label is visible at that size. A tooltip on hover shows step ID + agent + status + duration.

`dashboard/templates/fragments/item_overview.html` (lines 10–36) includes the macro followed by a "Duration row" — a separate `<div class="flex …">` that iterates `steps` and puts each duration in a `w-8` (32 px) div with `w-4` (16 px) gap dividers. Because the segments are 6 px + 1 px gap and the duration columns are 32 px + 16 px, the two rows are geometrically misaligned and all duration strings smash together.

Fix-cycle reruns are invisible: a step with `run_count=3` and `fix_cycle_count=2` still shows as one square because the macro does not expand.

CSS (`dashboard/static/styles.css` lines 352–358):
```
.iw-step-strip { display: flex; gap: 1px; align-items: center; }
.iw-step-seg   { width: 6px; height: 14px; border-radius: 1px; flex-shrink: 0; }
```

---

## Desired Behavior

The Step Pipeline section shows a horizontal strip of fixed-width labeled pills:

- Each pill is **52 px wide × 42 px tall**, `border-radius: 4px`.
- The pill displays the **step ID** (`S01`, `S02`, `MERGE`, …) in monospace bold (10 px) on the first line and the **duration** (e.g., `11m26s`) in monospace (9 px) on the second line. If duration is unknown the second line is omitted.
- Pills are separated by a thin 12 px horizontal connector line (`border-color`).
- **Fix-cycle reruns**: for a step with `fix_cycle_count = N`, the macro renders the main pill first, then N additional pills labelled `↺S01` in amber/warning colour with a dashed connector before each. This expands directly from the existing `step.fix_cycle_count` field — no backend changes.
- Colour mapping:
  - `completed` (original run): `var(--success)` background, white text
  - `in_progress`: `var(--primary)` background, white text, pulse animation
  - `failed`: `var(--destructive)` background, white text
  - `skipped`: `var(--muted)` background, muted foreground text
  - `pending`: `var(--secondary)` background, secondary foreground text
  - fix-cycle rerun pill: `var(--warning)` background, warning-foreground text
- The broken separate duration row in `item_overview.html` is **removed entirely**.
- Tooltip on hover: `{step_id} {agent_label}: {status} {duration}` (same as today).
- The strip is `overflow-x: auto` so it scrolls horizontally on narrow viewports.
- The existing `data-step-count` attribute is preserved on the outer container for automated tests.

---

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `step_pipeline.html` macro | 6×14 px squares, no label, no fix-cycle expansion | 52×42 px pills, step ID + duration inline, fix cycles expanded as ↺SXX amber pills |
| `item_overview.html` (lines 14–35) | Macro + broken separate duration row | Macro only (duration integrated into pill) |
| `styles.css` | `.iw-step-strip` / `.iw-step-seg` classes (6px width) | New `.iw-pipeline-strip`, `.iw-pipeline-pill`, `.iw-pipeline-connector` classes; old classes can remain for backward compat or be removed |

### Breaking Changes

None — purely presentational. No API, no schema, no Python changes.

### Data Migration

None.

---

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `frontend-impl` | Redesign `step_pipeline.html`, update `item_overview.html`, add CSS | — |
| S02 | `code-review-impl` | Review S01 | — |
| S03 | `code-review-final-impl` | Final cross-agent review | — |
| S04 | `qv-gate` (lint) | `make lint` | — |
| S05 | `qv-gate` (format) | `make format-check` | — |
| S06 | `qv-gate` (typecheck) | `make type-check` | — |
| S07 | `qv-gate` (unit-tests) | `make test-unit` | — |
| S08 | `qv-browser` | Browser verification | — |
| S09 | `self-assess-impl` | Post-execution self-assessment | — |

### Database Changes

None.

### API Changes

None.

### Frontend Changes

- **Modified components**: `step_pipeline.html` macro, `item_overview.html` (remove duration row), `dashboard/static/styles.css` (new pipeline pill classes)
- **New components**: None
- **Removed components**: The standalone duration row div in `item_overview.html`

---

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00039_CR_Design.md` | Design | This document |
| `CR-00039_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00039_S01_Frontend_prompt.md` | Prompt | S01: frontend implementation |
| `prompts/CR-00039_S02_CodeReview_prompt.md` | Prompt | S02: code review of S01 |
| `prompts/CR-00039_S03_CodeReviewFinal_prompt.md` | Prompt | S03: final cross-agent review |
| `prompts/CR-00039_S08_BrowserVerification_prompt.md` | Prompt | S08: browser verification |
| `prompts/CR-00039_S09_SelfAssess_prompt.md` | Prompt | S09: self-assessment |

---

## Acceptance Criteria

### AC1: Step IDs are visible in the pipeline strip

```
Given an item detail page with at least one completed workflow step
When I view the Step Pipeline section
Then each step shows its step ID (e.g. "S01", "S02") as readable text inside its pill
  and the pill is at least 28 px tall and at least 44 px wide
```

### AC2: Duration is shown inline — no separate broken row

```
Given a completed step with a known duration
When I view the Step Pipeline section
Then the duration (e.g. "11m26s") appears inside or directly below that step's pill
  and there is no separate duration row that can misalign with the pills
```

### AC3: Fix-cycle reruns are expanded as separate amber pills

```
Given a step whose fix_cycle_count is 2 (e.g. S03 ran 3 times total)
When I view the Step Pipeline section
Then S03 appears once as its normal completed/failed pill
  followed by 2 amber pills labelled "↺S03"
  so that all 3 runs are visually distinct and countable
```

### AC4: Original CSS test attribute is preserved

```
Given the pipeline strip outer container
When the page renders
Then the container has a data-step-count attribute equal to the number of WorkflowStep entries
  (existing tests that assert data-step-count must still pass)
```

### AC5: No regressions in the step detail table below

```
Given an item detail page
When I view the Step Pipeline section and the step table below it
Then the table still renders all steps with correct status badges, durations, run counts, and action buttons
```

---

## Rollback Plan

- **Database**: N/A — no schema changes
- **Code**: Revert the commit that changes `step_pipeline.html`, `item_overview.html`, and `styles.css`
- **Data**: No data loss on rollback

---

## Dependencies

- **Depends on**: None
- **Blocks**: None

---

## Impacted Paths

- `dashboard/templates/components/step_pipeline.html`
- `dashboard/templates/fragments/item_overview.html`
- `dashboard/static/styles.css`

---

## TDD Approach

- **Unit tests**: None — pure Jinja2 template; no Python logic added
- **Integration tests**: Existing dashboard tests that assert `data-step-count` must still pass after the rename of the outer container class; update any selector-based assertions if needed
- **Updated tests**: `tests/dashboard/` — check for any test that asserts on `.iw-step-strip` or `.iw-step-seg` selectors and update to match new class names

---

## Notes

- `step.fix_cycle_count` and `step.run_count` are already populated in `StepDetail` (see `dashboard/routers/items.py:_get_steps`). No backend change is needed to drive the expansion.
- The Jinja2 `range()` filter supports `{% for i in range(step.fix_cycle_count) %}` to emit N fix-cycle pills per step.
- `make css` may report "Nothing to be done" in worktrees (see I-00067). Append new CSS rules directly to `dashboard/static/styles.css` as plain CSS — they are served as-is.
- Old `.iw-step-strip` / `.iw-step-seg` CSS classes can remain in `styles.css` (they become dead code) or be removed. Removing is cleaner but must be verified against any remaining usages.
