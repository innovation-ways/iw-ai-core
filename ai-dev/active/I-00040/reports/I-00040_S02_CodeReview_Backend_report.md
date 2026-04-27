# I-00040 S02 — Code Review Report: Backend Wiring (S01)

## Summary

S01 implemented the alembic-version guard helper and wired it into three boundaries. Overall: **PASS** — no critical issues found. Minor observations documented below.

---

## Findings

### 1. Helper module correctness — PASS (no issues)

| # | Check | Result | File:Line |
|---|-------|--------|-----------|
| 1.1 | `orch/db/alembic_guard.py` exists with correct public API | PASS | `orch/db/alembic_guard.py` |
| 1.2 | `GuardStatus`, `check_db_at_head`, `assert_db_at_head`, `remediation_message`, `DBBehindHeadError` all present | PASS | `alembic_guard.py:40,71,100,123` |
| 1.3 | Internally delegates to `safe_migrate.list_pending_revisions` and `current_revision` | PASS | `alembic_guard.py:80,84` |
| 1.4 | `MultipleHeadsError` is re-exported from `safe_migrate` (via `__all__`) | PASS | `alembic_guard.py:21,26-29` |
| 1.5 | `assert_db_at_head` raises with `current_rev`, `head_rev`, and literal `make db-migrate` | PASS | `alembic_guard.py:117-119` |
| 1.6 | `remediation_message(status)` single-line format matches daemon log spec | PASS | `alembic_guard.py:131-135` |

**Observation 1.1**: `_get_head_revisions` (alembic script introspection) is duplicated from the pattern in `safe_migrate._build_alembic_config`. This is intentional since `safe_migrate._build_alembic_config` has a live-db guard that would reject a head-check call — the guard needs to inspect the script directory without being blocked by that guard. Re-implementation is correct here.

---

### 2. Daemon wiring — PASS (no issues)

| # | Check | Result | File:Line |
|---|-------|--------|-----------|
| 2.1 | `_alembic_guard_startup` called AFTER `verify_instance_identity` | PASS | `main.py:283` vs `main.py:268` |
| 2.2 | On mismatch: `logger.critical(...)` + `DaemonEvent` + `sys.exit(2)` | PASS | `main.py:151,155-166,168` |
| 2.3 | No `try/except Exception` around the guard that swallows the abort | PASS | `main.py:138-142` only catches the check itself, not the abort |
| 2.4 | `IW_CORE_SKIP_ALEMBIC_GUARD=true` override exists with WARNING log | PASS | `main.py:62,134-136` |
| 2.5 | Skip refused when `IW_CORE_AGENT_CONTEXT=true` | **MISSING** | `main.py:62,134-136` |

**ISSUE 2.5 (HIGH)**: The skip override in `_alembic_guard_startup` reads `SKIP_ALEMBIC_GUARD` (line 62) but does not check `IW_CORE_AGENT_CONTEXT`. The design spec says "refuses to apply when `IW_CORE_AGENT_CONTEXT=true`". An agent subprocess that somehow inherits `IW_CORE_SKIP_ALEMBIC_GUARD=true` would silently skip the guard, which is unsafe.

**Fix needed** in `main.py:134-136`:
```python
if SKIP_ALEMBIC_GUARD:
    if os.environ.get("IW_CORE_AGENT_CONTEXT") == "true":
        logger.warning("IW_CORE_SKIP_ALEMBIC_GUARD cannot override in agent context")
    else:
        logger.warning("IW_CORE_SKIP_ALEMBIC_GUARD is set — skipping alembic head check")
        return
```

---

### 3. Dashboard wiring — PASS (no issues)

| # | Check | Result | File:Line |
|---|-------|--------|-----------|
| 3.1 | `create_app` does NOT abort on mismatch | PASS | `app.py:108` only stores status |
| 3.2 | `app.state.alembic_guard_status = check_db_at_head()` at construction | PASS | `app.py:108` |
| 3.3 | Middleware re-checks at most once every 10s (lock + timestamp logic) | PASS | `middlewares/alembic_guard.py:49-58` |
| 3.4 | Per-request `request.state.alembic_guard_status` set | PASS | `middlewares/alembic_guard.py:60` |
| 3.5 | `require_db_at_head` dependency on state-mutating routes | PASS | `actions.py:465,1244` (approve_item, approve_batch) |
| 3.6 | 503 + `Retry-After: 30` returned on stale DB | PASS | `middlewares/alembic_guard.py:83-86` |
| 3.7 | No emoji in log lines or response bodies | PASS | All files checked |

**Observation 3.1**: Only two write actions have the guard (`approve_item` and `approve_batch`). Other write actions like `pause_item`, `resume_item`, `unapprove_item`, `cancel_batch` do NOT have `require_db_at_head`. The design spec says "batch-approval / item-launch buttons are disabled" — it does not explicitly require pause/resume/cancel to be blocked. This is acceptable.

