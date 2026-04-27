# CR-00024_S08_Tests_prompt

**Work Item**: CR-00024 — Step-monitor observability + per-gate timeout defaults
**Step**: S08
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

In tests, the only allowed docker usage is via testcontainers fixtures (which
self-label and self-destruct via Ryuk). NEVER stop/remove containers from test
teardown. NEVER invoke `docker compose` from test code.

## ⛔ Tests must NOT connect to the live orch DB

Every DB-touching test must use the testcontainer-backed fixtures from
`tests/conftest.py`. The conftest sets `IW_CORE_TEST_CONTEXT=true` which
arms the live-DB guard from I-00041 — do not bypass.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00024 --json` over reading workflow-manifest.json (CR-00023).
- `ai-dev/active/CR-00024/CR-00024_CR_Design.md` — design (all 7 ACs, "TDD Approach" section)
- All prior step reports (S01–S07)
- `tests/conftest.py` — fixture patterns
- `tests/CLAUDE.md` — testing rules

## Output Files

- `tests/unit/test_step_monitor_get_timeout.py` — new
- `tests/unit/test_step_monitor_warn_50pct.py` — new
- `tests/integration/test_step_monitor_lifecycle.py` — new
- `ai-dev/active/CR-00024/reports/CR-00024_S08_Tests_report.md`

## Context

This step writes the formal regression coverage. Each test maps to one or more
acceptance criteria. Use TDD: write the test expecting the new behavior, run it
(RED), then verify implementation already makes it pass (GREEN — since S01–S05
have shipped). If a test fails for a reason other than "implementation not yet
present", that is a real bug — capture in your report.

## Required Tests

### 1. `tests/unit/test_step_monitor_get_timeout.py` (covers AC1, AC2, AC3)

#### test_get_timeout_uses_gate_default_when_step_provided
Construct an in-memory `WorkflowStep` with `step_type=StepType.quality_validation, gate="integration-tests"`.
Call `get_timeout(project_config, "quality_validation", step_config=None, step=step)`.
Assert returns 900.

#### test_get_timeout_per_gate_dict_entries
Parametrize across all 7 gates from the design (lint=120, format=120, typecheck=240, unit-tests=300, integration-tests=900, frontend-tests=600, browser=1800).
For each, assert `get_timeout` returns the expected value when the step's `gate` is set.

#### test_get_timeout_falls_through_when_gate_is_none (AC2)
Construct a `WorkflowStep` with `gate=None`.
Assert `get_timeout` returns 600 (the legacy `quality_validation` default).

#### test_get_timeout_falls_through_when_gate_is_unknown
Construct a `WorkflowStep` with `gate="some-future-gate"`.
Assert `get_timeout` returns 600 (the legacy default — unknown gate is a safe fallthrough, NOT an error).

#### test_get_timeout_explicit_step_config_wins (AC3)
Pass `step_config={"timeout_secs": 1500}` AND a `step` with `gate="lint"`.
Assert `get_timeout` returns 1500 (explicit override wins over per-gate default).

#### test_get_timeout_project_override_wins_over_gate_default
Set `project_config.config["timeout_overrides"]["quality_validation"] = 700`.
Pass a `step` with `gate="lint"`.
Assert `get_timeout` returns 700 (project override is checked before per-gate dict).

#### test_get_timeout_step_kwarg_is_keyword_only
Use a small introspection check: `inspect.signature(get_timeout).parameters["step"].kind == KEYWORD_ONLY`.
This protects against accidental signature regressions.

#### test_get_timeout_legacy_callers_without_step_arg_still_work
Call `get_timeout(project_config, "quality_validation", step_config=None)` with NO `step=` kwarg.
Assert returns 600 (the legacy per-step-type default).

### 2. `tests/unit/test_step_monitor_warn_50pct.py` (covers AC4, AC5)

Use `unittest.mock.patch` to intercept `_emit_event` so we don't need a DB
session. Construct an in-memory `StepRun` with controllable `started_at`,
`timeout_secs`, `last_heartbeat`, and `warned_50pct_at`.

#### test_warn_50pct_emits_when_elapsed_exceeds_half_budget (AC4 — primary)
Set `started_at = now - 320s, timeout_secs=600, warned_50pct_at=None`.
Call `_check_step_health` with mocked `_emit_event`.
Assert `_emit_event` was called once with event_type `step_warning_50pct`.
Assert metadata contains `pid`, `elapsed_secs` (≈320), `timeout_secs` (600), `percent` (≈53).
Assert `run.warned_50pct_at` is now set (truthy).
Assert `run.status` is unchanged (the warn is non-terminal).

#### test_warn_50pct_idempotent_after_first_emission (AC4 — idempotency)
Set `warned_50pct_at = now - 30s` (already stamped from a previous cycle), elapsed=350.
Call `_check_step_health`.
Assert `_emit_event` was NOT called with `step_warning_50pct`.

#### test_warn_50pct_does_not_fire_below_half (AC4 — boundary)
Set `started_at = now - 250s, timeout_secs=600` (elapsed=250 < 300).
Call `_check_step_health`.
Assert `_emit_event` was NOT called with `step_warning_50pct`.

#### test_warn_50pct_shadowed_by_timeout (AC5 — primary)
Set `started_at = now - 700s, timeout_secs=600` (elapsed=700, past 100%).
Call `_check_step_health`.
Assert `_emit_event` was called with `step_timeout` (NOT `step_warning_50pct`).
Assert NO `step_warning_50pct` event was emitted in the same call.

#### test_warn_50pct_metadata_shape
Verify the metadata dict has exactly the keys `pid`, `elapsed_secs`, `timeout_secs`, `percent` — no more, no less. Future regressions that rename a key would break consumers.

### 3. `tests/integration/test_step_monitor_lifecycle.py` (covers AC4 + AC7 end-to-end)

Use the testcontainer fixtures. Insert a `WorkItem`, `WorkflowStep`, and a
running `StepRun` row into the DB. Then call `monitor_running_steps` to drive
the daemon code path.

#### test_step_warning_50pct_event_persisted_to_db
Set up a `StepRun` with `started_at = now - 320s, timeout_secs = 600,
warned_50pct_at = NULL`.
Call `monitor_running_steps(db, project_id, config)`.
Query `daemon_events` and assert exactly ONE row of `event_type='step_warning_50pct'` exists.
Assert `event_metadata` contains the expected keys.
Assert `step_runs.warned_50pct_at` is now non-NULL for the row.

#### test_step_warning_50pct_idempotent_across_polls
Same setup. Call `monitor_running_steps` once; assert one event. Advance the
test clock by 30 seconds (mock `datetime.now`); call again; assert STILL only
one event (no duplicate).

#### test_step_warning_50pct_severity_is_info_in_sse_registry (AC7)
Import `dashboard.routers.sse` (use the module attribute access, since the constants are name-mangled with a leading underscore: `from dashboard.routers import sse; sse._TOAST_SEVERITY[...]`).
Assert `sse._TOAST_SEVERITY["step_warning_50pct"] == "info"`.
Assert `"step_warning_50pct"` is in `sse._TOAST_EVENTS`.
Assert `"step_warning_50pct"` is in `sse._RUNNING_UPDATE_EVENTS`.
Add a `# noqa: SLF001` comment if ruff flags the private-attribute access — accessing module-private state in tests is acceptable per `tests/CLAUDE.md`.

