# F-00037 S10 QV Fix Cycle 1/5

Quality gate S10 for work item F-00037 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Timeout after 600s (limit: 600s)

**Command output**:
```
...(truncated)...
pi.py
===================================================================
--- /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00037/tests/integration/api/test_docs_ide_api.py
+++ /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00037/tests/integration/api/test_docs_ide_api.py
@@ -282,9 +282,9 @@
     )
 
     resp = client.get(f"/project/{proj.id}/api/docs/{doc.doc_id}/guide/sections")
     assert resp.status_code == 200
-    assert '<div class="space-y-4">' in resp.text
+    assert '<div class="space-y-3">' in resp.text
 
 
 def test_save_section_guide(client: TestClient, db_session: Session) -> None:
     """POST /guide/sections/{section_name} saves the section guide and the

[0m
[0m$ [0m.venv/bin/pytest tests/integration/ -q --deselect=tests/integration/api/test_docs_ide_api.py::test_ide_tab_loads --deselect=tests/integration/api/test_docs_ide_api.py::test_save_type_guide_empty 2>&1 | tail -15
........................................................................ [ 82%]
........................................................................ [ 99%]
....                                                                     [100%]
=============================== warnings summary ===============================
tests/integration/test_models.py::test_duplicate_item_id_in_same_project_rejected
tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00037/tests/integration/conftest.py:104: SAWarning: transaction already deassociated from connection
    transaction.rollback()

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00037/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x77da3d806d80> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x77da3d8057f0>
    db_session.flush()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
436 passed, 2 deselected, 3 warnings in 17.77s
[0m
[0m$ [0m.venv/bin/pytest tests/integration/ -q --deselect=tests/integration/api/test_docs_ide_api.py::test_ide_tab_loads --deselect=tests/integration/api/test_docs_ide_api.py::test_save_type_guide_empty 2>&1 | tail -5
/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00037/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x72e8b0969730> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x72e8b0346810>
    db_session.flush()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
436 passed, 2 deselected, 3 warnings in 18.18s
[0m
Now let me write the report and complete the step:
[0m$ [0mmkdir -p /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00037/ai-dev/active/F-00037/reports

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
