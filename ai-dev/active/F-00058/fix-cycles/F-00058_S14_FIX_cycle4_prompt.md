# F-00058 S14 QV Fix Cycle 4/5

Quality gate S14 for work item F-00058 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 9 unit tests failed: 5 CLI exit code mismatches (pre-existing), 2 CLI exit code mismatches (pre-existing), 2 failures due to IW_CORE_AGENT_CONTEXT=true leaking into test environment

**Command output**:
```
...(truncated)...
ocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

tests/unit/test_qa_engine_render_cache.py::TestRenderCache::test_cache_put_and_get
  /usr/lib/python3.12/unittest/mock.py:2188: RuntimeWarning: coroutine 'TestPhaseEventSequence.test_composing_phase_contains_render_id.<locals>.mock_classify' was never awaited
    def __init__(self, name, parent):
  Enable tracemalloc to get traceback where the object was allocated.
  See https://docs.pytest.org/en/stable/how-to/capture-warnings.html#resource-warnings for more info.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/unit/test_merge_queue_cli.py::TestUnfreezeRefusesWithoutAck::test_unfreeze_refuses_without_ack
FAILED tests/unit/test_merge_queue_cli.py::TestUnfreezeRefusesWithoutAck::test_unfreeze_refuses_with_empty_ack
FAILED tests/unit/test_merge_queue_cli.py::TestUnfreezeRefusesWithoutAck::test_unfreeze_refuses_with_whitespace_only_ack
FAILED tests/unit/test_merge_queue_cli.py::TestUnfreezeSuccess::test_unfreeze_success
FAILED tests/unit/test_merge_queue_cli.py::TestUnfreezeSuccess::test_unfreeze_success_json
FAILED tests/unit/test_migrations_cli.py::TestApplyRefusesWithoutOperatorFlag::test_apply_refuses_without_operator_flag
FAILED tests/unit/test_migrations_cli.py::TestApplyRefusesWithoutOperatorFlag::test_apply_refuses_with_json_output
FAILED tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_does_not_raise_when_env_absent
FAILED tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[None]
================= 9 failed, 1234 passed, 18 warnings in 11.22s =================
make: *** [Makefile:36: test-unit] Error 1
[0m
[0m$ [0mmkdir -p ai-dev/active/F-00058/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00058/reports/F-00058_S14_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00058 --step S14 --reason "9 unit tests failed: 5 CLI exit code mismatches (pre-existing), 2 CLI exit code mismatches (pre-existing), 2 failures due to IW_CORE_AGENT_CONTEXT=true leaking into test environment"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00058 step S14: 9 unit tests failed: 5 CLI exit code mismatches (pre-existing), 2 CLI exit code mismatches (pre-existing), 2 failures due to IW_CORE_AGENT_CONTEXT=true leaking into test environment
[0m
**FAIL** — 9/1243 unit tests failed.

Key failures:
- 7 CLI tests expect exit code 3 but get 2 (pre-existing exit code mismatch issue)
- 2 `safe_migrate` tests fail because `IW_CORE_AGENT_CONTEXT=true` leaks into the test environment from the shell

Full report at `ai-dev/active/F-00058/reports/F-00058_S14_QvGate_report.md`

```


## Gate Command

The quality gate that failed runs:
```bash
make test-unit
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
