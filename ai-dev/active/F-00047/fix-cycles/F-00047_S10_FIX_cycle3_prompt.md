# F-00047 S10 QV Fix Cycle 3/5

Quality gate S10 for work item F-00047 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Integration tests: 1 failure in test_project_doc_fts_full_text_search - FTS query for 'architecture' returns 2 results (matches title and content) instead of expected 1

**Command output**:
```
...(truncated)...
     .filter(ProjectDoc.content_search.op("@@")(text("plainto_tsquery('english', 'session')")))
            .all()
        )
        assert len(results) == 1
        assert results[0].doc_id == "module-auth"
    
        results = (
            db_session.query(ProjectDoc)
            .filter(ProjectDoc.content_search.op("@@")(text("plainto_tsquery('english', 'API')")))
            .all()
        )
        assert len(results) == 1
        assert results[0].doc_id == "api-users"
    
        results = (
            db_session.query(ProjectDoc)
            .filter(
                ProjectDoc.content_search.op("@@")(text("plainto_tsquery('english', 'architecture')"))
            )
            .all()
        )
>       assert len(results) == 1
E       assert 2 == 1
E        +  where 2 = len([<orch.db.models.ProjectDoc object at 0x7f44b9b71f40>, <orch.db.models.ProjectDoc object at 0x7f44b9b72750>])

tests/integration/test_project_docs.py:496: AssertionError
=============================== warnings summary ===============================
tests/integration/test_code_index_job.py::TestCodeIndexJobFKConstraints::test_code_index_job_fk_invalid_project
tests/integration/test_models.py::test_duplicate_item_id_in_same_project_rejected
tests/integration/test_project_docs.py::test_project_doc_unique_constraint

...2610 bytes truncated...

The tool call succeeded but the output was truncated. Full output saved to: /home/sergiog/.local/share/opencode/tool-output/tool_d965df51c001EB3Ddm2zpOD4Oq
Use the Task tool to have explore agent process this file with Grep and Read (with offset/limit). Do NOT read the full file yourself - delegate to save context.
[0m
**FAIL** - 1 test failed: `test_project_doc_fts_full_text_search`

The test expects FTS search for 'architecture' to return 1 result, but it returns 2 (matches both "Architecture Overview" title and "system architecture microservices diagram" content).
[0m$ [0muv run iw step-fail F-00047 --step S10 --reason "Integration tests: 1 failure in test_project_doc_fts_full_text_search - FTS query for 'architecture' returns 2 results (matches title and content) instead of expected 1"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00047 step S10: Integration tests: 1 failure in test_project_doc_fts_full_text_search - FTS query for 'architecture' returns 2 results (matches title and content) instead of expected 1
[0m
**FAIL**

- **Command**: `uv run pytest tests/integration/ -v --alluredir=allure-results`
- **Result**: 478 passed, **1 failed**
- **Failed test**: `tests/integration/test_project_docs.py::test_project_doc_fts_full_text_search:496`
- **Root cause**: The test searches for 'architecture' expecting 1 result, but FTS finds 2 — the term appears in both the title of "arch-overview" AND the content of "module-auth". The test assertion is too narrow.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
