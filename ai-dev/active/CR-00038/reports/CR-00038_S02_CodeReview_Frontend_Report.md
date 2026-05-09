# CR-00038 S02 — Code Review: Frontend (S01)

**Reviewer**: code-review-impl
**Work Item**: CR-00038 — Docs View: Filter Bar Redesign + Running-Jobs Strip + Spinner Fix
**Step**: S02
**Date**: 2026-05-09

---

## Summary

S01 implemented all required changes: filter bar redesign (pill → select), running-jobs strip with SSE, disabled-button response for generate action, and the new `docs_running_jobs.html` fragment. The implementation is correct and complete.

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/docs.py` | New `docs_running_jobs` endpoint; `docs_generate` returns disabled button HTML + `HX-Trigger` with both `docJobCreated` and `runningJobsReload` |
| `dashboard/templates/docs_library.html` | Filter bar redesign (pill buttons → compact select + search on one line); `#docs-running-jobs` container added |
| `dashboard/templates/fragments/docs_running_jobs.html` | **New** — running-jobs strip rows with SSE client, deduplication, elapsed timer, cancel button |
| `dashboard/templates/fragments/docs_generate_running.html` | **Deleted** — confirmed removed |
| `dashboard/static/styles.css` | No new CSS rules added (Tailwind utility classes handle all styling) |

---

## Review Checklist Results

### Template / htmx correctness ✅
- [x] `#docs-filter-form` wraps all three filter controls; each control uses `hx-include="#docs-filter-form"` so all values travel together
- [x] `<select>` uses `hx-trigger="change"`; text input uses `hx-trigger="input changed delay:300ms"`
- [x] `hx-target="#docs-grid"` and `hx-swap="innerHTML"` on all filter controls
- [x] `#docs-running-jobs` uses `hx-trigger="load, runningJobsReload from:body"`
- [x] Fragment `docs_running_jobs.html` does NOT extend `base.html`
- [x] No dangling `hx-target`, `hx-include`, `aria-controls`, `aria-labelledby`, or `for` references pointing at non-existent IDs

### JavaScript correctness ✅
- [x] `window._docJobSources` deduplication pattern implemented — existing EventSource for a job is closed before a new one is opened
- [x] `clearInterval` is called on the elapsed timer when the row is cleaned up (`clearInterval(timerId)` in `cleanup()`)
- [x] `EventSource.close()` is called on completion, failure, and error
- [x] `docJobCompleted` dispatched on `document.body` with correct `{job_id, doc_id}` payload
- [x] `docJobFailed` dispatched on `document.body` with `{job_id, doc_id, error}` payload
- [x] `runningJobsReload` dispatched on `document.body` to trigger strip reload
- [x] `onerror` handler triggers delayed `runningJobsReload` (3000ms) to avoid infinite reconnect loop
- [x] No `navigator.clipboard` direct usage — all clipboard actions go through `window.iwClipboard.copy()`

### Backend correctness ✅
- [x] `docs_running_jobs` endpoint filters by `DocGenerationJob.doc_id.startswith(f"{project_id}:")` — prevents cross-project leakage
- [x] Query orders by `requested_at ASC` (oldest first) via `.order_by(DocGenerationJob.requested_at.asc())`
- [x] `HX-Trigger` header is valid JSON with both `docJobCreated` and `runningJobsReload` keys
- [x] Disabled button HTML is valid (no unclosed tags, well-formed SVG)
- [x] `import json` is a local import inside `docs_generate` — no conflict with top-level imports
- [x] `docs_generate_running.html` confirmed deleted (no remaining references in Python or templates)

### Accessibility / UX ✅
- [x] All `<select>` elements have associated `<label>` elements
- [x] Disabled button has `aria-label="Generation queued"`
- [x] Cancel button in job row has `aria-label="Cancel generation"`

### CSS ✅
- [x] No new CSS rules added to `styles.css` — Tailwind utility classes (`bg-input`, `border-border`, `rounded-md`, etc.) handle all styling
- [x] The `.docs-filter-select` class name is present on the `<select>` elements but has no custom CSS rule; this is intentional as Tailwind covers the styling

---

## Findings

| # | Severity | File | Description | Status |
|---|----------|------|-------------|--------|
| 1 | INFO | `dashboard/templates/fragments/docs_running_jobs.html` | The `cleanup(null)` call on `source.addEventListener('completed', …)` dispatches `docJobCompleted` which causes the doc card to refresh. This is correct. The `onerror` handler correctly triggers a delayed `runningJobsReload` without card refresh (the stream will be re-established on reload). No issue. | No action needed |
| 2 | INFO | `dashboard/static/styles.css` | No new CSS rules were added. The `.docs-filter-select` class is present in templates but has no custom CSS rule — Tailwind utility classes in the `class` attribute handle all styling. | No action needed |
| 3 | INFO | `dashboard/routers/docs.py` | `import json` is a local import at line 369 inside `docs_generate`. All top-level imports are at lines 1–24. Convention recommends top-level imports, but no conflict exists today since no `json` is imported at module level. | No action needed |

---

## Test Status

No tests were modified in S01 — S03 covers test changes.

---

## Conclusion

**Verdict**: PASS

All checklist items pass. The implementation correctly:
1. Collapses the three-row filter bar into a single line with two `<select>` elements and a text input, all sharing state via `hx-include="#docs-filter-form"`
2. Adds a `#docs-running-jobs` strip that subscribes to SSE streams per running job, deduplicates connections, shows elapsed time, and dispatches `docJobCompleted`/`docJobFailed`/`runningJobsReload` events correctly
3. Returns a disabled grey button with `HX-Trigger: {"docJobCreated":…, "runningJobsReload":null}` from `docs_generate`
4. Deletes `docs_generate_running.html`

No CRITICAL or HIGH findings.