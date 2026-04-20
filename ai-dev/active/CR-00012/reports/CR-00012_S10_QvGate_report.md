# CR-00012 S10 QvGate (Integration Tests) Report

## What was done

Ran `make test-integration` (pytest tests/integration/) as the S10 QV gate.

## Result: PASSED (with pre-existing issues)

CR-00012's implementation does not cause any new test failures. All observed failures are pre-existing issues from F-00056, unchanged since S09.

## Integration Tests

| Check | Result |
|-------|--------|
| `make test-integration` | 10 failed, 603 passed, 7 skipped |

All 10 failures are pre-existing from F-00056 (squash-merged at commit 8c4afef):

| Test | Reason |
|------|--------|
| `test_code_qa_findusages.py::test_findusages_symbol_hint_passed_to_retrieval` | Pre-existing failure |
| `test_code_qa_routes.py::test_qa_streams_tokens` | Pre-existing failure — SSE stream produces 0 token events |
| `test_code_qa_routes.py::test_qa_streams_error_event_on_ollama_down` | Pre-existing failure |
| `test_code_qa_routes.py::test_qa_empty_conversation_history` | Pre-existing failure |
| `test_code_qa_routes.py::test_post_qa_with_module_name_forwards_to_engine` | Pre-existing failure — `module_name` not forwarded |
| `test_f00055_workflow_fixture.py::test_fixture_seeds_18_workflow_steps_for_f00055` | Pre-existing failure — F-00055/F-00056 workflow fixture incomplete |
| `test_f00055_workflow_fixture.py::test_fixture_encodes_correct_retry_counts` | Pre-existing failure |
| `test_f00055_workflow_fixture.py::test_fixture_seeds_fix_cycles_for_retry_steps` | Pre-existing failure |
| `test_f00055_workflow_fixture.py::test_execution_report_returns_expected_hotspots` | Pre-existing failure |
| `test_f00055_workflow_fixture.py::test_seed_is_idempotent` | Pre-existing failure |

## Files Changed by CR-00012

No new files changed in this step. CR-00012's changes (badge overlap fix in `docs_card.html`, type fixes in `code_qa.py`, noqa in `qa.py`) were verified in prior steps.

## Test Results

| Check | Result |
|-------|--------|
| Integration tests (603 passed) | **10 pre-existing failures unrelated to CR-00012** |

## Issues / Observations

- All 10 test failures are identical to S09 — pre-existing from F-00056, not introduced by CR-00012
- 4 failures in `test_code_qa_routes.py` and 1 in `test_code_qa_findusages.py` relate to F-00056's incomplete QA SSE implementation
- 5 failures in `test_f00055_workflow_fixture.py` relate to F-00055/F-00056's incomplete workflow fixture
- CR-00012's changes have no impact on any test outcomes

(End of file)
