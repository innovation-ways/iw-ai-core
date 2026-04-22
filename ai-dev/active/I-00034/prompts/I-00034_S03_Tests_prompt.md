# I-00034_S03_Tests_prompt

**Work Item**: I-00034 -- Item view step Duration is incorrect when a step goes through retries or fix cycles
**Step**: S03
**Agent**: Tests

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00034/I-00034_Issue_Design.md` -- Design document (read the **Test to Reproduce**, **Acceptance Criteria**, and **TDD Approach** sections first)
- `ai-dev/active/I-00034/reports/I-00034_S01_Backend_report.md` -- S01 implementation report
- `dashboard/routers/items.py` -- file modified by S01
- `tests/CLAUDE.md` -- test framework, fixtures, testcontainer rules, N+1 rules
- `tests/conftest.py` -- existing fixtures (`project_factory`, `work_item_factory`, step/run/cycle factories if they exist)

## Output Files

- `tests/integration/dashboard/test_items_duration.py` -- new (or extend an existing dashboard test module if one exists and conventions dictate that)
- Possibly `tests/unit/dashboard/test_items_duration_helper.py` if S01 extracted a pure aggregation helper worth unit-testing in isolation
- `ai-dev/active/I-00034/reports/I-00034_S03_Tests_report.md` -- Step report

## Context

You are writing the reproduction test and regression tests for the Item view duration bug. The bug: per-step **Duration** and the header **Total Time** metric card display only the final successful iteration's wall time, because the dashboard reads `WorkflowStep.started_at` / `completed_at` which are reset on each retry/fix-cycle. The fix (S01) aggregates from the append-only `step_runs` ∪ `fix_cycles` tables.

Your job: prove the bug exists (RED against pre-fix code), prove the fix works (GREEN against current code), prevent regressions, and prevent N+1 regressions.

Read `ai-dev/active/I-00034/I-00034_Issue_Design.md` end-to-end, then `tests/CLAUDE.md` and `tests/conftest.py`.

## Requirements

### 1. Reproduction test (MANDATORY) — `test_I00034_step_duration_spans_first_run_to_last_completion`

Write an integration test that:

- Seeds ONE `WorkflowStep` via testcontainer-backed DB.
- Seeds TWO `StepRun` rows for that step:
  - `run_number=1`, `status=failed`, `started_at=2026-04-22 12:00:00Z`, `completed_at=2026-04-22 12:02:00Z` (2 minutes)
  - `run_number=2`, `status=completed`, `started_at=2026-04-22 12:10:00Z`, `completed_at=2026-04-22 12:10:30Z` (30 seconds)
- Seeds ONE `FixCycle` row for that step: `cycle_number=1`, `started_at=2026-04-22 12:03:00Z`, `completed_at=2026-04-22 12:09:00Z` (6 minutes).
- Sets `WorkflowStep.started_at = 2026-04-22 12:10:00Z` and `WorkflowStep.completed_at = 2026-04-22 12:10:30Z` (simulating the daemon's buggy-but-existing state after the last retry — pre-fix these are the values the dashboard reads; post-fix they should be ignored).
- Calls `dashboard.routers.items._get_steps(project.id, item.id, db_session)`.
- Asserts `target.duration_secs == pytest.approx(630)` — exactly 10 minutes 30 seconds (from 12:00:00 to 12:10:30), including the 1-minute gap between run1 end and cycle start, the 1-minute gap between cycle end and run2 start.
- Asserts `target.started_at == datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC)` — the earliest start, not the last-iteration start.
- Asserts `target.completed_at == datetime(2026, 4, 22, 12, 10, 30, tzinfo=UTC)` — the latest completion.

**CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)**

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert target.duration_secs is not None` (shape only — the bug returns 30 which is also not-None)
- BAD: `assert target.duration_secs > 0` (shape only — 30 > 0 also passes)
- BAD: `assert target.duration_secs > 60` (still passes for a 2-minute last-run case that masks the bug)
- GOOD: `assert target.duration_secs == pytest.approx(630)` (semantic — verifies the exact aggregated span)
- GOOD: `assert target.duration_secs > 2 * 60 + 6 * 60 + 30` (semantic — verifies the fix INCLUDES the between-iteration gaps, not just the sum of run+cycle wall times; note: 630 > 510 so a "sum without gaps" buggy fix would also fail this)

Your assertions MUST be of the GOOD variety.

### 2. Total duration companion — `test_I00034_total_duration_spans_full_item`

