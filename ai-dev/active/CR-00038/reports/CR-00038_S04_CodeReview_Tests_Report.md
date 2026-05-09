# CR-00038 S04 — Code Review: Tests (S03)

**Reviewer**: code-review-impl
**Work Item**: CR-00038 — Docs View: Filter Bar Redesign + Running-Jobs Strip + Spinner Fix
**Step**: S04
**Agent Reviewed**: tests-impl
**Date**: 2026-05-09

---

## Summary

S03 added 7 new dashboard integration tests in `tests/dashboard/test_docs_running_jobs.py` covering the new `GET /project/{project_id}/api/docs/running-jobs` endpoint and the updated `POST /project/{project_id}/api/docs/{doc_id}/generate` response. All 7 tests pass cleanly (9.49s for the full relevant suite). The test file follows conventions, uses testcontainer-backed DB sessions, and makes no live-DB connections.

---

## Files Changed by S03

| File | Change |
|------|--------|
| `tests/dashboard/test_docs_running_jobs.py` | New file — 405 lines, 7 tests |
| `dashboard/routers/docs.py` | Modified `docs_running_jobs` endpoint (S01 scope) |
| `dashboard/templates/fragments/docs_running_jobs.html` | New fragment (S01 scope) |
| `dashboard/templates/fragments/docs_generate_running.html` | Deleted (S01 scope) |

Only the test file is in scope for this review.

---

## Coverage Checklist

| Check | Status |
|-------|--------|
| `test_running_jobs_empty` — zero running jobs → empty response | ✅ PASS |
| `test_running_jobs_shows_running` — one running job → correct row HTML | ✅ PASS |
| `test_running_jobs_multiple` — two running jobs → two rows | ✅ PASS |
| `test_running_jobs_cross_project_isolation` — other project's jobs not leaked | ✅ PASS |
| `test_running_jobs_completed_not_shown` — completed jobs excluded | ✅ PASS |
| `test_running_jobs_no_research_docs` — research doc jobs excluded (bonus) | ✅ PASS |
| `test_generate_response_disables_button` — disabled button + `runningJobsReload` in `HX-Trigger` | ✅ PASS |
| No remaining `filter-pill` class assertions | ✅ Verified via grep — none found |

---

## Test Quality Review

### Database Isolation

- ✅ Uses `db_session` fixture from `tests/integration/conftest.py` (testcontainer-backed). No hardcoded port 5433.
- ✅ No direct `psycopg2` env var manipulation.
- ✅ Client fixture (line 44-60) properly handles `IW_CORE_EXPECTED_INSTANCE_ID` cleanup using `os.environ.pop/putback` pattern (acceptable, not `importlib.reload`).
- ✅ No mocking of the database — all DB operations are real via the testcontainer session.

### URL Replacement

- ✅ psycopg2 URL replacement handled by the integration `conftest.py` `pg_container` fixture — test file correctly consumes `db_session` without needing its own replacement logic.

### Test Isolation

- ✅ Each test creates its own DB state via helper functions (`_make_project_doc`, `_make_running_job`).
- ✅ `db_session.commit()` is called within each test to persist state before the HTTP request.
- ✅ No shared mutable fixtures between tests — each test builds its own project/docs/jobs.

### Assertions

- `test_running_jobs_shows_running` (line 158-166): Asserts `docs-rjob-{job.id}` div, doc title, and `hx-delete` cancel URL. Specific and sufficient.
- `test_running_jobs_multiple` (line 188-191): Asserts both job row IDs and both doc titles. Clear.
- `test_running_jobs_cross_project_isolation` (line 250-253): Asserts Project A's row IS present AND Project B's row is NOT present. Correct bidirectional check.
- `test_generate_response_disables_button` (line 376-390): Checks `<button disabled`, absence of `docs_generate_running` string, absence of bare spinner, and presence of `HX-Trigger` header with `runningJobsReload`. Well-structured negative and positive assertions.

### No Live DB Connections

- ✅ Verified: no `port 5433` strings, no `IW_CORE_DB_HOST` env manipulation, no direct psycopg2 usage.

---

## Convention Compliance

| Convention | Status |
|------------|--------|
| Test naming: `test_<what>_<scenario>` | ✅ Follows `tests/CLAUDE.md` pattern |
| No hardcoded project IDs | ✅ `test_project` fixture used; proj-b uses static string `"proj-b"` which is a constant, not a shared mutable ID |
| No `importlib.reload(orch.config)` | ✅ None found |
| No `monkeypatch.delenv` misuse | ✅ Uses `os.environ.pop/putback` in client fixture, which is acceptable for non-testconfig env vars |

---

## `docs_generate_running.html` Deletion Verification

The step instructions required verifying that the old `docs_generate_running.html` fragment was removed from the template directory (since it is no longer referenced after the generate-button response change).

```
$ ls dashboard/templates/fragments/docs_generate_running.html
# No such file
```

✅ Confirmed deleted.

---

## Minor Observations (Non-Blocking)

1. **Unused `doc` variable in `test_running_jobs_shows_running`** (line 150-151): `_make_project_doc` returns a `doc` object that is never referenced after creation — `_make_running_job` only needs `project_id` and `doc_id`. Not a bug, but dead code. No action required.

2. **`IW_CORE_EXPECTED_INSTANCE_ID` env handling in client fixture** (line 47-59): The pattern of `pop` + restore is correct for non-config-munging cases. CLAUDE.md's `monkeypatch.delenv` warning specifically targets `importlib.reload(orch.config)` situations, so this is fine.

---

## Verdict

**PASS** — All 7 tests pass, coverage is complete against the checklist, no live DB connections, no mocking, correct psycopg2 handling, and no remaining `filter-pill` assertions. The test file is ready for the final cross-agent review (S05).

---

## Recommendations for S05

1. The `test_generate_response_disables_button` test covers the `HX-Trigger` header content but does **not** verify the `docJobCreated` key is also present alongside `runningJobsReload` (both are set by the route at line 388-393 of `docs.py`). Consider adding: `assert "docJobCreated" in hx_trigger`.
2. The endpoint filters `DocType.research` jobs from the strip — this is covered by `TestRunningJobsResearchExcluded`. The design doc (AC6) also mentions failed jobs show red/error styling — there is no test for the SSE `failed` event path's strip behavior (the JS in `docs_running_jobs.html` dispatches `docJobFailed` and applies `border-red-400 bg-red-50` before removal). This would require SSE mocking which is more involved; not a blocker.

---

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00038",
  "reviewed_agent": "tests-impl",
  "verdict": "PASS",
  "mandatory_fix_count": 0,
  "findings": [],
  "notes": "All 7 tests pass. No live DB connections. No filter-pill assertions remain. docs_generate_running.html confirmed deleted. One minor observation: test_generate_response_disables_button could additionally assert docJobCreated in HX-Trigger header, but the test is already comprehensive and the route code is straightforward."
}
```