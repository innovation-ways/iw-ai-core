# I-00062 S03 Backend Report

## What Was Done

Implemented the three-layer defense-in-depth against the I-00062 orch DB credential leak. All changes are in `orch/daemon/worktree_compose.py`, `orch/daemon/batch_manager.py`, and `orch/config.py`.

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/worktree_compose.py` | Added `discovered_db_credentials: dict[str, str]` to `UpResult` dataclass; `_read_db_credentials_from_toml()` helper reads HOST/NAME/USER/PASSWORD from `worktree-env.toml [env_overrides]`; all 6 `UpResult()` call sites updated |
| `orch/daemon/batch_manager.py` | Persist credentials at compose-up (4 new `BatchItem` columns); pass them through `worktree_info`; snapshot + strip `IW_CORE_DB_*` in `_agent_subprocess_env()`; inject all 5 per-worktree DB vars in `_launch_step` with belt-and-suspenders `RuntimeError` if incomplete |
| `orch/config.py` | `_check_agent_context_does_not_resolve_to_orch_port()` guard in `get_db_url()` only; `get_orch_db_url()` is untouched |

## Layer-by-layer Summary

### Layer 1 — Snapshot + Strip (`_agent_subprocess_env`)

Before stripping, the function now snapshots the daemon's 5 `IW_CORE_DB_*` values into `IW_CORE_ORCH_DB_*` via `setdefault` (won't clobber browser env injection). Then strips all 5 `IW_CORE_DB_*` keys from the returned env. This gives Layer 3 a reference for any agent context, including legacy worktrees whose `.env` mirrors main's `IW_CORE_DB_PORT=5433`.

### Layer 2 — Per-worktree injection (`_launch_step`)

When `worktree_compose_path` is set in `worktree_info`, all 5 DB vars are injected explicitly from the `BatchItem` columns (populated at compose-up). The `bv_env` merge runs **before** this block, so browser-verification steps still win for `IW_CORE_DB_*`. If credentials are incomplete, a `RuntimeError` is raised rather than silently falling back.

### Layer 3 — Fail-fast guard (`orch/config.py`)

`get_db_url()` now calls `_check_agent_context_does_not_resolve_to_orch_port(port)`. If `IW_CORE_AGENT_CONTEXT=true` AND `IW_CORE_ORCH_DB_PORT` matches `IW_CORE_DB_PORT`, it raises `RuntimeError` with the exact runbook reference string. Operator workflows (daemon, dashboard, `make db-migrate`) run with `IW_CORE_AGENT_CONTEXT` unset and are unaffected.

## Test Results

| Check | Result |
|-------|--------|
| `make format` | OK — 563 files already formatted |
| `make typecheck` | OK — 217 source files, no errors |
| `make lint` (modified files only) | OK — `orch/daemon/worktree_compose.py`, `orch/daemon/batch_manager.py`, `orch/config.py` all pass |
| `make test-unit` | 2486 passed, 2 skipped, 5 xfailed, 1 xpassed |

Two pre-existing unit tests required updates:
- `tests/unit/daemon/test_worktree_compose.py::TestUpResult::test_dataclass_frozen` — added `discovered_db_credentials={}` arg
- `tests/unit/test_agent_subprocess_env.py::test_preserves_unrelated_env_vars` — updated assertion to reflect the I-00062 strip behavior (with explanatory comment referencing the runbook)

## Notes

- **AC6 (browser-verification ordering) confirmed visually**: `_agent_subprocess_env()` runs first → `bv_env` merge happens second → compose-path block runs third. The `setdefault` in the snapshot ensures that if `bv_env` has already populated `IW_CORE_ORCH_DB_*`, we do not overwrite it.
- **`make lint` with full repo**: reports 8 errors in `scripts/arch_check.py` (unrelated file, pre-existing issues). Modified files are clean.
- **Integration tests**: timed out at 300s limit. Ran targeted unit tests for all modified files (46 passed, 9.4s).