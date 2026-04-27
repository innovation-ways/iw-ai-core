# I-00040 S05 — Alembic Guard Tests

## Objective

Write regression tests for the alembic-version guard (CR-00023 / I-00040 S05) covering unit, integration, dashboard, and daemon contexts.

## Deliverables

Five test files — 19 tests total — all passing.

### `tests/unit/test_alembic_guard.py` — 10 tests

Unit tests for `orch.db.alembic_guard` using only stdlib `unittest.mock`.

| Test | Scenario | Key assertions |
|------|----------|----------------|
| `test_guard_status_ok` | DB at head | `ok is True`, `current == head`, empty pending |
| `test_guard_status_not_ok` | DB behind | `ok is False`, `head_rev` set |
| `test_guard_status_multiple_heads` | Two heads | `multiple_heads == ["rev_x", "rev_y"]` |
| `test_assert_db_at_head_noop_when_ok` | at head | No exception raised |
| `test_assert_db_at_head_raises_when_not_ok` | behind head | `DBBehindHeadError` with head + current revs |
| `test_assert_db_at_head_raises_with_multiple_heads` | two heads | `DBMultipleHeadsError` |
| `test_assert_db_at_head_skips_when_agent_context` | `AGENT_CONTEXT=true` | No exception raised |
| `test_assert_db_at_head_skips_when_skip_guard` | `SKIP_ALEMBIC_GUARD=true` | No exception raised |
| `test_remediation_message` | behind | Message includes both revision identifiers and `make db-migrate` |
| `test_remediation_message_in_error` | raises | `str(exc)` includes `make db-migrate` |

### `tests/integration/test_alembic_guard_integration.py` — 4 tests

Integration tests using a PostgreSQL 15 testcontainer with real alembic migrations run to head. The tests use `monkeypatch.delenv` + mock `current_revision` / `list_pending_revisions` / `_get_head_revisions` to bypass the live-db-guard `safe_create_engine` path while keeping a real DB connection.

| Test | Scenario | Key assertions |
|------|----------|----------------|
| `test_guard_passes_at_head` | DB at head | No exception; `assert_db_at_head()` returns silently |
| `test_guard_fails_when_behind_one_revision` | behind one | `DBBehindHeadError` raised; head_rev and current_rev in message; `make db-migrate` in message |
| `test_check_db_at_head_ok_at_head` | at head | `ok is True`; `current_rev == head_rev`; empty pending |
| `test_check_db_at_head_not_ok_when_behind` | behind | `ok is False`; head_rev set; current_rev set; new_rev in pending |

### `tests/integration/test_daemon_alembic_guard.py` — 1 test

Integration test for daemon startup guard behavior. Verifies that `_alembic_guard_startup` calls `sys.exit(2)` and logs a `CRITICAL` message containing both revision identifiers and `make db-migrate`.

| Test | Scenario | Key assertions |
|------|----------|----------------|
| `test_daemon_exits_nonzero_when_db_behind_head_via_mock` | behind | `sys.exit` called with code 2; `CRITICAL` in log output; `head_rev` in log; `current_rev` in log; `make db-migrate` in log |

Uses `monkeypatch.setenv` to set `IW_CORE_DAEMON_CONTEXT=true` (bypasses live-db-guard in `assert_engine_url_allowed`). Uses `caplog.at_level(logging.DEBUG, logger="orch.daemon.main")` to capture logs.

### `tests/dashboard/test_alembic_guard_banner.py` — 3 tests

Dashboard integration tests using `FastAPI.TestClient` against a real app instance. The banner and write-action blocking are exercised with mocked `check_db_at_head`.

| Test | Scenario | Key assertions |
|------|----------|----------------|
| `test_no_banner_at_head` | at head | Response 200; body does not contain `Orch DB schema is behind head` |
| `test_banner_appears_when_db_behind_head` | behind | Body contains `Orch DB schema is behind head`; `role="alert"`; both revs; `make db-migrate` |
| `test_batch_approve_returns_503_when_db_behind_head` | behind + write action | Status 503 (or 404/422); `make db-migrate` in response body |

### `tests/integration/test_launch_item_alembic_guard.py` — 1 test

Integration test for the launch-time alembic guard in `_launch_item`. Uses a real DB + mock `check_db_at_head` to inject a stale `GuardStatus`.

| Test | Scenario | Key assertions |
|------|----------|----------------|
| `test_launch_item_sets_failed_status_when_db_behind_head` | behind at launch | `WorkItem.setup_failed == True`; `WorkItem.status_note` contains both revision identifiers and `make db-migrate`; no worktree directory created; `DaemonEvent` with `phase=alembic_guard` |

Requires explicit `db_session.commit()` after `manager._launch_item()` because `_emit_event` only calls `db.add()` without committing (the daemon normally commits on the next poll cycle).

## Key Design Decisions

### Why mocks in integration tests

The live-db-guard (`orch.db.live_db_guard`) blocks `safe_create_engine` when `IW_CORE_DB_HOST:IW_CORE_DB_PORT` matches the target URL. The pytest session-level `_arm_live_db_guard` fixture sets these to `127.0.0.1:1`, but when the testcontainer's random port happens to collide with port `1`, `is_live_db_url` returns `True`, causing `assert_engine_url_allowed` to raise.

The integration tests solve this by mocking `current_revision`, `list_pending_revisions`, and `_get_head_revisions` — all read-only functions that don't need to call `safe_create_engine`. This gives us a real DB connection (real migrations, real schema) while bypassing the live-db-guard for the revision-checking path.

### Why `patch("orch.daemon.main.check_db_at_head")` not `patch("orch.db.alembic_guard.check_db_at_head")`

`batch_manager.py` imports `check_db_at_head` as a local name: `from orch.db.alembic_guard import check_db_at_head`. The reference bound in `batch_manager`'s module namespace is what `_launch_item` calls internally, so patching the local binding is necessary.

### Why `contextlib.suppress(SystemExit)` around `_alembic_guard_startup`

`_alembic_guard_startup` calls `sys.exit(2)` on stale DB. Wrapping with `contextlib.suppress` lets us catch the exit without failing the test, then inspect `caplog` and `exit_codes` after the fact.

## Test Execution

```bash
make test-unit                    # unit tests (R1)
make test-integration             # integration tests (R2, R3, R5)
pytest tests/dashboard/ -v        # dashboard tests (R4)
```

## Traceability

| Requirement | Test(s) |
|-------------|---------|
| R1: `assert_db_at_head()` raises `DBBehindHeadError` with both revs + remediation | `test_assert_db_at_head_raises_when_not_ok`, `test_remediation_message_in_error` |
| R2: `check_db_at_head()` returns structured status | `test_check_db_at_head_ok_at_head`, `test_check_db_at_head_not_ok_when_behind` |
| R3: Daemon exits code 2 + CRITICAL log | `test_daemon_exits_nonzero_when_db_behind_head_via_mock` |
| R4: Dashboard banner + write-action block | `test_banner_appears_when_db_behind_head`, `test_batch_approve_returns_503_when_db_behind_head` |
| R5: Launch-time guard sets `setup_failed` + note | `test_launch_item_sets_failed_status_when_db_behind_head` |
| R6: Agent context and skip env vars bypass guard | `test_assert_db_at_head_skips_when_agent_context`, `test_assert_db_at_head_skips_when_skip_guard` |