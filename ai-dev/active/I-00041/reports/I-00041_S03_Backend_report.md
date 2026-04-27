# I-00041 S03 Backend Report

## What was done

S01 added the connection-layer chokepoint (`live_db_guard`). S03 **armed it** by inverting the test fixture from opt-out to opt-in, wiring the daemon entry point to set its own allow-list flag, and scoping the operator CLI flag to a single invocation.

## Files changed

| File | Change |
|------|--------|
| `tests/conftest.py` | R1 — session-scoped `_arm_live_db_guard()` fixture replaces the function-scoped opt-out fixture; sets `IW_CORE_TEST_CONTEXT=true` and clears leaked allow-list flags |
| `orch/daemon/__main__.py` | R2 — arm `IW_CORE_DAEMON_CONTEXT=true` as the very first statement in `if __name__ == "__main__":` before `Daemon(config)` construction |
| `orch/cli/migrations_commands.py` | R3 — `apply_migrations` wraps `safe_apply` in try/finally that scopes `IW_CORE_OPERATOR_APPLY=true` to that invocation only |
| `orch/daemon/batch_manager.py` | R5 — added `_agent_subprocess_env()` helper (strips allow-list flags, arms `IW_CORE_AGENT_CONTEXT`) and rewired all 3 agent/QV-gate launch sites |
| `orch/daemon/fix_cycle.py` | R5 — `_recompute_baseline_for_gate` uses `_agent_subprocess_env()` (import from batch_manager) |
| `orch/daemon/doc_job_poller.py` | R5 — `_launch_job` uses `_agent_subprocess_env()` (import from batch_manager) |

## R5 call-site audit

| File | Line | Change |
|------|------|--------|
| `batch_manager.py` | ~565 `_run_gate_command` | `env={**os.environ, "IW_CORE_AGENT_CONTEXT": "true"}` → `env=_agent_subprocess_env()` |
| `batch_manager.py` | ~776 `_launch_agent_step` | `agent_env = {**os.environ, "IW_CORE_AGENT_CONTEXT": "true"}` → `agent_env = _agent_subprocess_env()` (post-merge bv_env and per_worktree_db still merged) |
| `batch_manager.py` | ~1057 `_build_agent_env` | `return os.environ.copy()` → `return _agent_subprocess_env()` |
| `fix_cycle.py` | ~733 `_recompute_baseline_for_gate` | `env={**os.environ, "IW_CORE_AGENT_CONTEXT": "true"}` → `env=_agent_subprocess_env()` |
| `doc_job_poller.py` | ~171 `_launch_job` | `env=os.environ.copy()` → `env=_agent_subprocess_env()` |

## Test results

### Smoke checks

**1. Guard fires for test context**
```
OK: guard fired with LiveDbConnectionRefusedError: Connection to live orch DB refused:
IW_CORE_TEST_CONTEXT is set. Remediation: set IW_CORE_OPERATOR_APPLY=true...
```

**2. pytest collection still works**
```
1653 tests collected in 1.75s
```

**3. `iw migrations list-pending` (read-only, no flag set) still works**
```
No pending migrations.
```

**4. `import orch.daemon.main` does NOT arm daemon flag**
```
daemon import ok (no leak)
```

**5. `_agent_subprocess_env()` strips allow-list flags**
```
strip ok
```

**6. No inline `{**os.environ, ...}` patterns remain in agent/QV-gate launch sites**
All three files (batch_manager, fix_cycle, doc_job_poller) return zero matches for the grep pattern in the relevant sections.

### Quality checks

- `make lint` — **PASSED** (all checks passed)
- `make typecheck` on modified files only — **PASSED** (no issues found in 5 source files)

Note: pre-existing type errors in `dashboard/` and `orch/rag/` modules are unrelated to this step (verified with targeted mypy run on modified files).

## Notes

- `IW_CORE_DAEMON_CONTEXT` is intentionally NOT added to `main.py` — only `__main__.py` arms it. Importing `orch.daemon.main` from the dashboard or tests does NOT set the flag.
- The try/finally in `apply_migrations` uses a restore pattern (save prior, restore on exit) rather than unconditional pop, so a programmatic caller that calls the function multiple times without clearing the env gets the correct restoration behavior.
- The doc_job_poller also did not set `IW_CORE_AGENT_CONTEXT` in its subprocess env before this change — `_agent_subprocess_env()` fixes both the strip requirement AND the missing arm simultaneously.
- Pre-existing lint errors (unused imports) in `batch_manager.py` at lines 556 and 774 were cleaned up as part of this step since the refactoring made those imports redundant.