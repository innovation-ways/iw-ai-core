# CR-00014_S07_Tests_prompt

**Work Item**: CR-00014 — Orchestration DB instance-identity fingerprint
**Step**: S07
**Agent**: tests-impl

---

## Input Files

- `ai-dev/active/CR-00014/CR-00014_CR_Design.md` — Design (AC1–AC6)
- Reports from S01, S03, S05 — know what was built
- `tests/conftest.py` — existing fixtures (postgres testcontainer, FTS triggers, session scope)
- `tests/CLAUDE.md` — testcontainer rules (MUST follow)
- Implementation files from S01/S03/S05

## Output Files

- `ai-dev/active/CR-00014/reports/CR-00014_S07_Tests_report.md`
- `tests/unit/test_db_identity.py` — unit tests for the pure-Python logic in `orch.db.identity`
- `tests/integration/test_db_identity_integration.py` — end-to-end with a testcontainer DB
- Possibly update `tests/conftest.py` — add a `identity_matched` / `identity_mismatched` fixture

## Context

Formalize the tests. Unit coverage for the identity module. Integration coverage for the daemon startup gate and the dashboard endpoint across match / mismatch / bootstrap / missing modes.

Read `tests/CLAUDE.md` before writing anything — several hard rules apply (no live DB, psycopg v3 URL replacement, FTS triggers after `create_all()`, no `importlib.reload` on config).

## Requirements

### 1. Unit tests — `tests/unit/test_db_identity.py`

Cover `orch.db.identity` in isolation. Use mocks or an in-memory SQLite (NOT a postgres testcontainer — that's integration's job) where the DB interaction can be stubbed. If the module relies on postgres-specific types (UUID), use a light SQLAlchemy mock.

- `test_get_expected_instance_id_unset` — env var missing → returns None.
- `test_get_expected_instance_id_empty_string` — env var set to `""` → returns None.
- `test_get_expected_instance_id_whitespace` — env var set to `"   "` → returns None.
- `test_get_expected_instance_id_valid` — env var set to a canonical UUID string → returns `uuid.UUID`.
- `test_get_expected_instance_id_uppercase` — UUID with uppercase hex → returns same UUID (case-insensitive).
- `test_get_expected_instance_id_malformed` — garbage string → raises `ValueError`.
- `test_check_identity_match` — mocked session returning a UUID, env set to the same value → `mode == "match"`.
- `test_check_identity_mismatch` — different UUIDs → `mode == "mismatch"`.
- `test_check_identity_bootstrap` — env unset, DB row present → `mode == "bootstrap"`.
- `test_check_identity_missing_env_set` — env set, DB row missing → `mode == "missing"`.
- `test_check_identity_missing_env_unset` — env unset, DB row missing → whichever mode the module defines for this (`"missing"` or `"bootstrap"`) — assert the module's chosen behavior, not your preference.
- `test_verify_raises_on_mismatch` — asserts `InstanceMismatchError` is raised with both UUIDs in the message.
- `test_verify_raises_on_missing_with_env_set` — asserts `InstanceRowMissingError` is raised.
- `test_verify_does_not_raise_on_match` — returns `IdentityStatus`.
- `test_verify_does_not_raise_on_bootstrap` — returns `IdentityStatus`.

Use `monkeypatch.setenv` / `monkeypatch.delenv` for env control — **do NOT `importlib.reload(orch.config)`** (project rule).

### 2. Integration tests — `tests/integration/test_db_identity_integration.py`

Use the `postgres` testcontainer fixture from `tests/conftest.py` (if one exists — check conftest first; if not, create one that mirrors how F-00058 integration tests did it).

Fixtures to add in `conftest.py`:

- `identity_matched` — set `IW_CORE_EXPECTED_INSTANCE_ID` env var to the testcontainer DB's seeded UUID. Yields the session.
- `identity_mismatched` — set env var to a different random UUID. Yields the session.
- Both must use `monkeypatch.setenv` and NOT `importlib.reload`.

Tests:

- `test_daemon_startup_refuses_on_mismatch` — spin a testcontainer, apply migrations, set env to a different UUID, call the daemon's startup health check (or whatever helper runs `verify_instance_identity` in the daemon's init path). Assert `InstanceMismatchError` is raised.
- `test_daemon_startup_proceeds_on_match` — same but matching env. Startup returns normally.
- `test_daemon_startup_proceeds_on_bootstrap` — env unset. Startup returns; check that the bootstrap notice was logged (use `caplog`).
- `test_daemon_startup_refuses_on_missing_row` — delete the seed row, env set. Assert `InstanceRowMissingError`.
- `test_dashboard_healthz_identity_200_on_match` — FastAPI TestClient, identity_matched fixture → GET `/healthz/identity` → 200, JSON `{match: true, mode: "match", expected=<uuid>, actual=<uuid>}`.
- `test_dashboard_healthz_identity_503_on_mismatch` — identity_mismatched fixture → 503, `mode: "mismatch"`, both UUIDs present.
- `test_dashboard_healthz_identity_bootstrap` — env unset → 200, `mode: "bootstrap"`, `expected=null`, `match=null`.
- `test_dashboard_startup_refuses_on_mismatch` — attempt to construct `create_app()` with mismatched env against the testcontainer. Assert lifespan raises.
- `test_migration_downgrade_upgrade_roundtrip` — run `alembic downgrade -1` (or `-2` if another migration was added mid-CR), verify `iw_core_instance` is gone. Run `alembic upgrade head`, verify table and row exist with a UUID different from the previous one (proves a new seed ran).

### 3. Testcontainer hygiene

- Each testcontainer DB is ephemeral — no shared state between tests.
- Replace driver URL: `url.replace("postgresql+psycopg2://", "postgresql+psycopg://")`.
- Apply `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `Base.metadata.create_all()`. (Even though this CR doesn't touch FTS, the existing rule applies to any fixture that uses `create_all()`.)
- Do NOT connect to port 5433 live DB.

### 4. Existing test updates

If any existing test fixture constructs the daemon or dashboard (e.g., tests that hit live-ish endpoints), ensure it sets `IW_CORE_EXPECTED_INSTANCE_ID` to match the testcontainer's seeded UUID, or runs in bootstrap mode. Search for usages of `create_app()` and daemon startup helpers in `tests/`; update as needed. Do not change the public API of those tests — just their environment.

### 5. Coverage expectations

Aim for 100% branch coverage of `orch/db/identity.py` at the unit level. Integration coverage proves the wiring works. Don't pursue coverage numbers on code that already existed.

## Project Conventions

- pytest markers: `@pytest.mark.integration` on all integration tests; unit tests go in `tests/unit/`.
- Fixtures in `tests/conftest.py` — don't scatter.
- Parametrize where possible to cut duplication.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — all pass, including new unit tests.
2. `make test-integration` — all pass, including new integration tests.
3. `make lint` — pass.
4. Run `make test-integration` twice in a row — confirms testcontainer cleanup works.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "tests-impl",
  "work_item": "CR-00014",
  "completion_status": "complete",
  "files_changed": ["..."],
  "tests_passed": true,
  "test_summary": "N unit + M integration passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00014 --step S07
# write tests ...
uv run iw step-done CR-00014 --step S07 --report ai-dev/active/CR-00014/reports/CR-00014_S07_Tests_report.md
```
