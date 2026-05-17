# CR-00056: Surface step prompts in dashboard (Prompt column + modal viewer)

**Type**: Change Request
**Priority**: Medium
**Reason**: Operator observability — currently no way to see what prompt was sent to the AI agent without SSHing into the (possibly reaped) worktree.
**Created**: 2026-05-16
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This CR adds **one** Alembic migration: two nullable TEXT columns on `step_runs` (`prompt_text`, `fix_prompt_text`). Agents author the revision file; the daemon applies it during the merge pipeline (pre-merge dry-run + post-merge live apply). No data backfill — historical rows remain NULL and render as "—" in the UI.

## Description

The item-detail step table at `dashboard/templates/fragments/item_steps_table.html` shows agent, CLI, model, status, runs, etc., but **no visibility into the prompt that was actually sent to the LLM agent**. Today, retrieving a prompt requires SSHing into the worktree and reading `ai-dev/active/{ID}/prompts/*.md` — and worktrees are reaped after merge, so the file disappears for historical items.

This CR adds a **Prompt** column (between Model and Status) with a per-row "View" button. Clicking it opens an accessible modal — modeled on `dashboard/templates/fragments/activity_text_modal.html` — that shows the full prompt text, scrollable, with copy-to-clipboard. To keep prompts viewable after worktree reap, the daemon **snapshots the prompt content to the DB at step launch time** (new `StepRun.prompt_text` and `StepRun.fix_prompt_text` columns).

## Project Context

Read the project's [`CLAUDE.md`](../../CLAUDE.md), [`dashboard/CLAUDE.md`](../../dashboard/CLAUDE.md), and [`orch/CLAUDE.md`](../../orch/CLAUDE.md) for architecture, conventions, and hard rules. Key constraints for this CR:

- htmx + Jinja2 (no Alpine, no React). Fragment templates must NOT extend `base.html`.
- Clipboard buttons MUST use `window.iwClipboard.copy(text, button)` from `dashboard/static/clipboard.js`. Never call `navigator.clipboard.writeText` directly.
- Jinja `format` filter must use `%`-style (`"%s"|format(x)`), never `{}`-style.
- `StepRun` is append-only — each retry creates a new row. The new columns are written *at row creation*, never updated.

## Current Behavior

The item-detail page lists steps in a table fragment (`dashboard/templates/fragments/item_steps_table.html`). For each `WorkflowStep` the table renders:

```
Step | Agent | CLI | Model | Status | Started | Duration | Runs | Error | Actions
```

There is no Prompt column. The `WorkflowStep.prompt_file` field holds a relative path to the prompt file in the worktree (e.g. `ai-dev/active/F-00085/prompts/F-00085_S06_Backend_prompt.md`), but:

1. The path is **not surfaced** in the UI at all.
2. After the work item is merged and the worktree is reaped (`orch.daemon.worktree_reaper`), the file at that path no longer exists on disk.
3. Fix-cycle prompts live at `FixCycle.fix_prompt` (also a path) — same disappearance problem.

Operators currently have to:
1. Find the worktree path (if still alive).
2. SSH/cd into it.
3. Read the prompt file manually.

For historical items, the only fallback is `git log` against the merged commit — slow, indirect, and easy to get wrong.

## Desired Behavior

After this CR:

1. **At step launch**, the daemon snapshots the prompt file's contents into `StepRun.prompt_text` (or, for fix-cycle retries, `StepRun.fix_prompt_text`). Both columns are TEXT, nullable.
2. **In the item-detail steps table**, a new **Prompt** column appears between Model and Status. Each non-synthetic step row renders:
   - A small **"View"** button when at least one of `prompt_text` / `fix_prompt_text` is non-NULL for any of the step's runs.
   - A dash `—` for synthetic steps (S00 / MERGE) or steps with no runs yet, or for historical rows pre-CR.
3. **Clicking View** triggers an htmx GET to `/project/{project_id}/item/{item_id}/step/{step_id}/prompt-modal`. The route returns an HTML fragment (a modal dialog) that:
   - Has a header showing step number, agent label, and the prompt file path (if known).
   - Has a **scrollable `<pre>` body** with the snapshotted prompt text.
   - If any fix-cycle prompts exist for the step, shows them in additional stacked sections labelled `Fix Prompt (cycle N)` — chronologically after the initial prompt.
   - Has a **"Copy"** button (using `window.iwClipboard.copy(...)`) that copies the visible section's text to clipboard, with "Copied!" feedback.
   - Dismisses on backdrop click, Escape, or close-button click — same accessibility plumbing as `activity_text_modal.html` (focus trap, `aria-modal`, `aria-labelledby`, restores prior focus on close).