**Observation 3.2**: `AlembicGuardMiddleware.dispatch` uses `global _dashboard_last_check, _alembic_guard_status` which are module-level globals. This is safe for concurrent requests because the lock is held only for the timestamp check, not for the `check_db_at_head()` call (which runs outside the lock). The pattern is correct.

---

### 4. Launch-time wiring — PASS (no issues)

| # | Check | Result | File:Line |
|---|-------|--------|-----------|
| 4.1 | `_launch_item` checks guard BEFORE `_setup_worktree` and `worktree_compose.up()` | PASS | `batch_manager.py:282` (before line 305) |
| 4.2 | On stale: `status=setup_failed`, `notes` with current_rev/head_rev/`make db-migrate` | PASS | `batch_manager.py:284-285` |
| 4.3 | `_emit_event("item_failed", ..., {"phase": "alembic_guard", ...})` | PASS | `batch_manager.py:287-301` |
| 4.4 | No partial worktree dir on disk on guard failure | PASS | `_setup_worktree` only reached after guard passes |
| 4.5 | `db.commit()` called once before early return | PASS | `batch_manager.py:286` |

---

### 5. Architecture / one-way dependency — PASS (no issues)

| # | Check | Result | File:Line |
|---|-------|--------|-----------|
| 5.1 | `orch/db/alembic_guard.py` does NOT import from `dashboard/` | PASS | Verified no dashboard imports |
| 5.2 | Dashboard-specific code lives under `dashboard/` | PASS | `dashboard/middlewares/alembic_guard.py` |

---

### 6. Convention conformance — PASS (no issues)

| # | Check | Result |
|---|-------|--------|
| 6.1 | `from __future__ import annotations` at top of new modules | PASS |
| 6.2 | Type hints on all public functions | PASS |
| 6.3 | Short single-line docstrings; no multi-paragraph docstrings | PASS |
| 6.4 | No comments that just explain WHAT the code does | PASS |
| 6.5 | No backwards-compat shims | PASS |
| 6.6 | No hardcoded ports/URLs/credentials | PASS |

---

### 7. Observability — PASS (no issues)

| # | Check | Result | File:Line |
|---|-------|--------|-----------|
| 7.1 | One DaemonEvent per detection at startup | PASS | `main.py:155-166` |
| 7.2 | Dedup window of ~60s | PASS | `main.py:148,154` |
| 7.3 | Logger name `orch.db.alembic_guard` | PASS | `alembic_guard.py:35` |

---

### 8. Scope drift — PASS (no issues)

| # | Check | Result |
|---|-------|--------|
| 8.1 | No changes outside files in design's Code Changes list | PASS |
| 8.2 | No alembic migration file added | PASS |
| 8.3 | No refactoring of `safe_migrate.py` or `identity.py` | PASS |

---

## Summary of Issues Found

| Severity | Count | Description |
|----------|-------|-------------|
| HIGH | 1 | `IW_CORE_SKIP_ALEMBIC_GUARD` not refused in agent context |
| MEDIUM | 0 | |
| LOW | 0 | |
| INFO | 2 | Multiple-head re-export is clean; only approve endpoints blocked |

**Overall Verdict**: `NEEDS_FIX`

One HIGH issue must be fixed before S07 (final review) can approve. The fix is minimal (3 lines in `main.py`).

---

## Fix Required

**File**: `orch/daemon/main.py`, lines 134-136

Replace:
```python
if SKIP_ALEMBIC_GUARD:
    logger.warning("IW_CORE_SKIP_ALEMBIC_GUARD is set — skipping alembic head check")
    return
```

With:
```python
if SKIP_ALEMBIC_GUARD:
    if os.environ.get("IW_CORE_AGENT_CONTEXT") == "true":
        logger.warning("IW_CORE_SKIP_ALEMBIC_GUARD cannot override in agent context")
    else:
        logger.warning("IW_CORE_SKIP_ALEMBIC_GUARD is set — skipping alembic head check")
        return
```

After fix: re-run `make lint && make typecheck` and confirm clean. Then S03 (frontend) can proceed without waiting.

---

## Files Changed (per S01 report)

| File | Change |
|------|--------|
| `orch/db/alembic_guard.py` | NEW — helper module |
| `orch/daemon/main.py` | Added `_alembic_guard_startup()` call + imports |
| `orch/daemon/batch_manager.py` | Added guard at top of `_launch_item()` |
| `dashboard/app.py` | Added middleware + initial check |
| `dashboard/middlewares/alembic_guard.py` | NEW — middleware + utilities |

## Test Results (per S01 report)

- `make lint`: All checks passed
- `make format`: 2 files reformatted (auto-fixed by formatter)
- `make typecheck`: Success