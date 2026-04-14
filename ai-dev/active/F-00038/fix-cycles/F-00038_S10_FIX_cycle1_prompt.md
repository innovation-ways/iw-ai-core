# F-00038 S10 QV Fix Cycle 1/5

Quality gate S10 for work item F-00038 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Integration test failure: tests/integration/api/test_docs_ide_api.py::test_ide_tab_loads asserts 'Guide Editor' in response but the text is not present in the IDE tab HTML output. F-00041 (IDE tab) appears to be incompletely merged — template missing 'Guide Editor' panel.

**Command output**:
```
...(truncated)...
click Compare.</p>\n  </div>\n</div>\n  </div>\n</div>' = <Response [200 OK]>.text

tests/integration/api/test_docs_ide_api.py:109: AssertionError
=========================== short test summary info ============================
FAILED tests/integration/api/test_docs_ide_api.py::test_ide_tab_loads - asser...
!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!!
1 failed in 3.93s
[0m
[0m→ [0mRead ai-dev/active/F-00038/reports/F-00038_S09_QvGate_report.md
[0m
[0m$ [0mgit log --oneline -10
b93dab4 Merge F-00037: squash-merge from agent/F-00037-doc-type-guides-editable-edito
0a97fd2 fix(merge): resolve conflict in models/doc_service; add F-00037 S01 migrations and report
e057e30 Merge F-00039: squash-merge from agent/F-00039-section-level-guide
818b01e Archive BATCH-00019: remove F-00020, F-00022, F-00021, F-00023
5d655e9 Merge F-00023: squash-merge from agent/F-00023-iw-research-quick-skill
cd50e76 feat(planner): cross-batch file overlap detection + design review file check
0fe37b6 Merge F-00041: squash-merge from agent/F-00041-interactive-document-ide-guide
b2969e8 fix merge
05ca66b Merge F-00021: squash-merge from agent/F-00021-research-dashboard-panel-in-iw
87d965d Merge F-00022: squash-merge from agent/F-00022-iw-research-skill
[0m
[0m→ [0mRead tests/integration/api/test_docs_ide_api.py
[0m✱ [0mGrep "Guide Editor"[90m in dashboard · 0 matches[0m
[0m✱ [0mGrep "Guide Editor"[90m in dashboard · 0 matches[0m
The integration test `test_ide_tab_loads` is failing because the text "Guide Editor" is not found in the response from the IDE tab endpoint. This test was written for F-00041 (IDE tab implementation), which appears to have incomplete template coverage in the current worktree state.
[0m
[0m$ [0muv run iw step-fail F-00038 --step S10 --reason "Integration test failure: tests/integration/api/test_docs_ide_api.py::test_ide_tab_loads asserts 'Guide Editor' in response but the text is not present in the IDE tab HTML output. F-00041 (IDE tab) appears to be incompletely merged — template missing 'Guide Editor' panel."
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00038 step S10: Integration test failure: tests/integration/api/test_docs_ide_api.py::test_ide_tab_loads asserts 'Guide Editor' in response but the text is not present in the IDE tab HTML output. F-00041 (IDE tab) appears to be incompletely merged — template missing 'Guide Editor' panel.
[0m
Step S10 failed due to a pre-existing integration test that is unrelated to F-00038's feature scope (instance guide overlay). The test `test_ide_tab_loads` is checking for a "Guide Editor" panel from F-00041 (the IDE tab feature), but the HTML template doesn't contain that text — indicating F-00041 was not fully merged into this worktree.

The step has been marked as failed with the reason above.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