4. **No worktree dependency** at view time — the prompt comes from `step_runs.prompt_text` / `step_runs.fix_prompt_text`, which is durable.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `orch/db/models.py` (`StepRun`) | No prompt columns | + `prompt_text TEXT NULL`, `fix_prompt_text TEXT NULL` |
| `orch/db/migrations/versions/` | — | New alembic revision adding the two columns |
| `orch/daemon/batch_manager.py` | Writes prompt file then creates StepRun | Same, but also passes prompt **string** into `StepRun(..., prompt_text=...)` |
| `orch/daemon/fix_cycle.py` | Writes fix prompt file then creates StepRun for retry | Same, but also passes fix prompt **string** into `StepRun(..., fix_prompt_text=...)` |
| `dashboard/routers/items.py` | No prompt-modal route; `_get_steps()` doesn't pass prompt availability | + new `GET /item/{item_id}/step/{step_id}/prompt-modal` route; + `StepDetail.has_prompt: bool` |
| `dashboard/templates/fragments/item_steps_table.html` | 10-column table, no Prompt | 11-column table with new Prompt cell + htmx trigger |
| `dashboard/templates/fragments/` | — | + new `prompt_text_modal.html` (the fragment returned by the new route) |
| `dashboard/static/styles.css` | Has `.activity-modal-*` rules | + parallel `.prompt-modal-*` rules (or reuse existing if visually identical) |
| `dashboard/static/` | Has activity-modal JS inlined in template | + small JS to open the modal returned by htmx, manage focus trap, Escape, backdrop dismiss |

### Breaking Changes

None. Two new nullable TEXT columns; no existing columns altered; no API contract changes; no template removed.

### Data Migration

- Schema-only migration: `ALTER TABLE step_runs ADD COLUMN prompt_text TEXT NULL`, same for `fix_prompt_text`.
- **No backfill**. Historical rows have NULL → UI shows `—`. Acceptable per intake.
- **Reversible**: downgrade drops both columns (no data loss for the orchestration core — these are observability fields, not load-bearing).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Add `prompt_text` + `fix_prompt_text` to `StepRun`; alembic revision | — |
| S02 | code-review-impl | Review S01 (schema, ORM, migration roundtrip) | — |
| S03 | qv-gate `migration-check` | `make migration-check` | — |
| S04 | backend-impl | Wire daemon launch sites to snapshot prompt strings into the new columns | After S03 |
| S05 | code-review-impl | Review S04 | — |
| S06 | api-impl | New `GET /project/{pid}/item/{iid}/step/{step_id}/prompt-modal` route in `dashboard/routers/items.py`; extend `StepDetail` with `has_prompt` | — |
| S07 | code-review-impl | Review S06 | — |
| S08 | frontend-impl | Add Prompt column to `item_steps_table.html`; create `prompt_text_modal.html` fragment; CSS + JS | — |
| S09 | code-review-impl | Review S08 | — |
| S10 | code-review-final-impl | Cross-agent review of S01..S09 | — |
| S11 | tests-impl | Unit + integration + dashboard tests (see TDD Approach) | — |
| S12 | code-review-impl | Review S11 | — |
| S13 | code-review-final-impl | Final cross-agent review including tests | — |
| S14..S21 | qv-gate | lint, assertions, format, typecheck, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S22 | qv-browser | Browser E2E: open modal, Escape, backdrop, copy-to-clipboard, fix-cycle stacking, empty-state | — |
| S23 | self-assess-impl | Required (project `self_assess = true`) | — |

### Database Changes

- **New tables**: None
- **Modified tables**: `step_runs` — add `prompt_text TEXT NULL`, `fix_prompt_text TEXT NULL`
- **Migration notes**: standard `op.add_column` + `op.drop_column` pair. No indexes (these columns are display-only, never filtered or joined).

### API Changes

- **New endpoints**:
  - `GET /project/{project_id}/item/{item_id}/step/{step_id}/prompt-modal` → returns HTML fragment (the modal). 404 if the step is not found in the item, the item is not in the project, or there are no runs with any prompt text.
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**:
  - `dashboard/templates/fragments/prompt_text_modal.html` — the modal fragment returned by the new route.
  - JS handler in the fragment (or as a small standalone in `dashboard/static/`) for focus trap, Escape, backdrop close, copy button.
