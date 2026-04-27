# CR-00024: Step-monitor observability + per-gate timeout defaults

**Type**: Change Request
**Priority**: Medium
**Reason**: Tech debt / hardening — I-00041 post-mortem findings [4] and [5]. Eliminates the "QvGate integration-tests step inherits a 600s default that is too tight, then operators kill prematurely because there is no soft-warning signal, then the dashboard offers no way to tell whether the daemon is still polling the step" cluster of platform symptoms.
**Created**: 2026-04-27
**Status**: Draft

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

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Description

Three coordinated changes to `orch/daemon/step_monitor.py` + the dashboard:

1. **Per-gate timeout defaults** — a `QV_GATE_TIMEOUT_DEFAULTS` dict keyed on `WorkflowStep.gate` (lint=120, format=120, typecheck=240, unit-tests=300, integration-tests=900, frontend-tests=600, browser=1800), consulted in `get_timeout` before the existing per-step-type fallback. Eliminates the I-00041 case where S14's integration-tests rerun inherited the 600s default because the design author forgot to copy `timeout: 900` from S12.
2. **Soft-warn at 50% timeout** — a one-time `step_warning_50pct` `DaemonEvent` emitted by `_check_step_health` when elapsed crosses `timeout_secs * 0.5`, gated by a new `warned_50pct_at` column on `step_runs` for idempotency. Lets operators distinguish "still running, daemon is watching" from "stuck for ages" without preemptively killing.
3. **Dashboard heartbeat-age + pid-alive surfacing** — render `last_heartbeat` (as "Xs ago") and a `pid_alive` indicator on the running-tasks, worktrees, and jobs tables so operators can see "daemon polled this step 30s ago, alive then".

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key invariants:

- The daemon polls every `IW_CORE_POLL_INTERVAL` seconds (default 60s); detection lag for a dead PID is at most one poll cycle.
- Agents run in detached sessions (`start_new_session=True` in `batch_manager.py:787`) so the daemon doesn't get SIGCHLD; PID liveness is determined by `kill -0` + `/proc/<pid>/stat` zombie detection (see `orch/daemon/step_monitor.py:_is_pid_alive`).
- `step_runs` is append-only — never `UPDATE` a row to "reset" it; create a new run.

## Current Behavior

`orch/daemon/step_monitor.py:32-43` defines:

```python
PLATFORM_TIMEOUT_DEFAULTS: dict[str, int] = {
    "implementation": 2700,
    "code_review": 1800,
    ...
    "quality_validation": 600,
    "qv_fix": 1800,
    "browser_verification": 1800,
    "qv_browser_fix": 2700,
}
_FALLBACK_TIMEOUT = 1800
```

