# I-00034_S04_CodeReview_Tests_prompt

**Work Item**: I-00034 -- Item view step Duration is incorrect when a step goes through retries or fix cycles
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

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

- `ai-dev/active/I-00034/I-00034_Issue_Design.md` -- Design document
- `ai-dev/active/I-00034/reports/I-00034_S03_Tests_report.md` -- S03 test-writing report
- All test files listed in S03's `files_changed`
- `tests/CLAUDE.md` -- test framework rules, testcontainer policy, N+1 policy

## Output Files

- `ai-dev/active/I-00034/reports/I-00034_S04_CodeReview_Tests_report.md` -- Review report

## Context

You are reviewing the test work from S03. The tests must (a) prove the bug exists by FAILING on pre-fix code, (b) prove the fix works by PASSING on post-fix code, (c) verify SEMANTIC correctness (specific expected values), not shape, and (d) guard against N+1 regressions.

Read the design document and the S03 report to understand what tests were written and why. Then read the tests themselves.

## Review Checklist

### 1. Reproduction test FAILS on pre-fix code (CRITICAL)

- Did S03's report include `reproduction_test_red_verified: true`? If no, that's a CRITICAL finding.
- Re-verify it yourself if possible: temporarily revert `dashboard/routers/items.py` and confirm `test_I00034_step_duration_spans_first_run_to_last_completion` fails with `assert 30.0 == pytest.approx(630)` (or equivalent). Restore the file before finishing your review.
- The test must FAIL for the right reason — because duration is truncated to the last iteration, NOT because of a fixture bug, import error, or unrelated assertion.

### 2. Semantic correctness (CRITICAL — I003 lesson)

For each test, verify assertions match SPECIFIC expected values, not shape:

- BAD: `assert duration_secs is not None` — returns 30 on pre-fix code, also not-None
- BAD: `assert duration_secs > 0` — 30 > 0 on pre-fix code too
- BAD: `assert duration_secs > 60` — might still pass under some bug configurations
- BAD: `assert "duration_secs" in step_dict` — pure shape
- GOOD: `assert duration_secs == pytest.approx(630)` — exact semantic match
- GOOD: `assert started_at == datetime(2026, 4, 22, 12, 0, 0, tzinfo=UTC)` — exact semantic match
- GOOD: `assert duration_secs > 2*60 + 6*60 + 30` — semantic, proves gaps between iterations are included (this is on TOP of the exact assertion, not instead of it)

Any test that relies solely on shape-level assertions is a CRITICAL finding.

### 3. Test scope coverage (HIGH)

Verify tests exist for:

- [ ] Multi-run + fix-cycle aggregation (the core case) — `test_I00034_step_duration_spans_first_run_to_last_completion`
- [ ] Total duration of the item — `test_I00034_total_duration_spans_full_item`
- [ ] Happy path (single run, no retries, no regression) — `test_I00034_happy_path_single_run_duration_unchanged`
- [ ] In-progress step (duration_secs is None, but started_at is the aggregated earliest) — `test_I00034_in_progress_step_returns_none_duration_and_aggregated_start`
- [ ] Never-launched step (both None) — `test_I00034_never_launched_step_duration_is_none`
- [ ] Query-count / N+1 guard — `test_I00034_get_steps_query_count_is_bounded`

Missing any of the first five is HIGH. Missing the query-count guard is MEDIUM_FIXABLE (the N+1 constraint is clear in `tests/CLAUDE.md` so the guard should exist).

### 4. Testcontainer compliance (CRITICAL)

- Tests use testcontainer-backed DB (port is dynamic, not 5433). No `IW_CORE_DB_PORT=5433` hardcoding. No imports from a live-DB config.
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` run after `Base.metadata.create_all()` if the test-scaffolding requires it (likely inherited from `tests/conftest.py` fixtures).
- No `importlib.reload(orch.config)` — `monkeypatch.delenv` pattern instead if env manipulation is needed.
- No `unittest.mock` replacing the DB — the whole point is exercising real `MIN` / `MAX` aggregation.

### 5. Test isolation (MEDIUM)

- Each test gets a clean DB state (no cross-test pollution — the existing `db_session` fixture should handle this; verify)
- No sleep-based timing — timestamps are deterministic fixtures, not `datetime.now()`
- No reliance on test execution order

### 6. Helper unit test coverage (MEDIUM_FIXABLE if helper exists but is untested)

- If S01 extracted an aggregation helper AND S03 added a unit test file, verify the unit tests cover empty input, `StepRun`-only, `FixCycle`-only, union, and mixed-null cases.
- If S01 extracted a helper but S03 did NOT add a unit test, flag MEDIUM_FIXABLE.

### 7. Fixture convention consistency (MEDIUM)

- Tests use project factories (`project_factory`, `work_item_factory`, etc.) if they exist in `tests/conftest.py`
- If S03 created new local factories, verify they're minimal and don't duplicate global fixtures

### 8. Zero test regressions elsewhere (CRITICAL)

- Running `make test-unit` and `make test-integration` must show zero failures across the whole suite — not just the new module.
- If any pre-existing test was modified, verify the change is justified (e.g. the test encoded the buggy behaviour) and carries a comment explaining why.

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `make test-unit` — zero failures
2. Run `make test-integration` — zero failures (include the new module)
3. Run `make lint` — zero errors
4. Record the exact number of queries S03 pinned for `_get_steps` in your notes

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Shape-only assertions, reproduction test doesn't actually fail on pre-fix code, testcontainer bypass, DB mocking, pre-existing test regressions | Must fix |
| **HIGH** | Missing a core test case from the list in section 3, broken fixture, incorrect expected values | Must fix |
| **MEDIUM (fixable)** | Missing query-count guard, missing helper unit test, convention drift | Should fix |
| **MEDIUM (suggestion)** | Better fixture reuse, naming improvement | Optional |
| **LOW** | Nitpick, minor readability | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00034",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "tests/integration/dashboard/test_items_duration.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only when zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
- `mandatory_fix_count`: Count of CRITICAL + HIGH + MEDIUM_FIXABLE findings.
