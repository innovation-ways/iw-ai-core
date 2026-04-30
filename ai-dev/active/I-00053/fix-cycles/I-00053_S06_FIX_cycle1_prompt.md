# I-00053 S06 QV Fix Cycle 1/5

Quality gate S06 for work item I-00053 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: lint failed: 8 errors (PT028 default args in dashboard/routers/tests.py, SIM117 nested with in test_baseline_qv_pipeline.py)

**Unparseable output** (always surfaces):
  > qv-gate · MiniMax-M2.7
  $ make lint
  uv run ruff check .
  PT028 Test function parameter `db` has default argument
    --> dashboard/routers/tests.py:88:19
     |
  86 |     project_id: str,
  87 |     request: Request,
  88 |     db: Session = Depends(get_db),
     |                   ^^^^^^^^^^^^^^^
  89 |     tab: str = "launch",
  90 | ) -> Any:
     |
  help: Remove default argument
  PT028 Test function parameter `tab` has default argument
    --> dashboard/routers/tests.py:89:16
     |
  87 |     request: Request,
  88 |     db: Session = Depends(get_db),
  89 |     tab: str = "launch",
     |                ^^^^^^^^
  90 | ) -> Any:
  91 |     project = get_project_or_404(project_id, db)
     |
  help: Remove default argument
  PT028 Test function parameter `db` has default argument
     --> dashboard/routers/tests.py:131:19
      |
  129 |     project_id: str,
  130 |     request: Request,
  131 |     db: Session = Depends(get_db),
      |                   ^^^^^^^^^^^^^^^
  132 | ) -> Any:
  133 |     project = get_project_or_404(project_id, db)
      |
  help: Remove default argument
  PT028 Test function parameter `db` has default argument
     --> dashboard/routers/tests.py:152:19
      |
  150 |     project_id: str,
  151 |     request: Request,
  152 |     db: Session = Depends(get_db),
      |                   ^^^^^^^^^^^^^^^
  153 | ) -> Any:
  154 |     project = get_project_or_404(project_id, db)
      |
  help: Remove default argument
  PT028 Test function parameter `db` has default argument
     --> dashboard/routers/tests.py:170:19
      |
  168 |     project_id: str,
  169 |     request: Request,
  170 |     db: Session = Depends(get_db),
      |                   ^^^^^^^^^^^^^^^
  171 | ) -> Any:
  172 |     project = get_project_or_404(project_id, db)
      |
  help: Remove default argument
  PT028 Test function parameter `db` has default argument
     --> dashboard/routers/tests.py:190:19
      |
  188 |     run_id: int,
  189 |     request: Request,
  190 |     db: Session = Depends(get_db),
      |                   ^^^^^^^^^^^^^^^
  191 | ) -> Any:
  192 |     project = get_project_or_404(project_id, db)
      |
  help: Remove default argument
  PT028 Test function parameter `db` has default argument
     --> dashboard/routers/tests.py:219:19
      |
  217 |     run_id: int,
  218 |     request: Request,
  219 |     db: Session = Depends(get_db),
      |                   ^^^^^^^^^^^^^^^
  220 | ) -> Any:
  221 |     project = get_project_or_404(project_id, db)
      |
  help: Remove default argument
  SIM117 Use a single `with` statement with multiple contexts instead of nested `with` statements
     --> tests/integration/daemon/test_baseline_qv_pipeline.py:388:9
      |
  386 |               return MagicMock(stdout="", stderr="", returncode=0)
  387 |
  388 | /         with patch("orch.daemon.batch_manager.subprocess.run", side_effect=subprocess_side_effect):
  389 | |             with patch("orch.daemon.batch_manager.subprocess.Popen") as mock_popen:
      | |___________________________________________________________________________________^
  390 |                   mock_proc = MagicMock()
  391 |                   mock_proc.communicate.return_value = (b"", b"")
      |
  help: Combine `with` statements
  Found 8 errors.
  make: *** [Makefile:20: lint] Error 1
  $ mkdir -p ai-dev/active/I-00053/reports
  (no output)
  ← Write ai-dev/active/I-00053/reports/I-00053_S06_QvGate_report.md
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