Same fixture shape as Requirement 1. Call `dashboard.routers.items._get_metrics(project.id, item.id, steps, db_session)`. Assert `metrics.total_duration_secs == pytest.approx(630)` (when the single step's aggregated span IS the full item span, because the other steps are pending/not-started and therefore contribute `None` start/end).

If the item has synthetic setup/merge steps that DO contribute timestamps (because `BatchItem.started_at` / merged_at are set in the fixture), adjust the expected value accordingly — but the **point** of this test is that the total includes the pre-last-iteration history.

### 3. Happy-path regression test — `test_I00034_happy_path_single_run_duration_unchanged`

Seed a step that ran exactly once (one `StepRun`, no `FixCycle`), `started_at=T0`, `completed_at=T0+45s`. Set `WorkflowStep.started_at=T0`, `completed_at=T0+45s` (consistent). Assert `target.duration_secs == pytest.approx(45)`. This is the regression guard — confirms the fix doesn't break happy-path items.

### 4. In-progress regression test — `test_I00034_in_progress_step_returns_none_duration_and_aggregated_start`

Seed a step with ONE `StepRun` currently running: `started_at=T0`, `completed_at=None`. Seed ALSO one earlier failed `StepRun`: `started_at=T0-600s`, `completed_at=T0-300s`. Assert:

- `target.duration_secs is None` (so the template renders `—`, unchanged from before the fix)
- `target.started_at == T0 - 600` (aggregated earliest start — so the "Started" column in the step table reflects the true first-launch time, not the last-iteration start)

### 5. Never-launched regression test — `test_I00034_never_launched_step_duration_is_none`

Seed a step that has `status=pending` and zero `StepRun`s and zero `FixCycle`s. Assert `target.duration_secs is None` and `target.started_at is None`.

### 6. Query-count regression (N+1 guard) — `test_I00034_get_steps_query_count_is_bounded`

Using SQLAlchemy's event listener OR the project's existing query-counting fixture (check `tests/conftest.py` — CR-00013 introduced query-count assertions), seed a `WorkflowStep` count of N=10. Assert that `_get_steps` issues at most a small constant number of queries (≤ the number S01's implementation actually uses — pin to the concrete number so future regressions trip the test). If `tests/conftest.py` does NOT already have a query-counter fixture, use `sqlalchemy.event.listens_for(engine, "before_cursor_execute")`.

If this exact pattern is inconvenient given the current fixture setup, substitute an equivalent scalable check (e.g. assert the aggregation is called via `GROUP BY` by inspecting the query via logging, or rely on CR-00013's `assert_no_n_plus_one` helper if it exists). Pick the closest match.

### 7. Unit test for aggregation helper (if S01 extracted one)

If S01's report lists a new helper (e.g. `_aggregate_step_spans(db, step_db_ids)`), add `tests/unit/dashboard/test_items_duration_helper.py` that exercises:

- Empty `step_db_ids` → returns `{}` with zero queries
- Steps with only `StepRun` rows → correct `(min, max)` per step
- Steps with only `FixCycle` rows → correct `(min, max)` per step
- Steps with both → correct `(min, max)` across the union
- Steps with a run that has `completed_at=None` → the step's aggregate end is `None` (signalling in-flight)
- Multiple steps in one call → per-step aggregation is correctly bucketed by `step_id`

If S01 did NOT extract a helper, skip this requirement — the integration tests cover the logic.

## Project Conventions

Read `tests/CLAUDE.md` for:

- Testcontainer-only policy — NEVER connect to live DB (port 5433). Use the `postgres_container` / `db_session` fixtures from `tests/conftest.py`.
- MUST run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` (if the project-scaffolding fixture doesn't already do it, follow the pattern in existing integration tests).
- `DaemonEvent.metadata` → `event_metadata` in Python (unlikely to hit this test, but know it).
- Use existing factories (`project_factory`, `work_item_factory`, `workflow_step_factory`, `step_run_factory`, `fix_cycle_factory`) if they exist; if they don't, create minimal versions in the test module rather than modifying global fixtures.

Do NOT mock the database. Do NOT use live DB. Do NOT disable FTS. Follow the patterns used by the existing `tests/integration/dashboard/` tests.

## TDD Requirement

Your tests MUST fail against the pre-fix code and pass against the post-fix code. Verify this explicitly:

1. `git stash` the S01 change (or `git checkout HEAD~1 -- dashboard/routers/items.py` to temporarily revert)
2. Run your new tests — the reproduction test MUST FAIL (duration comes back as 30s, not 630s)
3. Restore S01's change — `git stash pop` or re-checkout
4. Run your new tests — they MUST all pass

Record in your report: "Reproduction test failed as expected against pre-fix code: assert 30.0 == pytest.approx(630) failed; passed against post-fix code."

## Test Verification (NON-NEGOTIABLE)

After writing tests:

1. Run `make test-integration` — zero failures in the new module AND zero regressions in pre-existing modules
2. Run `make test-unit` — zero failures
3. Run `make lint` — zero errors
4. Run `uv run mypy tests/` (if mypy is configured for tests; otherwise skip)
5. Do NOT report `tests_passed: true` unless all of the above succeed

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "I-00034",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/dashboard/test_items_duration.py"
  ],
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "reproduction_test_red_verified": true,
  "blockers": [],
  "notes": ""
}
```

- `reproduction_test_red_verified`: `true` only if you explicitly verified the reproduction test FAILS against pre-fix code.
- `notes`: Record the exact query count you observed for `_get_steps` (to pin future N+1 regressions), and whether you wrote a unit test for an S01 helper.
