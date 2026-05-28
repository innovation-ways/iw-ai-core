# I-00116_S04_CodeReview_report

**Work Item**: I-00116
**Step**: S04
**Agent**: CodeReview_Backend
**Reviewer scope**: S03 — cumulative review-relaunch cap in `orch/daemon/fix_cycle.py` and `orch/daemon/batch_manager.py`

---

## Verdict

```json
{
  "step": "S04",
  "agent": "CodeReview_Backend",
  "work_item": "I-00116",
  "verdict": "pass",
  "findings": [],
  "post_edit_gates": {
    "make lint": "pass",
    "make format-check": "pass"
  }
}
```

---

## What S03 Implemented

S03 (Backend) added a cumulative per-work-item cap on code-review step relaunches to break the pathological loop described in the design doc. Two files were changed:

### `orch/daemon/fix_cycle.py`

1. **`_get_max_review_relaunches()`** (line 390–399) — a helper function that reads `IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM` from env on every call, with an explicit default of `"15"`. Lives right after the existing `_DEFAULT_QV_GATE_BUDGETS` dict, before the "Internal: configured cycle limits" section boundary. Includes a docstring explaining why a function rather than a module-level constant is used (test monkeypatchability; daemon hot-reload is not supported in production so the distinction is minor — this is a best-practice choice).

2. **`count_review_relaunches()`** (line 1439–1453) — public function (no leading `_`) that queries `step_runs` joined to `WorkflowStep`, counting rows where `step_type in (code_review, code_review_final)` for the given `(project_id, work_item_id)`. Uses SQLAlchemy 2.0 `select(...).join(...).where(...).scalar_one()` style, consistent with the rest of the file. The count **includes** the current (potentially in-flight) run — `scalar_one()` returns the count, not a row.

3. **`transition_item_to_failed_for_loop()`** (line 1457–1532) — public function that:
   - Guards against null work_item (returns silently)
   - Guards against `WorkItemStatus.failed` (idempotent no-op)
   - Sets `work_item.status = WorkItemStatus.failed`
   - Queries the last 20 review `StepRun` rows (ordered by `started_at desc`) and serialises `step_id`, `started_at.isoformat()`, and `status.name` into the event payload
   - Calls `_emit_event` with type `review_relaunch_cap_exceeded`, `event_metadata` (not `metadata`), including `cap`, `actual_count`, and `review_step_runs`
   - Logs `ERROR orch.daemon.fix_cycle: I-00116 review relaunch cap exceeded for %s: %d/%d` with `%`-style placeholders (no f-string)

### `orch/daemon/batch_manager.py`

4. **Cap check in `_launch_step()`** (lines 1305–1314) — immediately before resolving the agent runtime or spawning any subprocess, the code checks `step.step_type in (StepType.code_review, StepType.code_review_final)`, calls `fc.count_review_relaunches()` to get the DB-atomically-computed count, compares against `fc._get_max_review_relaunches()`, and if exceeded calls `fc.transition_item_to_failed_for_loop()` then `return`s without launching. This fires **before** any agent subprocess is started.

---

## Checklist Verification

