# I-00052 S01 Backend Report

## What was done

Added `_capture_crashed_container_logs` helper to `orch/daemon/browser_env.py` and updated the error recording in `orch/daemon/batch_manager.py` to append container crash logs to `StepRun.error_message`.

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/browser_env.py` | Added `_capture_crashed_container_logs(compose_log, tail=50)` after `run_env_up_hook`. Parses compose output with regex `r"container\s+([\w\-]+)\s+exited\s+\(\d+\)"` (case-insensitive), deduplicates names, calls `docker logs <name> --tail 50` for each, formats output as `## Container Crash Logs\n\n`. Never raises — all exceptions caught and logged as "(unavailable)". |
| `orch/daemon/batch_manager.py:884–893` | Replaced `log_tail` block with new block that reads `compose_output` once, splits for `log_tail`, and calls `browser_env._capture_crashed_container_logs(compose_output)` to get `container_crash_logs`. Both concatenated in `error_msg`. Added `noqa: SLF001` to suppress private-access warning. |
| `pyproject.toml` | Added per-file ignore for `S603, S607` in `orch/daemon/browser_env.py` — `docker logs` is read-only introspection and name is derived from compose output (daemon-controlled), not user input. |

## Preflight Quality Gates

- **Format**: `uv run ruff format .` — no changes (already clean)
- **Typecheck**: `make typecheck` — pre-existing errors in `container_info.py` (unrelated to this change); `mypy orch/daemon/browser_env.py orch/daemon/batch_manager.py` passes with 0 errors
- **Lint**: `make lint` — pre-existing errors in `dashboard/routers/code_qa.py` (unrelated); `ruff check orch/daemon/browser_env.py orch/daemon/batch_manager.py` passes with 0 errors

## Test Results

- `_capture_crashed_container_logs` unit tests (inline via Python):
  - Empty input → empty string ✓
  - No exited containers → empty string ✓
  - Extracts container name, calls `docker logs`, includes output in result ✓

- `make test-unit`: 2054 passed, 9 failed, 2 skipped — **all failures are pre-existing** and unrelated to this change (RAG mermaid injection, safe_migrate agent-context guards). No regressions introduced.

## Notes

- The `noqa: SLF001` on the `browser_env._capture_crashed_container_logs` call in `batch_manager.py` is required because the design document specifies the call be prefixed with `browser_env.` (explicit module access), which triggers SLF001 on private member access.
- `docker logs` is read-only — does not change container/volume/network state. Explicitly allowed by CLAUDE.md constraints.
- The function preserves insertion order for deduplicated container names using `dict.fromkeys()`.