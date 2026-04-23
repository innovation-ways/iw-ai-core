# F-00058 S14 QV Fix Cycle 1/5

Quality gate S14 for work item F-00058 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 17 unit tests failed (test_daemon_core.py, test_merge_queue_cli.py, test_migrations_cli.py, test_oss_dashboard_service.py, test_safe_migrate*.py) — environment-specific failures: DB identity mismatch, env var isolation issues, CLI exit code regressions

**Command output**:
```
...(truncated)...
itespace_only_ack
FAILED tests/unit/test_merge_queue_cli.py::TestUnfreezeSuccess::test_unfreeze_success
FAILED tests/unit/test_merge_queue_cli.py::TestUnfreezeSuccess::test_unfreeze_success_json
FAILED tests/unit/test_migrations_cli.py::TestApplyRefusesWithoutOperatorFlag::test_apply_refuses_without_operator_flag
FAILED tests/unit/test_migrations_cli.py::TestApplyRefusesWithoutOperatorFlag::test_apply_refuses_with_json_output
FAILED tests/unit/test_oss_dashboard_service.py::TestSseMessageFormatter::test_sse_status_event
FAILED tests/unit/test_oss_dashboard_service.py::TestSseMessageFormatter::test_sse_progress_line_format
FAILED tests/unit/test_oss_dashboard_service.py::TestFreshnessHelper::test_compute_freshness_matches_head_sha
FAILED tests/unit/test_oss_dashboard_service.py::TestFreshnessHelper::test_compute_freshness_stale
FAILED tests/unit/test_oss_dashboard_service.py::TestFreshnessHelper::test_compute_freshness_fresh
FAILED tests/unit/test_safe_migrate.py::TestAssertNotAgentContext::test_does_not_raise_when_env_absent
FAILED tests/unit/test_safe_migrate_guards.py::TestAgentContextGuardSemantics::test_does_not_raise_when_absent_or_empty[None]
================ 17 failed, 1226 passed, 18 warnings in 12.58s =================
make: *** [Makefile:36: test-unit] Error 1
[0m
**FAIL** — 17 failed, 1226 passed.

The failures are environment-related (DB identity checks, CLI argument validation, asyncio event loop deprecations), not F-00058 code defects.
[0m$ [0mmkdir -p ai-dev/active/F-00058/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00058/reports/F-00058_S14_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00058 --step S14 --reason "17 unit tests failed (test_daemon_core.py, test_merge_queue_cli.py, test_migrations_cli.py, test_oss_dashboard_service.py, test_safe_migrate*.py) — environment-specific failures: DB identity mismatch, env var isolation issues, CLI exit code regressions"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00058 step S14: 17 unit tests failed (test_daemon_core.py, test_merge_queue_cli.py, test_migrations_cli.py, test_oss_dashboard_service.py, test_safe_migrate*.py) — environment-specific failures: DB identity mismatch, env var isolation issues, CLI exit code regressions
[0m
**FAIL**

`make test-unit` completed with **17 failures** (1226 passed). Key failures:

- `test_daemon_core.py` (3 failures) — DB identity mismatch (`IW_CORE_EXPECTED_INSTANCE_ID`)
- `test_merge_queue_cli.py` / `test_migrations_cli.py` (6 failures) — CLI exit code regressions
- `test_oss_dashboard_service.py` (5 failures) — asyncio event loop issues
- `test_safe_migrate*.py` (2 failures) — `IW_CORE_AGENT_CONTEXT` env var leaking between tests

Report written to `ai-dev/active/F-00058/reports/F-00058_S14_QvGate_report.md` and step marked as failed.

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
