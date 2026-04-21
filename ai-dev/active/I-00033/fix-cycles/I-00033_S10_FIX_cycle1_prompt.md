# I-00033 S10 QV Fix Cycle 1/5

Quality gate S10 for work item I-00033 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: 12 integration tests failed out of 657. See report for details.

**Command output**:
```
...(truncated)...
'>, ('test-proj:module-auth',), None) conflicts with persistent instance <ProjectDoc at 0x715f44a881a0>
    db_session.flush()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ============================
FAILED tests/integration/test_code_qa_findusages.py::test_findusages_symbol_hint_passed_to_retrieval
FAILED tests/integration/test_code_qa_routes.py::test_qa_streams_tokens - ass...
FAILED tests/integration/test_code_qa_routes.py::test_qa_streams_error_event_on_ollama_down
FAILED tests/integration/test_code_qa_routes.py::test_qa_empty_conversation_history
FAILED tests/integration/test_code_qa_routes.py::test_post_qa_with_module_name_forwards_to_engine
FAILED tests/integration/test_dashboard_pages.py::test_recent_activity_unknown_entity_type_falls_back_to_item_route
FAILED tests/integration/test_f00055_workflow_fixture.py::test_fixture_seeds_18_workflow_steps_for_f00055
FAILED tests/integration/test_f00055_workflow_fixture.py::test_fixture_encodes_correct_retry_counts
FAILED tests/integration/test_f00055_workflow_fixture.py::test_fixture_seeds_fix_cycles_for_retry_steps
FAILED tests/integration/test_f00055_workflow_fixture.py::test_execution_report_returns_expected_hotspots
FAILED tests/integration/test_f00055_workflow_fixture.py::test_seed_is_idempotent
FAILED tests/integration/test_module_gen_integration.py::TestModuleGeneratorIntegration::test_get_or_generate_creates_project_doc
=========== 12 failed, 645 passed, 7 skipped, 22 warnings in 47.66s ============
make: *** [Makefile:39: test-integration] Error 1
[0m
FAIL - 12 failed, 645 passed, 7 skipped

Key failures:
- `test_f00055_workflow_fixture` tests (5 failures): fixture not seeding workflow steps for F-00055
- `test_module_gen_integration`: doc_type assertion wrong (`code_components` vs `research`)
- `test_code_qa_*`: symbol_hint not being forwarded, SSE token events not streaming
- `test_dashboard_pages`: unknown entity type fallback route assertion
[0m← [0mWrite ai-dev/active/I-00033/reports/I-00033_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail I-00033 --step S10 --reason "12 integration tests failed out of 657. See report for details."
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed I-00033 step S10: 12 integration tests failed out of 657. See report for details.
[0m
**FAIL** — 12 of 657 integration tests failed.

Key failures:
- `test_f00055_workflow_fixture` (5 tests): e2e_seed fixture seeds 0 workflow steps for F-00055
- `test_code_qa_routes` (4 tests): SSE token streaming broken at route handler level
- `test_module_gen_integration`: DocType assertion wrong type
- `test_dashboard_pages`: unknown entity type fallback link missing

Report written to `ai-dev/active/I-00033/reports/I-00033_S10_QvGate_report.md`.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
