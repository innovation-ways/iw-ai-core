# I-00098_S03_Tests_prompt

**Work Item**: I-00098 -- Keep-alive scheduler re-fires successful slots around UTC midnight (TZ mismatch in `get_due_slots`)
**Step**: S03
**Agent**: Tests

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures spawned by pytest are exempt. Read-only `docker ps` / `docker inspect` / `docker logs` is allowed.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step writes test code; do NOT run `alembic upgrade/downgrade/stamp`.

## Input Files

- **Runtime step state**: `uv run iw item-status I-00098 --json`
- `ai-dev/active/I-00098/I-00098_Issue_Design.md` — AC1/AC2/AC3 + the spec for the bug-exposing test
- `ai-dev/active/I-00098/reports/I-00098_S01_Backend_report.md` — what S01 changed
- `ai-dev/active/I-00098/reports/I-00098_S02_CodeReview_report.md` — review verdict and any open findings
- `orch/keep_alive_service.py` — post-fix `get_due_slots`
- `tests/integration/test_keep_alive_integration.py` — existing integration tests for the service (where the new tests go)
- `tests/integration/conftest.py` — `db_session`, `db_session_factory`, per-test DB clone semantics
- `tests/CLAUDE.md` — testing rules (testcontainers only, `pytest-randomly` isolation contract, no `importlib.reload`)
- `skills/iw-ai-core-testing/SKILL.md` — assertion-strength rules, RED-evidence requirement

## Output Files

- `tests/integration/test_keep_alive_integration.py` (modified — new tests appended)
- `ai-dev/active/I-00098/reports/I-00098_S03_Tests_report.md`

## Context

You are writing the regression net for I-00098 — the TZ-mismatch bug in `orch.keep_alive_service.get_due_slots`. The Backend fix (S01) is in place. Your job is to add **integration tests** that:

1. Would have FAILED against pre-fix code (RED — captured by manually reverting only the predicate change and re-running, or by reasoning from the design spec).
2. PASS against the post-fix code (GREEN — your final state).
3. Cover the bug across multiple local-TZ offsets, not only the one the bug was first observed in.

The bug is fundamentally about SQL evaluation semantics on a `TIMESTAMPTZ` column. **A mocked unit test cannot reproduce it.** All new tests live in `tests/integration/test_keep_alive_integration.py`.

## Requirements

### 1. Bug-exposing test (MANDATORY)

Add a new test `test_get_due_slots_skips_already_run_slot_across_utc_midnight` to `tests/integration/test_keep_alive_integration.py`. It must:

