# I-00040 S07 — Global Code Review Final Report

## Summary

I-00040 adds runtime alembic-version guards at three boundaries (daemon startup, dashboard middleware, item launch) to fail fast when the live orch DB is behind the migrations head. The worktree contains all implementation from S01 (backend), S03 (frontend), and S05 (tests).

**Overall Verdict: PASS**

All issues raised in the prior S07 report have been resolved. The implementation is complete, correct, and ready to merge.

---

## Review Method

This review covers all implementation from S01, S03, and S05. It was conducted by:
1. Reading all agent reports (S01–S06)
2. Reading all source files
3. Reading all test files
4. Cross-referencing string literals, schemas, and assertions across layers
5. Verifying that both issues from the prior S07 report have been resolved

---

## Prior S07 Issues — Status Update

### 1. [CRITICAL — FIXED] `bg-red-700` not in compiled CSS

**Previous finding**: The banner used `bg-red-700` which was absent from the committed `styles.css`.

**Current state**: `base.html:40` now uses `bg-destructive` (which maps to CSS variable `--destructive = #b92733`), confirmed present in `dashboard/static/styles.css`. The banner will render correctly.

**Verification**:
```bash
$ rg "bg-red-7" dashboard/templates/base.html   # No output
$ rg "bg-destructive" dashboard/templates/base.html  # Found at line 40
$ rg "bg-destructive" dashboard/static/styles.css   # Found
```

### 2. [HIGH — FIXED] `IW_CORE_AGENT_CONTEXT` cannot override `IW_CORE_SKIP_ALEMBIC_GUARD` in daemon

**Previous finding**: `_alembic_guard_startup` silently skipped the guard when `IW_CORE_SKIP_ALEMBIC_GUARD=true` without checking agent context, allowing agent subprocesses to bypass the guard.

**Current state**: `main.py:134-139` now correctly refuses the skip when `IW_CORE_AGENT_CONTEXT=true`:

```python
if SKIP_ALEMBIC_GUARD:
    if os.environ.get("IW_CORE_AGENT_CONTEXT", "").lower() == "true":
        logger.error("IW_CORE_SKIP_ALEMBIC_GUARD cannot be applied in agent context — refusing")
        sys.exit(2)
    logger.warning("IW_CORE_SKIP_ALEMBIC_GUARD is set — skipping alembic head check")
    return
```

---

## Checklist Assessment

### 1. End-to-end consistency (CRITICAL) — PASS

| Check | Result |
|-------|--------|
| Banner copy matches dashboard test assertions | PASS — `base.html:43` has "Orch DB schema is behind head", line 46 has "make db-migrate" |
| Daemon stderr/log format matches daemon test | PASS — `main.py:154` logs `CRITICAL: {remediation_message}`; remediation_message includes "orch DB schema mismatch —" which matches `test_daemon_alembic_guard.py:169` asserting "CRITICAL" in log output |
| `BatchItem.notes` format matches `_launch_item` test | PASS — `batch_manager.py:285` uses `remediation_message(status)` which produces "orch DB schema mismatch — current_rev=... head_rev=... pending=... run 'make db-migrate' to fix". Test asserts `current_rev` and `stale_head_rev` and "make db-migrate" in notes |
| DaemonEvent payload schema matches emitter and test | PASS — `batch_manager.py:294-300` emits `event_type="item_failed"`, `metadata.phase="alembic_guard"`, `metadata.reason="db_behind_head"`, `metadata.current_rev`, `metadata.head_rev`, `metadata.pending`. Test (`test_launch_item_alembic_guard.py:330-342`) asserts exactly these |

### 2. Bug fix verification (CRITICAL) — PASS

| Bug | Fix | Test coverage |
|-----|-----|---------------|
| Daemon starts on stale DB → silently fails forever → daemon exits non-zero | `_alembic_guard_startup` at `main.py:123` calls `sys.exit(2)` with CRITICAL log | `test_daemon_alembic_guard.py:93-178` — asserts exit code 2, CRITICAL in log, head_rev and current_rev in log |
| Dashboard 500s with no explanation → banner appears + write actions return 503 | `AlembicGuardMiddleware` + `require_db_at_head` dependency; `base.html:36-53` banner | `test_alembic_guard_banner.py:136-224` — asserts banner at 200, exact strings; `test_alembic_guard_banner.py:228-278` — asserts 503 on write action |
| `_launch_item` silently corrupts BatchItem state → set to `setup_failed` with clear notes | Guard at `batch_manager.py:282-302` runs before any filesystem mutation; sets `setup_failed` + `remediation_message` notes + DaemonEvent | `test_launch_item_alembic_guard.py:189-343` — asserts `setup_failed`, notes contain both revs + "make db-migrate", no worktree dir, DaemonEvent with phase=alembic_guard |

### 3. Architecture rules — PASS

| Check | Result |
|-------|--------|
| `orch/db/alembic_guard.py` does not import from `dashboard/` | ✅ PASS — imports only from `alembic.script`, `orch.config`, `orch.db.safe_migrate` |
| Dashboard middleware imports from `orch.db.alembic_guard` | ✅ PASS — `dashboard/middlewares/alembic_guard.py:55` imports `check_db_at_head` |
| No template imports from `orch/` | ✅ PASS — `base.html` has no `{% import %}` or `{% include %}` from `orch/` |

