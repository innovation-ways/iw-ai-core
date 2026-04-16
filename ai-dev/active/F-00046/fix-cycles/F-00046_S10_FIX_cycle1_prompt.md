# F-00046 S10 QV Fix Cycle 1/5

Quality gate S10 for work item F-00046 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 6 integration tests fail: 1 test assertion bug (test_incremental_reindex expects bare filename in manifest which stores full paths) + 4 tests connect runner.run() background thread to live DB instead of testcontainer (UndefinedTable), + 1 test (test_regenerate_map_upserts_project_doc) also UndefinedTable. See report.

**Command output**:
```
...(truncated)...
/../.local/share/opencode/tool-output/tool_d9337789e001UridVIC56bynjI[90m [offset=100, limit=200][0m
[0m✱ [0mGrep "^_______________ [^_]+ _______________$"[90m in ../../../../../../.local/share/opencode/tool-output/tool_d9337789e001UridVIC56bynjI · 0 matches[0m
[0m✱ [0mGrep "FAILURES"[90m in ../../../../../../.local/share/opencode/tool-output/tool_d9337789e001UridVIC56bynjI · 1 match[0m
[0m→ [0mRead ../../../../../../.local/share/opencode/tool-output/tool_d9337789e001UridVIC56bynjI[90m [offset=491, limit=400][0m
[0m→ [0mRead tests/integration/test_code_index_pipeline.py
[0m→ [0mRead tests/integration/conftest.py
Let me look at the specific failures and the orch/rag/job.py to understand what's happening:
[0m→ [0mRead orch/rag/job.py
[0m
[0m$ [0muv run iw step-status F-00046 --step S10 2>&1
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Usage: iw [OPTIONS] COMMAND [ARGS]...
Try 'iw --help' for help.

Error: No such command 'step-status'.
[0m
Let me look at more of the test failures to understand the full picture:
[0m→ [0mRead ../../../../../../.local/share/opencode/tool-output/tool_d9337789e001UridVIC56bynjI[90m [offset=890, limit=200][0m
Now I have a clear picture of the issues. Let me create the report and call step-fail:
[0m
[0m$ [0mmkdir -p ai-dev/active/F-00046/reports
[0m
[0m← [0mWrite ai-dev/active/F-00046/reports/F-00046_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00046 --step S10 --reason "6 integration tests fail: 1 test assertion bug (test_incremental_reindex expects bare filename in manifest which stores full paths) + 4 tests connect runner.run() background thread to live DB instead of testcontainer (UndefinedTable), + 1 test (test_regenerate_map_upserts_project_doc) also UndefinedTable. See report."
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00046 step S10: 6 integration tests fail: 1 test assertion bug (test_incremental_reindex expects bare filename in manifest which stores full paths) + 4 tests connect runner.run() background thread to live DB instead of testcontainer (UndefinedTable), + 1 test (test_regenerate_map_upserts_project_doc) also UndefinedTable. See report.
[0m
**S10 QV Gate — Integration Tests: FAILED**

- 473 passed, 6 failed
- 6 failures all in `test_code_index_pipeline.py`:
  - **`test_incremental_reindex`**: Test asserts `"main.py" in manifest` but manifest stores full paths
  - **4 other tests**: `runner.run()` background threads use `SessionLocal()` connecting to live DB (port 5433) instead of testcontainer → `UndefinedTable: code_index_jobs`

Report written to `ai-dev/active/F-00046/reports/F-00046_S10_QvGate_report.md`.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
