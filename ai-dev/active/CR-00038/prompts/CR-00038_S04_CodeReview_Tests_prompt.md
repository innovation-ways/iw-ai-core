# CR-00038 S04 — Code Review: Tests (S03)

**Work Item**: CR-00038 — Docs View: Filter Bar Redesign + Running-Jobs Strip + Spinner Fix
**Step**: S04
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Standard policy. See `docs/IW_AI_Core_Agent_Constraints.md`.

## Objective

Review the test additions and modifications made in S03 of CR-00038.

## Input Files

- `ai-dev/active/CR-00038/CR-00038_CR_Design.md` — design reference
- `tests/dashboard/test_docs.py` — the modified test file
- `tests/CLAUDE.md` — test conventions

## Review Checklist

### Coverage
- [ ] `test_running_jobs_empty` — zero running jobs → empty response
- [ ] `test_running_jobs_shows_running` — one running job → correct row HTML
- [ ] `test_running_jobs_multiple` — two running jobs → two rows
- [ ] `test_running_jobs_cross_project_isolation` — other project's jobs not leaked
- [ ] `test_running_jobs_completed_not_shown` — completed jobs excluded
- [ ] `test_generate_response_disables_button` — POST returns disabled button + `runningJobsReload` in `HX-Trigger`
- [ ] Broken tests from old pill markup updated (no remaining `filter-pill` class assertions)

### Test quality
- [ ] No live DB connections (no port 5433 hardcoding, no direct psycopg2 env vars)
- [ ] No `importlib.reload(orch.config)` calls
- [ ] psycopg2 URL replacement rule applied where needed
- [ ] Tests are isolated (each test creates its own DB state, no shared mutable fixtures between tests)
- [ ] Tests do not mock the database
- [ ] Assertions are specific enough to catch regressions

### Conventions
- [ ] Test functions follow naming conventions in `tests/CLAUDE.md`
- [ ] No hardcoded project IDs or doc IDs that could collide across test runs

## Output

Write `ai-dev/active/CR-00038/reports/CR-00038_S04_CodeReview_Tests_Report.md` with findings.

Then call:
```bash
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/CR-00038/reports/CR-00038_S04_CodeReview_Tests_Report.md
```
