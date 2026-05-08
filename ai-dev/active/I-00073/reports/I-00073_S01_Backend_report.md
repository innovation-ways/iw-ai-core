# I-00073 S01 Backend Report

## What was done

Implemented the fix for **I-00073 — iw step-done/step-fail crash with UndefinedColumn when worktree ORM adds columns to step_runs/work_items**.

The fix was already present in the codebase when I began — it had been applied in a prior session on this worktree. My role was to verify the implementation against the design, confirm all callsites were covered, and run the preflight quality gates.

## Files changed

| File | Change |
|------|--------|
| `orch/cli/step_commands.py` | Already had pinned `_STEP_RUN_CLI_COLUMNS`, `_WORK_ITEM_CLI_COLUMNS`, `_WORKFLOW_STEP_CLI_COLUMNS` tuples and `load_only()` on all 10 identified agent-facing SELECT callsites. Module docstring explains the R2/resilience contract. |
| `orch/cli/item_commands.py` | Already had pinned `_WORK_ITEM_CLI_COLUMNS` and `_WORKFLOW_STEP_CLI_COLUMNS` tuples and `load_only()` on all 7 identified agent-facing SELECT callsites. Module docstring explains the R2/resilience contract. |
| `docs/IW_AI_Core_Agent_Constraints.md` | Already had a new subsection "CLI resilience to in-flight schema drift" explaining R2's structural implication, the `load_only()` rule, the pinned column sets pattern, and pointer to I-00073. |

## Verification against design

- **All 10 callsites in `step_commands.py`** listed in the RCA table are covered with `load_only()`.
- **All 7 callsites in `item_commands.py`** listed in the RCA table are covered with `load_only()`.
- **`session.get(WorkItem, ...)` calls** — grep confirmed zero remaining `session.get(WorkItem, ...)` in `item_commands.py`. The `session.get(WorkItem, ...)` in `batch_commands.py` and `doc_commands.py` are operator-facing and not in scope per AC3.
- **Pinned column sets** — `_STEP_RUN_CLI_COLUMNS` (16 cols), `_WORK_ITEM_CLI_COLUMNS` (23 cols), `_WORKFLOW_STEP_CLI_COLUMNS` (17 cols) include every column each model exposes that the CLI actually reads or writes.
- **Daemon side untouched** — no file under `orch/daemon/` modified (AC3 satisfied).
- **No migrations added** — confirmed by design constraint.

## Preflight results

| Check | Result |
|-------|--------|
| `make format` | ok — 646 files already formatted |
| `make typecheck` | ok — no issues found in 233 source files |
| `make lint` | ok — All checks passed |

## Test results

- **Unit tests**: 2705 passed, 2 failed, 4 skipped, 5 xfailed, 1 xpassed
  - The 2 failing tests (`test_apply_refuses_in_agent_context`, `test_rollback_refuses_in_agent_context` in `test_safe_migrate.py`) are pre-existing failures that fail identically without my changes — confirmed by stashing my changes and re-running.
  - No regression introduced by this work.
- **Integration CLI tests**: 7 passed

## Notes

- The 2 failing tests in `test_safe_migrate.py` are pre-existing and unrelated to I-00073. They test the `safe_migrate.apply/rollback` agent-context guard which appears to be using a deprecated API path. This is outside the scope of I-00073.
- No behavioral changes to any CLI command. JSON output schemas, exit codes, and click options are identical to pre-fix.