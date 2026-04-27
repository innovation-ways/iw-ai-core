# CR-00024_S09_CodeReview_Tests_prompt

**Work Item**: CR-00024 — Step-monitor observability + per-gate timeout defaults
**Step**: S09
**Agent**: code-review-impl

---

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00024 --json` over reading workflow-manifest.json (CR-00023).
- `ai-dev/active/CR-00024/CR-00024_CR_Design.md` — design (all 7 ACs)
- `ai-dev/active/CR-00024/reports/CR-00024_S08_Tests_report.md` — including AC coverage map
- `tests/unit/test_step_monitor_get_timeout.py`
- `tests/unit/test_step_monitor_warn_50pct.py`
- `tests/integration/test_step_monitor_lifecycle.py`

## Output Files

- `ai-dev/active/CR-00024/reports/CR-00024_S09_CodeReview_Tests_report.md`

## Review Checklist

### Acceptance criteria coverage
- [ ] AC1: at least one test asserts each gate value from `QV_GATE_TIMEOUT_DEFAULTS`
- [ ] AC2: a test asserts the NULL-gate fallthrough returns 600 (the legacy default)
- [ ] AC3: a test asserts explicit `step_config["timeout_secs"]` wins over a per-gate default
- [ ] AC4: tests cover BOTH positive emission AND idempotency (post-stamp re-poll does NOT re-emit)
- [ ] AC5: a test sets up a run past 100% timeout AND verifies that `step_warning_50pct` is NOT emitted in the same poll cycle
- [ ] AC6: deferred to S15 BrowserVerification (acceptable — UI assertions need a real browser)
- [ ] AC7: a test asserts `SEVERITY_BY_TYPE["step_warning_50pct"] == "info"` AND that the event_type is in `SUBSCRIBED_EVENT_TYPES`

### Semantic correctness (per `tests/CLAUDE.md` lesson — I-00003)
- [ ] Tests verify SPECIFIC VALUES, not shape only
  - BAD: `assert "elapsed_secs" in metadata`
  - GOOD: `assert metadata["elapsed_secs"] == pytest.approx(320, abs=1)`
- [ ] Idempotency test compares a count of events (1, then still 1 after a second poll)
- [ ] Boundary test for 50% (elapsed=250, timeout=600) actually exercises the threshold (not just elapsed=200 which is far below)
- [ ] Timeout-shadowing test asserts `step_timeout` is emitted AND `step_warning_50pct` is NOT — both assertions must be present

### Test isolation
- [ ] No test depends on another test's side effects
- [ ] Each integration test uses fresh testcontainer DB state (or a transaction-rollback fixture)
- [ ] No test connects to the live orch DB (port 5433)
- [ ] No test calls `importlib.reload(orch.config)`
- [ ] No integration test mocks the database
- [ ] FTS DDL is run after `Base.metadata.create_all()` if a fresh testcontainer is created
- [ ] Time mocking uses `monkeypatch.setattr` on `datetime.now` — not `freezegun` (project convention; verify by grepping existing tests)

### Test quality
- [ ] Test names follow `test_<unit>_<scenario>_<expectation>` convention
- [ ] Each test has a docstring describing the scenario
- [ ] Common fixtures (in-memory `WorkflowStep`, `StepRun` constructors) are factored into `conftest.py` if reused across files
- [ ] No flaky patterns (sleeps, race-prone assertions)
- [ ] Parameterised tests use `@pytest.mark.parametrize` correctly

### Hard rules (carried)
- [ ] No `docker compose` invocation in test code
- [ ] No `alembic upgrade/downgrade` against live DB
- [ ] All `psycopg2` URLs replaced with `psycopg`
- [ ] mypy clean on test files
- [ ] `make lint` clean

## Findings Severity

- **CRITICAL**: a test connects to live DB; an AC has zero coverage; idempotency test re-stamps to NULL and re-runs (defeats the purpose)
- **HIGH**: shape-only assertions on metadata; missing AC5 timeout-shadowing test; signature regression test missing
- **MEDIUM**: missing edge-case coverage; flaky pattern; un-deduplicated boilerplate
- **LOW**: docstring missing, naming convention drift

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-impl",
  "work_item": "CR-00024",
  "completion_status": "complete",
  "files_reviewed": [
    "tests/unit/test_step_monitor_get_timeout.py",
    "tests/unit/test_step_monitor_warn_50pct.py",
    "tests/integration/test_step_monitor_lifecycle.py"
  ],
  "ac_coverage_assessment": {
    "AC1": "adequate|gaps:<list>",
    "AC2": "adequate|gaps:<list>",
    "AC3": "adequate|gaps:<list>",
    "AC4": "adequate|gaps:<list>",
    "AC5": "adequate|gaps:<list>",
    "AC6": "deferred-to-S15",
    "AC7": "adequate|gaps:<list>"
  },
  "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "verdict": "approved|fix-required",
  "blockers": [],
  "notes": ""
}
```
