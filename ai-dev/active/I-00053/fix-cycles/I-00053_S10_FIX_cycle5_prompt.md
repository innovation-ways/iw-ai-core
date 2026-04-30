# I-00053 S10 QV Fix Cycle 5/5

Quality gate S10 for work item I-00053 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: integration-tests gate failed: exit=143 (SIGTERM - test suite timed out after 300s; ~78% tests completed)

**Command output**:
```
...(truncated)...
78%]
tests/integration/test_oss_dashboard_sse.py::TestSseHeartbeatEvery20s::test_heartbeat_emitted_at_20s_interval PASSED [ 78%]
tests/integration/test_oss_dashboard_sse.py::TestSseHeartbeatEvery20s::test_heartbeat_comment_format make: *** [Makefile:54: allure-integration] Error 143


<bash_metadata>
bash tool terminated command after exceeding timeout 300000 ms. If this command is expected to take longer and is not waiting for interactive input, retry with a larger timeout value in milliseconds.
</bash_metadata>
[0m
The command timed out after 300 seconds. Let me check the Makefile target and the current test status to understand what happened.
[0m$ [0mcat Makefile | grep -A 10 "allure-integration"
allure-unit allure-integration allure-all allure-report allure-serve allure-clean \
         e2e-health e2e-logs e2e-stats \
         security-deps security-iac security-image-dashboard security-all security-report

# --- Setup ---
install:
	uv sync
	uv run alembic upgrade head

# --- Quality ---
lint: lint-js
--
allure-integration:
	uv run pytest tests/integration/ -v --timeout=550 --timeout-method=signal --alluredir=allure-results

allure-all:
	uv run pytest tests/ -v --alluredir=allure-results

allure-serve:
	@command -v allure >/dev/null 2>&1 || { \
		echo "ERROR: 'allure' CLI not found on PATH."; \
		echo ""; \
		echo "Install via npm:  npm install -g allure-commandline"; \
[0m
[0m$ [0mls -la ai-dev/active/I-00053/reports/ 2>/dev/null || echo "Reports directory does not exist yet"
total 72
drwxrwxr-x 2 sergiog sergiog 4096 Apr 30 13:04 .
drwxrwxr-x 6 sergiog sergiog 4096 Apr 30 11:56 ..
-rw-rw-r-- 1 sergiog sergiog 4567 Apr 30 11:50 I-00053_S01_Backend_report.md
-rw-rw-r-- 1 sergiog sergiog 6674 Apr 30 11:55 I-00053_S02_CodeReview_report.md
-rw-rw-r-- 1 sergiog sergiog 4823 Apr 30 12:34 I-00053_S03_Tests_report.md
-rw-rw-r-- 1 sergiog sergiog 9094 Apr 30 12:39 I-00053_S04_CodeReview_report.md
-rw-rw-r-- 1 sergiog sergiog 5197 Apr 30 12:43 I-00053_S05_CodeReviewFinal_report.md
-rw-rw-r-- 1 sergiog sergiog  430 Apr 30 12:46 I-00053_S06_QvGate_report.md
-rw-rw-r-- 1 sergiog sergiog  448 Apr 30 12:49 I-00053_S07_QvGate_report.md
-rw-rw-r-- 1 sergiog sergiog  464 Apr 30 12:52 I-00053_S08_QvGate_report.md
-rw-rw-r-- 1 sergiog sergiog  540 Apr 30 12:58 I-00053_S09_QvGate_report.md
-rw-rw-r-- 1 sergiog sergiog 2028 Apr 30 14:15 I-00053_S10_QvGate_report.md
[0m
Let me read the existing report and then update it with the correct outcome:
[0m→ [0mRead ai-dev/active/I-00053/reports/I-00053_S10_QvGate_report.md
The report has already been written. Since the command exited with code 143 (SIGTERM/timeout), the gate failed. Let me call `iw step-fail`:
[0m
[0m$ [0muv run iw step-fail I-00053 --step S10 --reason "integration-tests gate failed: exit=143 (SIGTERM - test suite timed out after 300s; ~78% tests completed)"
Failed I-00053 step S10: integration-tests gate failed: exit=143 (SIGTERM - test suite timed out after 300s; ~78% tests completed)
[0m

```


## Gate Command

The quality gate that failed runs:
```bash
make allure-integration
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**ESCALATION**: This is the FINAL fix cycle (5/5). If you cannot resolve all issues, clearly document which remain and why.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
