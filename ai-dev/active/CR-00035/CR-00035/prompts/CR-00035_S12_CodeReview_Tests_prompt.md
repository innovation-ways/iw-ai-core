# CR-00035_S12_CodeReview_Tests_prompt

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Step Being Reviewed**: S11 (tests-impl)
**Review Step**: S12

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers (via `tests/conftest.py`) exempt. No lifecycle commands.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00035 --json`.
- `ai-dev/active/CR-00035/CR-00035_CR_Design.md` (esp. `## TDD Approach`).
- `ai-dev/active/CR-00035/reports/CR-00035_S11_Tests_report.md`.
- All files in S11's `files_changed`.
- `tests/CLAUDE.md` — HARD RULES.

## Output Files

- `ai-dev/active/CR-00035/reports/CR-00035_S12_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any new violation in S11's changed files = **CRITICAL**.

## Review Checklist

### Falsifiability (the most important check)

For each new test, mentally answer: **would this test fail if I reverted the corresponding S03 / S05 / S07 / S09 change?** If a test's assertion is too loose (e.g. only checks shape, not values), or if it asserts something true on `main`, flag it as **HIGH** with severity `testing`.

Spot-check a sample:
- `test_dead_pid_marks_job_failed_within_one_cycle` — would FAIL on main because the probe doesn't exist. Pass.
- `test_complete_writes_full_log_when_small` — would FAIL on main because `agent_output` is never populated. Pass.
- `test_log_tail_returns_last_n_lines` — would FAIL on main because the endpoint doesn't exist. Pass.

Any test that passes on main is a useless test; flag it.

### Test isolation rules (`tests/CLAUDE.md`)

- **NEVER** connect to live DB on port 5433. Verify no `localhost:5433` or `IW_CORE_DB_HOST` references in the new tests.
- **NEVER** call `importlib.reload(orch.config)`. Verify by `grep -n importlib.reload tests/`.
- **NEVER** mock the database in integration tests.
- **MUST** replace `psycopg2://` URL with `psycopg://` in any new testcontainer setup.
- **MUST** run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()` in tests that build a fresh schema.
- `DaemonEvent.metadata` → `event_metadata` Python attr. Trap.

### Coverage parity with the design

- Every AC in the design has at least one corresponding assertion. Map AC1..AC8 to specific tests; if any AC is missing coverage, flag it.

### Flake risk

- SSE / heartbeat tests use **deterministic** triggers, not `time.sleep` polling. The heartbeat test should either use an injectable interval or be marked `@pytest.mark.slow`.
- Subprocess / file-system tests use `tmp_path` and clean up.
- `os.kill` is mocked or scoped to a synthetic PID; no real process is signalled.

### Fixture hygiene

- `tests/fixtures/doc_jobs/doc_00004_replay.log` is the **actual captured** log (verify by `wc -l` ≈ 98, presence of `iw item-status 727a12bd` line).
- Synthetic fixtures (`successful_run.log`, `process_exited_early.log`) exercise distinct branches (success vs. process-exited-early).
- No fixture file is gitignored or .gitignored-by-pattern.

### Pre-existing test updates

- Any pre-existing assertion about `complete_doc_job` producing only lint_warnings has been updated, not deleted.
- `grep -rn "complete_doc_job" tests/` shows the updated assertions match the new behaviour.

## Test Verification

Run the full suite:

```bash
make test-unit
make allure-integration
```

Report results.

## Severity Levels

Standard. Falsifiability failures are HIGH or CRITICAL; flake risk is MEDIUM_FIXABLE.

## Review Result Contract

```json
{
  "step": "S12",
  "agent": "CodeReview",
  "work_item": "CR-00035",
  "step_reviewed": "S11",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