- **Modified components**:
  - `dashboard/templates/fragments/item_steps_table.html` — add `<th>Prompt</th>` between Model and Status; add `<td>` with View button (htmx-driven).
- **Removed components**: None

## File Manifest

All files for this CR live under `ai-dev/active/CR-00056/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00056_CR_Design.md` | Design | This document |
| `CR-00056_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/CR-00056_S01_Database_prompt.md` | Prompt | S01 |
| `prompts/CR-00056_S02_CodeReview_Database_prompt.md` | Prompt | S02 |
| `prompts/CR-00056_S04_Backend_prompt.md` | Prompt | S04 |
| `prompts/CR-00056_S05_CodeReview_Backend_prompt.md` | Prompt | S05 |
| `prompts/CR-00056_S06_API_prompt.md` | Prompt | S06 |
| `prompts/CR-00056_S07_CodeReview_API_prompt.md` | Prompt | S07 |
| `prompts/CR-00056_S08_Frontend_prompt.md` | Prompt | S08 |
| `prompts/CR-00056_S09_CodeReview_Frontend_prompt.md` | Prompt | S09 |
| `prompts/CR-00056_S10_CodeReview_Final_prompt.md` | Prompt | S10 |
| `prompts/CR-00056_S11_Tests_prompt.md` | Prompt | S11 |
| `prompts/CR-00056_S12_CodeReview_Tests_prompt.md` | Prompt | S12 |
| `prompts/CR-00056_S13_CodeReview_Final_prompt.md` | Prompt | S13 |
| `prompts/CR-00056_S22_BrowserVerification_prompt.md` | Prompt | S22 |
| `prompts/CR-00056_S23_SelfAssess_prompt.md` | Prompt | S23 |
| `evidences/pre/CR-00056_before_no_prompt_column.png` | Evidence | Pre-state screenshot of the steps table |

QV gate steps (S03, S14..S21) have no prompt files — `qv-gate` runs the declared `command` directly.

## Acceptance Criteria

### AC1: Schema additions

```
Given the alembic migration in this CR has been applied
When a developer inspects the `step_runs` table
Then columns `prompt_text` (TEXT NULL) and `fix_prompt_text` (TEXT NULL) exist
 And `make migration-check` passes (upgrade-from-base, drift, downgrade roundtrip)
```

### AC2: Daemon snapshots prompts at launch

```
Given a work item is approved and the daemon picks it up
When the daemon creates the StepRun for an implementation step
Then StepRun.prompt_text contains the *contents* of the prompt file that was written for that step
 And the value is non-empty when WorkflowStep.prompt_file is set
```

### AC3: Daemon snapshots fix-cycle prompts at launch

```
Given a step has failed and a fix cycle is triggered
When the daemon creates the new retry StepRun for that fix cycle
Then StepRun.fix_prompt_text contains the *contents* of the generated fix-prompt file
 And StepRun.prompt_text remains the base prompt for that step (for backwards-traceability)
```

### AC4: Prompt column renders with View button

```
Given an item has at least one StepRun with a non-NULL prompt_text
When the user loads /project/{pid}/item/{iid}
Then the steps table contains a "Prompt" column between "Model" and "Status"
 And the cell for that step renders a "View" button
 And the cell for synthetic steps (S00, MERGE) or steps without a prompt renders "—"
```

### AC5: Modal opens on click and shows prompt text

```
Given a step has prompt_text snapshotted
When the user clicks the "View" button in that row
Then an htmx GET to /project/{pid}/item/{iid}/step/{step_id}/prompt-modal fires
 And the returned fragment renders a modal dialog with role="dialog" aria-modal="true"
 And the modal body contains the full prompt text inside a <pre> element
 And the modal header shows the step ID, agent label, and prompt file path
```

### AC6: Modal dismissal honors a11y conventions

```
Given the prompt modal is open
When the user presses Escape OR clicks the backdrop OR clicks the close button
Then the modal closes and aria-hidden is restored to "true"
 And focus returns to the "View" button that triggered the modal
```

### AC7: Fix-cycle prompts shown in stacked sections

```
Given a step has one initial run and one fix-cycle retry
 And StepRun.prompt_text is set on the first run
 And StepRun.fix_prompt_text is set on the retry run
When the user opens the prompt modal for that step
Then the modal contains two labelled sections: "Initial Prompt" and "Fix Prompt (cycle 1)"
 And both bodies are independently scrollable
```

### AC8: Copy-to-clipboard works

