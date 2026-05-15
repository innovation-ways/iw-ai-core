# F-00083 S10 QV Fix Cycle 1/3

Quality gate S10 for work item F-00083 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00083/ai-dev/active/F-00083/F-00083_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: lint failed: exit=2

**Unparseable output** (always surfaces):
  uv run python scripts/check_templates.py
  uv run ruff check .
  F401 [*] `pytest` imported but unused
    --> tests/dashboard/test_app_lifespan_opencode.py:25:8
     |
  23 | from unittest.mock import AsyncMock, MagicMock, patch
  24 |
  25 | import pytest
     |        ^^^^^^
  26 | from fastapi.testclient import TestClient
     |
  help: Remove unused import: `pytest`
  F401 [*] `fastapi.testclient.TestClient` imported but unused
    --> tests/dashboard/test_app_lifespan_opencode.py:26:32
     |
  25 | import pytest
  26 | from fastapi.testclient import TestClient
     |                                ^^^^^^^^^^
  27 |
  28 | from dashboard.dependencies import get_db
     |
  help: Remove unused import: `fastapi.testclient.TestClient`
  S105 Possible hardcoded password assigned to: "password"
    --> tests/dashboard/test_app_lifespan_opencode.py:49:37
     |
  47 |             mock_runtime = MagicMock()
  48 |             mock_runtime.base_url = "http://localhost:4096"
  49 |             mock_runtime.password = "test-pw-xyz"
     |                                     ^^^^^^^^^^^^^
  50 |             mock_runtime.health = AsyncMock(return_value=True)
  51 |             mock_runtime.start = AsyncMock()
     |
  S106 Possible hardcoded password assigned to argument: "password"
     --> tests/dashboard/test_app_lifespan_opencode.py:99:21
      |
   97 |                 mock_cl.assert_called_once_with(
   98 |                     base_url="http://localhost:4096",
   99 |                     password="test-pw-xyz",
      |                     ^^^^^^^^^^^^^^^^^^^^^^
  100 |                 )
  101 |                 mock_rm.assert_called_once_with(mock_client)
      |
  S105 Possible hardcoded password assigned to: "password"
     --> tests/dashboard/test_app_lifespan_opencode.py:161:37
      |
  159 |             mock_runtime = MagicMock()
  160 |             mock_runtime.base_url = "http://localhost:4096"
  161 |             mock_runtime.password = "pw"
      |                                     ^^^^
  162 |             mock_runtime.health = AsyncMock(return_value=True)
  163 |             mock_runtime.start = AsyncMock()
      |
  W292 [*] No newline at end of file
     --> tests/dashboard/test_app_lifespan_opencode.py:221:73
      |
  219 |         finally:
  220 |             if original_id is not None:
  221 |                 os.environ["IW_CORE_EXPECTED_INSTANCE_ID"] = original_id
      |                                                                         ^
      |
  help: Add trailing newline
  Found 6 errors.
  [*] 3 fixable with the `--fix` option.
  make: *** [Makefile:22: lint] Error 1


## Gate Command

The quality gate that failed runs:
```bash
make lint
```

After applying fixes, re-run this command to verify the issues are resolved.

## Pre-fix Procedure

1. **Read the design doc** at the path above. Skim the section that covers this step's scope; quote-of-the-doc lives in this prompt when available.
2. **Diff your target file(s) against the spec** — list deviations explicitly before editing.
3. **Apply the minimum patch** to align code with the spec; the reported errors should resolve as a side effect of that alignment.
4. **If the errors disagree with the spec, the spec wins.** Note the disagreement in your output rather than silently following the errors.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
