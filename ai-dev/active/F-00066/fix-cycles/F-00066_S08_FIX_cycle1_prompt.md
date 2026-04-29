# F-00066 S08 QV Fix Cycle 1/5

Quality gate S08 for work item F-00066 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Lint failed with 4 errors: I001 import order in ai-dev/active/CR-99025/e2e_fixtures, E402 module import in tests/unit/conftest.py, PT006 parametrize type in test_merge_queue_migration_pipeline.py, ERA001 commented-out code in test_merge_queue_migration_pipeline.py

**Unparseable output** (always surfaces):
  !  agent "qv-gate" is a subagent, not a primary agent. Falling back to default agent
  > build · MiniMax-M2.7
  $ uv run iw step-start F-00066 --step S08
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  Started F-00066 step S08 (already in progress)
  $ make lint
  uv run ruff check .
  warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
  I001 [*] Import block is un-sorted or un-formatted
    --> ai-dev/active/CR-99025/e2e_fixtures/001_cr99025_evidence_fixture.py:11:1
     |
   9 |   """
  10 |
  11 | / from __future__ import annotations
  12 | |
  13 | | from datetime import UTC, datetime
  14 | | from typing import TYPE_CHECKING
  15 | |
  16 | | from orch.db.models import (
  17 | |     StepStatus,
  18 | |     StepType,
  19 | |     WorkItem,
  20 | |     WorkItemPhase,
  21 | |     WorkItemType,
  22 | |     WorkflowStep,
  23 | | )
     | |_^
  24 |
  25 |   if TYPE_CHECKING:
     |
  help: Organize imports
  E402 Module level import not at top of file
    --> tests/unit/conftest.py:20:1
     |
  20 | from tests.integration.conftest import db_engine, pg_container, test_project
     | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  21 |
  22 | __all__ = ["db_engine", "db_session", "pg_container", "test_project"]
     |
  PT006 Wrong type passed to first argument of `pytest.mark.parametrize`; expected `tuple`
    --> tests/unit/test_merge_queue_migration_pipeline.py:59:9
     |
  58 |     @pytest.mark.parametrize(
  59 |         "batch_id, expected",
     |         ^^^^^^^^^^^^^^^^^^^^
  60 |         [
  61 |             ("BATCH-00060", 60),
     |
  help: Use a `tuple` for the first argument
  ERA001 Found commented-out code
     --> tests/unit/test_merge_queue_migration_pipeline.py:253:9
      |
  251 |         mocks = self._run_merge_item(item)
  252 |         call_args = mocks["rebase"].call_args
  253 |         # positional: (batch_id, worktree_path, working_dir)
      |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  254 |         assert call_args[0][0] == "BATCH-00060"
  255 |         assert call_args[0][1] == "/wt/F-00060"
      |
  help: Remove commented-out code
  Found 4 errors.
  [*] 1 fixable with the `--fix` option (1 hidden fix can be enabled with the `--unsafe-fixes` option).
  make: *** [Makefile:17: lint] Error 1
  $ mkdir -p ai-dev/active/F-00066/reports
  (no output)
  ← Write ai-dev/active/F-00066/reports/F-00066_S08_QvGate_report.md
  Wrote file successfully.


## Gate Command

The quality gate that failed runs:
```bash
make lint
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
