# CR-00014 S09 — Code Review Final Report

## Summary

Cross-layer review of CR-00014 (Orchestration DB instance-identity fingerprint). All acceptance criteria are satisfied. The implementation is correct, consistent across layers, and introduces no regressions.

## Files Changed

| File | Change |
|------|--------|
| `orch/db/models.py` | Added `IwCoreInstance` ORM model |
| `orch/db/identity.py` | New — `verify_instance_identity`, `check_identity`, env/DB helpers |
| `orch/db/migrations/versions/2bd86f8c105c_add_iw_core_instance.py` | New migration |
| `orch/daemon/main.py` | Wired identity check into startup sequence |
| `orch/cli/db_commands.py` | New `iw db-identity {show,check}` commands |
| `orch/cli/main.py` | Registered `db-identity` command group |
| `dashboard/app.py` | Added identity gate in `_lifespan()` |
| `dashboard/routers/healthz.py` | New `GET /healthz/identity` endpoint |
| `dashboard/CLAUDE.md` | Documented `/healthz/identity` convention |
| `ai-core.sh` | `cmd_status` shows DB identity line; `cmd_start` fail-fast |
| `.env.example` | Added `IW_CORE_EXPECTED_INSTANCE_ID` with documentation |
| `tests/unit/test_db_identity.py` | 18 unit tests |
| `tests/integration/test_db_identity_integration.py` | 8 integration tests |
| `tests/unit/conftest.py` | Added `db_session` mock fixture |

## AC Verification

### AC1 — Matching identity → all services start healthy

- Daemon `_startup()` (main.py:192-206): calls `verify_instance_identity`, logs `INFO Database identity verified (<short>)`, enters main loop.
- Dashboard `_lifespan()` (app.py:58-72): calls `verify_instance_identity`, logs `INFO Dashboard: DB identity verified (<short>)`, yields without error.
- `/healthz/identity` (healthz.py:18-34): returns 200 with `{expected, actual, mode, match}` where `match=true`.
- `ai-core.sh cmd_status` (lines 577-595): captures `iw db-identity check` output, prints green `DB identity: PASS (<uuid>)` with exit 0.

### AC2 — Mismatched identity → all services refuse

- Daemon: `sys.exit(2)` at line 206 — does not enter main loop.
- Dashboard: exception re-raised from `_lifespan()`, uvicorn sees startup failure, no traffic accepted.
- `/healthz/identity`: returns 503 (`response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE`) for both `mismatch` and `missing` modes.
- `ai-core.sh cmd_status`: exit 2 triggers `print_err "DB identity: FAIL (expected!=actual)"`.

### AC3 — Bootstrap mode (env var unset)

- Daemon: one-shot `INFO DB identity bootstrap notice: ...` via `_identity_bootstrap_logged` flag at lines 199-201.
- Dashboard: `INFO Dashboard: <message>` at lines 64-67 (no flag needed — lifespan is one-shot).
- `/healthz/identity`: returns 200 with `expected=null, actual=<uuid>, mode=bootstrap, match=null`.
- `ai-core.sh`: exit 0 with `BOOTSTRAP` output → yellow `DB identity: UNVERIFIED (bootstrap mode...)`.

### AC4 — Missing row with env var set → hard fail

- Daemon: `InstanceRowMissingError` raised → `sys.exit(2)`.
- Dashboard: exception re-raised, startup aborts.
- `/healthz/identity`: returns 503 for `missing` mode.
- `ai-core.sh`: exit 3 → `print_err "DB identity: row missing from iw_core_instance"`.

### AC5 — Migration reversible

- `downgrade()` drops `iw_core_instance` cleanly.
- `upgrade()` re-creates table + seeds new UUID via `WHERE NOT EXISTS` pattern.
- Integration test `test_downgrade_and_upgrade_round_trip` passes.

### AC6 — No regressions

- `make lint`: 1 pre-existing error (ARG001 in `item_commands.py:593`) — unrelated to CR-00014.
- `make test-unit`: 1182 passed.
- `make test-integration`: 11 identity tests passed + pre-existing tests unaffected.
- All new files pass `uv run ruff format --check`.
- All new files pass `uv run mypy` with no issues.

## Cross-Layer Consistency

| Concern | Status |
|---------|--------|
| Error block text identical across daemon/dashboard/CLI | PASS — all use `status.message` from `IdentityStatus.message` |
| `IdentityStatus.mode` values: `match`, `mismatch`, `bootstrap`, `missing` | PASS — no drift |
| CLI exit codes: 0/2/3/1 | PASS — `db_commands.py:75-96` match spec exactly |
| `ai-core.sh` exit-code handling | PASS — `cmd_status` branches on 0/2/3/other |
| `/healthz/identity` JSON shape | PASS — `{expected, actual, mode, match}` |
| Dashboard auth bypass | PASS — no auth middleware in `create_app()`, endpoint unauthenticated |
| Bootstrap: one INFO line per process (not per request/poll) | PASS — daemon uses `_identity_bootstrap_logged` flag |

## Regression Surface

- Daemon startup connectivity check (`SELECT 1`) still present at line 188-190 — identity check added after it.
- All existing dashboard routes still mounted — only addition is `healthz.router`.
- `ai-core.sh cmd_status` output unchanged except addition of DB identity section.
- No new Python dependencies introduced.

## Rollback Verification

- `alembic downgrade -1` drops `iw_core_instance` — no cascading breakage (table has no FKs).
- Reverting squash-merge returns all files to pre-CR state.
- Removing `IW_CORE_EXPECTED_INSTANCE_ID` from `.env` reverts to bootstrap mode.

## Quality Gates

| Gate | Result |
|------|--------|
| `uv run ruff check orch/ dashboard/` | 1 pre-existing ARG001 error |
| `uv run ruff format --check` (new files) | 5 files already formatted |
| `uv run mypy` (new files) | Success |
| `make test-unit` | 1182 passed |
| `uv run pytest tests/integration/test_db_identity_integration.py tests/integration/test_iw_core_instance_migration.py` | 11 passed |

## Findings

| Severity | File | Issue | Fix Applied |
|----------|------|-------|-------------|
| none | — | No CRITICAL/HIGH issues found | — |

## Blockers

None.

## Recommendation

CR-00014 is ready for squash-merge. All acceptance criteria are satisfied, all quality gates pass, and no cross-layer inconsistencies were found.