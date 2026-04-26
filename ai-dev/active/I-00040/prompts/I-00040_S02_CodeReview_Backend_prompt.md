# I-00040 S02 — Code review of S01 (backend wiring)

**Work Item**: I-00040
**Step Being Reviewed**: S01 (backend-impl — alembic guard helper + daemon/dashboard/launch wiring)
**Review Step**: S02
**Agent**: code-review-impl

## ⛔ Docker / Migrations off-limits

Standard rules.

## Input Files

- `ai-dev/active/I-00040/I-00040_Issue_Design.md`
- `ai-dev/active/I-00040/reports/I-00040_S01_Backend_report.md`
- All files modified by S01 (per the report)
- `orch/db/safe_migrate.py` (verify helpers were reused, not re-implemented)
- `orch/db/identity.py` (style consistency reference)

## Output Files

- `ai-dev/active/I-00040/reports/I-00040_S02_CodeReview_Backend_report.md`

## Review Checklist

### 1. Helper module correctness — CRITICAL

- [ ] `orch/db/alembic_guard.py` exists.
- [ ] Public API matches the design: `GuardStatus`, `check_db_at_head`, `assert_db_at_head`, `remediation_message`, `DBBehindHeadError`.
- [ ] Internally delegates to `orch.db.safe_migrate.list_pending_revisions` and `current_revision` — NO duplicated alembic-introspection code.
- [ ] `MultipleHeadsError` is either re-exported from `safe_migrate` or wrapped with a clearer message. Either is fine; flag if it's silently shadowed.
- [ ] `assert_db_at_head` raises with a message containing `current_rev`, `head_rev`, and the literal string `make db-migrate`.
- [ ] `remediation_message(status)` is single-line and matches the format from the daemon log spec (`current_rev=… head_rev=… run 'make db-migrate' to fix`).

### 2. Daemon wiring — CRITICAL

- [ ] `orch/daemon/main.py` calls the guard BEFORE entering the polling loop.
- [ ] Guard runs AFTER `verify_instance_identity` (operator gets the most-fundamental error first).
- [ ] On mismatch: `logger.critical(...)` + `DaemonEvent` row + `sys.exit(2)` (or a clearly distinct non-zero code).
- [ ] No `try/except Exception` around the guard that swallows the abort.
- [ ] `IW_CORE_SKIP_ALEMBIC_GUARD=true` override exists, logs WARNING, and refuses to apply when `IW_CORE_AGENT_CONTEXT=true`.

### 3. Dashboard wiring — CRITICAL

- [ ] `dashboard/app.py::create_app` does NOT abort on mismatch — the dashboard must keep serving read pages.
- [ ] On startup, `GuardStatus` is stored on `app.state.alembic_guard_status`.
- [ ] A middleware re-checks at most once every 10 seconds (throttle implemented; verify the lock + timestamp logic).
- [ ] Per-request `request.state.alembic_guard_status` is set so templates can read it.
- [ ] State-mutating routes (`/batches/*/approve`, `/batches/*/items/*/launch`, `/items/*/approve`) gain a FastAPI dependency that returns 503 with the remediation message when stale. Verify by grepping the actual route signatures.
- [ ] No emoji in log lines or response bodies.

### 4. Launch-time wiring — CRITICAL

- [ ] `_launch_item` checks the guard BEFORE creating the worktree directory and BEFORE `worktree_compose.up()`.
- [ ] On stale state: BatchItem status set to `setup_failed`, `notes` contains current_rev / head_rev / `make db-migrate`, `_emit_event("item_failed", …, {"phase": "alembic_guard", ...})` is called, function returns early.
- [ ] No partial worktree directory left on disk if the guard fails.
- [ ] `db.commit()` is called once before the early return so the status change is persisted.

### 5. Architecture / one-way dependency

- [ ] `orch/db/alembic_guard.py` does NOT import from `dashboard/` or any other reverse direction.
- [ ] Anything dashboard-specific (middleware, request helpers, template helpers) lives under `dashboard/`.

### 6. Convention conformance

- [ ] `from __future__ import annotations` at the top of new modules.
- [ ] Type hints on all public functions.
- [ ] Short single-line docstrings; NO multi-paragraph docstrings.
- [ ] No comments that just explain WHAT the code does (per `CLAUDE.md`).
- [ ] No backwards-compat shims for the new helper.
- [ ] No hardcoded ports / URLs / credentials.

### 7. Observability

- [ ] One DaemonEvent per detection at startup.
- [ ] Dedup window of ~60s for repeated mismatches (so the events table doesn't fill up if the dashboard's middleware re-checks every 10s).
- [ ] Logger name is `orch.db.alembic_guard` for the helper module.

### 8. Scope drift

- [ ] No changes outside the files in the design's **Code Changes** list, except for: any single-line import additions or `__all__` updates that are obviously necessary.
- [ ] No alembic migration file added.
- [ ] No refactoring of `safe_migrate.py` or `identity.py`.

## Output Report

Findings list with severity (CRITICAL / HIGH / MEDIUM / LOW / INFO), file:line, and a one-line verdict per item. End with an overall verdict (`PASS` / `NEEDS_FIX` / `BLOCKED`) and the appropriate `iw step-done` or `iw step-fail` call.

## Lifecycle Commands

When you START:
```bash
uv run iw step-start I-00040 --step S02
```

When you COMPLETE:
```bash
mkdir -p ai-dev/active/I-00040/reports
uv run iw step-done I-00040 --step S02 --report ai-dev/active/I-00040/reports/I-00040_S02_CodeReview_Backend_report.md
```
