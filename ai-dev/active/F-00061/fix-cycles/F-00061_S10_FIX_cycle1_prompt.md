# F-00061 S10 QV Fix Cycle 1/5

Quality gate S10 for work item F-00061 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Lint failed with 16 errors: ARG001, I001, SIM105, N806, F401, UP041, E501 violations in dashboard/services/oss_service.py, tests/unit/test_oss_dashboard_service.py, tests/unit/orch/daemon/test_qv_baseline.py, tests/unit/executor/test_scope_gate.py, and ai-dev/active/CR-00013/e2e_fixtures/001_perf_dataset.py

**Command output**:
```
...(truncated)...
lue.order_by.return_value.first.return_value = None
   |                                                                                                     ^^^^^^^
89 |
90 |         with patch("dashboard.services.oss_service._git_head", return_value="abc123"):
   |

E501 Line too long (112 > 100)
   --> tests/unit/test_oss_dashboard_service.py:109:101
    |
108 |         mock_session.query.return_value.filter.return_value.first.return_value = mock_project
109 |         mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_scan
    |                                                                                                     ^^^^^^^^^^^^
110 |
111 |         with patch("dashboard.services.oss_service._git_head", return_value="def456"):
    |

E501 Line too long (112 > 100)
   --> tests/unit/test_oss_dashboard_service.py:130:101
    |
129 |         mock_session.query.return_value.filter.return_value.first.return_value = mock_project
130 |         mock_session.query.return_value.filter.return_value.order_by.return_value.first.return_value = mock_scan
    |                                                                                                     ^^^^^^^^^^^^
131 |
132 |         with patch("dashboard.services.oss_service._git_head", return_value="abc123"):
    |

Found 16 errors.
[*] 4 fixable with the `--fix` option (2 hidden fixes can be enabled with the `--unsafe-fixes` option).
make: *** [Makefile:17: lint] Error 1
[0m
Lint failed with 16 errors. Writing report and marking step as failed.
[0m$ [0mmkdir -p ai-dev/active/F-00061/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/F-00061/reports/F-00061_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00061 --step S10 --reason "Lint failed with 16 errors: ARG001, I001, SIM105, N806, F401, UP041, E501 violations in dashboard/services/oss_service.py, tests/unit/test_oss_dashboard_service.py, tests/unit/orch/daemon/test_qv_baseline.py, tests/unit/executor/test_scope_gate.py, and ai-dev/active/CR-00013/e2e_fixtures/001_perf_dataset.py"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00061 step S10: Lint failed with 16 errors: ARG001, I001, SIM105, N806, F401, UP041, E501 violations in dashboard/services/oss_service.py, tests/unit/test_oss_dashboard_service.py, tests/unit/orch/daemon/test_qv_baseline.py, tests/unit/executor/test_scope_gate.py, and ai-dev/active/CR-00013/e2e_fixtures/001_perf_dataset.py
[0m
**FAIL** — `make lint` returned exit code 1 with 16 errors:

- 4 auto-fixable (I001 import sorting, SIM105 contextlib.suppress)
- 12 manual fixes needed (N806 variable naming, E501 line length, F401 unused import, ARG001 unused arg, UP041 TimeoutError alias)

Report written to `ai-dev/active/F-00061/reports/F-00061_S10_QvGate_report.md`.

```


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