#### test_legacy_null_gate_row_keeps_existing_default (AC2 — integration)
Insert a `WorkflowStep` with `step_type=quality_validation, gate=None`.
Call `get_timeout(project_config, "quality_validation", step=step)`.
Assert returns 600.
This proves CR-00024 doesn't break items registered before CR-00023.

## Hard Constraints

- All DB-touching tests MUST use testcontainer fixtures from `tests/conftest.py`. NEVER hit port 5433.
- NEVER call `importlib.reload(orch.config)` — use `monkeypatch.delenv()` only.
- NEVER mock the database in integration tests — the lifecycle test must use a real testcontainer.
- After `Base.metadata.create_all()`, MUST run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL`.
- Tests must be deterministic and isolated.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift
2. `make typecheck` — must report zero errors
3. `make lint` — must report zero errors

## Test Verification

```bash
make test-unit
make test-integration
```

Both must pass. Run the full suite, not just your new tests — we need to confirm
no existing test broke from the `get_timeout` signature change.

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "tests-impl",
  "work_item": "CR-00024",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_step_monitor_get_timeout.py",
    "tests/unit/test_step_monitor_warn_50pct.py",
    "tests/integration/test_step_monitor_lifecycle.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X new tests added, all passing; full suite: Y passed, 0 failed",
  "ac_coverage": {
    "AC1": ["test_get_timeout_uses_gate_default_when_step_provided", "test_get_timeout_per_gate_dict_entries"],
    "AC2": ["test_get_timeout_falls_through_when_gate_is_none", "test_legacy_null_gate_row_keeps_existing_default"],
    "AC3": ["test_get_timeout_explicit_step_config_wins", "test_get_timeout_project_override_wins_over_gate_default"],
    "AC4": ["test_warn_50pct_emits_when_elapsed_exceeds_half_budget", "test_warn_50pct_idempotent_after_first_emission", "test_step_warning_50pct_idempotent_across_polls"],
    "AC5": ["test_warn_50pct_shadowed_by_timeout"],
    "AC6": "covered by S15 BrowserVerification (UI assertions need a real browser)",
    "AC7": ["test_step_warning_50pct_severity_is_info_in_sse_registry"]
  },
  "blockers": [],
  "notes": ""
}
```
