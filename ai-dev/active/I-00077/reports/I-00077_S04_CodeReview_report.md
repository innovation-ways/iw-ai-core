# I-00077 S04 Code Review Report

**Step**: S04 — code-review-impl
**Work Item**: I-00077 — Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page
**Reviewed Step**: S03 (frontend-impl)
**Completion**: 2026-05-11

---

## Summary

Reviewed S03's implementation of AC3 (Fix #3: Docs catalogue page surfaces job failures). All checklist items pass; no CRITICAL/HIGH/MEDIUM_FIXABLE findings. Tests pass.

---

## Files Changed (S03)

| File | Change |
|------|--------|
| `dashboard/routers/docs.py` | `docs_running_jobs` query widened to include recently-failed jobs; per-job dict gains `status` + `error` |
| `dashboard/templates/fragments/docs_running_jobs.html` | Failed rows render as dismissible red strip entries |
| `dashboard/templates/docs_library.html` | `toast.html` included; `docJobFailed` + `docJobCreated` listeners added |
| `tests/dashboard/test_docs_running_jobs.py` | `TestRunningJobsFailedIncluded` class with 3 regression tests |

---

## Pre-Review Gate

| Check | Result |
|-------|--------|
| `make lint` | All checks passed (`scripts/check_templates.py` + `ruff check` + `node --check`) |
| `make format-check` | 667 files already formatted |
| `make typecheck` | mypy on `dashboard/routers/docs.py` — no issues |

---

## Test Verification

```
uv run pytest tests/dashboard/test_docs_running_jobs.py -v
→ 10 passed (21.21s)
```

All new tests pass:
- `test_running_jobs_includes_recently_failed_job` — failed job appears with error text, dismiss button, no Cancel, no EventSource
- `test_running_jobs_excludes_stale_failed_job` — failed job 30 min ago is excluded
- `test_running_jobs_running_first_then_failed` — ordering is deterministic (running first)

---

## Checklist

### 1. Router (`docs_running_jobs`)

- ✅ Query returns `running` jobs **and** `failed` jobs whose `completed_at >= datetime.now(UTC) - timedelta(minutes=10)` — using aware datetime
- ✅ `research` docs excluded via `ProjectDoc.doc_type != DocType.research`
- ✅ `doc_id` scoped to project via `startswith(f"{project_id}:")`
- ✅ Ordering: `priority` computed column (`case((status==running, 0), else=1)`) → running first, then failed, both by `requested_at asc`
- ✅ Per-job dict gained `status: job.status.value` and `error: job.error or ""`; existing keys (`job_id`, `doc_id`, `doc_title`) intact
- ✅ No new N+1 (handler already calls `svc.get_doc` per job — same as before)

### 2. Fragment (`docs_running_jobs.html`)

- ✅ Running rows unchanged (spinner, elapsed timer, Cancel button, EventSource SSE stream)
- ✅ Failed rows: red background (`bg-red-50 dark:bg-red-900/20`), red border (`border-red-200 dark:border-red-800`), 4px left border using `--destructive` CSS variable (pre-existing token)
- ✅ Error text rendered through Jinja2 autoescaping (`{{ item.error }}` — no `|safe`)
- ✅ Dismiss control: `onclick="this.closest('[id^=docs-rjob-]').remove()"` — client-side removal
- ✅ No EventSource, no elapsed timer, no Cancel button for failed rows
- ✅ Outer `id="docs-rjob-{{ item.job_id }}"` convention preserved
- ✅ Jinja2 `format` filter: no `str.format`-style usage anywhere in the new template code

### 3. Catalogue Page (`docs_library.html`)

- ✅ `{% include "components/toast.html" %}` added at line 3 (not double-included)
- ✅ `docJobFailed` listener calls `showToast({type:'error', message: ...})` with 160-char truncation on long errors
- ✅ `docJobCreated` → `runningJobsReload` re-poll: immediate + 3 s + 8 s setTimeout calls (bounded, 3 calls only — no unbounded loop)
- ✅ `#docs-running-jobs` `hx-trigger="load, runningJobsReload from:body"` unchanged — no regression to existing `docJobCompleted` flow

### 4. Conventions / Quality / Security

- ✅ No hardcoded URLs/ports in changed files
- ✅ XSS: `showToast` in `toast.html` uses `_escapeHtml(message)` which creates a text node via `document.createTextNode` — all HTML metacharacters escaped
- ✅ Error string from DB (`item.error`) autoescaped by Jinja2 in `{{ item.error }}`
- ✅ No scope creep into `orch/` or skills
- ✅ `--destructive` CSS variable already defined in `theme.css` (line 49: `--destructive: #b92733`)
- ✅ `border-l-4 border-l-[var(--destructive)]` is a plain CSS class string, not dynamic class construction — JIT Tailwind will NOT purge it

### 5. Testing

- ✅ `tests/dashboard/test_docs_running_jobs.py::TestRunningJobsFailedIncluded` asserts:
  - A recently-failed job appears in `GET .../api/docs/running-jobs`
  - Failed row carries error text (autoescaped by Jinja2)
  - Failed row carries a dismiss control (`onclick`, `remove()`)
  - Failed row does NOT carry a Cancel button
  - Failed row does NOT open an EventSource
- ✅ CSS-class assertions are attribute-scoped (`'id="docs-rjob-job-failed-001"'` in resp.text — specific div id, not a bare substring)
- ✅ `docs_library.html` includes `docJobFailed` handler — verified by grep; test asserts the full HTML response

---

## Findings

No CRITICAL, HIGH, or MEDIUM_FIXABLE findings.

---

## Verdict

**PASS** — zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.

