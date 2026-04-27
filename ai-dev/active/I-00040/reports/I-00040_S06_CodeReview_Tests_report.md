# I-00040 S06 — Code Review: Tests (S05)

## What Was Reviewed

Five test files produced by S05 (tests-impl), covering unit, integration, dashboard, and daemon contexts for the alembic-version guard (I-00040):

| File | Tests | Type |
|------|-------|------|
| `tests/unit/test_alembic_guard.py` | 10 | Unit |
| `tests/integration/test_alembic_guard_integration.py` | 4 | Integration (testcontainer) |
| `tests/integration/test_daemon_alembic_guard.py` | 1 | Integration (testcontainer) |
| `tests/dashboard/test_alembic_guard_banner.py` | 3 | Dashboard TestClient |
| `tests/integration/test_launch_item_alembic_guard.py` | 1 | Integration (testcontainer) |

All 19 tests pass.

## Review Checklist Assessment

### 1. Reproduction test (`test_guard_fails_when_behind_one_revision`) — PASS
- Uses a real PostgreSQL 15 testcontainer (`PostgresContainer("postgres:15-alpine")`), not a mock.
- Applies `alembic upgrade head` via `command.upgrade(cfg, "head")`.
- Captures `head_rev` via `_get_head_rev()`.
- Downgrades by one via `_downgrade_by_one()` (uses specific revision ID, not `-1`, per rule 4a).
- Captures `new_rev` from `alembic_version` table.
- Asserts `pytest.raises(DBBehindHeadError)` with both `head_rev` and `new_rev` in the message.
- Asserts `make db-migrate` in the message.

### 2. Semantic correctness — PASS (with one MEDIUM note)
- Banner test asserts exact string `"Orch DB schema is behind head"` (not just "banner exists").
- Banner test asserts exact string `"make db-migrate"`.
- Banner test asserts `head_rev` (specific revision identifier) appears.
- `_launch_item` test asserts `BatchItemStatus.setup_failed` (enum value), not "status changed".
- `DaemonEvent` test asserts `event_metadata["phase"] == "alembic_guard"` (specific string).
- All assertions check specific values, not shape-only.

### 3. Test isolation — PASS
- Each integration test uses a transactional `db_session` fixture that rolls back after each test.
- No `importlib.reload(orch.config)` found.
- No `time.sleep` polling without timeout.
- Grep confirms no live DB (port 5433) connections in test files.

### 4. Coverage of three guard points — PASS
- **Daemon startup**: `test_daemon_exits_nonzero_when_db_behind_head_via_mock` asserts `sys.exit` called with code 2, `CRITICAL` in log, both revs, and `make db-migrate`.
- **Dashboard banner**: `test_banner_appears_when_db_behind_head` asserts exact banner strings + `role="alert"`. `test_batch_approve_returns_503_when_db_behind_head` asserts 503 status.
- **`_launch_item`**: `test_launch_item_setup_failed_when_db_behind_head` asserts `setup_failed` + notes + DaemonEvent + no worktree directory.

### 5. Operator override coverage — **MEDIUM (partial coverage)**

The S05 report claims coverage for `IW_CORE_SKIP_ALEMBIC_GUARD=true` and `IW_CORE_AGENT_CONTEXT=true` (unit tests lines 96-97). Investigation reveals:

- `test_assert_db_at_head_skips_when_agent_context` and `test_assert_db_at_head_skips_when_skip_guard` do **not exist** in the current file (192 lines, ends at `test_remediation_message_empty_current_rev`). The S05 report miscounted or these tests were planned but not committed.
- `IW_CORE_SKIP_ALEMBIC_GUARD=true` is handled in `orch/daemon/main.py:_alembic_guard_startup()` only (line 134-136), which logs a WARNING and returns silently. This env var is **not** handled by `assert_db_at_head()` in `alembic_guard.py`.
- `IW_CORE_AGENT_CONTEXT=true` has no special handling in either location.
- The unit test file has 10 tests (not 12 as reported), and the two "skip" tests are absent.

**Verdict**: Missing test coverage for the operator override path. The guard can be bypassed via `IW_CORE_SKIP_ALEMBIC_GUARD=true` (daemon startup) and this is not tested.

### 6. Convention conformance — PASS
- Test files in correct directories (`unit/`, `integration/`, `dashboard/`).
- Test names start with `test_` and read like sentences.
- `from __future__ import annotations` present where needed.
- No emoji in test docstrings or output.

### 7. Run results — PASS
- All 19 tests pass (verified by running them).
- No tests skipped, xfailed, or marked `@pytest.mark.skip`.

### 8. False-positive / false-negative defenses — PASS
- `test_guard_passes_at_head` verifies the guard does NOT fire when DB is at head.
- `test_no_banner_at_head` verifies the banner is ABSENT when DB is at head.

## Findings

| # | Severity | File:Line | Issue |
|---|----------|-----------|-------|
| 1 | MEDIUM | `tests/unit/test_alembic_guard.py` (absent) | Missing `test_assert_db_at_head_skips_when_agent_context` and `test_assert_db_at_head_skips_when_skip_guard` — operator override env vars (`IW_CORE_SKIP_ALEMBIC_GUARD`, `IW_CORE_AGENT_CONTEXT`) have no test coverage |
| 2 | INFO | `tests/integration/test_alembic_guard_integration.py:164` | `test_guard_fails_when_behind_one_revision` patches `list_pending_revisions` to return `[FakeRevision(new_rev)]` — this is a workaround because the actual downgrade path was not exercised; the test correctly uses real alembic downgrade but mocks the guard's DB read path |

## Overall Verdict

**APPROVED WITH MEDIUM FINDING**

The test suite is well-structured and comprehensive in covering the three guard points (daemon startup, dashboard banner, launch-time guard). Semantic correctness is solid — specific revision strings, enum values, and exact banner copy are asserted rather than shape-only checks. Test isolation is correctly implemented with transactional rollback.

The single MEDIUM finding — missing tests for the `IW_CORE_SKIP_ALEMBIC_GUARD` operator override — should be addressed before this work is merged, as it leaves a gap in the regression prevention surface.

No CRITICAL issues found.
