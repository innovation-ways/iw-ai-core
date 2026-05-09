# CR-00038: Docs View — Filter Bar Redesign + Running-Jobs Strip + Spinner Fix

**Type**: Change Request
**Priority**: Medium
**Reason**: UX improvement — filter bar is visually cluttered; generate spinner never stops (SSE not connected), forcing a manual page reload to see results.
**Created**: 2026-05-08
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This CR adds no database migrations. Schema is unchanged.

## Description

The docs library page has a three-row filter bar (Type pills, Status pills, Search) that wastes vertical space and looks cluttered. Additionally, clicking Generate or Regenerate on a doc card shows a spinner that never stops — the `docs_generate_running.html` fragment returns static HTML with no SSE subscription, so the UI never learns when the job finishes. This CR collapses the filters into a single line (two `<select>` dropdowns + search input), adds a persistent running-jobs strip below the filter line that polls via SSE and auto-dismisses on completion, makes the generate button go grey/disabled while the job runs, and auto-refreshes the card when the job finishes.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key points for this CR:
- Dashboard stack: FastAPI + Jinja2 + htmx (no React).
- Fragment templates under `dashboard/templates/fragments/` MUST NOT extend `base.html`.
- Plain CSS rules go directly into `dashboard/static/styles.css` when `make css` reports "Nothing to be done".
- Use `window.iwClipboard.copy()` for clipboard actions — never `navigator.clipboard` directly.
- `playwright-cli` exclusively for browser automation.

## Current Behavior

**Filter bar**: Three separate rows stacked vertically — a Type pill row (All + one pill per `DocType`), a Status pill row (All + one pill per `DocStatus`), and a standalone search `<input>`. Each pill fires an independent `hx-get` without including the other filter values, so switching type clears an active status filter and vice versa.

**Generate/Regenerate button**: On click, the button area (`#doc-generate-btn-{slug}`) is swapped with the content of `docs_generate_running.html` — a static spinner with "Generating…" text. This fragment has no SSE subscription and no polling; once displayed it spins indefinitely. The card JS already has `docJobCompleted` / `docJobFailed` listeners that would refresh the card, but nothing dispatches those events because nothing connects to the SSE stream at `/api/docs/jobs/{job_id}/stream`.

**Running jobs**: No visual indicator on the library page that any jobs are in flight — the only feedback is the stuck spinner inside the button area.

## Desired Behavior

**Filter bar**: A single horizontal row with a Type `<select>`, Status `<select>`, and search `<input>`, all inside a `<form id="docs-filter-form">`. Each control uses `hx-include="#docs-filter-form"` so all three values are sent together on any change. No pills remain.

**Running-jobs strip**: A `<div id="docs-running-jobs">` sits between the filter bar and the card grid. It loads on page load and reloads whenever a `runningJobsReload` custom event fires on `document.body`. When running jobs exist, it renders a compact row per job (spinner + doc title + elapsed timer + Cancel button). When empty it renders nothing. Each job row opens an `EventSource` to the job's SSE stream; on `completed` or `failed` the row dispatches `docJobCompleted` / `docJobFailed` (triggering card refresh) and `runningJobsReload` (triggering strip reload) on `document.body`, then closes the EventSource.

**Generate/Regenerate button**: On click the POST response immediately returns a disabled grey button (spinner icon + "Queued…") with `HX-Trigger: {"docJobCreated": ..., "runningJobsReload": null}`. The button stays disabled until the card auto-refreshes when the job completes. No spinner lives in the button area permanently.

**Card auto-refresh**: Existing `docJobCompleted` handler in `docs_card.html` already calls `htmx.ajax` to refresh the whole card — no change needed there. The refresh restores the enabled Generate/Regenerate button.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `docs_library.html` filter bar | 3-row pill/input layout | Single-row `<form>` with two `<select>` + one `<input>` |
| `docs_library.html` | No running-jobs area | `#docs-running-jobs` strip between filters and grid |
| `docs_card.html` generate button | `hx-swap="innerHTML"` → static spinner | `hx-swap="innerHTML"` → disabled button; strip gets job |
| `dashboard/routers/docs.py` `docs_generate` | Returns `docs_generate_running.html` | Returns disabled-button HTML + `HX-Trigger` with `runningJobsReload` |
| `dashboard/routers/docs.py` | No running-jobs endpoint | `GET /api/docs/running-jobs` added |
| `fragments/docs_running_jobs.html` | Does not exist | New fragment: running-jobs strip rows with SSE |
| `fragments/docs_generate_running.html` | Static spinner fragment | Deleted (replaced by inline HTML in route) |

### Breaking Changes

- None. The `GET /api/docs/running-jobs` endpoint is new. The `docs_generate` POST still accepts the same request and returns an HTML fragment targeting the same element ID — only the fragment content changes.

### Data Migration

- Not required. No schema changes.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | frontend-impl | Redesign filter bar, add running-jobs strip endpoint + fragment, fix generate button response | — |
| S02 | code-review-impl | Review S01 output | — |
| S03 | tests-impl | Dashboard integration tests for new `GET /api/docs/running-jobs` endpoint; update any tests that assert the old pill markup | — |
| S04 | code-review-impl | Review S03 output | — |
| S05 | code-review-final-impl | Global review of S01 + S03 | — |
| S06 | qv-gate lint | `make lint` | — |
| S07 | qv-gate format | `make format-check` | — |
| S08 | qv-gate typecheck | `make type-check` | — |
| S09 | qv-gate unit-tests | `make test-unit` | — |
| S10 | qv-gate integration-tests | `make test-integration` | — |
| S11 | qv-browser | Browser verification | — |
| S12 | self-assess-impl | Self-assessment | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: N/A

