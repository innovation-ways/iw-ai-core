# I-00063_S03_Tests_prompt

**Work Item**: I-00063 — Daemon Phase 2 migration apply self-deadlocks against its own idle-in-transaction session
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state. Testcontainer fixtures
spun up by pytest are the only exception (they self-label and
self-destruct via Ryuk).

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against the live
orch DB (port 5433). Tests may run alembic against testcontainer URLs
freely — that's the whole point.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00063 --json`
- `ai-dev/active/I-00063/I-00063_Issue_Design.md` — Design (read **Test to Reproduce**, **Acceptance Criteria** AC1-AC5, and **TDD Approach** sections in particular)
- `ai-dev/active/I-00063/reports/I-00063_S01_Backend_report.md` — S01 report (which approach was chosen for each trade-off)
- `ai-dev/active/I-00063/reports/I-00063_S02_CodeReview_report.md` — S02 review (any deferred-to-tests items)
- `tests/CLAUDE.md` — test patterns (REQUIRED reading; many gotchas around testcontainers, FTS triggers, FOR UPDATE)
- All files in S01's `files_changed`

## Output Files

- `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py` (new)
- `tests/integration/db/test_safe_migrate_self_blocker.py` (new — covers `_assert_no_self_blockers` and `lock_timeout` wiring)
- Possibly additional unit tests in `tests/unit/` if cleanly testable in isolation
- `ai-dev/active/I-00063/reports/I-00063_S03_Tests_report.md` — Step report

## Context

S01 has implemented the fix. Your job is to write the tests that prove
it works AND prevent regression. The reproduction test is the
load-bearing one — it must FAIL against the pre-S01 code (verify by
`git stash` of S01's diff, run the test, see it time out, then unstash
and confirm it passes).

The design doc's **Test to Reproduce** section sketches the
reproduction test; treat it as a starting point, not a finished
implementation. Adapt it to whatever signal S01 actually exposes
(`SelfBlockerError`, `lock_timeout`, etc.) per S01's report.

## Requirements

### 1. Reproduction integration test (AC2, primary deliverable)

Create `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py`:

- Uses the project's standard testcontainer fixture (read
  `tests/conftest.py` — likely `pg_container_url` or similar).
- Apply the migration chain to **head minus one** so there is exactly
  one pending migration that takes `AccessExclusiveLock` on a busy
  table. Pick a migration in the chain that ALTERs `batch_items` if
  one exists, OR add a synthetic test-only migration in a
  `versions/` directory that the test points alembic at (avoid
  modifying the real migration chain).
- In the test body:
  1. Open an outer `Session`, run a `SELECT` on `batch_items` that
     acquires `AccessShareLock`. Do NOT commit/close — leave it idle
     in transaction.
  2. Invoke `safe_migrate.apply(testcontainer_url, batch_id=None)`
     in a separate thread (so the test can time out instead of
     hanging the suite).
  3. Assert the call returns within 45s (well under the 60s
     `pytest.mark.timeout`).
  4. Assert the result is either successful (if S01's session
     discipline made the test scenario impossible to trigger via
     normal flow — but the synthetic test bypasses `_merge_item`
     and calls `safe_apply` directly while holding the lock) OR
     failed with a clear error (`SelfBlockerError` or
     `lock_timeout`).
  5. Always rollback and close the outer session in a `finally` so
     the testcontainer can be cleaned up.

```python
@pytest.mark.integration
@pytest.mark.timeout(60)
def test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock(
    pg_container_url, alembic_at_head_minus_one, seeded_batch_item
):
    """Reproduces I-00063: apply() must not hang when caller holds a
    share lock on a table the migration alters.

    Pre-fix: hangs indefinitely. Post-fix: completes within 45s, either
    succeeding (if disciplined session lifecycle made this
    impossible — but the test forces the bad state synthetically) or
    failing with SelfBlockerError / lock_timeout."""
    # Implementation per design doc Test to Reproduce section + S01
    # report's actual exception/error class names.
```

### 2. `_merge_item` session-lifecycle regression test (AC1)

Add a test that exercises the **fixed** code path end-to-end:

- Spin a testcontainer at a migration head where a pending migration
  ALTERs `batch_items` (or a smaller stand-in table).
- Drive `_merge_item` (or whatever entry point S01's session-discipline
  fix lives in) through the merge → apply transition.
- Assert no hang, migration applies, daemon continues.

