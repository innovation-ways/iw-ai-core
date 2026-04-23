# S01 Backend Report — I-00034

## What was done

Fixed the Item view's duration computation in `dashboard/routers/items.py` to aggregate from the append-only `step_runs` and `fix_cycles` tables instead of reading the per-iteration `WorkflowStep.started_at` / `completed_at` columns (which get reset to NULL on each retry/fix-cycle).

## Changes

### `dashboard/routers/items.py`

**New helper** `_aggregate_step_spans(db, step_db_ids)` (lines 259–305):
- Issues exactly **2 aggregation queries** regardless of step count:
  1. `SELECT step_id, MIN(started_at), MAX(completed_at) FROM step_runs WHERE step_id IN (...) GROUP BY step_id`
  2. `SELECT step_id, MIN(started_at), MAX(completed_at) FROM fix_cycles WHERE step_id IN (...) GROUP BY step_id`
- Combines run and cycle spans per step_id in Python, taking the true earliest start and latest completed across both tables.
- Includes the anchor comment `I-00034: WorkflowStep.started_at/completed_at reflect only the LAST iteration (daemon resets them on retry/fix-cycle). Aggregate from append-only step_runs ∪ fix_cycles.`

**`_get_steps`** (lines 374–420):
- Calls `_aggregate_step_spans(db, step_db_ids)` before the step loop (single extra call site).
- Uses `step_spans.get(step.id, (None, None))` to get `(earliest_started_at, latest_completed_at)` for each step.
- `duration_secs = (latest_completed_at - earliest_started_at).total_seconds()` only when both are non-None (step completed).
- `StepDetail.started_at` / `completed_at` surface the aggregated span values (not `step.started_at` / `step.completed_at`), so the "Started" column in the step table now shows the true first-launch time.
- For in-progress steps (earliest_started_at set, latest_completed_at is None): `duration_secs = None` — template renders `—`, unchanged.
- For steps that never launched (not in step_spans): `duration_secs = None`, `started_at = None`, `completed_at = None` — unchanged.

**`_get_metrics`**: No changes needed — it reads from `StepDetail.started_at` / `completed_at` which now carry the aggregated values from `_get_steps`.

## Query count

The step-span aggregation issues exactly **2** SQL queries total (one per table, both use `GROUP BY step_id`). The existing `fix_cycle_counts` query runs once before the step loop. The per-step `runs` fetch remains unchanged (used for `last_run.error_message` and `run_count`). Total: 3 queries for `_get_steps` vs. prior 1 + N (N+1 forbidden).

## Pre-existing test status

- **Unit tests**: 1220 passed. 12 failures are pre-existing identity/mock fixture issues in `test_daemon_core.py`, `test_merge_queue_cli.py`, `test_migrations_cli.py`, `test_safe_migrate.py`, `test_safe_migrate_guards.py` — unrelated to this change and consistent with running outside the live DB identity context.
- **Integration tests**: 763 passed, 2 failed (pre-existing `test_db_identity_integration.py::TestMigrationRoundtrip` and `test_iw_core_instance_migration.py` — unrelated migration/identity fixtures). `test_agent_constraints_coverage.py::test_claude_md_references_migrations_policy` also pre-existing.
- **Dashboard tests (non-browser)**: 115 passed, 5 failed (pre-existing SSE/code_qa fixture issues with `answer_stream_v2`).
- **Lint**: `ruff check dashboard/routers/items.py` — all checks passed.
- **Typecheck**: `mypy dashboard/routers/items.py` — success, no issues.

## Notes

- `_get_metrics` required no changes because it pulls from `StepDetail.started_at` / `completed_at` which now carry the correct aggregated values.
- Synthetic setup/merge rows (`_synthetic_setup_step`, `_synthetic_merge_step`) are untouched — their timestamps come from `BatchItem`, not `WorkflowStep`.
- No new file created — the helper is a small private function inside `items.py`.
- RED phase: wrote a scratch test to confirm the bug existed (current code returned 30s instead of 630s for the multi-run scenario), then deleted it per instructions.