### API Changes

- **New endpoints**: `GET /project/{project_id}/api/docs/running-jobs` — returns HTML fragment of currently running `DocGenerationJob` rows for the project
- **Modified endpoints**: `POST /project/{project_id}/api/docs/{doc_id}/generate` — response body changes (disabled button HTML instead of spinner fragment); `HX-Trigger` header gains `runningJobsReload` alongside `docJobCreated`
- **Removed endpoints**: None

### Frontend Changes

- **New components**: `dashboard/templates/fragments/docs_running_jobs.html`
- **Modified components**: `dashboard/templates/docs_library.html`, `dashboard/templates/fragments/docs_card.html`, `dashboard/routers/docs.py`
- **Removed components**: `dashboard/templates/fragments/docs_generate_running.html` (no longer referenced)

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00038_CR_Design.md` | Design | This document |
| `CR-00038_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00038_S01_Frontend_prompt.md` | Prompt | S01 frontend implementation |
| `prompts/CR-00038_S02_CodeReview_Frontend_prompt.md` | Prompt | S02 code review of S01 |
| `prompts/CR-00038_S03_Tests_prompt.md` | Prompt | S03 test coverage |
| `prompts/CR-00038_S04_CodeReview_Tests_prompt.md` | Prompt | S04 code review of S03 |
| `prompts/CR-00038_S05_CodeReview_Final_prompt.md` | Prompt | S05 final cross-agent review |
| `prompts/CR-00038_S11_BrowserVerification_prompt.md` | Prompt | S11 browser verification |
| `prompts/CR-00038_S12_SelfAssess_prompt.md` | Prompt | S12 self-assessment |

## Acceptance Criteria

### AC1: Single-line filter bar

```
Given the user is on the /project/{id}/docs page
When the page loads
Then the filter area shows exactly one row containing a "Type" select, a "Status" select,
     and a search input — no pill buttons are visible
```

### AC2: Filter selects work together

```
Given the user has selected a Type filter and a Status filter
When they type in the search input
Then the grid refreshes with results matching all three filters simultaneously
```

### AC3: Running-jobs strip appears on generate

```
Given a doc card with a Generate or Regenerate button
When the user clicks the button
Then the button becomes grey/disabled showing a spinner icon and "Queued…" text,
     and a running-jobs row appears below the filter bar showing the doc title and a spinner
```

### AC4: Running-jobs strip disappears on completion

```
Given a running-jobs row is visible for a doc generation job
When the daemon completes the job (status transitions to completed or failed)
Then the running-jobs row disappears from the strip,
     and the corresponding doc card auto-refreshes (showing updated status/content)
```

### AC5: Multiple concurrent jobs each get a row

```
Given the user clicks Generate on three different doc cards
When all three POSTs complete
Then the running-jobs strip shows three rows, one per job, each with its own spinner and doc title
```

### AC6: Failed job shows error feedback

```
Given a running-jobs row for a job that transitions to failed
When the SSE stream delivers the failed event
Then the row turns red with an error indicator before disappearing,
     and the card refreshes showing the "Last run failed" badge
```

## Rollback Plan

- **Database**: N/A — no schema changes
- **Code**: Revert commit; the filter bar and running-jobs strip are purely additive frontend changes with no persistent side effects
- **Data**: No data loss on rollback

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/templates/docs_library.html`
- `dashboard/templates/fragments/docs_card.html`
- `dashboard/templates/fragments/docs_running_jobs.html`
- `dashboard/templates/fragments/docs_generate_running.html`
- `dashboard/routers/docs.py`
- `dashboard/static/styles.css`
- `tests/dashboard/test_docs.py`

## TDD Approach

- **Unit tests**: None needed — no pure-Python logic added
- **Integration tests**: Dashboard `TestClient` tests for `GET /api/docs/running-jobs`:
  - Returns empty fragment when no running jobs
  - Returns one row per running job with correct doc title
  - Does not leak research docs (only non-research docs)
- **Updated tests**: Any existing test in `tests/dashboard/test_docs.py` that asserts pill-button markup (class `filter-pill`, text like "Status:" or "Type:" adjacent to buttons) needs updating to match the new `<select>` markup

## Notes

- The `docs_generate_running.html` fragment becomes unused after S01. The frontend-impl agent should delete it.
- The `docs_job_status.html` fragment (used by the detail page's job panel, `GET /api/docs/jobs/{job_id}/panel`) is unaffected by this CR.
- The `docJobCompleted` / `docJobFailed` event listeners in `docs_card.html` already handle card refresh correctly; no changes are needed there beyond ensuring `runningJobsReload` is also dispatched so the strip reloads.
- EventSource connections in the strip rows must be deduplicated using `window._docJobSources = {}` keyed by job ID to prevent duplicate connections on strip reload.
- If `make css` is not available (Tailwind toolchain broken per I-00067), append any new CSS rules for `<select>` styling directly to `dashboard/static/styles.css`.