If `_merge_item` is too coupled to the worktree subprocess to test
in isolation, add a fixture that mocks `worktree_commit.sh` to a
no-op and asserts the session-lifecycle invariant: after `db.commit()`
+ `db.close()` and before `run_post_merge_apply`, the session must
NOT hold `AccessShareLock` on `batch_items`. Verify by querying
`pg_locks` from a separate connection.

### 3. `_assert_no_self_blockers` happy/error tests (AC4)

Create `tests/integration/db/test_safe_migrate_self_blocker.py`:

- **Happy path**: clean DB, no other connections in `idle in
  transaction`. `_assert_no_self_blockers(...)` returns cleanly.
- **Detection path**: open a second session via
  `psycopg.connect(...)`, run a `SELECT` on the target table, leave
  it idle. Call `_assert_no_self_blockers(...)` — must raise
  `SelfBlockerError` (or whatever S01 named it) with a message that
  names the relation.
- **False-positive resistance**: another connection holding a lock
  on a **different** table must NOT cause `_assert_no_self_blockers`
  to raise.
- **Same-process check robustness**: if S01's signal is
  `application_name`, set `application_name=iw-ai-core-daemon-main`
  on the blocking session and confirm detection. With a different
  `application_name`, confirm no false positive.

### 4. `lock_timeout` wiring test (AC3)

In the same file:

- Verify `SET lock_timeout = '30s'` is actually issued on the apply
  connection. The cleanest way: use a `psycopg` connection to
  `SHOW lock_timeout` after the apply has connected (catch via a
  `connect` event hook in test code, or run a no-op alembic upgrade
  and inspect logs).
- Verify `IW_CORE_MIGRATION_LOCK_TIMEOUT_SECS` env var is honored.
  Test with `5` (small) and `0` (disabled).
- Verify a synthetic blocker that's NOT same-process (i.e. a
  separate test connection holding the share lock, with an
  `application_name` that doesn't match the daemon) causes apply
  to fail with `lock_timeout` after ~5s when the env var is set
  to 5.

### 5. `pending_migration_log` audit test (AC5)

- After a `SelfBlockerError`-induced apply failure, query
  `pending_migration_log` and assert a row exists with
  `phase='apply'`, `success=false`, and a non-empty `error_message`
  matching the expected pattern.
- Same for `lock_timeout`-induced failure.

### 6. Rollback-fires-after-apply-failure test (AC1 end-to-end)

AC1 promises that on a Phase 2 failure the daemon "fails fast (within
~30s) with a clear error that triggers Phase 3 rollback rather than a
silent hang." Add one integration test that exercises this transition
end-to-end through `_merge_item` (or the closest entry point that
composes apply + rollback):

- Drive the merge path to the point of `run_post_merge_apply` with a
  setup that forces apply to fail (e.g. `lock_timeout` triggered by a
  separate-process synthetic blocker, or a monkeypatched
  `safe_migrate.apply` that returns `ApplyResult(success=False, ...)`).
- Assert `run_rollback` is invoked (spy/monkeypatch) with the correct
  `batch_id`.
- Assert a `migration_pipeline` `DaemonEvent` row is written via a
  fresh session (regression on the lifecycle fix — proves S01 didn't
  reuse the closed `db`).
- Assert the daemon does not hang and continues past `_merge_item`.

The point is to catch a regression where S01's session-discipline fix
breaks the post-apply bookkeeping — `db` is closed, then the failure
branch tries to use it without reopening, and silently throws or
loses the `migration_pipeline` event.

### 7. Test placement and naming

- Integration tests with testcontainer: `tests/integration/...`
- Unit tests (no testcontainer): `tests/unit/...`
- Filenames: `test_i_00063_*.py` or `test_phase2_apply_*.py` —
  match existing convention in the directory.
- All tests use `@pytest.mark.integration` if they need a
  testcontainer. Add `@pytest.mark.timeout(60)` to any test that
  could hang on a regression.

## CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is
non-empty) and passed. But the bug was NOT fixed. Tests must verify
SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For I-00063 specifically:

