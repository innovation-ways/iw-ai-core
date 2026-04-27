# I-00040 S01 Backend Report

## What was done

Implemented the alembic-version guard helper (`orch/db/alembic_guard.py`) and wired it into three boundaries:

1. **R1 — New helper module** (`orch/db/alembic_guard.py`):
   - `GuardStatus` frozen dataclass: `current_rev`, `head_rev`, `pending: list[str]`, `multiple_heads: list[str]`, `ok: bool`
   - `DBBehindHeadError` (RuntimeError) and re-exported `MultipleHeadsError`
   - `check_db_at_head(db_url?) -> GuardStatus` — pure read-only check, never raises
   - `assert_db_at_head(db_url?)` — raises `DBBehindHeadError` or `MultipleHeadsError` on mismatch; error message contains `current_rev` (or `EMPTY`), `head_rev`, and `make db-migrate`
   - `remediation_message(status) -> str` — single-line human-readable message with all three elements
   - Internally delegates to `safe_migrate.list_pending_revisions` and `current_revision` — no alembic introspection re-implemented

2. **R2 — Daemon startup guard** (`orch/daemon/main.py`):
   - Added `_alembic_guard_startup(session_factory)` called after `verify_instance_identity`
   - Logs `CRITICAL: <msg>` on mismatch and emits a `DaemonEvent` of `event_type="db_schema_mismatch"`
   - Deduplicates events within a 60-second window (`_last_mismatch_event_time`)
   - Exits with `sys.exit(2)` on mismatch
   - Skippable via `IW_CORE_SKIP_ALEMBIC_GUARD=true` (logs WARNING when used)

3. **R4 — Launch-time guard** (`orch/daemon/batch_manager.py::_launch_item`):
   - Added re-check BEFORE any worktree filesystem mutation (before `_setup_worktree`)
   - On mismatch: sets `BatchItem.status = setup_failed`, sets `notes = remediation_message(status)`, emits `item_failed` event with `phase=alembic_guard`, and returns early

4. **R3 — Dashboard guard** (`dashboard/app.py` + `dashboard/middlewares/alembic_guard.py`):
   - `app.state.alembic_guard_status = check_db_at_head()` at construction
   - `AlembicGuardMiddleware` (BaseHTTPMiddleware): re-checks at most once every 10 seconds using module-level lock + timestamp; stores status on `request.state.alembic_guard_status`
   - `require_db_at_head` FastAPI dependency: returns HTTP 503 with `Retry-After: 30` on stale DB
   - Applied to `/batch/{batch_id}/approve` and `/item/{item_id}/approve` in `dashboard/routers/actions.py`

## Files changed

| File | Change |
|------|--------|
| `orch/db/alembic_guard.py` | **NEW** — helper module |
| `orch/daemon/main.py` | Added `_alembic_guard_startup()` call + imports |
| `orch/daemon/batch_manager.py` | Added guard at top of `_launch_item()` |
| `dashboard/app.py` | Added middleware + initial check |
| `dashboard/middlewares/alembic_guard.py` | **NEW** — middleware + utilities |

## Test results

- `make lint`: All checks passed
- `make format`: 2 files reformatted (dashboard/app.py, orch/db/alembic_guard.py) — auto-fixed
- `make typecheck`: Success — no issues found

## Notes / observations

- `orch/db/alembic_guard.py` intentionally does NOT import from `dashboard/` (one-way dependency: dashboard → orch)
- The dashboard middleware does NOT block reads — operators retain full read access to diagnose mismatches
- The `IW_CORE_SKIP_ALEMBIC_GUARD` env var is honored in the daemon startup guard (not inside `_launch_item` which is runtime, not startup)
- The launch-time guard (R4) runs before ANY filesystem mutation in `_launch_item`, which is the earliest possible point after the status change to `setting_up` but before the worktree is created
- The `AlembicGuardMiddleware.dispatch` method signature matches `TimingMiddleware` in the existing codebase (uses `Callable[[Request], Awaitable[Response]]` in TYPE_CHECKING block)
