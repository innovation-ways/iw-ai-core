# I-00041_S06_CodeReview_Tests_prompt

**Work Item**: I-00041 — Connection-layer guard against integration tests writing to the live orchestration DB
**Step Being Reviewed**: S05 (tests-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Same rules as previous prompts. Read-only introspection only.

## Input Files

- `ai-dev/active/I-00041/I-00041_Issue_Design.md`
- `ai-dev/active/I-00041/reports/I-00041_S05_Tests_report.md`
- `tests/unit/test_live_db_guard.py` (new)
- `tests/unit/test_agent_subprocess_env.py` (new — covers S03 R5 strip helper)
- `tests/integration/test_live_db_guard_reproduction.py` (new)
- `tests/integration/test_migration_pipeline.py` (modified — helper extraction + unique batch_id)
- `tests/CLAUDE.md`

## Output Files

- Report: `ai-dev/active/I-00041/reports/I-00041_S06_CodeReview_Tests_report.md`

## Context

You are reviewing the test suite that locks in the I-00041 fix and cleans
up the offending test file. Pay special attention to:

1. Whether assertions verify **specific values**, not just shape (this was
   the I-00003 lesson and is the bar for this project).
2. Whether the reproduction test would have caught the original bug.
3. Whether the cleanup of `test_migration_pipeline.py` actually removes
   all 5 hardcoded `batch_id = 42` instances and the offending mock gaps.

## Review Checklist

### 1. Reproduction test correctness

- [ ] `test_subprocess_in_test_context_cannot_connect_to_live_db` would
      have FAILED against the pre-fix code (no connection-layer guard).
      Confirm by reading the test and tracing what it asserts.
- [ ] The subprocess sets `IW_CORE_TEST_CONTEXT=true` AND clears
      `IW_CORE_OPERATOR_APPLY` / `IW_CORE_DAEMON_CONTEXT` (the env state
      a real test would have).
- [ ] The subprocess attempts an actual `e.connect()` — not just engine
      construction. The guard fires at connect, not at engine creation,
      so an engine-only test would pass even pre-fix.
- [ ] The assertion checks `result.returncode != 0` AND
      `"LiveDbConnectionRefused" in result.stderr` AND the live port
      number appears in stderr. Three specific-value checks, not just
      "subprocess failed."

### 1b. Daemon-armed agent reproduction

A second reproduction test in
`tests/integration/test_live_db_guard_reproduction.py` —
`test_daemon_armed_subprocess_via_agent_env_helper_cannot_connect_to_live_db`
— locks in the closure of the executor leak (S03 R5).

- [ ] The test sets `IW_CORE_DAEMON_CONTEXT=true` on the *parent* env
      (simulating the daemon process) before spawning the child.
- [ ] The child uses `_agent_subprocess_env()` to build its env (proves
      the helper was actually called, not just defined).
- [ ] The child attempts `e.connect()` against the live URL and fails
      non-zero with `LiveDbConnectionRefused` in stderr and the live
      port in stderr.
- [ ] Without S03 R5, this test would PASS-IN-ERROR (subprocess
      connects). Confirm by reasoning about the env state.

### 2. Strip-helper unit-test specific-value assertions

For each test in `tests/unit/test_agent_subprocess_env.py`:

- [ ] `test_strips_daemon_context_when_set`,
      `test_strips_operator_apply_when_set`, `test_strips_both_when_both_set`
      — each asserts the specific key is **absent** from the returned env,
      not just that "something was stripped".
- [ ] `test_arms_agent_context` and
      `test_overrides_inherited_agent_context_with_true` — each asserts
      the value is exactly `"true"` (string), not just truthy.
- [ ] `test_extra_dict_is_merged_after_strip_and_arm` covers the case
      where `extra` cannot accidentally re-introduce `IW_CORE_DAEMON_CONTEXT`
      via merge order — read the helper to confirm strip happens BEFORE
      `extra.update`.
- [ ] `test_does_not_mutate_real_environment` actually checks `os.environ`
      before and after by snapshotting keys/values, not just length.
- [ ] `test_build_agent_env_delegates_to_helper` proves the public
      delegator is wired correctly — without this, S03 could have left a
      stale `os.environ.copy()` body in `_build_agent_env` and most tests
      would still pass.

### 3. Guard unit-test specific-value assertions

For each of the 13 unit tests, verify:

- [ ] The assertion checks a SPECIFIC value (refusal message contains
      `"5433"`, `"IW_CORE_TEST_CONTEXT"`, `"iw migrations apply
      --i-am-operator"`), not just `pytest.raises(LiveDbConnectionRefused)`
      with no message inspection.
- [ ] The "default-allow" test (test 11) verifies the boundary case
      where no flags are set — this preserves backwards-compat for
      ad-hoc local scripts and MUST be tested.
- [ ] Operator-vs-test priority test (test 12) explicitly asserts which
      flag wins.
- [ ] `test_safe_create_engine_calls_guard_before_creating_engine` mocks
      both `assert_engine_url_allowed` and `create_engine` and verifies
      the call order. Without this, a future refactor that calls
      `create_engine` first would not be caught.

### 4. Cleanup of `test_migration_pipeline.py`

- [ ] `grep -nE "batch_id\s*=\s*42" tests/integration/test_migration_pipeline.py`
      returns ZERO matches.
- [ ] Each test that previously used `batch_id = 42` now uses the
      `unique_batch_id` fixture.
- [ ] The `unique_batch_id` fixture returns NEGATIVE values (range
      excludes real positive batch IDs).
- [ ] The fixture's hash incorporates xdist worker ID so parallel runs
      don't collide.
- [ ] Each test docstring or a one-line comment notes that the test
      "must not write to live DB; defense-in-depth via connection guard
      and mocks."
- [ ] The new operator-only smoke test (`test_no_pending_migration_log_writes…`)
      skips cleanly when `IW_CORE_OPERATOR_APPLY` is not set. Confirm
      with `pytest.skip` raising the right message.
- [ ] No new live-DB connections in the integration suite beyond the
      explicit reproduction subprocess and operator-only smoke.

### 5. Coverage of refused-context flows

- [ ] Both refused-context flags (`IW_CORE_TEST_CONTEXT`,
      `IW_CORE_AGENT_CONTEXT`) have at least one test that asserts they
      trigger refusal.
- [ ] Both allowed-context flags (`IW_CORE_OPERATOR_APPLY`,
      `IW_CORE_DAEMON_CONTEXT`) have at least one test that asserts they
      bypass refusal.
- [ ] The DEPRECATION warning for `_assert_not_agent_context` is asserted
      at least once (use `pytest.warns(DeprecationWarning)` if relevant —
      this may live in `tests/unit/test_safe_migrate.py` already; if so,
      verify it).

### 6. Test isolation

- [ ] No test in `tests/unit/test_live_db_guard.py` connects to any DB
      (real or testcontainer). All work is via `monkeypatch` + `make_url`.
- [ ] The reproduction integration test does NOT pollute the live DB —
      the subprocess is expected to FAIL before any write happens.
- [ ] The `unique_batch_id` fixture handles missing `PYTEST_XDIST_WORKER`
      gracefully (default to "main" — verify the fixture's source).

### 7. Project conventions

- [ ] Tests follow `tests/CLAUDE.md` patterns — testcontainer URL
      replacement (`postgresql+psycopg2://` → `postgresql+psycopg://`)
      where applicable.
- [ ] Test names start with `test_`.
- [ ] Markers (`@pytest.mark.integration`, `@pytest.mark.unit`) used
      consistently with the rest of the codebase.
- [ ] No `time.sleep`-based polling without explicit timeout + assertion.
- [ ] Type hints on fixture functions.

### 8. Semantic correctness across all asserts

Pick three random assertions from the new tests and ask:

> "If the function under test returned an empty / wrong / no-op value,
> would this assertion still pass?"

If yes for any of them, mark a HIGH finding and require the assertion
to be tightened.

### 9. Scope drift

- [ ] No tests added outside `tests/unit/test_live_db_guard.py`,
      `tests/unit/test_agent_subprocess_env.py`,
      `tests/integration/test_live_db_guard_reproduction.py`, and the
      cleanup + helper extraction in `tests/integration/test_migration_pipeline.py`.
- [ ] No production code changed by S05. Verify with `git diff --stat`
      that only `tests/` paths show up (plus the report file).

## Output Report

Findings list with severity (CRITICAL / HIGH / MEDIUM / LOW / INFO),
`file:line`, and a one-line verdict per item. End with overall verdict
(`PASS` / `NEEDS_FIX` / `BLOCKED`).

## Lifecycle Commands

When you START:
```bash
uv run iw step-start I-00041 --step S06
```

When you COMPLETE:
```bash
mkdir -p ai-dev/active/I-00041/reports
uv run iw step-done I-00041 --step S06 --report ai-dev/active/I-00041/reports/I-00041_S06_CodeReview_Tests_report.md
```
