# CR-00024_S04_CodeReview_Backend_prompt

**Work Item**: CR-00024 — Step-monitor observability + per-gate timeout defaults
**Step**: S04
**Agent**: code-review-impl

---

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00024 --json` over reading workflow-manifest.json (CR-00023).
- `ai-dev/active/CR-00024/CR-00024_CR_Design.md` — design (AC1–AC5, AC7)
- `ai-dev/active/CR-00024/reports/CR-00024_S03_Backend_report.md`
- `orch/daemon/step_monitor.py` (modified)
- `orch/daemon/batch_manager.py` (caller-site updated)
- `orch/daemon/fix_cycle.py` (caller-site updated)
- `dashboard/routers/sse.py` (event registry updated)

## Output Files

- `ai-dev/active/CR-00024/reports/CR-00024_S04_CodeReview_Backend_report.md`

## Review Checklist

### Per-gate defaults (AC1, AC2, AC3)
- [ ] `QV_GATE_TIMEOUT_DEFAULTS` exists with the 7 expected gate keys (`lint`/`format`/`typecheck`/`unit-tests`/`integration-tests`/`frontend-tests`/`browser`) and the values from the design doc
- [ ] `get_timeout` resolution order is: explicit `step_config["timeout_secs"]` → project override → gate default → step-type default → `_FALLBACK_TIMEOUT`
- [ ] `step` parameter is keyword-only (`*, step: WorkflowStep | None = None`) — verify legacy 3-positional callers still type-check
- [ ] When `step.gate` is NULL or unknown (not in `QV_GATE_TIMEOUT_DEFAULTS`), the function falls through to the step-type bucket — does NOT return None and does NOT crash
- [ ] All daemon callers pass `step=step`: both call sites in `batch_manager.py` (verify with `grep -n "get_timeout(" orch/daemon/batch_manager.py`) and the call inside `fix_cycle.py:_launch_fix_agent`. The fix_cycle call must keep `fix_step_type` (the remapped string from `_FIX_TIMEOUT_MAP`) as the second positional arg — only `step=step` is added; `fix_step_type` is NOT replaced with `step.step_type.value`

### 50%-warn emission (AC4, AC5)
- [ ] The warn branch in `_check_step_health` is positioned AFTER the timeout check and BEFORE the stall check
- [ ] The warn branch fires only when `run.warned_50pct_at IS NULL` AND `elapsed > timeout_secs * 0.5`
- [ ] `run.warned_50pct_at = now` is set in the same poll cycle as the event emission (idempotency)
- [ ] The warn branch does NOT terminate the run (no status change, no early return) — the step continues running
- [ ] The emitted event has metadata containing `pid`, `elapsed_secs`, `timeout_secs`, `percent`
- [ ] If a run has both `elapsed > 50%` AND `elapsed > 100%`, the timeout branch fires first; the warn branch is unreachable in that cycle (verify by branch ordering)

### SSE registry (AC7)
- [ ] `step_warning_50pct` is added to `_TOAST_EVENTS` in `dashboard/routers/sse.py` (so the SSE pump renders a toast for the event)
- [ ] `_TOAST_SEVERITY["step_warning_50pct"] == "info"`
- [ ] `step_warning_50pct` is added to `_RUNNING_UPDATE_EVENTS` (so the running-table fragment refreshes when the warn fires)
- [ ] No existing event_type was removed or renamed from any of the three constants
- [ ] Order/style of the additions matches the existing format
- [ ] The implementing agent did NOT introduce new identifiers named `SUBSCRIBED_EVENT_TYPES` or `SEVERITY_BY_TYPE` (those names are not part of this codebase)

### Backward compatibility
- [ ] Legacy NULL-gate rows still resolve to the existing `quality_validation: 600s` bucket (AC2)
- [ ] No `PLATFORM_TIMEOUT_DEFAULTS` values were modified
- [ ] No call site lost its `get_timeout` argument; signature change is purely additive

### Style + lint
- [ ] mypy clean on `step_monitor.py`, `batch_manager.py`, `fix_cycle.py`, `sse.py`
- [ ] `make lint` clean
- [ ] Inline comments reference CR-00024 for the new code paths (so future readers find the rationale)
- [ ] `WorkflowStep` import for type hints lives under `TYPE_CHECKING` to avoid circular import

## Findings Severity

- **CRITICAL**: idempotency broken (warn fires more than once); branch order wrong (warn before timeout); `step` kwarg made positional (breaks existing callers); SSE registry edit dropped an existing event_type
- **HIGH**: per-gate value mismatch with design; `step.gate is None` triggers crash; `warned_50pct_at` not set after emission
- **MEDIUM**: missing CR-00024 inline comment; daemon caller missed the kwarg
- **LOW**: cosmetic / wording

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00024",
  "completion_status": "complete",
  "files_reviewed": [
    "orch/daemon/step_monitor.py",
    "orch/daemon/batch_manager.py",
    "orch/daemon/fix_cycle.py",
    "dashboard/routers/sse.py"
  ],
  "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "verdict": "approved|fix-required",
  "blockers": [],
  "notes": ""
}
```
