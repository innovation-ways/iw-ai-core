# F-00083 S14 QV Fix Cycle 1/5

Quality gate S14 for work item F-00083 failed. Fix the issues below so the gate passes on re-run.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00083/ai-dev/active/F-00083/F-00083_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Errors to Address

The block below is **one hypothesis** generated from the failed gate. Verify it against the design doc spec above before applying any fix; the spec wins on conflict.

**Error**: unit-tests failed: exit=2

**Unparseable output** (always surfaces):
  uv run pytest tests/unit/ -v
  platform linux -- Python 3.12.3, pytest-9.0.3, pluggy-1.6.0 -- /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00083/.venv/bin/python
  cachedir: .pytest_cache
  rootdir: /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00083
  configfile: pyproject.toml
  plugins: timeout-2.4.0, asyncio-1.3.0, cov-7.1.0, respx-0.22.0, xdist-3.8.0, allure-pytest-2.15.3, Faker-40.13.0, anyio-4.13.0
  asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
  collecting ... collected 2887 items / 1 error
  ____________ ERROR collecting tests/unit/test_cancel_validators.py _____________
  ImportError while importing test module '/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00083/tests/unit/test_cancel_validators.py'.
  Hint: make sure your test modules/packages have valid Python names.
  Traceback:
  tests/unit/test_cancel_validators.py:11: in <module>
      from orch.cancel import (
  E   ImportError: cannot import name 'validate_batch_cancel_transition' from 'orch.cancel' (/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00083/orch/cancel.py)
  orch/db/models.py:225
    /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00083/orch/db/models.py:225: PytestCollectionWarning: cannot collect test class 'TestRunStatus' because it has a __init__ constructor (from: tests/unit/test_test_runner.py)
      class TestRunStatus(enum.Enum):
  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  ERROR tests/unit/test_cancel_validators.py
  !!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
  make: *** [Makefile:79: test-unit] Error 2


## Gate Command

The quality gate that failed runs:
```bash
make test-unit
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
