# CR-00024_S07_CodeReview_Final_prompt

**Work Item**: CR-00024 — Step-monitor observability + per-gate timeout defaults
**Step**: S07
**Agent**: code-review-final-impl

---

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00024 --json` over reading workflow-manifest.json (CR-00023).
- `ai-dev/active/CR-00024/CR-00024_CR_Design.md` — design (all 7 ACs)
- All prior step reports (S01–S06)
- All modified files across the chain:
  - `orch/db/models.py` (S01)
  - `orch/db/migrations/versions/<new_revision>_add_warned_50pct_at_to_step_runs.py` (S01)
  - `orch/daemon/step_monitor.py` (S03)
  - `orch/daemon/batch_manager.py` (S03)
  - `orch/daemon/fix_cycle.py` (S03)
  - `dashboard/routers/sse.py` (S03)
  - `dashboard/routers/running.py` (S05)
  - `dashboard/routers/worktrees.py` (S05)
  - `dashboard/routers/jobs_ui.py` (S05)
  - `dashboard/templates/fragments/{running,step_row,jobs}_table.html` (S05)

## Output Files

- `ai-dev/active/CR-00024/reports/CR-00024_S07_CodeReview_Final_report.md`

## Context

This is a global cross-step review. Per-step reviews (S02, S04, S06) caught
local issues. Your job is to verify the END-TO-END contract holds:

```
schema column → daemon emits event + stamps column → SSE registers severity →
dashboard surfaces last_heartbeat + pid_alive
```

AND that the dependency on CR-00023 is preserved (no per-gate code path tries
to access the `gate` column on a row where CR-00023 hasn't been merged yet).

## End-to-End Verification

### Chain integrity
- [ ] The new `warned_50pct_at` column (S01) matches the field name accessed by `_check_step_health` (S03) — exact spelling
- [ ] The `step_warning_50pct` event_type emitted by `_emit_warn_50pct` (S03) matches the key added to `_TOAST_EVENTS`, `_TOAST_SEVERITY`, and `_RUNNING_UPDATE_EVENTS` in `dashboard/routers/sse.py` (S03) — exact string match across all three
- [ ] `WorkflowStep.gate` is read in `get_timeout` only via the optional `step` kwarg, never as a positional or required argument — proves backward compat
- [ ] `RunningRow.last_heartbeat_age_secs` and `pid_alive` (S05) source from the same DB columns the daemon writes (`StepRun.last_heartbeat`, `StepRun.pid_alive`)

### Acceptance criteria coverage
- [ ] AC1: per-gate defaults override step-type bucket — verified by code path inspection
- [ ] AC2: legacy NULL-gate falls through — verified by `if step is not None and step.gate is not None` guard
- [ ] AC3: explicit `step_config["timeout_secs"]` still wins — verified by branch order
- [ ] AC4: 50%-warn idempotency — `warned_50pct_at IS NULL` guard + stamp
- [ ] AC5: timeout shadowing — branch order is dead → timeout (returns) → warn → stall
- [ ] AC6: dashboard renders heartbeat age + pip — visible in the 3 fragments
- [ ] AC7: `_TOAST_SEVERITY["step_warning_50pct"] == "info"`, and the event_type appears in `_TOAST_EVENTS` and `_RUNNING_UPDATE_EVENTS`

### Dependency on CR-00023
- [ ] `step.gate` is NEVER assumed non-NULL; every read is guarded
- [ ] If CR-00023 is reverted, CR-00024 still functions (returns to per-step-type bucket for everything) — verified by the `step is not None and step.gate is not None` guard
- [ ] The Alembic migration's `down_revision` chains correctly past CR-00023's migration

### Cross-cutting concerns
- [ ] No silent dependency on test data / fixture state — production code paths are self-contained
- [ ] No new dependency added to `pyproject.toml`
- [ ] mypy clean across all modified files
- [ ] `make lint` clean
- [ ] All preflight gates ran on each implementation step (verified via S01/S03/S05 report `preflight` field)

### Risk surface
- [ ] No long-running operation added inside `_check_step_health` (it must remain cheap — runs every poll cycle for every running step). The new warn branch is two integer comparisons + one event emit when the trigger fires; no DB query inside the predicate.
- [ ] The `_emit_warn_50pct` helper does NOT call any blocking I/O beyond the existing DaemonEvent insert pattern
- [ ] No race condition: the daemon's polling loop is single-threaded (per `orch/CLAUDE.md`), so two concurrent invocations on the same `StepRun.id` cannot happen

## Findings Severity

- **CRITICAL**: chain breaks (e.g., daemon emits event_type X but SSE registers Y); dependency on CR-00023 is hard (would crash if `gate` column missing); idempotency violated under any scenario
- **HIGH**: branch order off; `last_heartbeat` rendered as `0s ago` when NULL; missing AC coverage
- **MEDIUM**: missing CR-00024 inline comment; minor naming drift
- **LOW**: style, comment wording

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "CR-00024",
  "completion_status": "complete",
  "global_verdict": "approved|fix-required",
  "ac_coverage": {
    "AC1_per_gate_defaults": "covered|gap",
    "AC2_legacy_fallback": "covered|gap",
    "AC3_explicit_override_wins": "covered|gap",
    "AC4_warn_idempotency": "covered|gap",
    "AC5_timeout_shadows_warn": "covered|gap",
    "AC6_dashboard_heartbeat": "covered|gap",
    "AC7_sse_event_mapping": "covered|gap"
  },
  "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "blockers": [],
  "notes": ""
}
```