`get_timeout` uses a 3-level chain:
1. Step-level override (`step_config["timeout_secs"]`, sourced from manifest's `timeout` field)
2. Project-level override (`.iw-orch.json` `timeout_overrides`)
3. The per-step-type bucket

The per-step-type bucket means `lint`, `format`, `typecheck`, `unit-tests`, `integration-tests`, `frontend-tests`, and `browser` all share `quality_validation: 600s`. Real workloads diverge wildly: `lint`/`format`/`typecheck` finish in 10–30s while integration test suites typically run 200–600s and can spike to 900s+.

`_check_step_health` (line 149) handles three terminal cases:
- PID dead → `_handle_crashed` emits `step_crashed` event
- Timeout exceeded → `_handle_timeout` emits `step_timeout` event
- Heartbeat stale → `_handle_stall` emits `step_stalled` event

There is **no signal between "running" and these terminal states** — operators have no way to tell that a step is past 50% of its timeout budget but still healthy. This produced the I-00041 S13 thrash: 2 manual kills + 1 timeout + 1 success.

`step_runs` columns (after CR-00023) include `last_heartbeat`, `pid_alive`, and the new `command/gate/timeout_secs`. **None of `last_heartbeat`/`pid_alive` are surfaced anywhere in the dashboard** — the only columns rendered today are step_id, status, started_at, and duration.

## Desired Behavior

After CR-00024:

1. `get_timeout(project_config, step_type, step_config, step=<WorkflowStep>)` consults `step.gate` BEFORE the per-step-type bucket. A new `QV_GATE_TIMEOUT_DEFAULTS` dict provides per-gate values:

   ```python
   QV_GATE_TIMEOUT_DEFAULTS: dict[str, int] = {
       "lint": 120,
       "format": 120,
       "typecheck": 240,
       "unit-tests": 300,
       "integration-tests": 900,
       "frontend-tests": 600,
       "browser": 1800,
   }
   ```

   Resolution order becomes: explicit `step_config["timeout_secs"]` → project override → **gate-specific default** (when `step.gate` is non-NULL) → step-type bucket → `_FALLBACK_TIMEOUT`.

2. When `_check_step_health` observes `elapsed > run.timeout_secs * 0.5` AND `run.warned_50pct_at IS NULL`, it stamps `run.warned_50pct_at = now` and emits a one-time `step_warning_50pct` `DaemonEvent` with metadata `{pid, elapsed_secs, timeout_secs, percent}`. The warning fires at most once per step run (idempotent).

3. The dashboard's `/system/running` page renders a "Last seen" column showing `f"{(now - run.last_heartbeat).total_seconds():.0f}s ago"` and a coloured pip indicating `pid_alive`. The same data appears in the `/system/worktrees` and `/system/jobs` tables. SSE-driven fragment refresh continues to work.

4. `dashboard/routers/sse.py`'s event-type registry recognises `step_warning_50pct` (severity `info`) so the toast notifications render correctly.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `step_runs` table | Has `last_heartbeat`, `pid_alive`, `timeout_secs` (after CR-00023) | + `warned_50pct_at TIMESTAMPTZ NULL` for one-time warn idempotency |
| `orch/db/models.py:StepRun` | 19 mapped columns | 20 mapped columns |
| `orch/daemon/step_monitor.py:get_timeout` | 3-level chain, ignores `gate` | 4-level chain consulting `step.gate` before step-type bucket; new `QV_GATE_TIMEOUT_DEFAULTS` constant |
| `orch/daemon/step_monitor.py:_check_step_health` | Emits crashed/timeout/stalled only | Also emits `step_warning_50pct` once when elapsed > 50% |
| `dashboard/routers/sse.py` | Recognises 3 step events | Recognises 4 (adds `step_warning_50pct` with severity `info`) |
| `dashboard/routers/running.py` | `RunningRow` has step_id, status, started_at, duration | + `last_heartbeat_age_secs`, `pid_alive` fields surfaced from `StepRun` |
| `dashboard/routers/worktrees.py` | Renders worktree git status | Adds `last_heartbeat_age_secs`/`pid_alive` per active step |
| `dashboard/routers/jobs_ui.py` | Aggregated jobs view | Same heartbeat surfacing for step-run rows |
| `dashboard/templates/fragments/running_table.html` | 4 columns | + "Last seen" column + alive-pip |
| `dashboard/templates/fragments/jobs_table.html` | Mixed jobs view | + heartbeat column for step-run rows |
| Daemon callers of `get_timeout` | Pass `step_config` only | Also pass `step` argument so `step.gate` is reachable |

### Breaking Changes

- **None.** The `warned_50pct_at` column is nullable and additive. The new `QV_GATE_TIMEOUT_DEFAULTS` table is consulted only when `step.gate` is non-NULL, so legacy rows registered before CR-00023 (where `gate` is NULL) keep falling through to the existing `quality_validation: 600s` bucket. The `step_warning_50pct` event_type is additive — `dashboard/routers/sse.py`'s SUBSCRIBED_EVENT_TYPES filter currently ignores any unknown event_type silently (verified at sse.py:107-111), so any external consumers that don't know about the new type are unaffected.

### Data Migration

- **Not required.** `warned_50pct_at` defaults to NULL for existing rows. In-flight runs that are past 50% at deployment time simply miss their one-time 50% warning — no harm; the operator was already living with the no-warn status quo. New runs after deployment get the warning.
- Reversibility: the Alembic migration `downgrade()` drops the single column. No data loss for any caller (the column is informational only, used to suppress duplicate warnings).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Alembic migration: add `warned_50pct_at TIMESTAMPTZ NULL` to `step_runs`; update `StepRun` model | — |
| S02 | code-review-impl | Review S01 schema + migration | — |
| S03 | backend-impl | Add `QV_GATE_TIMEOUT_DEFAULTS` dict + per-gate lookup in `get_timeout`; update `get_timeout` signature to accept optional `step` arg; update all daemon callers to pass `step`; emit one-time `step_warning_50pct` `DaemonEvent` in `_check_step_health`; add `step_warning_50pct` → `info` to `dashboard/routers/sse.py:SEVERITY_BY_TYPE` | — |
| S04 | code-review-impl | Review S03 daemon changes | — |
| S05 | frontend-impl | Surface `last_heartbeat_age_secs` (rendered "Xs ago") and a `pid_alive` indicator pip on the running-tasks, worktrees, and jobs tables; update `RunningRow` dataclass + `running_table.html`/`step_row.html`/`jobs_table.html` fragments | — |
| S06 | code-review-impl | Review S05 dashboard changes | — |
| S07 | code-review-final-impl | Cross-step global review of S01/S03/S05 — verify the schema/daemon/dashboard chain holds end-to-end | — |
| S08 | tests-impl | Unit tests (`get_timeout` per-gate lookup, 50%-warn idempotency, sse event_type registration); integration test (full step-monitor lifecycle: launch → past 50% → assert single warning event); regression test (legacy NULL-gate row keeps the existing 600s default) | — |
| S09 | code-review-impl | Review S08 tests | — |
| S10 | qv-gate | QV: lint (`make lint`) | — |
| S11 | qv-gate | QV: format (`make format`) | — |
| S12 | qv-gate | QV: typecheck (`make typecheck`) | — |
| S13 | qv-gate | QV: unit tests (`make test-unit`) | — |
| S14 | qv-gate | QV: integration tests (`make allure-integration`, timeout 900) | — |
| S15 | qv-browser | QV: Browser verification — heartbeat age + pid-alive indicator render correctly on `/system/running` and `/system/worktrees` | — |

### Database Changes

- **New tables**: None
- **Modified tables**: `step_runs` — add `warned_50pct_at TIMESTAMPTZ NULL` (one nullable column).
- **Migration notes**: Generate via `alembic revision --autogenerate`. The migration must be reversible (`downgrade()` drops the column). No backfill required.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None (CLI-only orchestration plus dashboard HTML; no REST/JSON API touched)
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: `running_table.html`, `step_row.html`, `jobs_table.html` fragments (add Last-seen column + pid-alive pip)
- **Removed components**: None

## File Manifest

All files for this work item live under `ai-dev/active/CR-00024/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00024_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00024_S01_Database_prompt.md` | Prompt | Schema migration + model update |
| `prompts/CR-00024_S02_CodeReview_Database_prompt.md` | Prompt | Review S01 |
| `prompts/CR-00024_S03_Backend_prompt.md` | Prompt | Per-gate defaults + 50%-warn emission + SSE wiring |
| `prompts/CR-00024_S04_CodeReview_Backend_prompt.md` | Prompt | Review S03 |
| `prompts/CR-00024_S05_Frontend_prompt.md` | Prompt | Dashboard heartbeat surfacing |
| `prompts/CR-00024_S06_CodeReview_Frontend_prompt.md` | Prompt | Review S05 |
| `prompts/CR-00024_S07_CodeReview_Final_prompt.md` | Prompt | Cross-step final review |
| `prompts/CR-00024_S08_Tests_prompt.md` | Prompt | Unit + integration tests |
| `prompts/CR-00024_S09_CodeReview_Tests_prompt.md` | Prompt | Review S08 |
| `prompts/CR-00024_S15_BrowserVerification_prompt.md` | Prompt | QV-Browser end-to-end |
| `evidences/pre/CR-00024-running-before.png` | Evidence | Pre-state of /system/running |
| `evidences/pre/CR-00024-worktrees-before.png` | Evidence | Pre-state of /system/worktrees |

QvGate steps S10–S14 use the inline `command` field in the manifest (no prompt files).

Files to be modified by the steps (for batch planner overlap analysis):

- `orch/db/models.py` (S01)
- `orch/db/migrations/versions/<new_revision>.py` (S01)
- `orch/daemon/step_monitor.py` (S03)
- `orch/daemon/batch_manager.py` (S03 — caller-site update for `get_timeout`)
- `orch/daemon/fix_cycle.py` (S03 — caller-site update for `get_timeout`)
- `dashboard/routers/sse.py` (S03 — register `step_warning_50pct`)
- `dashboard/routers/running.py` (S05)
- `dashboard/routers/worktrees.py` (S05)
- `dashboard/routers/jobs_ui.py` (S05)
- `dashboard/templates/fragments/running_table.html` (S05)
- `dashboard/templates/fragments/step_row.html` (S05)
- `dashboard/templates/fragments/jobs_table.html` (S05)
- `tests/unit/test_step_monitor_get_timeout.py` (S08, new)
- `tests/unit/test_step_monitor_warn_50pct.py` (S08, new)
- `tests/integration/test_step_monitor_lifecycle.py` (S08, new)

### Scope (for executor scope gate)

```
scope.allowed_paths:
  - orch/db/models.py
  - orch/db/migrations/versions/**.py
  - orch/daemon/step_monitor.py
  - orch/daemon/batch_manager.py
  - orch/daemon/fix_cycle.py
  - dashboard/routers/sse.py
  - dashboard/routers/running.py
  - dashboard/routers/worktrees.py
  - dashboard/routers/jobs_ui.py
  - dashboard/templates/fragments/running_table.html
  - dashboard/templates/fragments/step_row.html
  - dashboard/templates/fragments/jobs_table.html
  - tests/unit/test_step_monitor_get_timeout.py
  - tests/unit/test_step_monitor_warn_50pct.py
  - tests/integration/test_step_monitor_lifecycle.py
```

## Acceptance Criteria

### AC1: Per-gate defaults override the per-step-type bucket

```
Given a fresh `WorkflowStep` row with step_type=quality_validation, gate="integration-tests",
  no per-step `timeout_secs` override, and no project-level override
When `get_timeout(project_config, step.step_type.value, step_config=None, step=step)` is called
Then it returns 900 (the QV_GATE_TIMEOUT_DEFAULTS["integration-tests"] value)
And NOT 600 (the legacy quality_validation default).

And given the same row with gate="lint",
When get_timeout is called identically
Then it returns 120 (QV_GATE_TIMEOUT_DEFAULTS["lint"]).
```

### AC2: Legacy NULL-gate rows fall through to the existing default

```
Given a `WorkflowStep` row with step_type=quality_validation, gate=NULL
  (representing an item registered before CR-00023)
When `get_timeout` is called
Then it returns 600 (the existing PLATFORM_TIMEOUT_DEFAULTS["quality_validation"] value)
And the daemon's behavior for that legacy item is byte-identical to today's.
```

### AC3: Explicit overrides still win

```
Given a step with gate="integration-tests" AND step_config={"timeout_secs": 1500}
When get_timeout is called
Then it returns 1500 (explicit override wins over the gate default and the type default).
```

### AC4: 50% soft-warn fires exactly once per step run

```
Given a running StepRun with timeout_secs=600, started 320 seconds ago,
  warned_50pct_at IS NULL
When `_check_step_health` is invoked
Then exactly one `step_warning_50pct` `DaemonEvent` is inserted with metadata
  containing pid, elapsed_secs (~320), timeout_secs (600), and percent (~53)
And `run.warned_50pct_at` is set to the current time
And the StepRun status remains `running` (the warn is non-terminal).

And given the same StepRun is checked again 30 seconds later (elapsed=350),
When _check_step_health is invoked
Then NO additional step_warning_50pct event is emitted (idempotent).
```

### AC5: Soft-warn does not interfere with terminal states

```
Given a running StepRun whose elapsed time exceeds BOTH 50% AND 100% of timeout_secs
When _check_step_health is invoked
Then the timeout branch fires (status → timeout, step_timeout event emitted, SIGTERM sent)
And NO step_warning_50pct event is emitted in this same poll cycle for this run
  (the timeout handler short-circuits before reaching the warn branch — verified by branch order).
```

### AC6: Dashboard surfaces last_heartbeat age and pid_alive

```
Given a running StepRun with last_heartbeat = now - 30 seconds and pid_alive = True
When the operator visits `/system/running` (or `/system/worktrees` or `/system/jobs`)
Then the row for that StepRun displays "30s ago" (or similar human-readable form) in a "Last seen" column
And a green/positive indicator pip showing pid_alive=True
And the existing columns (step_id, status, duration) are unchanged.

And given a StepRun with pid_alive = False (i.e., the daemon detected a dead PID
  but has not yet processed the crash, or the row is post-crash with status=failed),
When the same page renders
Then the indicator pip is red/negative for that row.
```

### AC7: SSE pipeline surfaces the new event type

```
Given the daemon emits a `step_warning_50pct` DaemonEvent
When the SSE stream at `/system/events/stream` includes that event
Then the event's severity is `info` per `dashboard/routers/sse.py:SEVERITY_BY_TYPE`
And the dashboard's toast notification renders without a console error
And no existing event-type handler regresses (step_crashed → error, step_timeout → warning,
  step_stalled → warning).
```

## Rollback Plan

- **Database**: Reverse migration drops `warned_50pct_at`. No data loss (the column is purely a duplicate-suppression marker).
- **Code**: `git revert` the merge commit. The fallback chain in `get_timeout` is internally consistent — reverting the per-gate dict alone would leave the function returning the per-step-type bucket as it does today, which is the pre-CR-00024 behavior.
- **Data**: No data loss. The dashboard column additions are purely cosmetic; reverting the dashboard reverts the rendering with no DB impact.

## Dependencies

- **Depends on**: CR-00023 (needs the `gate` column on `WorkflowStep` to be live in the orch DB before scope item (1) — per-gate defaults — can resolve correctly. CR-00024 must be batched AFTER CR-00023 lands.)
- **Blocks**: None

## TDD Approach

- Unit tests (no DB):
  - `tests/unit/test_step_monitor_get_timeout.py` — covers AC1, AC2, AC3. Use a `WorkflowStep` constructed in-memory (no DB session) with various `gate` values; assert resolution order and value.
  - `tests/unit/test_step_monitor_warn_50pct.py` — covers AC4 (idempotency) and AC5 (timeout shadowing). Construct an in-memory `StepRun` with a controllable clock; mock `_emit_event` and assert the event is emitted at most once.
- Integration tests (testcontainer):
  - `tests/integration/test_step_monitor_lifecycle.py` — full daemon-side lifecycle. Insert a `StepRun` row with `started_at = now - 320s` and `timeout_secs = 600`; call `monitor_running_steps`; assert exactly one `DaemonEvent` of type `step_warning_50pct` with the expected metadata; advance clock 30s; call again; assert NO new event (idempotent at DB layer).
- SSE / dashboard tests:
  - Extend `tests/dashboard/` if a sibling test exists for the SSE event-type registry; otherwise add a focused unit test asserting `SEVERITY_BY_TYPE["step_warning_50pct"] == "info"`.
- Updated tests:
  - Any existing `tests/unit/test_step_monitor*.py` that asserts the exact signature of `get_timeout` will need updating (the new `step` parameter is optional / keyword-only).
  - Any existing dashboard test asserting the exact column count of `running_table.html` will need updating.

## Notes

- **Why not also tighten `IW_CORE_POLL_INTERVAL`?** Lower polling cuts detection lag but multiplies daemon CPU + DB load and doesn't help the I-00041 case (the operator-anxiety problem dominated the wasted time, not the detection lag). Out of scope per Step 2 confirmation.
- **Why not the SIGCHLD-based out-of-process reaper?** That requires restructuring the daemon process model (a sibling reaper that retains parent-child to all agents). Big lift, and the I-00041 evidence doesn't justify it — average detection lag was within one poll cycle. Re-evaluate after this CR ships and we have heartbeat-age data in the dashboard.
- **Why is the `warned_50pct_at` column on `step_runs` rather than computed?** Computing "have we already warned?" by querying `daemon_events` for a matching event would work but adds a query per poll per step. A column is one cheap UPDATE per step lifecycle. `step_runs` already has fine-grained lifecycle columns (`pid_alive`, `last_heartbeat`); this is consistent.
- **Why include the `step` argument as optional / keyword-only in `get_timeout`?** Existing callers pass only `(project_config, step_type, step_config)`. Making `step` keyword-only and optional preserves call-site compatibility — the function still works without it (just falls through to the per-type bucket). Daemon callers in `batch_manager.py` and `fix_cycle.py` are updated in S03 to pass `step=step` so per-gate defaults activate immediately.
- **Future risk:** if a future CR adds a new gate name that isn't in `QV_GATE_TIMEOUT_DEFAULTS`, the function falls through to the per-step-type bucket (600s for quality_validation). Document this as the contract: unknown gates inherit the type default, which is a safe fallback.