```
Given the prompt modal is open
When the user clicks the "Copy" button in a section
Then window.iwClipboard.copy is invoked with that section's text
 And the button briefly shows "Copied" feedback
```

### AC9: Authorization scope

```
Given a step_run that belongs to a different project
When a request hits /project/{project_id}/item/{item_id}/step/{step_id}/prompt-modal for the wrong project_id or item_id
Then the response is 404 (not 403, not 500 — mirrors items.py convention)
```

## Rollback Plan

- **Database**: Reverse migration is automatic (`alembic downgrade -1`). Drops both columns. No data dependency on these columns in the orchestration core.
- **Code**: Revert the merge commit. Daemon snapshotting and the new route gracefully tolerate absent columns only if the migration also rolls back; otherwise the daemon would write to dropped columns. Standard sequence: revert code → downgrade migration.
- **Data**: No data loss — the snapshotted prompt text is observability metadata, not load-bearing. Prompt files in worktrees are unaffected.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `orch/db/models.py`
- `orch/db/migrations/versions/**`
- `orch/daemon/batch_manager.py`
- `orch/daemon/fix_cycle.py`
- `dashboard/routers/items.py`
- `dashboard/templates/fragments/item_steps_table.html`
- `dashboard/templates/fragments/prompt_text_modal.html`
- `dashboard/static/styles.css`
- `dashboard/static/prompt_modal.js`
- `tests/unit/test_step_run_prompt_columns.py`
- `tests/integration/test_daemon_prompt_snapshot.py`
- `tests/dashboard/test_prompt_modal_route.py`
- `tests/dashboard/test_item_steps_table_render.py`

## TDD Approach

### Unit tests

- `tests/unit/test_step_run_prompt_columns.py`
  - `StepRun` accepts `prompt_text=None` and `prompt_text="..."` at construction.
  - `StepRun` accepts `fix_prompt_text=None` and `fix_prompt_text="..."` at construction.
  - Both columns default to NULL when omitted.

### Integration tests (testcontainer Postgres)

- `tests/integration/test_daemon_prompt_snapshot.py`
  - When the daemon launches a StepRun for a workflow step with a `prompt_file`, the resulting `step_runs.prompt_text` equals the file contents.
  - When the daemon launches a fix-cycle retry, the resulting `step_runs.fix_prompt_text` equals the fix-prompt file contents AND `prompt_text` equals the base prompt contents.
  - Round-trip: write StepRun, query back, assert both columns are durable.

### Dashboard tests (TestClient)

- `tests/dashboard/test_prompt_modal_route.py`
  - `GET /project/{pid}/item/{iid}/step/{step_id}/prompt-modal` returns 200 + a fragment containing the prompt text for a step with `prompt_text` set.
  - Returns 200 with both Initial + Fix sections when the step has runs with each.
  - Returns 404 for a step belonging to a different project.
  - Returns 404 for a step that exists but has no StepRun with any prompt content.
  - The rendered fragment contains `role="dialog"` and `aria-modal="true"`.
  - The rendered fragment does NOT extend `base.html` (no `<html>` tag in the response body).

### Template/render tests

- The Prompt column header appears between Model and Status in `item_steps_table.html` rendering with at least one run with prompt_text.
- Rows for synthetic steps render `—` in the Prompt cell, not a button.

### Updated tests

- Any existing test that asserts on the column count or column order of `item_steps_table.html` (grep for `<th>Model</th>` / `<th>Status</th>` patterns) — update to expect 11 columns and the new ordering.

## Notes

- **Reuse vs new CSS**: prefer reusing `.activity-modal-*` classes if they're visually identical to what we want. Only add `.prompt-modal-*` rules if there's a specific styling difference (e.g., wider modal for long prompts). The implementer chooses; both options are acceptable.
- **Modal width**: prompts can be long (>2000 chars). Consider `max-width: 64rem` and `max-height: 80vh` with overflow-y scroll in the body. The implementer can adjust based on visual review.
- **Lazy loading rationale**: shipping prompt text inline in the steps-table fragment would bloat the initial render for items with 25+ steps (each prompt 1-10 KB). Lazy htmx load keeps the table fast.
- **NEVER call `navigator.clipboard.writeText` directly** — `dashboard/CLAUDE.md` documents the past pain (silent `TypeError` outside secure contexts). Always go through `window.iwClipboard.copy(text, button)`.
- **Future work (out of scope)**: batch detail page, history page (item list view does not show step rows today, so nothing to add); syntax highlighting; prompt diff between cycles; backfilling historical rows from merged git history.
