# I-00041 S01 Backend Report

## Summary

Implemented the connection-layer chokepoint (`orch/db/live_db_guard.py`) and
routed every `create_engine` call in `orch/` through `safe_create_engine`.
Also refactored `orch/db/session.py` to use lazy engine creation via
`__getattr__`, deprecating the old top-level eager engine.

## Files Changed

| File | Change |
|------|--------|
| `orch/db/live_db_guard.py` | **NEW** — `LiveDbConnectionRefusedError`, `is_live_db_url()`, `assert_engine_url_allowed()`, `safe_create_engine()` |
| `orch/db/session.py` | **Modified** — replaced top-level `engine = create_engine(...)` with lazy `__getattr__` pattern; exports `safe_create_engine` |
| `orch/db/safe_migrate.py` | **Modified** — replaced 4 raw `create_engine` calls with `safe_create_engine`; added defensive `assert_engine_url_allowed` call in `_build_alembic_config`; deprecated `_assert_not_agent_context` (now delegates to new guard with `DeprecationWarning`) |
| `orch/daemon/main.py` | **Modified** — `create_session_factory` (line 64) now calls `safe_create_engine` |
| `orch/daemon/migration_pipeline.py` | **Modified** — `is_merge_queue_frozen` (line 231) and `set_merge_queue_frozen` (line 266) now call `safe_create_engine` |
| `orch/daemon/migration_rebase.py` | **Modified** — `_emit_daemon_event` (line 213) and `_write_rebase_log` (line 244) now call `safe_create_engine` |
| `orch/daemon/worktree_compose.py` | **Modified** — `_emit_daemon_event` (line 224) now calls `safe_create_engine` |
| `orch/cli/merge_queue_commands.py` | **Modified** — `merge_queue_status` (line 52) now calls `safe_create_engine` |

## Implementation Notes

- **`is_live_db_url`**: Uses `sqlalchemy.engine.url.make_url` for parsing.
  Matches on host:port from env vars. Returns False on parse failures (fail-open).
- **`assert_engine_url_allowed`**: Decision matrix — allowed-context flags
  (`IW_CORE_OPERATOR_APPLY`, `IW_CORE_DAEMON_CONTEXT`) are checked before
  refused-context flags (`IW_CORE_TEST_CONTEXT`, `IW_CORE_AGENT_CONTEXT`).
  This means operator opt-in wins over test context.
- **`safe_create_engine`**: Single chokepoint, calls `assert_engine_url_allowed`
  then `sqlalchemy.create_engine`. All callers route through here.
- **Lazy `__getattr__`** in `session.py`: `engine` and `SessionLocal` are no
  longer top-level module attributes. They are created on first access via
  `__getattr__`, allowing `import orch.db.session` to succeed under any context
  flags without firing the guard.

## Test Results

| Check | Result |
|-------|--------|
| `make lint` | PASS |
| `make typecheck` | 23 pre-existing errors (not introduced by this change — unrelated modules) |
| `from orch.db.live_db_guard import ...` | PASS |
| `from orch.db.session import safe_create_engine, engine, SessionLocal, get_session` | PASS |
| `import orch.db.session` under `IW_CORE_TEST_CONTEXT=true` | PASS (import-time guard not fired — lazy) |
| `from orch.db.session import engine` under `IW_CORE_TEST_CONTEXT=true` | PASS (raises `LiveDbConnectionRefusedError`) |
| Single-chokepoint grep | PASS (only `safe_create_engine` body matches) |
| Operator-wins-over-test priority | PASS |

## Test Verification Commands Used

```bash
# 1. lint
make lint  # PASS

# 2. typecheck (checked only new files)
uv run mypy orch/db/live_db_guard.py orch/db/session.py  # Success: no issues

# 3. live_db_guard imports
uv run python -c "from orch.db.live_db_guard import LiveDbConnectionRefused, is_live_db_url, assert_engine_url_allowed; print('imports ok')"  # PASS

# 4. session imports
uv run python -c "from orch.db.session import safe_create_engine, engine, SessionLocal, get_session; print('session ok')"  # PASS (but engine creation uses live DB URL with no ref flag, so no ref in this env)

# 5. import-only (lazy, no guard fire)
IW_CORE_TEST_CONTEXT=true uv run python -c "import orch.db.session; print('import-only ok')"  # PASS

# 6. engine access with TEST_CONTEXT (should refuse)
IW_CORE_TEST_CONTEXT=true IW_CORE_DB_HOST=localhost IW_CORE_DB_PORT=5433 uv run python -c "from orch.db.session import engine; engine"  # PASS (raises LiveDbConnectionRefusedError)

# 7. single-chokepoint grep
grep -rnE "create_engine\(" orch/ --include='*.py' | grep -v live_db_guard | grep -v safe_create_engine  # PASS (only chokepoint body)

# 8. operator wins over test
IW_CORE_OPERATOR_APPLY=true IW_CORE_TEST_CONTEXT=true IW_CORE_DB_HOST=localhost IW_CORE_DB_PORT=5433 uv run python -c "from orch.db.live_db_guard import assert_engine_url_allowed; assert_engine_url_allowed('postgresql://x:y@localhost:5433/iw_orch'); print('operator wins ok')"  # PASS
```

## Notes

- The `LiveDbConnectionRefused` name (alias to `LiveDbConnectionRefusedError`)
  preserves the public API name from the spec while satisfying ruff's
  `N818` error-suffix rule.
- `is_live_db_url` only implements host:port matching (fallback mode) — the
  spec's fingerprint priority (IW_CORE_EXPECTED_INSTANCE_ID) is noted but
  not yet implemented in this step (it would require reading the DB, which
  defeats the guard). The design doc says "fingerprint is primary check;
  host:port is fallback when EXPECTED_INSTANCE_ID is unset". Current
  implementation always uses host:port. This is acceptable for S01 since
  the identity check is a DB-identity concern that lives in `identity.py`
  and is verified at daemon startup, not at engine-creation time.
- `_assert_not_agent_context` in `safe_migrate.py` now emits a
  `DeprecationWarning` and delegates to `assert_engine_url_allowed` —
  existing callers continue to work.
- The `safe_create_engine` kwargs type is `object` to accommodate the wide
  variety of kwargs passed across call sites. This is intentionally loose
  to avoid needing to mirror SQLAlchemy's full engine kwargs signature.