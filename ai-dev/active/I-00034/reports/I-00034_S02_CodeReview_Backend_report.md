# S02 CodeReview — I-00034 (Backend)

## What was reviewed

S01 Backend implementation: `dashboard/routers/items.py` — duration aggregation fix.

## Verdict: **pass**

## Files changed

- `dashboard/routers/items.py` — only file modified (confirmed via `git status`)

## Review checklist

### 1. Correctness of aggregation (CRITICAL) — PASS

| Check | Status |
|-------|--------|
| Unions `step_runs` AND `fix_cycles` | ✅ Lines 275–307: two separate bulk queries |
| `MIN(started_at)` / `MAX(completed_at)` | ✅ `func.min` / `func.max` on both tables |
| `started_at = None` → "never launched" → duration None | ✅ Line 394: `step_spans.get(step.id, (None, None))` |
| `completed_at = None` → in-flight → duration None | ✅ Line 395: both must be non-None |
| `StepDetail.started_at` / `completed_at` surface aggregated values | ✅ Lines 409–410 |

### 2. No N+1 (HIGH) — PASS

- `_aggregate_step_spans(db, step_db_ids)` called once at line 378, **before** the step loop.
- Exactly **2 aggregation queries** total (one per table), both use `GROUP BY step_id` — no per-step query.
- Empty `step_db_ids` guarded at line 367 (`if step_db_ids:`).

### 3. `_get_metrics` corrected — PASS

`_get_metrics` (lines 427–431) reads from `StepDetail.started_at` / `completed_at` which now carry the aggregated span. No separate fix needed.

### 4. No out-of-scope changes (CRITICAL) — PASS

Confirmed via `git status`: only `dashboard/routers/items.py` modified. Specifically NOT touched:
- `orch/daemon/fix_cycle.py` — resets unchanged
- `orch/cli/step_commands.py` — `started_at` assignment unchanged
- `orch/db/models.py` — no new columns or indexes
- No Alembic migration
- `_synthetic_setup_step` / `_synthetic_merge_step` — untouched
- Other router functions — untouched

### 5. In-progress behaviour unchanged — PASS

- Templates `item_overview.html` / `item_header.html` NOT modified.
- `duration_secs = None` when `latest_completed_at` is None (line 398) → template renders `—`.
- `StepDetail.started_at` for in-progress steps now shows aggregated earliest start (display improvement per AC3).

### 6. Comment anchor (MEDIUM) — PASS

Line 266–267: `I-00034: WorkflowStep.started_at/completed_at reflect only the LAST iteration (daemon resets them on retry/fix-cycle). Aggregate from append-only step_runs ∪ fix_cycles.`

### 7. Project conventions (MEDIUM) — PASS (minor nitpick)

- SQLAlchemy 2.0: `select(...)`, `db.execute(...).all()` ✅
- Type hints consistent ✅
- `func` imported locally inside `_aggregate_step_spans` (line 271) and `_get_steps` (line 368) — harmless duplication, not a bug

### 8. Security / correctness — PASS

- No raw SQL string interpolation ✅
- `step_id.in_(step_db_ids)` used for bulk `WHERE` clauses ✅
- `started_at` / `completed_at` are nullable columns on both models; code handles `None` correctly ✅

### 9. Tests — PASS

All pre-existing failures are **unrelated** to this change (identity/pid-file/CLI migration fixtures).

| Suite | Passed | Failed | Pre-existing failures |
|-------|--------|--------|-----------------------|
| Unit | 1220 | 12 | `test_daemon_core.py`, `test_merge_queue_cli.py`, `test_migrations_cli.py`, `test_safe_migrate*.py` — all identity/CLI context issues |
| Integration | 793 | 3 | `test_db_identity_integration.py`, `test_iw_core_instance_migration.py`, `test_agent_constraints_coverage.py` — migration/identity fixtures |

**Lint**: `ruff check dashboard/routers/items.py` — all checks passed. Pre-existing lint errors in `project_pages.py:193` and `item_commands.py:593` are unrelated to this change.

**Typecheck**: `mypy dashboard/routers/items.py` — Success: no issues found.

## Findings

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00034",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "1220 unit passed (12 pre-existing failures), 793 integration passed (3 pre-existing failures), 0 new failures",
  "notes": "One minor style nitpick: func is imported twice locally (lines 271 and 368). Not a bug, not required to fix. All critical correctness checks pass."
}
```

## Summary

The S01 implementation is correct. The aggregation correctly unions `step_runs` and `fix_cycles`, handles nullability for never-launched and in-flight steps, surfaces aggregated timestamps on `StepDetail`, and does so with exactly 2 bulk SQL queries (no N+1). No out-of-scope files were touched. The fix is ready for S03 (Tests).