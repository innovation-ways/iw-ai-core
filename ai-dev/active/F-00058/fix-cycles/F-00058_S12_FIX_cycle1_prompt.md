# F-00058 S12 QV Fix Cycle 1/5

Quality gate S12 for work item F-00058 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 9 files would be reformatted by ruff format

**Command output**:
```
...(truncated)...
h the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Started F-00058 step S12 (already in progress)
[0m
[0m$ [0muv run ruff format --check .
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Would reformat: orch/db/migrations/versions/13014259ab68_add_project_oss_job.py
Would reformat: orch/db/models.py
Would reformat: tests/integration/test_oss_dashboard_boundary.py
Would reformat: tests/integration/test_oss_dashboard_routes.py
Would reformat: tests/integration/test_oss_dashboard_service.py
Would reformat: tests/integration/test_oss_dashboard_sse.py
Would reformat: tests/integration/test_oss_dashboard_templates_extras.py
Would reformat: tests/integration/test_project_oss_job_migration.py
Would reformat: tests/unit/test_oss_dashboard_service.py
9 files would be reformatted, 291 files already formatted
[0m
**FAIL** — 9 files would be reformatted:
- `orch/db/migrations/versions/13014259ab68_add_project_oss_job.py`
- `orch/db/models.py`
- `tests/integration/test_oss_dashboard_boundary.py`
- `tests/integration/test_oss_dashboard_routes.py`
- `tests/integration/test_oss_dashboard_service.py`
- `tests/integration/test_oss_dashboard_sse.py`
- `tests/integration/test_oss_dashboard_templates_extras.py`
- `tests/integration/test_project_oss_job_migration.py`
- `tests/unit/test_oss_dashboard_service.py`
[0m$ [0mmkdir -p ai-dev/active/F-00058/reports && cat > ai-dev/active/F-00058/reports/F-00058_S12_QvGate_report.md << 'EOF'
# F-00058 S12 Report: QV Format Gate (ruff)

## Gate
- **Command**: `uv run ruff format --check .`
- **Result**: FAIL

## Output
9 files would be reformatted:
- orch/db/migrations/versions/13014259ab68_add_project_oss_job.py
- orch/db/models.py
- tests/integration/test_oss_dashboard_boundary.py
- tests/integration/test_oss_dashboard_routes.py
- tests/integration/test_oss_dashboard_service.py
- tests/integration/test_oss_dashboard_sse.py
- tests/integration/test_oss_dashboard_templates_extras.py
- tests/integration/test_project_oss_job_migration.py
- tests/unit/test_oss_dashboard_service.py

291 files already formatted.
EOF
(no output)
[0m
[0m$ [0muv run iw step-fail F-00058 --step S12 --reason "9 files would be reformatted by ruff format"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00058 step S12: 9 files would be reformatted by ruff format
[0m
**FAIL**

9 files would be reformatted by `ruff format`:
- `orch/db/migrations/versions/13014259ab68_add_project_oss_job.py`
- `orch/db/models.py`
- 7 test files under `tests/integration/` and `tests/unit/`

291 files already formatted.

Step failed with reason: "9 files would be reformatted by ruff format"

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
