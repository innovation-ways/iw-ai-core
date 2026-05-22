# CR-00077: Overlap details popup (read-only)

**Type**: Change Request
**Priority**: Medium
**Reason**: Operators currently can't see the full list of files behind the truncated `Held: overlaps with X on \`<files>+N\`` pill in a batch's Items tab. They have no way to know which files are conflicting without a database dump.
**Created**: 2026-05-22
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This CR adds **no** database schema changes and **no** alembic migrations. All the data needed for the popup already exists in `daemon_events` rows of type `item_held_for_scope` (emitted by `orch/daemon/batch_manager.py:464-478`).

## Description

Make the `Held: …` overlap pill in `dashboard/templates/fragments/batch_items_rows.html` clickable. Clicking it opens an htmx modal grouped by conflicting item, showing the full list of overlapping file globs without truncation. This is a **read-only** display feature — no operator actions, no DB writes, no daemon hooks. The follow-up CR-00078 adds the per-file Ignore button and master "Ignore all & start" button on top of the modal partial this CR introduces.

## Project Context

Read the project's `CLAUDE.md` (root, `dashboard/CLAUDE.md`, `orch/CLAUDE.md`) for FastAPI + Jinja2 + htmx conventions, the rule about appending plain CSS to `dashboard/static/styles.css` when Tailwind recompile is unavailable, and the `playwright-cli` browser-automation policy.

## Current Behavior

`dashboard/routers/batches.py::ScopeStatus.pill_text` (lines 84-124) truncates the conflicting-globs list to the first two patterns and appends `+N` for any remaining files. Example today on BATCH-00127, every Held item shows:

```
Held: overlaps with CR-00076 on `docs/IW_AI_Core_Testing_Strategy.md, skills/iw-ai-core-testing/**+2`
```

Operators cannot see which `+2` files are conflicting. The full glob list is available in `DaemonEvent.event_metadata["conflicting_globs"]` for each emitted `item_held_for_scope` row (one row per `(held_item, blocking_item)` pair), but it is only exposed through the cell's hover `title` attribute (`ScopeStatus.pill_tooltip`, lines 114-124) — a single concatenated string with no structure, no grouping by blocking item, and no per-file presentation.

The same pill markup also appears on the project Queue page, but `_queue_items` excludes items that belong to an active batch — so a `Held` pill on the Queue page is a rare edge case. The Queue-page trigger is **out of scope** for this CR (see Notes).

## Desired Behavior

The `Held: …` pill becomes a clickable button. Clicking it:

1. Fires an htmx `GET` to a new dashboard endpoint that returns an HTML fragment for the modal.
2. The modal opens centred over the batch page with a translucent backdrop.
3. The modal title is `Overlap details — {held_item_id}`.
4. The modal body is **grouped by conflicting item**: one section per `blocking_item_id` with the format:

   ```
   ┌─ CR-00076 — Data-Layer Test Module — Migrations, FTS, DB Identity   [open ↗]
   │  • docs/IW_AI_Core_Testing_Strategy.md
   │  • skills/iw-ai-core-testing/**
   │  • .claude/skills/iw-ai-core-testing/**
   │  • ai-dev/work/TESTS_ENHANCEMENT.md
   └─
   ```

   Section header is the conflicting item's ID + title with a link to `/project/{slug}/item/{id}`. Files are listed verbatim in their original order from `DaemonEvent.event_metadata["conflicting_globs"]` — no truncation.
5. Closing the modal: click on the backdrop, click an explicit `Close` button, or press Esc.
6. **No action buttons** in this CR. The modal is read-only. (CR-00078 adds Ignore buttons + master "Ignore all & start" inside this same modal partial.)

The clickable trigger ships in the batch Items tab. The modal fragment template is a single shared partial — designed so CR-00078 can extend it for the per-file Ignore controls without rewriting the layout.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| Batch items overlap pill (`batch_items_rows.html`) | Static span with truncated text + hover tooltip | Button-styled trigger with `hx-get` to the new endpoint; tooltip preserved as fallback |
| Batch detail page (`batch_detail.html`) | No modal mount point | Add a single `<div id="overlap-modal-root">` as the htmx swap target, outside the polled items fragment |
| Dashboard router `batches.py` | Returns batch detail pages; `_get_scope_statuses` reads recent events | Add new endpoint `GET /project/{slug}/batch/{batch_id}/overlap/{held_item_id}` returning a modal HTML fragment |
| Items fragment endpoint (`batch_items_fragment` in `batches.py`) | Renders `batch_items_rows.html` with `{current_project, items}` only — no `batch` in context | Also pass `batch` into the context so the new trigger button's `hx-get` URL keeps a valid `batch_id` after each htmx live refresh of the Items tab |
| Dashboard CSS | No modal styling for this overlay | Append plain CSS rules for modal container, backdrop, sections, close button |

### Breaking Changes

- None. Pure additive feature.

### Data Migration

- None. No schema changes. The data already exists in `daemon_events` rows of type `item_held_for_scope`.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | api-impl | New htmx endpoint that loads recent `item_held_for_scope` events for a `(batch_id, held_item_id)` pair, joins to `WorkItem` to fetch each blocking item's title, groups by `blocking_item_id`, and renders the modal fragment; also adds `batch` to the existing `batch_items_fragment` template context so the S03 trigger URL survives htmx Items-tab refreshes | — |
| S02 | code-review-impl | Review S01 endpoint contract, query window semantics, error paths, and Jinja escaping | — |
| S03 | frontend-impl | Make the `Held` pill in `batch_items_rows.html` a clickable trigger (`hx-get` + `hx-target="#overlap-modal-root"`); add the `#overlap-modal-root` div to `batch_detail.html`. Create new `batch_overlap_modal.html` fragment. Append modal CSS to `dashboard/static/styles.css` | — |
| S04 | code-review-impl | Review S03 template diff + CSS additions; verify the modal partial is the single source of truth; verify focus trap + Esc key handling | — |
| S05 | tests-impl | Dashboard tests: TestClient hits the endpoint, asserts grouping, asserts no truncation, asserts 404 when there is no recent event; one unit test exercising the grouping helper | — |
| S06 | code-review-impl | Review S05 tests for fixture isolation, assertion strength, and coverage of the empty-events edge case | — |
| S07 | code-review-final-impl | Global cross-agent review — verify the modal partial is a single fragment (not duplicated), verify scope discipline (no `orch/` or daemon files modified) | — |
| S08 | qv-gate | `make lint` | — |
| S09 | qv-gate | `make format-check` | — |
| S10 | qv-gate | `make type-check` | — |
| S11 | qv-gate | `make test-unit` | — |
| S12 | qv-gate | `make test-integration` | — |
| S13 | qv-gate | `make test-assertions` | — |
| S14 | qv-browser | Playwright: open BATCH-00127, click the truncated `Held: …` cell, assert modal opens with at least one grouped section and a Close control, click Close, assert modal disappears | — |
| S15 | self-assess-impl | Post-execution analysis via `iw-item-analyze` | — |

Agent slugs are per `skills/iw-workflow/SKILL.md` canonical table.

### Database Changes

- **New tables**: None.
- **Modified tables**: None.
- **Migration notes**: This CR adds no alembic migration.

### API Changes

- **New endpoints**:
  - `GET /project/{slug}/batch/{batch_id}/overlap/{held_item_id}` → returns an HTML fragment (the modal body). Status 200 with the rendered modal on success. Status 404 when no recent `item_held_for_scope` event exists for that `(batch_id, held_item_id)` within the lookup window (same 300s window used by `_get_scope_statuses`). The endpoint is read-only — no side effects, no DB writes.
- **Modified endpoints**: `GET /project/{slug}/batch/{batch_id}/fragment/items` (`batch_items_fragment`) — add `batch` to the Jinja render context. No change to URL, status code, or response shape; the rendered rows are byte-identical except the new `Held` trigger button can now resolve `{{ batch.id }}` after a live refresh.
- **Removed endpoints**: None.

### Frontend Changes

- **New components**:
  - `dashboard/templates/fragments/batch_overlap_modal.html` — modal partial (does NOT extend `base.html`).
- **Modified components**:
  - `dashboard/templates/fragments/batch_items_rows.html` — `Held` pill becomes `hx-get` trigger.
  - `dashboard/templates/pages/project/batch_detail.html` — add the `<div id="overlap-modal-root">` htmx swap target.
  - `dashboard/static/styles.css` — append modal layout rules (backdrop, container, section list).
- **Removed components**: None.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00077/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00077_CR_Design.md` | Design | This document |
| `CR-00077_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00077_S01_API_prompt.md` | Prompt | S01 endpoint implementation |
| `prompts/CR-00077_S02_CodeReview_prompt.md` | Prompt | S02 review |
| `prompts/CR-00077_S03_Frontend_prompt.md` | Prompt | S03 template + CSS |
| `prompts/CR-00077_S04_CodeReview_prompt.md` | Prompt | S04 review |
| `prompts/CR-00077_S05_Tests_prompt.md` | Prompt | S05 tests |
| `prompts/CR-00077_S06_CodeReview_prompt.md` | Prompt | S06 review |
| `prompts/CR-00077_S07_CodeReview_Final_prompt.md` | Prompt | S07 cross-agent review |
| `prompts/CR-00077_S14_BrowserVerification_prompt.md` | Prompt | S14 Playwright spec |
| `prompts/CR-00077_S15_SelfAssess_prompt.md` | Prompt | S15 analysis |
| `evidences/pre/CR-00077-before-truncated-cell.png` | Evidence | Screenshot of the current truncated `Held` pill on BATCH-00127 |

Reports are created during execution in `ai-dev/active/CR-00077/reports/`.

## Acceptance Criteria

### AC1: Truncated pill becomes clickable

```
Given a batch with at least one Held item showing the truncated `Held: overlaps with X on \`<files>+N\`` pill
When the operator clicks the pill in the Items tab
Then an HTTP GET request is sent to /project/{slug}/batch/{batch_id}/overlap/{held_item_id}
And the response is rendered into the page as a modal overlay
```

### AC2: Modal is grouped by conflicting item

```
Given a held item with overlapping files against two other in-flight items
When the modal renders
Then the body shows two distinct sections, one per blocking_item_id
And each section header shows that item's id and title with a link to /project/{slug}/item/{id}
And each section lists every file glob from that event's conflicting_globs without truncation
```

### AC3: No truncation in the modal

```
Given a held item whose `pill_text` shows `dir/a.py, dir/b.py+3`
When the modal renders
Then every file in `conflicting_globs` appears on its own row in the modal
And the `+3` ellipsis from the pill no longer hides any file
```

### AC4: Modal dismissal

```
Given the modal is open
When the operator presses Esc, clicks the backdrop, or clicks the explicit Close button
Then the modal closes and focus returns to the trigger pill
```

### AC5: 404 when no recent event

```
Given a held_item_id with no `item_held_for_scope` event in the last 300 seconds
When the endpoint is called
Then the response is HTTP 404 with a small Jinja fragment "No overlap details available — the item may have been released since this page rendered."
And the page does not crash
```

### AC6: Read-only

```
Given the modal is open
When inspecting the rendered HTML
Then there are no form elements, no POST endpoints, no Ignore buttons, no "Force start" buttons
And the endpoint does not write to the database
```

## Rollback Plan

- **Database**: N/A — no schema change.
- **Code**: Revert the merge commit. The pill returns to its current static behaviour. No data migration to reverse.
- **Data**: No data is created or modified by this CR; rollback has no data impact.

## Dependencies

- **Depends on**: None.
- **Blocks**: CR-00078 (per-batch ignore overlap & force-start) — CR-00078 extends the modal partial added here.

## Impacted Paths

- `dashboard/routers/batches.py`
- `dashboard/templates/fragments/batch_items_rows.html`
- `dashboard/templates/fragments/batch_overlap_modal.html`
- `dashboard/templates/pages/project/batch_detail.html`
- `dashboard/static/styles.css`
- `tests/dashboard/test_batch_overlap_modal.py`
- `tests/unit/test_batch_overlap_grouping.py`

## TDD Approach

- **Unit tests** (`tests/unit/test_batch_overlap_grouping.py`):
  - The pure helper that groups a list of `DaemonEvent` rows by `blocking_item_id` and returns ordered `(blocking_item_id, conflicting_globs)` tuples.
  - Edge cases: empty list, single event, multiple events to the same blocking item (most recent wins on duplicates), preserved insertion order across blocking items.
- **Integration tests** (`tests/dashboard/test_batch_overlap_modal.py`):
  - TestClient hits the new endpoint with a seeded `BatchItem` + matching `DaemonEvent` rows.
  - Assert: 200 status, HTML contains a section per blocking item, every file glob from the event payload appears, no `+N` truncation, the section header links to the conflicting item's detail page.
  - Assert: 404 when no recent event exists for the `(batch_id, held_item_id)` pair.
  - Assert: response is a fragment (no `<html>` / `<body>` tags from `base.html`).
- **Updated tests**: None. Existing batch-page tests in `tests/dashboard/` continue to pass — the pill change is additive (existing `pill_text` / `pill_tooltip` assertions still hold).

## Notes

- The `Held` cell's existing `title`/`aria-label` attributes currently sit on the wrapping `<td>` (`batch_items_rows.html` lines 40-42), not on the inner `<span>`. S03 moves them onto the new `<button>` so the tooltip and accessible label travel with the interactive element.
- The modal mount point (`<div id="overlap-modal-root">`) must live in the `batch_detail.html` page template, not in `batch_items_rows.html`: the latter is a `<tr>`-only fragment that the Items tab re-polls via htmx, so a div placed there would be invalid table markup and would be wiped on each refresh.
- **Live-refresh gotcha (S01 owns the fix).** The `Held` trigger button's `hx-get` URL embeds `{{ batch.id }}`. `batch_items_rows.html` is rendered by two paths: the initial `batch_detail.html` page load (where `batch` is in scope) and the htmx live-refresh handler `batch_items_fragment` (`GET /batch/{batch_id}/fragment/items`), which today passes only `current_project` + `items`. S01 MUST add `batch` to `batch_items_fragment`'s context — otherwise the trigger URL collapses to `/project/{slug}/batch//overlap/{id}` (empty `batch_id`) after the first `batch-items-refresh` SSE swap, i.e. exactly while items are still held and the modal is most needed.
- The project Queue page also renders the `Held` pill, but `_queue_items` excludes items already in an active batch, so a held pill there is a rare edge case — and the batch-scoped endpoint URL has no `batch_id` to bind to from Queue-row context. The Queue-page trigger is intentionally **out of scope** for this CR; it can be revisited if the Queue page is ever shown to surface held items in practice.
- The modal partial MUST be reused by CR-00078 — keep the file at `dashboard/templates/fragments/batch_overlap_modal.html` and design its block structure so CR-00078 can extend the per-file-row block to add Ignore buttons without rewriting the layout.
- Browser verification uses BATCH-00127 as the live fixture if it is still alive in the production DB at execution time; otherwise the worktree-seeded copy via `pg_dump` will preserve those rows. No new `e2e_fixtures/` file is expected to be needed.
