# CR-00019_S12_CodeReview_prompt

**Work Item**: CR-00019 -- Selection-driven OSS Prepare with reviewable worktree lifecycle
**Step Being Reviewed**: S11 (tests-impl)
**Review Step**: S12

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Same guards.

## Input Files

- `ai-dev/active/CR-00019/CR-00019_CR_Design.md`
- `ai-dev/work/CR-00019/reports/CR-00019_S11_Tests_report.md`
- All files listed in S11's `files_changed`

## Output Files

- `ai-dev/work/CR-00019/reports/CR-00019_S12_CodeReview_report.md`

## Context

You are reviewing S11: the extended test coverage for CR-00019.

## Review Checklist

### 1. AC coverage

Check every AC from the design doc against the tests. The S11 report should include an AC → test-file mapping. Verify:
- AC1 (dead link gone) → template test.
- AC2 (checkbox rule) → template test.
- AC3 (filter + grouping) → template test.
- AC4 (details modal + OSPS link) → template test.
- AC5 (confirm dialog) → template or browser test.
- AC6 (worker awaiting-review) → worker test.
- AC7 (awaiting-review card rendered) → template test.
- AC8 (accept happy path) → accept test.
- AC9 (accept moved-main refusal) → accept test.
- AC10 (discard idempotent) → discard test.
- AC11 (concurrency gating) → concurrency test.
- AC12 (stale disables fix button) → stale-ui test.
- AC13 (rationale + OSPS e2e) → skill test + template test.
- AC14 (worktrees surface) → worktrees-page test.
- AC15 (publish untouched) → `tests/integration/test_cr_00019_publish_regression.py` must exist and assert the publish path is unaffected (old JSON body accepted, `/tmp/` worktree, no `awaiting_review` transition, no `base_sha` / `branch_name` / `commit_sha` / `files_changed_summary` written). Flag HIGH if the file is missing or its assertions are absent.

Flag any AC without a mapped test as a HIGH finding.

### 2. Test isolation

- No live-DB access. Every integration test uses a testcontainer.
- `postgresql+psycopg://` URL scheme in fixtures.
- No `importlib.reload(orch.config)` — `monkeypatch.delenv()` used instead.
- FTS trigger SQL applied after `create_all` where needed.

### 3. Tests fail on pre-change code

For each new test file, the S11 author should have verified the test fails on main. Spot-check three: check out main briefly (or inspect the diff), confirm those tests would fail on pre-CR code.

### 4. No mock abuse

- Database is NOT mocked in integration tests (testcontainer). Unit tests may mock the DB helper but not the ORM session.
- The subprocess for `iw oss prepare` IS mocked in worker tests — that's correct. But don't mock out the git operations in the accept/discard tests; those tests need a real git repo fixture to verify the squash-merge actually lands.

### 5. Semantic assertions

- Tests assert behavior (status=awaiting_review, branch exists, worktree exists) — not shape-only (no "response has 4 keys" type tests).
- Error paths assert both status code AND detail string.

### 6. Existing tests updated, not deleted

- Tests that previously exercised the "fix-everything" Prepare behavior should be ADAPTED (sending a JSON body with explicit checks), not deleted.
- Scanner tests that asserted the 4 old always-try fixes run unconditionally should now assert those fixes surface as regular findings with `auto_fix_available=true`.

### 7. Naming + layout

- Test files follow `test_cr_00019_<topic>.py` convention.
- Unit vs integration split matches project convention (`tests/unit/` for pure-Python, `tests/integration/` for testcontainer DB).

### 8. Project conventions

Read `tests/CLAUDE.md` and `CLAUDE.md`. Flag any rule breach.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — zero failures.
2. `make test-integration` — zero failures.
3. `make lint` — clean.
4. `uv run mypy orch/ dashboard/` — clean.
5. If you spot tests that would pass on pre-change code (e.g. they don't actually exercise the new behavior), that's a HIGH finding.

## Severity Levels

Standard. Missing AC coverage → HIGH per AC. Live-DB test → CRITICAL. Test that would pass on main → HIGH.

## Review Result Contract

```json
{
  "step": "S12",
  "agent": "CodeReview",
  "work_item": "CR-00019",
  "step_reviewed": "S11",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit, Y integration, 0 failed",
  "notes": ""
}
```
