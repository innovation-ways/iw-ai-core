# I-00116_S03_Backend_prompt

**Work Item**: I-00116
**Step**: S03
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migration.

## Scope (`allowed_paths`)

You MAY only modify `orch/daemon/fix_cycle.py` and `orch/daemon/batch_manager.py`. The workflow manifest's `scope.allowed_paths` declares the item-level allowlist; for THIS step you stay within those two files.

## Input Files

- **Runtime step state**: `uv run iw item-status I-00116 --json`
- **Design** (read §"Root Cause Analysis" sub-bug 3 + "Fix Plan" S03 row): `ai-dev/active/I-00116/I-00116_Issue_Design.md`
- **S01 + S02 reports**: (S01 is parallel; reference if needed for shared module knowledge)
- **Reference**: I-00113's scope-blocked analysis: `ai-dev/active/I-00113/reports/I-00113_scope_blocked_root_cause_analysis.md` — documents the loop pattern this cap defends against

## Output Files

- Source changes: `orch/daemon/fix_cycle.py` AND `orch/daemon/batch_manager.py`
- Step report: `ai-dev/active/I-00116/reports/I-00116_S03_Backend_report.md`

## Context

Each fix-cycle today caps re-runs per individual step (5, configurable via `IW_CORE_FIX_CYCLE_MAX`). But because every fix-cycle completion in the workflow causes ALL downstream review steps to be re-launched, a single item's review steps can churn ~40+ relaunches without any individual step ever approaching its own cap. Your job: add a cumulative per-work-item cap on review-step relaunches.

## Requirements

### 1. New env var `IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM`

Read with `os.getenv` at module load in `fix_cycle.py` with explicit default `15`:

```python
MAX_REVIEW_RELAUNCHES_PER_ITEM = int(os.getenv("IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM", "15"))
```

**Do NOT modify `orch/config.py`** — that file is outside `scope.allowed_paths` for this step and any edit there will be flagged by S04 as a CRITICAL scope violation. Add a one-line code comment above the constant citing I-00116 (e.g. `# I-00116: cumulative cap; see docs/IW_AI_Core_Daemon_Design.md`).

### 2. Count cumulative review-step relaunches from the DB, not in-memory

The counter MUST be computed by querying `step_runs` so it survives daemon restart. Pattern:

```python
def _count_review_relaunches(db: Session, project_id: str, work_item_id: str) -> int:
    """Count cumulative StepRun rows for review-type steps of this work item."""
    return (
        db.query(StepRun)
        .join(WorkflowStep, ...)  # join on (project_id, work_item_id, step_id)
        .filter(
            StepRun.project_id == project_id,
            StepRun.work_item_id == work_item_id,
            WorkflowStep.step_type.in_(("code_review", "code_review_final")),
        )
        .count()
    )
```

Use SQLAlchemy 2.0 `select(...).where(...)` style if that matches the project's existing convention; check `orch/daemon/fix_cycle.py` for the prevailing style and match it.

### 3. Cap check + transition + DaemonEvent

In `fix_cycle.py` (or wherever a code-review re-launch is decided — likely `batch_manager.py`'s step-launch path), BEFORE launching another review step run:

```python
relaunch_count = _count_review_relaunches(db, project_id, work_item_id)
if relaunch_count >= MAX_REVIEW_RELAUNCHES_PER_ITEM:
    _transition_item_to_failed_for_loop(db, project_id, work_item_id, relaunch_count)
    return  # do NOT launch
```

`_transition_item_to_failed_for_loop` must:
- Set `WorkItem.status = WorkItemStatus.failed`
- Emit `DaemonEvent` of type `review_relaunch_cap_exceeded` with `event_metadata` (NOT `metadata`):
  ```python
  {
      "work_item_id": work_item_id,
      "cap": MAX_REVIEW_RELAUNCHES_PER_ITEM,
      "actual_count": relaunch_count,
      "review_step_runs": [
          {"step_id": sr.step_id, "started_at": sr.started_at.isoformat(), "status": sr.status.name}
          for sr in last_20_review_runs  # most recent 20 for diagnostics
      ],
  }
  ```
- Log `ERROR orch.daemon.fix_cycle: I-00116 review relaunch cap exceeded for %s: %d/%d` with `%`-style.
- Be idempotent: if the item is already `failed`, no-op (use `if wi.status == WorkItemStatus.failed: return`).

### 4. RED → GREEN

S07 owns the test file `tests/integration/test_fix_cycle_review_relaunch_cap.py`. Capture RED reasoning in your report:

> "Pre-fix `fix_cycle.py` / `batch_manager.py` has no per-item relaunch counter; the S07 cap-overflow test will fail because no `review_relaunch_cap_exceeded` DaemonEvent is ever emitted and the work item stays in `in_progress` indefinitely."

### 5. Post-edit gate (MANDATORY)

```bash
make format-check
make lint
```

Fix any violation YOUR edits introduced before exit.

## Project Conventions

- SQLAlchemy 2.0 select style preferred (check existing `fix_cycle.py` for style).
- `DaemonEvent.metadata` is `event_metadata` in Python — never use `.metadata`.
- `WorkItemStatus.failed` (not the string `'failed'`).
- Log with `%`-style placeholders.
- Idempotent transitions — the cap check might fire from multiple polls.

## Constraints

- Touch ONLY `orch/daemon/fix_cycle.py` and `orch/daemon/batch_manager.py`.
- Do NOT touch `orch/daemon/step_monitor.py` (S01).
- Do NOT touch the prompt template files (S05).
- Do NOT touch tests (S07).
- Do NOT add a migration — this is pure runtime logic.

## Step Done Contract

Your report MUST contain:
```json
{"step": "S03", "agent": "Backend", "work_item": "I-00116",
 "files_changed": ["orch/daemon/fix_cycle.py", "orch/daemon/batch_manager.py"],
 "env_var_added": "IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM (default 15)",
 "tdd_red_evidence": "...",
 "post_edit_gates": {"make format-check": "pass", "make lint": "pass"},
 "notes": "..."}
```

After writing the report, call `iw step-done S03 --report ai-dev/active/I-00116/reports/I-00116_S03_Backend_report.md`. **DO NOT exit without calling `iw step-done`.**