- Use the testcontainer-backed `db_session` fixture (NOT mocks; see `tests/CLAUDE.md` rule #3).
- Use `freezegun.freeze_time` to pin Python's clock to **a local-midnight UTC-mismatch instant** (e.g., `datetime(2026, 5, 18, 0, 30, 0)` — at 00:30 local, a +01:00 host sees 23:30 UTC May 17, so local-date ≠ UTC-date).
- Seed a `KeepAliveConfig` + `KeepAliveSlot` with `time_hhmm` inside the trailing-30-min window (e.g., `"00:15"`).
- Write a `KeepAliveRun(status='success', slot_time='00:15')` for that slot, **and then deterministically re-stamp `fired_at`** to an explicit `TIMESTAMPTZ` instant that lies "earlier today (operator local time) but on the previous UTC calendar day". For the +01:00 host example: re-stamp `fired_at` to `datetime(2026, 5, 17, 23, 30, tzinfo=UTC)` (= `00:30 Europe/Lisbon May 18` local, = `23:30 UTC May 17`). Mechanism: call `log_run(db_session, slot.id, "00:15", "success")` (which uses the server default `func.now()` — production code path), `flush`, then issue an explicit `UPDATE keep_alive_runs SET fired_at = :ts WHERE id = :run_id` with the chosen instant. This is the **only** reliable way to make the test reproduce the bug — `func.now()` is server-side and `freezegun` cannot freeze it, so leaving `fired_at` as the real wall-clock UTC makes the test wall-clock-dependent (it passes pre-fix whenever the suite happens to run far enough from local midnight, which hides the bug).
- Call `get_due_slots(db_session)` and assert it returns `[]`.

The test must be wall-clock independent (the freeze + the re-stamp together enforce that). Annotate the test docstring with a one-line note explaining the pre-fix behaviour ("returned the slot because `func.date(fired_at)` was UTC and `today_date` was local").

**Why re-stamp instead of leaving `func.now()` alone**: To trigger the bug pre-fix, `func.date(fired_at)` (UTC) must differ from `today_date` (local). `today_date` is frozen by `freezegun`; `fired_at` is **not** unless you set it explicitly. A bare `log_run()` lets the DB stamp `fired_at` with the actual current UTC instant, which on most CI clocks lands on the same UTC date as the frozen local date — so the pre-fix filter matches, the slot is correctly skipped, and the test passes pre-fix (no RED). Re-stamping after the insert preserves the production write path (we call `log_run()` exactly as production does) AND gives us a deterministic instant the bug actually depends on.

### 2. Parametrized TZ-offset coverage (MANDATORY)

Add `@pytest.mark.parametrize` cases — either as a separate test or as parameters to the bug-exposing one — covering at minimum these local-TZ scenarios:

1. **UTC host** — local TZ = UTC. Expectation: no mismatch window, slot is correctly skipped (this case should pass on both pre-fix and post-fix code; it's a non-regression control).
2. **+01:00 host (WEST DST)** — the original failing scenario; slot must be skipped post-fix.
3. **+02:00 host (CEST / Tokyo-ish)** — wider mismatch window; slot must be skipped post-fix.
4. **Negative offset host** — e.g., `-05:00` (US East). Verify the predicate is symmetric: at a local time that's still in the previous UTC calendar day, a same-local-day successful run still skips the slot.

Use `freezegun.freeze_time` with the `tz_offset=` parameter (in hours) OR manually patch `datetime.now().astimezone().tzinfo` if `freeze_time` doesn't propagate the offset to `astimezone()`. **Verify your approach works** — naïve `freeze_time` does NOT change `astimezone()`'s tz lookup; you may need to additionally `monkeypatch.setenv("TZ", "Europe/Lisbon")` and call `time.tzset()` on Linux. Pick whichever pattern produces a deterministic test that actually exercises the bug.

If you cannot find a way to exercise all four TZ variants deterministically, drop variants you can't make reliable AND record the gap in your report's `notes` (do NOT ship a flaky parametrize set).

### 3. No regression in existing tests

After writing your tests, run:

```bash
uv run pytest tests/integration/test_keep_alive_integration.py -v --no-cov
```

All existing tests in that file MUST still pass. If any breaks because of a tz interaction you introduced (e.g., `TZ` env-var leaking out of a parametrize variant), fix the leak.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For this incident specifically:

- BAD: `assert isinstance(get_due_slots(db_session), list)` — passes pre- and post-fix.
- BAD: `assert len(get_due_slots(db_session)) < 2` — could pass pre-fix accidentally.
- BAD: relying on bare `func.now()` for `fired_at` — passes pre-fix whenever the suite runs at a UTC-date matching the frozen local-date (i.e., almost always), hides the bug.
- GOOD: `assert get_due_slots(db_session) == []` after re-stamping `fired_at` to a deterministic earlier-today-local / yesterday-UTC instant — fails pre-fix when the slot leaks through, passes post-fix.
- GOOD: assertions on `KeepAliveRun` row count: `assert db_session.query(KeepAliveRun).count() == 1` (only the pre-seeded one) when verifying poller-level behaviour, if you add a poller-level test.

## Project Conventions

Read `tests/CLAUDE.md`:

- Testcontainers only — no live DB.
- No `importlib.reload(orch.config)`.
- Per-test PostgreSQL template-clone via `pgtestdbpy` — your tests must work under any random pytest-randomly seed (run a couple of seeds to confirm).
- `db_session` and `db_session_factory` share a connection; writes are visible across both.

## TDD Requirement

This is a `tests-impl` step. Per the implementation prompt template, the runtime-RED-check is **NOT** required (the design-time human authored the spec; you author the regression net). However:

1. Run the new tests against the **post-fix** code — they MUST be GREEN.
2. Reason in your report (`tdd_red_evidence` field) about whether each new test would have failed against pre-fix code. For the bug-exposing test, quote the expected pre-fix output ("`get_due_slots(db) == [<slot>]` — returns the slot because the date filter mismatches"). For TZ-variant controls (e.g., UTC), state "would have passed pre-fix — non-regression control" — that's a fine entry, not a defect.

Do NOT `git checkout HEAD~1 -- orch/keep_alive_service.py` or otherwise revert files mid-step. That's the explicit anti-pattern in the prompt template.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — auto-fix; re-stage if it changes the file.
2. `make typecheck` — zero errors on the test file.
3. `make lint` — zero errors.

Record in the `preflight` block.

## Test Verification (NON-NEGOTIABLE)

Run **only** your new test file:

```bash
uv run pytest tests/integration/test_keep_alive_integration.py -v --no-cov
```

Run twice with different `--randomly-seed=` values (e.g., `12345` and `67890`) to confirm no order-dependence.

Do NOT run `make test-integration` or `make test-unit` — owned by S11/S12.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00098",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/test_keep_alive_integration.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (tests/integration/test_keep_alive_integration.py)",
  "tdd_red_evidence": "test_get_due_slots_skips_already_run_slot_across_utc_midnight — would fail pre-fix with `assert [<slot>] == []` (slot leaks through because func.date(fired_at) UTC != today_date local); plus N tz-variant cases (UTC = non-regression control, +01:00 + +02:00 + -05:00 = regression coverage). Verified under randomly-seed=12345 and 67890.",
  "blockers": [],
  "notes": ""
}
```
