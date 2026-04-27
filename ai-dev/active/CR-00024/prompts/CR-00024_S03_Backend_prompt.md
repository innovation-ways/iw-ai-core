# CR-00024_S03_Backend_prompt

**Work Item**: CR-00024 — Step-monitor observability + per-gate timeout defaults
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

(Same Docker rules as other steps — testcontainers only, no compose mutations.)

## ⛔ Migrations

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch DB.
Your work here does not require a migration; S01 already shipped one.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00024 --json` over reading workflow-manifest.json (CR-00023).
- `ai-dev/active/CR-00024/CR-00024_CR_Design.md` — design (AC1, AC2, AC3, AC4, AC5, AC7)
- `ai-dev/active/CR-00024/reports/CR-00024_S01_Database_report.md`, `CR-00024_S02_*_report.md`
- `orch/daemon/step_monitor.py` — `PLATFORM_TIMEOUT_DEFAULTS` (line 32), `get_timeout` (line 51), `_check_step_health` (line 149), `_handle_timeout` (line 224)
- `orch/daemon/batch_manager.py` — caller of `get_timeout` (line 704, 765)
- `orch/daemon/fix_cycle.py` — caller of `get_timeout` (search for `get_timeout(`)
- `dashboard/routers/sse.py` — `SUBSCRIBED_EVENT_TYPES` (line ~29) and `SEVERITY_BY_TYPE` (line ~107)

## Output Files

- `orch/daemon/step_monitor.py` — modified
- `orch/daemon/batch_manager.py` — modified (caller-site update)
- `orch/daemon/fix_cycle.py` — modified (caller-site update)
- `dashboard/routers/sse.py` — modified
- `ai-dev/active/CR-00024/reports/CR-00024_S03_Backend_report.md`

## Context

Three coordinated daemon changes:

1. **Per-gate timeout defaults** — new `QV_GATE_TIMEOUT_DEFAULTS` dict; `get_timeout` consults `step.gate` BEFORE the per-step-type bucket.
2. **50%-warn emission** — `_check_step_health` emits a one-time `step_warning_50pct` `DaemonEvent` when elapsed > `timeout_secs * 0.5` and `warned_50pct_at IS NULL`; idempotency is enforced by stamping the column.
3. **SSE registry** — `dashboard/routers/sse.py` maps the new event_type to severity `info` so toast notifications render correctly.

## Requirements

### 1. Add `QV_GATE_TIMEOUT_DEFAULTS` and update `get_timeout`

In `orch/daemon/step_monitor.py`, add the dict immediately after `PLATFORM_TIMEOUT_DEFAULTS`:

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

Then update `get_timeout`'s signature to accept an optional keyword-only `step` argument and consult the gate dict:

```python
def get_timeout(
    project_config: ProjectConfig,
    step_type: str,
    step_config: dict[str, Any] | None = None,
    *,
    step: WorkflowStep | None = None,
) -> int:
    """Resolve timeout (seconds) for a step type via the override chain.

    Priority (highest → lowest):
    1. Step-level override: ``step_config["timeout_secs"]``
    2. Project-level override: ``.iw-orch.json`` ``timeout_overrides[step_type]``
    3. Per-gate default (``QV_GATE_TIMEOUT_DEFAULTS[step.gate]``) when ``step`` is
       provided and ``step.gate`` is non-NULL (CR-00024).
    4. Per-step-type default (``PLATFORM_TIMEOUT_DEFAULTS``).
    5. ``_FALLBACK_TIMEOUT`` (1800s).
    """
    # 1. Step-level override
    if step_config and "timeout_secs" in step_config:
        return int(step_config["timeout_secs"])

    # 2. Project-level override
    project_overrides: dict[str, Any] = project_config.config.get("timeout_overrides", {})
    if step_type in project_overrides:
        return int(project_overrides[step_type])

    # 3. Per-gate default (CR-00024) — only when the WorkflowStep row carries a gate name
    if step is not None and step.gate is not None:
        gate_default = QV_GATE_TIMEOUT_DEFAULTS.get(step.gate)
        if gate_default is not None:
            return gate_default

    # 4. Platform per-step-type defaults
    return PLATFORM_TIMEOUT_DEFAULTS.get(step_type, _FALLBACK_TIMEOUT)
```

Add `from orch.db.models import WorkflowStep` to the TYPE_CHECKING block (avoid runtime circular import).

### 2. Update daemon callers to pass `step=step`

In `orch/daemon/batch_manager.py` find every `get_timeout(...)` call (currently at line 704 and 765) and add `step=step` (where `step` is the local `WorkflowStep` already in scope). Same for `orch/daemon/fix_cycle.py`.

If a caller does NOT have a `WorkflowStep` in scope (e.g., a future call site that operates on raw step_type), leave it without the kwarg — `step=None` falls through to the per-type bucket, which is the legacy behavior.

### 3. Emit the one-time `step_warning_50pct` event

In `orch/daemon/step_monitor.py:_check_step_health`, AFTER the timeout check (so timeout shadowing AC5 holds — `_handle_timeout` returns before reaching this branch) and BEFORE the stall check, add:

```python
# 50%-timeout soft warning (CR-00024) — fires at most once per run.
if (
    run.started_at is not None
    and run.timeout_secs is not None
    and run.warned_50pct_at is None
):
    elapsed_total = (now - run.started_at).total_seconds()
    half_budget = run.timeout_secs * 0.5
    if elapsed_total > half_budget:
        _emit_warn_50pct(db, run, project_id, now, elapsed_total)
        run.warned_50pct_at = now
```

Then add the helper near `_handle_stall`:

```python
def _emit_warn_50pct(
    db: Session,
    run: StepRun,
    project_id: str,
    now: datetime,
    elapsed: float,
) -> None:
    """Emit a one-time soft-warn that a step has consumed >50% of its timeout."""
    timeout_secs = run.timeout_secs or 0
    percent = round((elapsed / timeout_secs) * 100, 1) if timeout_secs else 0.0
    msg = f"Step has used {percent:.0f}% of its timeout budget ({elapsed:.0f}s / {timeout_secs}s)"

    step = db.get(WorkflowStep, run.step_id)
    work_item_id = step.work_item_id if step else None

    _emit_event(
        db,
        project_id,
        "step_warning_50pct",
        work_item_id,
        message=msg,
        entity_type="work_item",
        metadata={
            "pid": run.pid,
            "elapsed_secs": elapsed,
            "timeout_secs": timeout_secs,
            "percent": percent,
        },
    )
    logger.info("step_run %d crossed 50%%: %s", run.id, msg)
```

The branch order in `_check_step_health` MUST be: dead-PID → timeout → 50%-warn → stall. The timeout branch already returns; the warn branch must NOT return (the run continues normally after warning).

### 4. Register the new event type in the SSE pipeline

In `dashboard/routers/sse.py`:

- Find the event-type subscription set (line ~29 — currently includes `step_crashed`, `step_timeout`, `step_stalled`). If `step_warning_50pct` should be subscribed (it should — operators want to see toasts when steps cross the half-way mark), add it.
- Find `SEVERITY_BY_TYPE` (line ~107) and add `"step_warning_50pct": "info"`.

Match the existing comma/quote style. Do NOT touch any other event type.

### 5. Hard Constraints

- The 50%-warn branch MUST come AFTER the timeout branch. If you put it before, AC5 fails (a run past 100% would emit warn before timeout).
- Do NOT run `_emit_warn_50pct` before stamping `run.warned_50pct_at = now`. The stamp must happen in the same poll cycle — otherwise the next poll re-emits the event (idempotency violated).
- The `step` kwarg in `get_timeout` MUST be keyword-only (`*,` separator) so existing callers that pass three positional args still work.
- Do NOT remove or rename any existing event type. Adding `step_warning_50pct` is additive only.
- Do NOT change `PLATFORM_TIMEOUT_DEFAULTS` values — those are the legacy fallback for NULL-gate rows (AC2).

## Project Conventions

Read `orch/CLAUDE.md` for daemon module structure. The daemon's polling loop is
single-threaded; you don't need to worry about concurrent `_check_step_health`
invocations on the same run.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift
2. `make typecheck` — must report zero errors involving the files you touched
3. `make lint` — must report zero errors

## TDD Requirement

S08 writes the formal coverage. Locally exercise:

```bash
uv run pytest tests/unit/test_step_monitor*.py -q   # existing tests must still pass
uv run mypy orch/daemon/step_monitor.py orch/daemon/batch_manager.py orch/daemon/fix_cycle.py dashboard/routers/sse.py
make lint
```

If any pre-existing test fails because the `get_timeout` signature changed, fix it here (those callers were the legacy 3-positional-arg form; update them to use the new keyword-only `step=` argument).

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00024",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/step_monitor.py",
    "orch/daemon/batch_manager.py",
    "orch/daemon/fix_cycle.py",
    "dashboard/routers/sse.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed; mypy clean; lint clean",
  "blockers": [],
  "notes": "Branch order in _check_step_health: dead → timeout → 50%-warn → stall. step kwarg is keyword-only so legacy 3-positional callers are unaffected."
}
```
