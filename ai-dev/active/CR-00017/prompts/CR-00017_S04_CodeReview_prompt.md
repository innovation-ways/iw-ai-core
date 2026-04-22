# CR-00017_S04_CodeReview_prompt

**Work Item**: CR-00017 — Daemon-only migration application
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## Input Files

- `ai-dev/active/CR-00017/CR-00017_CR_Design.md`
- `ai-dev/active/CR-00017/reports/CR-00017_S03_Backend_report.md`
- All files in S03's `files_changed`
- `orch/CLAUDE.md`, `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00017/reports/CR-00017_S04_CodeReview_report.md`

## Review Checklist

### 1. Guard invariants (CRITICAL)
- `apply()` and `rollback()` have `_assert_not_agent_context()` as their very first statement — before any session, before any alembic call.
- `dry_run()` refuses when `tempdb_url == live_db_url`; sanity check uses `is_live_db_url()` helper, not string equality alone (URL normalisation matters).
- `list_pending_revisions()` and `current_revision()` do NOT have the agent-context guard (they're pure reads).
- The guard reads env DIRECTLY each call (no cached value) — so a test can flip the env with `monkeypatch.setenv`.

### 2. Multi-head detection
- Uses `ScriptDirectory.get_heads()`.
- `MultipleHeadsError` message includes both head names and the exact suggested resolution command.
- Triggered from `list_pending_revisions` AND transitively from `dry_run` / `apply` (anywhere the pipeline would otherwise pick an ambiguous head).

### 3. Log writing
- Every `dry_run` / `apply` / `rollback` opens a **fresh** short-lived session (not reusing a caller's session).
- Session is closed (context manager or explicit `session.close()`) in a `finally`.
- stdout/stderr captured via `redirect_stdout` + `redirect_stderr`; truncated to last 16KB before write.
- Success and failure paths BOTH write a log row.
- Log row has correct `direction` / `phase` for each method.

### 4. Alembic programmatic API
- `alembic.config.Config` constructed in Python; no shell-out.
- `set_main_option("sqlalchemy.url", ...)` and `set_main_option("script_location", ...)` set.
- No relative paths that break when called from a different cwd — use `Path(__file__).parent.parent / "migrations"` or equivalent.

### 5. Migration lock
- `apply()` and `rollback()` acquire the lock with a distinct item name (e.g. `"daemon-runtime"`), distinct from agent item names.
- Lock released in `finally`.
- `MigrationLockHeldError` raised with a clear message naming the current holder.

### 6. Type hints and dataclasses
- Public API has full type hints.
- Dataclasses are frozen.
- Exceptions are `RuntimeError` subclasses (not bare `Exception`).

### 7. Test quality
- Tests monkeypatch `IW_CORE_AGENT_CONTEXT` (don't assume process-level state).
- Tests mock `ScriptDirectory` for multi-head scenarios (don't require a real alembic graph).
- Tests fail on pre-change code (the module doesn't exist there).
- No live-DB connections in tests.

### 8. No daemon wiring
- S03 did NOT touch `orch/daemon/`. If it did, that's scope creep — HIGH.

### 9. Project conventions
- `logging.getLogger(__name__)`, no `print`.
- Relative imports OK; no cross-layer imports (e.g. `orch.db.*` must not import `dashboard`).

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW — standard. Fix in place.

## Subagent Result Contract

Standard code-review JSON.

## Lifecycle commands

```bash
uv run iw step-start CR-00017 --step S04
uv run iw step-done CR-00017 --step S04 --report ai-dev/active/CR-00017/reports/CR-00017_S04_CodeReview_report.md
```
