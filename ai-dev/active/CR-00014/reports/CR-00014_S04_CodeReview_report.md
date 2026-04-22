# CR-00014 S04 — Code Review Report

## Summary

S03 implementation passes review with no blockers. The identity module, daemon wiring, CLI, and `ai-core.sh` changes are correct and complete.

## Files Changed

- `orch/db/identity.py` — identity verification module
- `orch/daemon/main.py` — startup wiring
- `orch/cli/db_commands.py` — `iw db-identity` CLI commands
- `orch/cli/main.py` — command group registration
- `ai-core.sh` — `cmd_status` and `cmd_start` wiring
- `.env.example` — documented `IW_CORE_EXPECTED_INSTANCE_ID` entry

## Review Findings

### 1. `orch/db/identity.py` — PASS

| Criterion | Result |
|-----------|--------|
| Importable without DB connection | PASS — no module-level queries |
| `get_expected_instance_id()` returns None for unset/empty/whitespace | PASS — `raw.strip()` then `not stripped` check |
| Raises `ValueError` on malformed non-empty | PASS — `uuid.UUID(stripped)` handles it |
| `get_live_instance_id()` returns None for missing row | PASS — `session.get()` returns None |
| `check_identity()` is pure, returns `IdentityStatus` | PASS — no raises, all four modes covered |
| `verify_instance_identity()` raises exactly two types | PASS — `InstanceMismatchError`, `InstanceRowMissingError` |
| Error messages include both UUIDs + remediation | PASS — multiline with Expected/Actual/Remediation |

### 2. Daemon Startup Wiring — PASS

- Identity check happens AFTER `SELECT 1` DB connectivity (line 188-190), BEFORE project loading
- On `mismatch`/`missing`: `sys.exit(2)` — does NOT return from helper
- On bootstrap: one-shot via per-instance `_identity_bootstrap_logged` flag (line 125, 199-201)
- On match: single `INFO Database identity verified (<short-uuid>)` line
- No partial-start path: projects.toml, poll loop, signal handlers all come after identity check

### 3. `iw db-identity` CLI — PASS

- Command registered: `uv run iw --help` shows `db-identity`
- `show`: always exits 0, read-only diagnostic
- `check` exit codes: 0 (match/bootstrap), 2 (mismatch), 3 (missing), 1 (connection error) — matches spec exactly
- No tracebacks on expected failure modes — formatted error block only
- Short-UUID extraction in `ai-core.sh` uses `grep -oE '[0-9a-f]{8}'` — handles digit-leading UUIDs

### 4. `ai-core.sh` — PASS

- `cmd_status`: runs identity check but does NOT fail the overall status command on mismatch (exit 2 triggers `print_err` then continues) — matches design explicitly
- Uses existing `print_ok`/`print_err`/`print_warn` helpers with consistent colours
- `cmd_start`: identity check fail-fast before daemon/dashboard start
- `set -uo pipefail` compatible: `identity_output=$(uv run iw db-identity check 2>&1)` with double-quoted command substitution

### 5. `.env.example` — PASS

- Section added with comment and empty value
- Shows exact command to find value: `uv run iw db-identity show`
- Warning against committing populated value
- No value in `.env` itself (user-owned, gitignored)

### 6. Regression Surface — PASS

- Bootstrap mode (env var unset) still allows daemon, dashboard, and status to proceed normally with one-shot INFO notice
- Happy-path DB connectivity check preserved before identity check

## Quality Gates

| Gate | Result |
|------|--------|
| `make lint` | 2 pre-existing errors (ARG001 in `item_commands.py`, W292 in `test_item_report_cli.py`) — unchanged from S01/S02 |
| `make test-unit` | 1164 passed, 18 warnings (pre-existing) |
| `uv run mypy` (new files) | Success: no issues found |
| `bash -n ai-core.sh` | shell syntax OK |
| `uv run iw --help` | `db-identity` command visible |

## Blockers

None.

## Notes

- The lint errors (`ARG001` and `W292`) are pre-existing and unrelated to S03 changes.
- The one-shot bootstrap notice re-emits on daemon restart, which is the intended behavior per design.
- No S05 (dashboard API) changes are included in S03 scope — reviewed separately in S06.
