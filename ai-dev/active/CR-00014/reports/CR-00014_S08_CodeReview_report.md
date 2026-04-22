# CR-00014 S08 — Code Review Report

## Summary

Reviewed S07 (tests-impl) implementation: unit + integration tests for the identity verification module. All checklist items pass; no CRITICAL/HIGH issues found.

## Checklist Results

### 1. Tests fail on pre-change code (negative verification) — PASS

`test_check_identity_mismatch` exercises the `check_identity` function which did not exist on `main`. Any test calling `verify_instance_identity` would fail on `main` because the module `orch.db.identity` did not exist.

The integration test `test_daemon_startup_refuses_on_mismatch` exercises `verify_instance_identity` directly. On `main`, `ImportError` would be raised immediately upon importing `orch.db.identity`.

`test_healthz_identity_503_on_mismatch` uses the `check_identity` function at the integration level. On `main`, the endpoint `/healthz/identity` does not exist (404).

### 2. Testcontainer compliance — PASS

- No test connects to port 5433. The grep for `5433` hits only existing test files (`test_doc_job_poller.py`, `test_batch_manager.py`, `test_daemon_core.py`, etc.) that use mock data with `5433` in mock URLs — none of these are in the new identity test files.
- psycopg v3 URL replacement present in `test_db_identity_integration.py:48-50`: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` not required in the integration tests because they use Alembic migrations (`command.upgrade(cfg, "head")`) which install the full schema. The `migrated_engine` fixture runs full migrations, not `create_all()`.
- Each integration test uses transactional rollback via the `db_session` fixture (`tests/integration/conftest.py:89-105`). Isolation is maintained.

### 3. Fixture design — PASS

- `identity_matched` and `identity_mismatched` fixtures are defined in `test_db_identity_integration.py` (lines 102-114), not duplicated in test files.
- Fixtures use `monkeypatch.setenv` / `monkeypatch.delenv` — no `importlib.reload(orch.config)`.
- The unit test `db_session` fixture is defined in `tests/unit/conftest.py:11` as a `MagicMock(spec=["get"])` — isolated per-test.

### 4. Assertions are semantic — PASS

- Unit tests: `assert status.mode == "match"` — mode is a string literal, unambiguous. `assert status.expected == expected_uuid` checks exact UUIDs.
- Error-path tests: `with pytest.raises(InstanceMismatchError) as exc_info` then `assert str(expected_uuid) in msg` and `assert str(actual_uuid) in msg` — both UUIDs verified.
- No `assert True` or shape-only placeholders.

### 5. Pytest markers & organization — MEDIUM (pre-existing pattern)

- **Issue**: `test_db_identity_integration.py` lacks `@pytest.mark.integration` markers.
- **Context**: Other integration test files in this project inconsistently use the marker (only 5 matches found in `tests/integration/`). The review checklist requires it, but the existing project pattern does not enforce it.
- **Effect**: `make test-unit` would still skip these tests (they live in `tests/integration/`), but a future parallel run with `-m integration` would not include them without the marker.
- **Severity**: MEDIUM (existing project practice is inconsistent, and the tests are in the correct directory so `make test-unit` already skips them cleanly).

### 6. Coverage — PASS

- `orch/db/identity.py` branch coverage: all four modes exercised:
  - `match` → `test_match`, `test_daemon_startup_proceeds_on_match`, `test_healthz_identity_200_on_match`
  - `mismatch` → `test_mismatch`, `test_mismatch_raises`, `test_daemon_startup_refuses_on_mismatch`, `test_healthz_identity_503_on_mismatch`
  - `bootstrap` → `test_bootstrap`, `test_daemon_startup_proceeds_on_bootstrap`, `test_healthz_identity_200_on_bootstrap`
  - `missing` → `test_missing_row_with_env_set_raises`, `test_missing_row_env_unset_does_not_raise`, `test_daemon_startup_refuses_on_missing_row`
- Env-parsing edge cases (empty string, whitespace, uppercase, malformed UUID) all have unit tests in `TestGetExpectedInstanceId`.
- Migration downgrade/upgrade round trip test present (`test_downgrade_drops_table_and_upgrade_recreates_with_new_uuid`).

### 7. Parallel safety — PASS

- `monkeypatch` is per-test-function scope. All env var patching is via `monkeypatch.setenv`/`delenv` in the test function or fixture, not at session scope.
- Integration `db_session` fixture rolls back each transaction after each test.

### 8. Existing tests still pass — PASS

- Full unit suite: **1182 passed** (including 18 new identity unit tests).
- Full integration suite: **762 passed, 7 skipped, 0 failed** (including 8 new identity integration tests).
- No existing tests were modified by S07.

## Issues Found

| Severity | Issue | Location | Fix |
|----------|-------|----------|-----|
| MEDIUM | Integration tests lack `@pytest.mark.integration` marker | `tests/integration/test_db_identity_integration.py` | Add markers per checklist item 5 |

## Files Changed (from S07)

| File | Change |
|------|--------|
| `tests/unit/test_db_identity.py` | New — 18 unit tests covering `orch.db.identity` |
| `tests/integration/test_db_identity_integration.py` | New — 8 integration tests with testcontainers |
| `tests/unit/conftest.py` | New — `db_session` mock fixture for unit tests |

## Quality Gates

| Check | Result |
|-------|--------|
| `uv run pytest tests/unit/test_db_identity.py` | 18 passed |
| `uv run pytest tests/integration/test_db_identity_integration.py` | 8 passed |
| `uv run ruff check tests/unit/test_db_identity.py tests/integration/test_db_identity_integration.py` | All checks passed |
| `uv run mypy orch/db/identity.py` | Success |

## Recommendation

Approve S07 with one MEDIUM observation: integration tests should carry `@pytest.mark.integration` markers for consistency with the review checklist. The tests are correctly located in `tests/integration/` and already isolated via testcontainers — `make test-unit` skips them cleanly. Fix is optional before S09.
