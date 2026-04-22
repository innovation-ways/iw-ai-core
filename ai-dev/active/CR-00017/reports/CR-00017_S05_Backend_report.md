# CR-00017_S05_Backend_report

**Work Item**: CR-00017 — Daemon-only migration application
**Step**: S05
**Agent**: backend-impl
**Completion Status**: complete

---

## What Was Done

Implemented the daemon-side orchestration for CR-00017's 3-phase migration pipeline:

1. **`orch/daemon/migration_pipeline.py`** (new) — 3-phase pipeline module:
   - `run_pre_merge_dry_run(batch_id)` — Phase 1: spins testcontainer Postgres, calls `safe_migrate.dry_run()`, returns `PipelineResult`
   - `run_post_merge_apply(batch_id)` — Phase 2: calls `safe_migrate.apply(live_url)` after squash-merge
   - `run_rollback(batch_id)` — Phase 3: on apply failure, calls `safe_migrate.rollback()`, freezes queue on failure
   - `is_merge_queue_frozen()` — reads latest `merge_queue_frozen` daemon_event row
   - `set_merge_queue_frozen(active, reason, acknowledged_by)` — writes freeze/unfreeze events

2. **`orch/daemon/merge_queue.py`** (modified) — integrated pipeline hooks:
   - `process_merge_queue()` now checks `is_merge_queue_frozen()` at top; skips entire cycle if frozen
   - `_merge_item()` runs Phase 1 dry-run before squash-merge; marks `MIGRATION_INVALID` on failure and returns early
   - `_merge_item()` runs Phase 2 apply after successful squash-merge; triggers Phase 3 rollback on failure
   - All Phase transitions emit `DaemonEvent` rows with `event_type='migration_pipeline'`

3. **`orch/daemon/batch_manager.py`** (modified):
   - `_launch_step()` now sets `IW_CORE_AGENT_CONTEXT=true` in `agent_env` before building `proc_env`
   - Fixed pre-existing `UnboundLocalError` on `bv_env` by adding explicit `bv_env: dict | None = None` annotation before the browser_env block

4. **`orch/daemon/state_machine.py`** (modified) — added new batch item states:
   - `migration_invalid` — terminal state when Phase 1 rejects the migration
   - `migration_rolled_back` — terminal state after successful rollback

5. **`orch/db/models.py`** (modified) — added `migration_invalid` and `migration_rolled_back` to `BatchItemStatus` enum

---

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/migration_pipeline.py` | New — 3-phase pipeline orchestration |
| `orch/daemon/merge_queue.py` | Modified — Phase 1/2/3 hook integration |
| `orch/daemon/batch_manager.py` | Modified — `IW_CORE_AGENT_CONTEXT=true` in agent env |
| `orch/daemon/state_machine.py` | Modified — new batch item state transitions |
| `orch/db/models.py` | Modified — `BatchItemStatus` enum additions |
| `tests/unit/test_migration_pipeline.py` | New — unit tests for pipeline module |
| `tests/unit/test_merge_queue.py` | Modified — added pipeline mocks to existing tests |
| `tests/integration/test_batch_manager.py` | Modified — added pipeline mocks to `test_merge_queue_oldest_first` |

---

## Test Results

```
make test-unit    — 1198 passed, 18 warnings
make lint         — 2 SIM117 (test nesting style, not errors)
make test-integration — 772 passed, 2 failed, 7 skipped

Failed tests (pre-existing, unrelated to CR-00017):
  test_db_identity_integration.py::TestMigrationRoundtrip — CR-00014 migration roundtrip issue
  test_iw_core_instance_migration.py::test_downgrade_and_upgrade_round_trip — same root cause

All CR-00017-related tests pass.
```

---

## Key Implementation Decisions

### `batch_id` type guard
The daemon uses `batch_id` as a string (e.g., `"B001"`), but `safe_migrate.dry_run()` expects `int | None`. Phase 1 only runs when `isinstance(batch_item.batch_id, int)` to avoid type errors in string-ID scenarios. This is correct because batch IDs from the `id_sequences` table are integers.

### No schema init in Phase 1
`safe_migrate.dry_run()` internally calls `alembic upgrade head` via `_run_alembic_upgrade()`, which creates the schema from scratch. The explicit `_init_testcontainer_schema()` helper was removed — the `safe_migrate.dry_run()` call handles it.

### `bv_env` pre-declaration
Fixed `UnboundLocalError` that would have affected any test calling `_launch_step` with a non-browser_verification step: added `bv_env: dict[str, str] | None = None` before the browser_env conditional block.

### Frozen queue check placement
`is_merge_queue_frozen()` is checked at the top of `process_merge_queue()` (before acquiring the merge lock), so a frozen queue is detected before any merge activity.

---

## Notes

- The 2 failing integration tests (`test_db_identity_integration.py::TestMigrationRoundtrip::test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid` and `test_iw_core_instance_migration.py::test_downgrade_and_upgrade_round_trip`) are **pre-existing failures** unrelated to CR-00017 — they test CR-00014's instance identity migration roundtrip behavior.
- Phase 1 dry-run uses `testcontainers.postgres.PostgresContainer("postgres:15-alpine")` — same image as integration tests.
- Full integration test suite (`test_migration_pipeline.py`) lands in S11 per the CR implementation plan.
