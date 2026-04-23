# CR-00013 S11 QV Fix Cycle 1/5

Quality gate S11 for work item CR-00013 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 41 files would be reformatted by ruff format

**Command output**:
```
...(truncated)...
unning.py
Would reformat: dashboard/routers/worktrees.py
Would reformat: dashboard/services/oss_service.py
Would reformat: dashboard/utils/timing.py
Would reformat: scripts/backfill_functional_doc.py
Would reformat: tests/integration/api/test_docs_diff_api.py
Would reformat: tests/integration/api/test_docs_ide_api.py
Would reformat: tests/integration/test_artifact_browser_api.py
Would reformat: tests/integration/test_code_module_routes.py
Would reformat: tests/integration/test_code_qa_eval_set.py
Would reformat: tests/integration/test_code_qa_findusages.py
Would reformat: tests/integration/test_code_qa_no_regression.py
Would reformat: tests/integration/test_code_qa_routes.py
Would reformat: tests/integration/test_code_qa_routing.py
Would reformat: tests/integration/test_code_qa_workitem_flow.py
Would reformat: tests/integration/test_dashboard_actions.py
Would reformat: tests/integration/test_dashboard_fragments.py
Would reformat: tests/integration/test_dashboard_pages.py
Would reformat: tests/integration/test_dashboard_remaining.py
Would reformat: tests/integration/test_doc_automation.py
Would reformat: tests/integration/test_doc_commands_integration.py
Would reformat: tests/integration/test_doc_job_routes.py
Would reformat: tests/integration/test_doc_polish.py
Would reformat: tests/integration/test_docs_routes.py
Would reformat: tests/integration/test_execution_report_dashboard_route.py
Would reformat: tests/integration/test_history_sorting.py
Would reformat: tests/integration/test_jobs_api.py
Would reformat: tests/integration/test_n1_bounded_queries.py
Would reformat: tests/integration/test_nav_worktree_badge_cache.py
Would reformat: tests/integration/test_oss_dashboard_service.py
Would reformat: tests/integration/test_pages_lazy_libs.py
Would reformat: tests/integration/test_project_onboarding_api.py
Would reformat: tests/unit/test_base_html_renders.py
Would reformat: tests/unit/test_daemon_control_async.py
Would reformat: tests/unit/test_db_pool_config.py
Would reformat: tests/unit/test_oss_dashboard_service.py
Would reformat: tests/unit/test_pool_config.py
Would reformat: tests/unit/test_static_assets.py
Would reformat: tests/unit/test_timing_middleware.py
41 files would be reformatted, 275 files already formatted
[0m
FAIL - 41 files would be reformatted
[0m$ [0mmkdir -p ai-dev/active/CR-00013/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/CR-00013/reports/CR-00013_S11_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail CR-00013 --step S11 --reason "41 files would be reformatted by ruff format"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed CR-00013 step S11: 41 files would be reformatted by ruff format
[0m
**FAIL** — 41 files would be reformatted by ruff format. Report written to `ai-dev/active/CR-00013/reports/CR-00013_S11_QvGate_report.md`.

```


## Gate Command

The quality gate that failed runs:
```bash
uv run ruff format --check .
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