- BAD: `assert result is not None` (shape — anything non-None passes)
- GOOD: `assert result.success is True` (semantic — explicit success)
- GOOD: `assert "self-blocker" in result.error_message.lower() or "lock_timeout" in result.error_message.lower()` (semantic — verifies the specific failure reason, not just "some failure")
- BAD: `assert lock_timeout_set` (shape — the variable just being set means nothing)
- GOOD: query `SHOW lock_timeout` from a connection that runs through the apply path and assert it returns `'30s'` (semantic — verifies the actual postgres setting)
- BAD: `assert pending_migration_log_row is not None`
- GOOD: `assert pending_migration_log_row.success is False and "self-blocker" in pending_migration_log_row.error_message.lower()`

For lock detection tests, query `pg_locks` and assert the **exact**
relation/mode you expect, not just "some lock exists".

## Project Conventions

Read `tests/CLAUDE.md`:

- **NEVER** connect tests to live DB (port 5433). Use testcontainers.
- **NEVER** call `importlib.reload(orch.config)` — use
  `monkeypatch.delenv()` instead.
- **MUST** replace psycopg2 URLs in testcontainer URLs:
  `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after
  `Base.metadata.create_all()` if your test needs FTS.
- `DaemonEvent.metadata` is `event_metadata` in Python.

### Rule 4a exception (alembic in test code)

`tests/CLAUDE.md` rule 4a says "NEVER invoke alembic directly from
test code outside of dedicated migration round-trip tests." This
reproduction test IS a dedicated migration test — it specifically
exercises the apply path through `safe_migrate.apply` against a
testcontainer. That qualifies as the rule's exception.

Constraints that still apply:

- Do NOT modify the real migration chain in `orch/db/migrations/versions/`.
  If you need a synthetic DDL that ALTERs `batch_items`, put it in a
  test-only `versions/` directory and point alembic at it via a
  test-only `alembic.ini` or a programmatic `Config` (see how
  `orch/db/safe_migrate._build_alembic_config` constructs config).
- If you downgrade in any test, downgrade to a **specific revision ID**,
  never `-1` (that breaks when new migrations land).
- Use the existing `pg_container` / `db_engine` fixtures in
  `tests/integration/conftest.py` rather than spinning up a new
  testcontainer per test.

Note: the design doc's `Test to Reproduce` snippet uses fixture names
(`pg_container_url`, `alembic_at_head_minus_one`, `seeded_batch_item`)
that don't exist in the repo. Treat those as illustrative; build on
the real fixtures.

### Existing fixtures you can reuse

- `pg_container` (session scope) — the testcontainer itself.
- `db_engine` (session scope) — engine bound to the testcontainer with
  schema + FTS triggers already applied.
- `db_session` (function scope) — transactional session that rolls
  back on teardown.
- `db_session_factory` — sessionmaker on the same connection so
  background services see test writes.
- `test_project` — pre-seeded `Project` row.

Match the test style in adjacent files (`tests/integration/daemon/`
for daemon tests, `tests/integration/db/` for DB-layer tests).

## TDD Verification

After writing tests, **prove the reproduction test catches the bug**:

1. `git stash` S01's diff (carefully — keep your S03 test diff
   untouched if possible; use `git stash --keep-index` after staging
   your tests).
2. Run `pytest tests/integration/daemon/test_phase2_apply_no_self_deadlock.py -v`.
3. Confirm it FAILS (times out or asserts).
4. `git stash pop`.
5. Re-run the test.
6. Confirm it PASSES.

Document the before/after results in your report. If the test passes
on the unfixed code, your test is too lenient — sharpen it.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — must be clean.
2. `make typecheck` — zero errors involving your new test files.
3. `make lint` — zero errors.

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit` — must pass.
2. Run `make test-integration` — must pass, including your new tests.
3. Run your reproduction test against the pre-fix code (per TDD
   verification above).
4. Do **NOT** report `tests_passed: true` unless all suites pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00063",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/daemon/test_phase2_apply_no_self_deadlock.py",
    "tests/integration/db/test_safe_migrate_self_blocker.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_green_verified": true,
  "blockers": [],
  "notes": "Document the before/after of the TDD verification (stash + retest). Cite specific test names and pytest output. If any test was downgraded from semantic to shape because the underlying primitive isn't observable, explain why and propose a follow-up."
}
```

- `tdd_red_green_verified` is mandatory for this step. Set to `true`
  only if you actually performed the stash/retest dance.
- If you could not stash cleanly (e.g. S01 and S03 diffs entangle on
  the same file lines), describe the alternative verification you
  used (e.g. running the test against a `git checkout HEAD~1` of the
  S01 files in a temp dir).
