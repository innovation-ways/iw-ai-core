# CR-00014 S03 — Backend Implementation Report

## Summary

Step S03 (backend-impl) for CR-00014 completed successfully. Implemented the DB instance-identity verification module, daemon startup wiring, `iw db-identity` CLI, and `ai-core.sh` wiring.

## Files Changed

| File | Change |
|------|--------|
| `orch/db/identity.py` | New — `IdentityStatus`, `InstanceMismatchError`, `InstanceRowMissingError`, `get_live_instance_id`, `get_expected_instance_id`, `check_identity`, `verify_instance_identity` |
| `orch/daemon/main.py` | Extended `_startup()` to call `verify_instance_identity()` after DB connectivity check; added `_identity_bootstrap_logged` flag for one-shot bootstrap notice |
| `orch/cli/db_commands.py` | New — `db-identity show` and `db-identity check` Click commands |
| `orch/cli/main.py` | Registered `db_identity` command group |
| `ai-core.sh` | Extended `cmd_status` with DB identity line; extended `cmd_start` with identity check fail-fast |
| `.env.example` | Added `IW_CORE_EXPECTED_INSTANCE_ID` documented entry |

## What Was Done

### 1. `orch/db/identity.py`

- **`InstanceMismatchError`** / **`InstanceRowMissingError`**: Custom `RuntimeError` subclasses for enforcement errors
- **`IdentityStatus`**: Frozen dataclass with `expected`, `actual`, `mode` (match/mismatch/bootstrap/missing), and `message`
- **`get_live_instance_id(session)`**: Queries `IwCoreInstance` by PK=1; returns UUID or None
- **`get_expected_instance_id()`**: Reads `IW_CORE_EXPECTED_INSTANCE_ID` from env; strips whitespace; returns None if unset/empty; raises `ValueError` on malformed non-empty value
- **`check_identity(session)`**: Pure function — reads both values, classifies mode, returns `IdentityStatus` (never raises)
- **`verify_instance_identity(session)`**: Calls `check_identity`; raises `InstanceMismatchError` or `InstanceRowMissingError` on enforcement failures; returns status on match/bootstrap

Error messages name both UUIDs and include remediation hints. Bootstrap notice shows the exact `.env` line to add.

### 2. Daemon Startup Wiring (`orch/daemon/main.py`)

After the `SELECT 1` DB connectivity check:
- Calls `verify_instance_identity(session)` via short-lived session
- **match**: logs `INFO Database identity verified (<short-uuid>)`
- **bootstrap**: logs bootstrap notice once per process lifetime (via `_identity_bootstrap_logged` flag)
- **mismatch** or **missing** (with env set): logs boxed `ERROR` multi-line message, then `sys.exit(2)` — daemon refuses to enter main loop

### 3. `iw db-identity` CLI (`orch/cli/db_commands.py`)

New Click group with two subcommands:
- **`iw db-identity show`**: Shows live UUID, expected UUID (or unset), and mode. Always exits 0 (read-only diagnostic)
- **`iw db-identity check`**: Runs `verify_instance_identity`. Exit codes: 0 (match/bootstrap), 2 (mismatch), 3 (missing row with env set), 1 (connection error)

Registered in `orch/cli/main.py` alongside other command groups.

### 4. `ai-core.sh`

- **`cmd_status`**: After "PostgreSQL: accepting connections" line, runs `uv run iw db-identity check`:
  - Exit 0 + bootstrap → `print_warn "DB identity: UNVERIFIED (bootstrap mode…)"`
  - Exit 0 + match → `print_ok "DB identity: PASS (<short-uuid>)"`
  - Exit 2 → `print_err "DB identity: FAIL (expected!=actual)"` + indented error block
  - Exit 3 → `print_err "DB identity: row missing from iw_core_instance"`
  - Exit 1 → `print_err "DB identity: could not connect"`
- **`cmd_start`**: Added identity check after `cmd_db start` as fail-fast; propagates non-zero exit with error message

### 5. `.env.example`

Added documented section:
```bash
# -----------------------------------------------------------------------------
# DB instance-identity fingerprint (CR-00014)
# -----------------------------------------------------------------------------
IW_CORE_EXPECTED_INSTANCE_ID=
```

## Smoke Tests

| Test | Result |
|------|--------|
| `uv run iw db-identity show` (bootstrap mode, no env set) | PASS — shows live UUID, "Expected: (unset)", "Mode: bootstrap" |
| `uv run iw db-identity check` (bootstrap mode) | PASS — exit 0, prints bootstrap notice |
| `IW_CORE_EXPECTED_INSTANCE_ID=<wrong> uv run iw db-identity check` | PASS — exit 2, boxed MISMATCH error with both UUIDs |
| `uv run python -c "from orch.daemon.main import Daemon"` | PASS — module imports cleanly |
| `bash -n ai-core.sh` | PASS — shell syntax valid |
| `uv run mypy orch/db/identity.py orch/cli/db_commands.py` | PASS — no type errors |
| `make test-unit` | PASS — 1164 passed |

## Test Results

```
make test-unit: 1164 passed, 18 warnings (pre-existing warnings)
make lint: 2 pre-existing errors (ARG001 in item_commands.py, W292 in test_item_report_cli.py) — unchanged from S01
uv run ruff check (new files only): All checks passed
uv run mypy (new files only): Success: no issues found
```

## Blockers

None.

## Notes

- Bootstrap mode confirmed working: with `IW_CORE_EXPECTED_INSTANCE_ID` unset, `db-identity check` exits 0 and prints the exact `.env` line to add
- Mismatch mode confirmed working: wrong UUID in env var causes exit 2 with full error block
- The one-shot bootstrap notice in the daemon uses a per-`Daemon` instance flag (`_identity_bootstrap_logged`) — a restart re-emits it, which is the intended behavior
