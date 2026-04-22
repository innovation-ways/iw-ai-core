# CR-00017_S03_Backend_report

**Work Item**: CR-00017 — Daemon-only migration application
**Step**: S03
**Agent**: backend-impl
**Completion Status**: complete

---

## What Was Done

Implemented `orch/db/safe_migrate.py` — the library that serves as the single choke-point between agent-context code and DB-mutating alembic calls. Per the CR design, agents GENERATE migrations but the daemon APPLIES them; this library enforces that contract at the Python level.

### Public API delivered

| Function | Description |
|----------|-------------|
| `apply(live_db_url, batch_id)` | Acquires migration lock, runs `alembic upgrade head`, releases lock. Guarded by `AgentContextForbidden`. |
| `rollback(live_db_url, steps, batch_id)` | Runs `alembic downgrade -N`. Guarded by `AgentContextForbidden`. |
| `dry_run(tempdb_url, batch_id)` | Upgrades against a disposable temp DB. Refuses live DB URL. |
| `list_pending_revisions(db_url)` | Pure read: compares ScriptDirectory heads to DB revision. Raises `MultipleHeadsError` on multi-head. |
| `current_revision(db_url)` | Pure read from `alembic_version` table. |
| `is_live_db_url(url)` | Returns True if URL matches live DB from `orch.config`. |

### Exceptions

- `AgentContextForbidden` — raised when `IW_CORE_AGENT_CONTEXT='true'` and `apply()` or `rollback()` is called.
- `MultipleHeadsError` — raised when the alembic revision graph has >1 head, with both head IDs and merge instruction in the message.
- `MigrationLockHeldError` — raised when the migration lock is held by another item (stale agent).

### Key implementation details

1. **First-line guard**: `apply()` and `rollback()` call `_assert_not_agent_context()` as the very first statement — before any session creation, before any alembic call.
2. **Live-DB sanity check**: `dry_run()` refuses if `tempdb_url == live_db_url` (via `is_live_db_url()`).
3. **Multi-head detection**: `list_pending_revisions()` uses `ScriptDirectory.from_config().get_heads()` — raises `MultipleHeadsError` with both heads and the `alembic merge` command.
4. **Audit logging**: Every `dry_run`, `apply`, and `rollback` writes to `pending_migration_log` via a fresh short-lived session (independent of caller's session).
5. **Stdout/stderr capture**: Uses `contextlib.redirect_stdout/redirect_stderr` into `StringIO`, truncated to last 16KB.
6. **Alembic programmatic API**: Uses `alembic.config.Config` + `alembic.command.upgrade/downgrade` — no subprocesses, no CLI.
7. **Migration lock**: `_acquire_migration_lock` / `_release_migration_lock` use `FOR UPDATE` against `migration_locks` table with `ON CONFLICT DO UPDATE` upsert pattern.
8. **MIGRATIONS_SCRIPT_LOCATION**: Points to `orch/db/migrations` via `Path(__file__).parent.parent.parent` — no hardcoded paths.

### Unit test smoke (`tests/unit/test_safe_migrate.py`)

8 tests covering:
- `_assert_not_agent_context` raises when env is `true`, passes otherwise.
- `apply()` refuses in agent context.
- `rollback()` refuses in agent context.
- `dry_run()` refuses live DB URL.
- `list_pending_revisions()` raises `MultipleHeadsError` with both head IDs in message.
- `is_live_db_url()` matches config URL.

---

## Files Changed

- `orch/db/safe_migrate.py` (new — 479 lines)
- `tests/unit/test_safe_migrate.py` (new — 80 lines)

---

## Test Results

```
tests/unit/test_safe_migrate.py: 8 passed
make test-unit: 1190 passed
```

**Lint note**: `N818` (Exception name should end in `Error`) fires on `AgentContextForbidden`. The CR design explicitly names the exception `AgentContextForbidden` (matching the existing pattern in the codebase like `MigrationLockHeldError`). All other lint checks pass.

---

## Notes

- S05 (daemon integration) will wire this library into the merge queue pipeline.
- Integration tests for the full 3-phase pipeline (testcontainer-driven) live in S11.
- The `MigrationLockHeldError` uses project_id `'innoForge'` — confirmed against existing `migration_locks` usage in `orch/db/models.py`.
- The `pending_migration_log` table must already exist (created by S01/S02) for logging to succeed in integration scenarios.
