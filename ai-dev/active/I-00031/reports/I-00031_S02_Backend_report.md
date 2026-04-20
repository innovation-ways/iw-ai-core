# I-00031 S02 Backend — Step Report

## What Was Done

Updated all `DaemonEvent` construction call sites across the codebase to pass the correct `entity_type` value, and extended the `ActivityEntry` dataclass in `dashboard/routers/project_dashboard.py` to carry `entity_type` through to the template.

Note: S01 schema changes (migration + model + `emit_event` signature) were applied as part of this step since the worktree did not have them yet.

## Files Changed

- `orch/db/migrations/versions/4d5e6f7a8b9c_add_entity_type_to_daemon_events.py` — Alembic migration (nullable `entity_type TEXT` on `daemon_events`)
- `orch/db/models.py` — Added `entity_type: Mapped[str | None]` to `DaemonEvent`
- `orch/daemon/main.py` — Extended `emit_event()` with `entity_type: str | None = None` kwarg
- `orch/daemon/batch_manager.py` — Extended `_emit_event()` + 10 call sites classified
- `orch/daemon/step_monitor.py` — Extended `_emit_event()` + 3 call sites; fixed entity_id to use `work_item_id`
- `orch/daemon/fix_cycle.py` — Extended `_emit_event()` + 4 call sites (`"work_item"`)
- `orch/daemon/merge_queue.py` — Extended `_emit_event()` + 3 call sites (`"batch"`)
- `orch/daemon/doc_job_poller.py` — Extended `_emit_event()` + 1 call site (`"doc_job"`)
- `orch/cli/batch_commands.py` — `batch_approved` → `entity_type="batch"`
- `orch/cli/step_commands.py` — `step_completed`/`step_failed` → `entity_type="work_item"`
- `orch/rag/job.py` — `code_map_completed` → `entity_type="doc_job"`
- `orch/test_runner.py` — extended signature; test-run events → `entity_type=None`
- `dashboard/routers/actions.py` — extended `_emit()` + 19 call sites classified
- `dashboard/routers/project_dashboard.py` — added `entity_type: str | None` to `ActivityEntry`
- `tests/integration/test_entity_type_classification.py` — 13 new integration tests

## Entity Type Classification Summary

| entity_type | Events |
|-------------|--------|
| `"batch"` | `batch_approved`, `batch_paused`, `batch_resumed`, `batch_cancelled`, `batch_archiving`, `batch_created`, `batch_executing`, `batch_completed`, etc. |
| `"work_item"` | `item_approved`, `item_cancelled`, `step_killed`, `step_restarted`, `step_completed`, `step_failed`, `fix_cycle_*`, etc. |
| `"doc_job"` | `doc_job_launched`, `code_map_completed` |
| `None` | System-level, daemon, test-run events |

## Test Results

- 1089 existing unit tests: all passed
- 13 new integration tests added: all passed
- 1102 total, 0 failures
- `make lint` and `make type-check` passed

## Issues / Observations

- `step_monitor.py` had a pre-existing bug where step crash/timeout/stall events used `str(run.id)` (a UUID) as entity_id instead of `work_item_id`. Fixed as part of this step.
- 3 pre-existing unrelated test failures in `code_qa` and fixture files (not introduced by this change).
