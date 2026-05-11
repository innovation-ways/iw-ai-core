# I-00077 S03 Frontend Implementation Report

**Step**: S03 — frontend-impl
**Work Item**: I-00077 — Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page
**Agent**: frontend-impl
**Completion**: 2026-05-11

---

## Summary

Implemented AC3 of I-00077: making doc-generation job failures visible on the Docs catalogue page (`/project/<id>/docs`). Three components were changed, plus regression tests.

---

## Changes

### 1. `dashboard/routers/docs.py` — `docs_running_jobs` query widened

**What changed**: `docs_running_jobs` now returns both `running` jobs (existing) and `failed` jobs whose `completed_at` is within ~10 minutes.

- Added `timedelta` to the `datetime` import.
- Added `and_`, `case`, `or_` from `sqlalchemy`.
- Query filter uses `or_` with `and_(status==failed, completed_at >= cutoff)` so that:
  - `running` jobs always appear.
  - `failed` jobs with a `completed_at` in the window appear alongside them.
  - User-cancelled jobs (status=failed, `completed_at=NULL`) are excluded — they would stay in the strip forever otherwise.
- A `priority` computed column (`case((status==running, 0), else=1)`) orders running jobs first, then failed, both by `requested_at asc`.
- Per-job dict now includes `status: job.status.value` (string `"running"` or `"failed"`) and `error: job.error or ""`.

### 2. `dashboard/templates/fragments/docs_running_jobs.html` — failed rows rendered distinctly

**What changed**: The Jinja2 loop body is split by `{% if item.status == 'failed' %}`:

- **Failed rows**: red background (`bg-red-50 dark:bg-red-900/20`), red border (`border-red-200 dark:border-red-800`), 4px left border using `--destructive` CSS variable, error icon (red X circle SVG), the `doc_title`, the error text in red, and a **Dismiss** button with `onclick="this.closest('[id^=docs-rjob-]').remove()"`. No spinner, no elapsed timer, no EventSource, no Cancel button.
- **Running rows**: unchanged (spinner, elapsed timer, Cancel button, EventSource SSE stream).

### 3. `dashboard/templates/docs_library.html` — toast + event listeners added

**What changed**:
- Added `{% include "components/toast.html" %}` near the top to load the `showToast()` helper.
- Added `docJobFailed` listener on `document.body` that calls `showToast({type: 'error', message: ...})` with a 160-char truncation on long errors.
- Added `docJobCreated` listener that dispatches `runningJobsReload` immediately and again at ~3 s and ~8 s so a quick `queued → running` transition shows up without manual refresh.

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/routers/docs.py` | `docs_running_jobs` query widened to include recently-failed jobs; per-job dict includes `status` and `error` |
| `dashboard/templates/fragments/docs_running_jobs.html` | Failed rows render as dismissible red strip entries |
| `dashboard/templates/docs_library.html` | `toast.html` included; `docJobFailed` and `docJobCreated` listeners added |
| `tests/dashboard/test_docs_running_jobs.py` | Added `TestRunningJobsFailedIncluded` class with 3 regression tests |

---

## Tests

`uv run pytest tests/dashboard/test_docs_running_jobs.py -v` → **10 passed**

New tests (all pass):
- `test_running_jobs_includes_recently_failed_job` — verifies the strip includes a recent failed job with error text, dismiss button, no Cancel, no EventSource
- `test_running_jobs_excludes_stale_failed_job` — verifies a failed job 30 min ago is not shown
- `test_running_jobs_running_first_then_failed` — verifies running jobs appear before failed jobs in HTML

---

## Preflight

| Check | Result |
|-------|--------|
| `make format` | `ruff format` reformatted 1 file (test file); all 667 files now pass `format --check` |
| `make typecheck` | `mypy orch/ dashboard/` → **Success: no issues found in 240 source files** |
| `make lint` | **All checks passed** (`scripts/check_templates.py` + `ruff check` + `node --check` on dashboard JS) |

---

## Notes

- The `_make_failed_job` helper in the test class uses `datetime.now(UTC)` — `datetime` is imported at module level; `UTC`/`timedelta` come from `datetime` within the helper method.
- No new CSS variables were introduced; `--destructive` was already defined in `theme.css` / `styles.css`.
- The Jinja2 `format` filter was not used anywhere in the new template code (`"%dm%02ds"|format` pattern was not needed since no elapsed-time display was added for failed rows).