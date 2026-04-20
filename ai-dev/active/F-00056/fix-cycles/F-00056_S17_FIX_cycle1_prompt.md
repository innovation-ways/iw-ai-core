# F-00056 S17 QV Fix Cycle 1/5

Quality gate S17 for work item F-00056 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 5 integration tests failed in code QA routes and findusages

**Command output**:
```
...(truncated)...
ss_then_done
tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00056/orch/rag/indexer.py:148: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in db.table_names():

tests/integration/test_code_sse.py::TestCodeSSEStream::test_sse_returns_idle_when_no_running_job
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00056/.venv/lib/python3.12/site-packages/starlette/testclient.py:439: DeprecationWarning: You should not use the 'timeout' argument with the TestClient. See https://github.com/Kludex/starlette/issues/1108 for more information.
    warnings.warn(

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00056/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x7c772a884980> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x7c77ad17c920>
    db_session.flush()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_code_qa_findusages.py::test_findusages_symbol_hint_passed_to_retrieval
FAILED tests/integration/test_code_qa_routes.py::test_qa_streams_tokens - ass...
FAILED tests/integration/test_code_qa_routes.py::test_qa_streams_error_event_on_ollama_down
FAILED tests/integration/test_code_qa_routes.py::test_qa_empty_conversation_history
FAILED tests/integration/test_code_qa_routes.py::test_post_qa_with_module_name_forwards_to_engine
============ 5 failed, 598 passed, 7 skipped, 21 warnings in 43.28s ============
make: *** [Makefile:39: test-integration] Error 1
[0m
The tests ran with **5 failures** out of 610 tests (598 passed, 7 skipped). Exit code was 1.
[0m$ [0mmkdir -p ai-dev/active/F-00056/reports
[0m
[0m← [0mWrite ai-dev/active/F-00056/reports/F-00056_S17_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail F-00056 --step S17 --reason "5 integration tests failed in code QA routes and findusages"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00056 step S17: 5 integration tests failed in code QA routes and findusages
[0m
**FAIL**

Exit code: 1 — 5 tests failed, 598 passed, 7 skipped.

Failed tests are all in code QA / RAG pipeline:
- `test_findusages_symbol_hint_passed_to_retrieval` 
- `test_qa_streams_tokens`
- `test_qa_streams_error_event_on_ollama_down`
- `test_qa_empty_conversation_history`
- `test_post_qa_with_module_name_forwards_to_engine`

Report written to `ai-dev/active/F-00056/reports/F-00056_S17_QvGate_report.md` and step marked as failed via `iw step-fail`.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
