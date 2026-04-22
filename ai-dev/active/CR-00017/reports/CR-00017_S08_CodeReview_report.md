# CR-00017 S08 Code Review Report — CLI Implementation

## What Was Reviewed

S07 backend implementation of two new CLI command groups:
- `orch/cli/migrations_commands.py` — `iw migrations {list-pending|dry-run|apply}`
- `orch/cli/merge_queue_commands.py` — `iw merge-queue {status|unfreeze}`

Plus test files:
- `tests/unit/test_migrations_cli.py`
- `tests/unit/test_merge_queue_cli.py`

## Findings

### CRITICAL / HIGH Issues — None

### Exit-Code Discipline ✅
- Canonical codes (0/2/3/4/5/1) match design exactly.
- `apply_migrations` exits 2 on agent-context, 3 on missing `--i-am-operator`, 5 on migration failure, 4 on multi-head.
- `unfreeze` exits 2 on agent-context, 3 on missing `--ack`.
- No expected failure mode leaks a Python traceback — `output_error()` produces formatted output on all error paths.
- Exit code 1 is reserved for unexpected `Exception` in all commands.

### Ack Flag Enforcement ✅
- `iw migrations apply` checks `IW_CORE_AGENT_CONTEXT` first (line 164), then checks `i_am_operator` (line 175) — correct order.
- `iw merge-queue unfreeze` checks `IW_CORE_AGENT_CONTEXT` first (line 165), then checks `ack_text` (line 176) — correct order.
- Both guards fire before any safe_migrate call.

### Agent-Context Refusal ✅
- `apply_migrations` and `merge_queue_unfreeze` check `IW_CORE_AGENT_CONTEXT` before any state change.
- `list_pending`, `dry_run`, and `merge_queue_status` do NOT have the agent-context check — correct, they are read-only/safe.

### Output Formats ✅
- `--json` on all five commands produces valid JSON (confirmed by `json.loads` in tests).
- Human-readable output is consistent with existing `iw` CLI style (uses `click.echo` with descriptive messages, follows same patterns as `lock_commands.py`).

### Session Hygiene ✅
- `merge_queue_status` opens its own engine/session and closes both in `finally:` (lines 52-142).
- `list_pending` uses `safe_migrate.list_pending_revisions` which handles its own session (S03 implementation).
- `apply_migrations` uses `safe_apply` which handles its own session.
- No leaked cursors.

### Registration ✅
- Both groups registered in `orch/cli/main.py` via `add_command` (lines 97-98).
- `uv run iw --help` shows `migrations` and `merge-queue` groups.

### Test Coverage ✅
- 19 tests pass (10 migrations_cli + 9 merge_queue_cli).
- All documented exit codes tested:
  - `migrations apply` without flag → exit 3
  - `migrations apply` in agent context → exit 2
  - `migrations apply --i-am-operator` in agent context → exit 2 (via JSON path)
  - `migrations dry-run` failure → exit 5
  - `migrations list-pending` multi-head → exit 4
  - `merge-queue unfreeze` without ack → exit 3 (3 variants: missing, empty, whitespace)
  - `merge-queue unfreeze` in agent context → exit 2 (2 variants)
  - `merge-queue status` JSON → exit 0, parseable
- Tests mock `safe_migrate` / `migration_pipeline` — no live DB or testcontainer usage.
- Fresh env fixture via `monkeypatch.setenv("IW_CORE_AGENT_CONTEXT", "true")` in setup ensures no leakage between tests.

### Project Conventions ✅
- Click decorators match existing style (e.g., `@migrations_group.command("apply")`).
- Error messages use `output_error` helper from `orch/cli/utils.py` (same pattern used by `lock_commands.py` and `step_commands.py`).
- `getpass.getuser()` used for operator identity, consistent with daemon pattern.

## Minor Observations

- `merge_queue_commands.py` line 52: `db_url = get_db_url()` called before try block, so if `get_db_url()` raises, the exception is caught by the `except Exception` at line 138 and printed via `output_error`. This is acceptable — no resource leak.
- The `finally` block in `merge_queue_status` (lines 140-142) correctly closes session then disposes engine.
- Exit code mapping is documented in both file docstrings and the S07 report.

## Verdict

**APPROVED** — S07 implementation is correct, complete, and meets all acceptance criteria for AC7 (CLI surface).

All 1217 unit tests pass. New files pass ruff and mypy. Manual `iw --help` confirms registration.