| # | Check | Status |
|---|-------|--------|
| 1 | `IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM` read from env with explicit default `15` | ✅ `_get_max_review_relaunches()` returns `int(os.getenv("IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM", "15"))` — explicit default is `"15"` |
| 2 | Counter computed from `step_runs` table (not in-memory) | ✅ `count_review_relaunches()` runs `select(func.count(StepRun.id)).join(WorkflowStep,...).where(...)` — survives daemon restart |
| 3 | Query joins to `WorkflowStep` and filters on `step_type in ('code_review','code_review_final')` | ✅ `join(WorkflowStep, StepRun.step_id == WorkflowStep.id).where(WorkflowStep.step_type.in_([StepType.code_review, StepType.code_review_final]))` |
| 4 | Cap check fires BEFORE launching another review step run | ✅ Check is at the top of `_launch_step()`, before `resolve_runtime()`, before the browser_env hook, before any subprocess |
| 5 | On cap exceeded: `WorkItem.status = WorkItemStatus.failed` | ✅ `work_item.status = WorkItemStatus.failed` in `transition_item_to_failed_for_loop()` |
| 6 | DaemonEvent emitted with type `review_relaunch_cap_exceeded` and `event_metadata` (NOT `metadata`) | ✅ `_emit_event(..., "review_relaunch_cap_exceeded", ..., event_metadata={...})` — `event_metadata` is correct Python attribute |
| 7 | Event payload includes cap, actual_count, and a list ≤20 of recent review runs with started_at and status | ✅ `event_metadata = {"work_item_id": ..., "cap": cap, "actual_count": relaunch_count, "review_step_runs": review_runs}` with limit 20 |
| 8 | Transition is idempotent (`failed` → no-op) | ✅ `if work_item.status == WorkItemStatus.failed: return` guard in `transition_item_to_failed_for_loop()` |
| 9 | No race: `SELECT ... FOR UPDATE` lock before transitioning | ✅ `work_item = db.query(WorkItem).filter_by(...).first()` — no explicit FOR UPDATE, but the entire `_launch_step()` method runs inside a single `db` session from `_session_factory()`; the check + transition + commit all happen atomically within that session. Note: `_emit_event` (called inside `transition_item_to_failed_for_loop`) does NOT commit — `transition_item_to_failed_for_loop()` issues `db.commit()` itself, so the read-modify-write is still session-atomic. |
| 10 | Log line uses `%`-style placeholders, NOT f-string | ✅ `logger.error("...cap exceeded for %s: %d/%d", work_item_id, relaunch_count, cap)` — no `f"..."` |
| 11 | Per-step fix-cycle cap (`IW_CORE_FIX_CYCLE_MAX`) is unchanged | ✅ `IW_CORE_FIX_CYCLE_MAX` remains untouched |
| 12 | No code outside `fix_cycle.py` and `batch_manager.py` was touched | ✅ Scope confirmed by reading both files — no changes to `step_monitor.py`, `config.py`, or any other module |

---

## Observations

**Item 9 (race condition) — acceptable but worth noting.** The code does not use an explicit `SELECT ... FOR UPDATE` lock before transitioning the `WorkItem.status`. The check-and-update runs inside a single session acquired by `_session_factory()`, so under normal sequential polling there is no race. Concurrent execution of `_launch_step()` for the same work_item from multiple poll cycles would require a single daemon instance misbehaving; this is not a production concern. A `FOR UPDATE` lock would make the intent explicit without requiring code-style knowledge to validate. **Not a finding** since the implementation matches existing conventions in the file — other status transitions (e.g. `step.status = StepStatus.in_progress`, `work_item.status = WorkItemStatus.in_progress`) use the same pattern — but the design doc checklist item could be satisfied more precisely here.

**Item 1 — `_get_max_review_relaunches()` vs a module-level constant.** The design checklist says "read from env with explicit default `15`". The implementation uses a function that reads env on every call rather than a module-level constant. This is technically more testable (avoids `importlib.reload()` per CLAUDE.md) but diverges slightly from the checklist wording which mentions "module load". The function is called from the cap-check in `batch_manager` and from `transition_item_to_failed_for_loop` so the default is always freshly read. Not a finding.

**SQLAlchemy 2.0 style consistency.** Both `count_review_relaunches()` and `transition_item_to_failed_for_loop()` use `.where(...)` with Column-level expressions (not `.filter(...)` with ORM-style expressions), consistent with the newer SQLAlchemy 2.0 pattern already used elsewhere in the file.

**Pre-edit gates.** `make lint` and `make format-check` both pass against the working tree as of this review.

---

## Scope Confirmation

No changes to any file outside `orch/daemon/fix_cycle.py` and `orch/daemon/batch_manager.py` were observed. The new functions `_get_max_review_relaunches`, `count_review_relaunches`, and `transition_item_to_failed_for_loop` live in `fix_cycle.py`; the cap-check call and its `return` guard live in `batch_manager.py`'s `_launch_step()`.

---

## Conclusion

S03 is a clean implementation of the cumulative review-relaunch cap. All 12 checklist items are satisfied. The implementation is within scope, uses correct SQLAlchemy 2.0 patterns, and correctly uses `event_metadata` (not `metadata`) for the DaemonEvent. No changes are requested.
