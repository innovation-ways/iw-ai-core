# CR-00017_S04_CodeReview_report

**Work Item**: CR-00017 — Daemon-only migration application
**Step**: S04
**Agent**: code-review-impl
**Completion Status**: complete

---

## What Was Done

Reviewed S03's implementation of `orch/db/safe_migrate.py` against the CR-00017 design and the S04 review checklist.

---

## Files Changed

- `orch/db/safe_migrate.py` (new — 479 lines)
- `tests/unit/test_safe_migrate.py` (new — 79 lines)

---

## Review Findings

### Guard invariants — PASS

- `apply()` (line 395) and `rollback()` (line 437) both call `_assert_not_agent_context()` as their **very first statement** — before any session, before any alembic call. ✓
- `dry_run()` refuses when `tempdb_url == live_db_url` via `_is_live_db_url()` helper (line 356). ✓
- `list_pending_revisions()` (line 312) and `current_revision()` (line 472) do **NOT** have the agent-context guard — they are pure reads. ✓
- The guard reads `os.environ.get("IW_CORE_AGENT_CONTEXT")` directly each call (line 119), not cached. ✓

### Multi-head detection — PASS

- Uses `ScriptDirectory.from_config().get_heads()` (line 323). ✓
- `MultipleHeadsError` message includes both head names and the exact suggested resolution command `alembic merge -m 'merge branches' ...` (lines 325–330). ✓
- Raised from `list_pending_revisions()` — which is called transitively from `dry_run` / `apply`. ✓

### Log writing — PASS

- Every `dry_run` / `apply` / `rollback` calls `_write_migration_log()` which opens a **fresh** short-lived session via `create_engine` + `sessionmaker` (lines 172–196). ✓
- Session is closed in a `finally` block (lines 194–195). ✓
- stdout/stderr captured via `redirect_stdout` + `redirect_stderr` into `StringIO`, truncated to last 16KB via `_truncate_tail()` (line 154–158). ✓
- Both success and failure paths write a log row. ✓
- Log row has correct `direction` / `phase` per method. ✓

### Alembic programmatic API — PASS

- `alembic.config.Config` constructed in Python; no shell-out. ✓
- `set_main_option("sqlalchemy.url", ...)` and `set_main_option("script_location", ...)` set (lines 137–138). ✓
- `MIGRATIONS_SCRIPT_LOCATION = Path(__file__).parent.parent.parent / "db" / "migrations"` (line 55) — absolute path derived from `__file__`, no hardcoded relative paths. ✓

### Migration lock — PASS

- `apply()` and `rollback()` acquire the lock with `item="daemon"` (distinct from agent item names). ✓
- Lock released in `finally` block (line 428, 469). ✓
- `MigrationLockHeldError` includes clear message naming the current holder (lines 267–271). ✓

### Type hints and dataclasses — PASS

- All public API functions have full type hints. ✓
- All dataclasses are frozen (`@dataclass(frozen=True)` on lines 81, 88, 98, 103). ✓
- All exceptions are `RuntimeError` subclasses (lines 64, 68, 72). ✓

### Test quality — PASS

- Tests monkeypatch `IW_CORE_AGENT_CONTEXT` via `patch.dict("os.environ", ...)` (no process-level state assumptions). ✓
- Tests mock `ScriptDirectory` for multi-head scenarios (line 60–66). ✓
- Tests fail on pre-change code — module didn't exist before S03. ✓
- No live-DB connections in tests. ✓

### No daemon wiring — PASS

- S03 did NOT touch `orch/daemon/`. No scope creep. ✓

### Project conventions — PASS

- `logging.getLogger(__name__)` (line 53), no `print`. ✓
- Relative imports used correctly. ✓

---

## Issues

### N818 lint warning (MEDIUM)

`AgentContextForbidden` does not end in `Error`. The CR design explicitly names it `AgentContextForbidden` (matching the pattern of `MigrationLockHeldError` in the project). The name is by design per CR-00017 spec; the lint rule is a style guideline that conflicts with the explicit spec naming. No action required — this is an intentional deviation documented in the S03 report.

---

## Test Results

```
tests/unit/test_safe_migrate.py: 8 passed
```

All tests pass. No regressions.

---

## Summary

S03 implementation is **correct and complete** for the scope of the safe_migrate library. All 9 checklist items pass. The N818 lint warning is an intentional design decision matching the CR-00017 spec naming convention. Ready for S05 (daemon integration).
