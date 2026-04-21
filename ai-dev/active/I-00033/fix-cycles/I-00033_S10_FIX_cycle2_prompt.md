# I-00033 S10 QV Fix Cycle 2/5

Quality gate S10 for work item I-00033 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 4 integration tests in test_code_qa_routes.py failing: SSE token/error events not being emitted from QA endpoint

**Command output**:
```
...(truncated)...
  self._context.run(self._callback, *self._args)

tests/integration/test_code_index_pipeline.py::test_full_index_cycle
tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done
tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00033/orch/rag/indexer.py:148: DeprecationWarning: table_names() is deprecated, use list_tables() instead
    if table_name in db.table_names():

tests/integration/test_code_sse.py::TestCodeSSEStream::test_sse_returns_idle_when_no_running_job
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00033/.venv/lib/python3.12/site-packages/starlette/testclient.py:439: DeprecationWarning: You should not use the 'timeout' argument with the TestClient. See https://github.com/Kludex/starlette/issues/1108 for more information.
    warnings.warn(

tests/integration/test_project_docs.py::test_project_doc_unique_constraint
  /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00033/tests/integration/test_project_docs.py:141: SAWarning: New instance <ProjectDoc at 0x7ee3588d8140> with identity key (<class 'orch.db.models.ProjectDoc'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x7ee35838da30>
    db_session.flush()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_code_qa_routes.py::test_qa_streams_tokens - ass...
FAILED tests/integration/test_code_qa_routes.py::test_qa_streams_error_event_on_ollama_down
FAILED tests/integration/test_code_qa_routes.py::test_qa_empty_conversation_history
FAILED tests/integration/test_code_qa_routes.py::test_post_qa_with_module_name_forwards_to_engine
============ 4 failed, 653 passed, 7 skipped, 22 warnings in 46.00s ============
make: *** [Makefile:39: test-integration] Error 1
[0m
[0m$ [0mmkdir -p ai-dev/active/I-00033/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/I-00033/reports/I-00033_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail I-00033 --step S10 --reason "4 integration tests in test_code_qa_routes.py failing: SSE token/error events not being emitted from QA endpoint"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed I-00033 step S10: 4 integration tests in test_code_qa_routes.py failing: SSE token/error events not being emitted from QA endpoint
[0m
**FAIL** — 4/657 integration tests failed in `test_code_qa_routes.py`. The 4 tests all check SSE token/error event emission from the `/api/projects/{id}/code/qa` endpoint; all 4 show 0 events being received. The remaining 653 tests pass. Report written to `ai-dev/active/I-00033/reports/I-00033_S10_QvGate_report.md` and step marked as failed.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
