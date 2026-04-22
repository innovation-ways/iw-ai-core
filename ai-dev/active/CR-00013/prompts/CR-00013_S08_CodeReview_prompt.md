# CR-00013_S08_CodeReview_prompt

**Work Item**: CR-00013 -- Dashboard navigation performance — eliminate multi-second hangs between pages
**Step Being Reviewed**: S07 (tests-impl)
**Review Step**: S08

---

## Input Files

- `ai-dev/active/CR-00013/CR-00013_CR_Design.md` — Design
- `ai-dev/active/CR-00013/reports/CR-00013_S07_Tests_report.md` — S07 report
- All test files listed in S07's `files_changed`

## Output Files

- `ai-dev/active/CR-00013/reports/CR-00013_S08_CodeReview_report.md` — review report

## Context

Review S07: regression test coverage for all behavior changes in S01/S03/S05. The goal is to verify tests are real guards, not shape-only.

## Review Checklist

### 1. Red-before-Green Verification

- The S07 report must document that each new regression test fails on pre-change code. Re-verify by picking 1–2 tests and doing the stash/unstash yourself.
- If any test passes on pre-change code, that's a CRITICAL finding.

### 2. Semantic Assertions

- Query-count tests assert a **numeric bound** (`<= K`), not just `> 0`. A test that asserts "at least one query ran" is not a regression guard.
- TTL cache tests assert actual cache behavior (call count of the wrapped function), not "the cache object was constructed".
- Middleware tests assert WARN log with the specific fields, not just "a log was emitted".
- base.html render test asserts specific substrings (absence of `cdn.tailwindcss.com`, presence of `/static/styles.css`), not a vague template check.

### 3. Testcontainer Compliance

- Integration tests use the testcontainer fixture (check `tests/conftest.py`).
- No test connects to port 5433.
- No `importlib.reload(orch.config)` — `monkeypatch.setenv`/`delenv` used.
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` run after `create_all()` if the test uses FTS.
- psycopg2 URL replacement pattern applied where relevant.

### 4. Test Isolation

- Each test cleans up state (cache, env vars, monkeypatched time) before/after.
- Tests don't depend on ordering.
- No shared mutable state across tests.

### 5. Coverage of AC1–AC8

Map each AC to tests:
- AC1 (badge <50 ms + zero subprocess) — `test_nav_worktree_badge_cache.py`
- AC2 (pool config) — `test_db_pool_config.py`
- AC3 (bounded queries on 5 hotspots) — 5 query-count tests
- AC4 (subprocess cache TTL) — covered via `test_nav_worktree_badge_cache.py` + `test_git_branch_and_stats_cache.py` (both must exist)
- AC5 (async sleep in daemon_control) — `test_daemon_control_async.py`
- AC6 (Tailwind prebuilt + lazy libs + self-hosted font) — `test_base_html_renders.py`, `test_static_assets.py`, `test_pages_lazy_libs.py`
- AC7 (timing middleware WARN) — `test_timing_middleware.py`
- AC8 (visual parity) — covered by S15 browser verification, not S07 (OK)

Any AC without a test assertion is a HIGH finding.

### 6. Project Conventions

- Tests live in `tests/unit/` or `tests/integration/` as appropriate.
- Fixture reuse from `tests/conftest.py` where applicable.
- No duplicated fixture logic.
- Test names are descriptive (`test_<component>_<behavior>`).

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all tests pass.
2. `make test-integration` — all tests pass.
3. `make quality` — clean.

## Severity Levels

(Same table as S02.)

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "CodeReview",
  "work_item": "CR-00013",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