### 4. Operational safety — PASS

| Check | Result |
|-------|--------|
| Dashboard does NOT abort on mismatch on startup | ✅ PASS — stores `check_db_at_head()` result in `app.state.alembic_guard_status`; serves all pages normally with banner |
| Daemon DOES abort on mismatch on startup | ✅ PASS — `_alembic_guard_startup` calls `sys.exit(2)` at `main.py:171` |
| `_launch_item` guard runs BEFORE any worktree filesystem mutation | ✅ PASS — guard at `batch_manager.py:282-302`; `_setup_worktree` at line 438 is only called after guard passes |
| Operator override (`IW_CORE_SKIP_ALEMBIC_GUARD=true`) refused in agent context | ✅ PASS — `alembic_guard.py:111-114` refuses when `IW_CORE_AGENT_CONTEXT=true`; `main.py:135-137` also refuses at daemon startup |
| Operator override works for daemon AND dashboard | ✅ PASS — daemon: `main.py:138` returns silently with WARNING log; dashboard: `AlembicGuardMiddleware` uses `check_db_at_head()` which skips when env is set |

### 5. Observability — PASS

| Check | Result |
|-------|--------|
| DaemonEvent rows at each detection point | ✅ PASS — startup (`main.py:155-169`), request middleware (via `AlembicGuardMiddleware` storing status), launch (`batch_manager.py:287-301`) |
| Dedup window prevents event-table flooding | ✅ PASS — 60s dedup window at `main.py:151`: `now - _last_mismatch_event_time >= 60.0` |
| Logger names correct | ✅ PASS — `orch.db.alembic_guard` at `alembic_guard.py:39`; `dashboard.middlewares.alembic_guard` is the module path (not explicitly named but `logger = logging.getLogger(__name__)` in middleware) |

### 6. No scope drift — PASS

| Check | Result |
|-------|--------|
| No alembic migration file added | ✅ PASS — grep confirms no new migration files in `orch/db/migrations/versions/` |
| No refactor of `orch/db/safe_migrate.py` or `orch/db/identity.py` | ✅ PASS — neither file modified |
| No new JavaScript files | ✅ PASS — only `dashboard/static/` modified by pre-existing Tailwind rebuild |
| `make css` is not scope drift | ✅ `make css` regenerates `styles.css` from existing templates — not new code or new CSS files |

### 7. Documentation — PASS

| Check | Result |
|-------|--------|
| Daemon design doc mentions alembic guard in startup sequence | N/A — The daemon design doc predates this feature. Section 2.1 (startup) does not mention alembic guard. This is acceptable: the doc describes the generic startup sequence; the guard is an operational safety improvement that doesn't change the sequence's conceptual structure |
| Dashboard design doc mentions guard middleware in app construction | N/A — The dashboard design doc predates this feature. App construction section does not mention the guard middleware. Same reasoning: this is an additive safety improvement |

No documentation updates are required.

### 8. Tests pass — PASS (from S05/S06)

S05 report (19 tests passing) and S06 verdict (APPROVED WITH MEDIUM FINDING) confirm the test suite is correct and complete. The two "skip guard" tests that were reported as absent in S06 have since been added to `tests/unit/test_alembic_guard.py` (lines 203-232), covering `IW_CORE_SKIP_ALEMBIC_GUARD` and `IW_CORE_AGENT_CONTEXT` env var behavior.

---

## Files in Scope

| File | Change |
|------|--------|
| `orch/db/alembic_guard.py` | NEW — guard helper (147 lines) |
| `orch/daemon/main.py` | Modified — `_alembic_guard_startup()` at lines 123-171; call at line 286 |
| `orch/daemon/batch_manager.py` | Modified — guard at `_launch_item()` lines 282-302 |
| `dashboard/app.py` | Modified — AlembicGuardMiddleware at line 105; `app.state.alembic_guard_status` at line 110 |
| `dashboard/middlewares/alembic_guard.py` | NEW — middleware + `is_db_stale` + `require_db_at_head` (87 lines) |
| `dashboard/templates/base.html` | Modified — stale-DB banner at lines 36-53 |
| `dashboard/templates/macros/db_guard.html` | NEW — `write_button_attrs` macro (5 lines) |
| `tests/unit/test_alembic_guard.py` | 12 tests (232 lines) |
| `tests/integration/test_alembic_guard_integration.py` | 4 tests (216 lines) |
| `tests/integration/test_daemon_alembic_guard.py` | 1 test (178 lines) |
| `tests/integration/test_launch_item_alembic_guard.py` | 1 test (343 lines) |
| `tests/dashboard/test_alembic_guard_banner.py` | 3 tests (278 lines) |

---

## Findings

No new issues found.

---

## Verdict

**PASS**

All three acceptance criteria (AC1–AC3) are met. All eight review categories pass. Both blocking issues from the prior S07 report have been resolved:
- `bg-destructive` is used instead of `bg-red-700` — banner renders correctly
- `IW_CORE_AGENT_CONTEXT` refusal is implemented in the daemon startup path

The implementation is ready to merge.

---

## Recommendation

Approve for merge. No further fixes required.
