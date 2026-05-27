# I-00116_S04_CodeReview_Backend_prompt

**Work Item**: I-00116
**Step**: S04
**Agent**: CodeReview (reviewing S03 — Backend)

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy.

## Scope of review

ONLY `orch/daemon/fix_cycle.py` and `orch/daemon/batch_manager.py`. Flag any change outside these two files as a CRITICAL scope violation.

## Input Files

- **Runtime state**: `uv run iw item-status I-00116 --json`
- **Design**: `ai-dev/active/I-00116/I-00116_Issue_Design.md`
- **S03 report**: `ai-dev/active/I-00116/reports/I-00116_S03_Backend_report.md`
- **The changed files**: `orch/daemon/fix_cycle.py`, `orch/daemon/batch_manager.py`

## Output Files

- Review report: `ai-dev/active/I-00116/reports/I-00116_S04_CodeReview_report.md`

## Review Checklist

| # | Check |
|---|-------|
| 1 | `IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM` is read from env with explicit default `15` |
| 2 | The counter is computed from the `step_runs` table (NOT in-memory) so it survives daemon restart |
| 3 | The query joins to `WorkflowStep` to filter on `step_type in ('code_review','code_review_final')` |
| 4 | Cap check fires BEFORE launching another review step run (not after) |
| 5 | On cap exceeded: `WorkItem.status = WorkItemStatus.failed` |
| 6 | DaemonEvent emitted with type `review_relaunch_cap_exceeded` and `event_metadata` (NOT `metadata`) |
| 7 | DaemonEvent payload includes cap, actual_count, and a list of recent review step runs with their started_at and status |
| 8 | Transition is idempotent: if item is already `failed`, no-op (guard with `if wi.status == WorkItemStatus.failed: return`) |
| 9 | No race: holding `SELECT ... FOR UPDATE` lock OR equivalent before transitioning |
| 10 | Log line uses `%`-style placeholders, NOT f-string inside `logger.error(...)` |
| 11 | Per-step fix-cycle cap (`IW_CORE_FIX_CYCLE_MAX`) is unchanged |
| 12 | No code outside `fix_cycle.py` and `batch_manager.py` was touched |

## Required Pre-flight Gates

```bash
make lint
make format-check
```

## Verdict Contract (REQUIRED in your report)

Same JSON contract block as S02. Verdict must be `pass` or `fail`. Findings array empty if pass.

## Step Done Contract

Call `iw step-done S04 --report ai-dev/active/I-00116/reports/I-00116_S04_CodeReview_report.md` before exit. Never exit without calling `iw step-done` or `iw step-fail`.
