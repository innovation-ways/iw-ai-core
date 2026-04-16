# F-00047 S10 QV Fix Cycle 1/5

Quality gate S10 for work item F-00047 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: Integration tests timed out after 300 seconds (479 tests collected, test_code_sse.py::TestCodeSSEStream::test_sse_returns_idle_when_no_running_job was in progress)

**Command output**:
```
...(truncated)...
d PASSED [ 24%]
tests/integration/test_cli_steps.py::test_step_fail_stores_reason_in_step_run PASSED [ 24%]
tests/integration/test_cli_steps.py::test_step_fail_rejects_non_in_progress PASSED [ 24%]
tests/integration/test_cli_steps.py::test_full_step_lifecycle_start_done PASSED [ 24%]
tests/integration/test_cli_steps.py::test_full_step_lifecycle_start_fail PASSED [ 24%]
tests/integration/test_code_index_job.py::TestCodeIndexJobDefaults::test_create_code_index_job_defaults PASSED [ 25%]
tests/integration/test_code_index_job.py::TestCodeIndexJobAllFields::test_create_code_index_job_all_fields PASSED [ 25%]
tests/integration/test_code_index_job.py::TestCodeIndexJobStatusTransitions::test_code_index_job_status_transitions PASSED [ 25%]
tests/integration/test_code_index_job.py::TestCodeIndexJobFKConstraints::test_code_index_job_fk_invalid_project PASSED [ 25%]
tests/integration/test_code_index_job.py::TestCodeIndexJobDocIdNull::test_code_index_job_doc_id_null PASSED [ 25%]
tests/integration/test_code_index_job.py::TestCodeIndexJobLanguagesDetected::test_code_index_job_languages_detected_jsonb PASSED [ 26%]
tests/integration/test_code_index_job.py::TestCodeIndexJobErrors::test_code_index_job_errors_jsonb PASSED [ 26%]
tests/integration/test_code_index_pipeline.py::test_full_index_cycle PASSED [ 26%]
tests/integration/test_code_index_pipeline.py::test_start_index_job_raises_when_already_running PASSED [ 26%]
tests/integration/test_code_index_pipeline.py::test_runner_emits_progress_then_done PASSED [ 26%]
tests/integration/test_code_index_pipeline.py::test_regenerate_map_upserts_project_doc PASSED [ 27%]
tests/integration/test_code_index_pipeline.py::test_runner_cleans_up_on_ollama_error PASSED [ 27%]
tests/integration/test_code_sse.py::TestCodeSSEStream::test_sse_returns_idle_when_no_running_job FAILED [ 27%]
tests/integration/test_code_sse.py::TestCodeSSEStream::test_sse_sends_progress_and_done_events 

<bash_metadata>
bash tool terminated command after exceeding timeout 300000 ms
</bash_metadata>
[0m
The test execution timed out after 300 seconds. This is a FAIL condition.
[0m$ [0muv run iw step-fail F-00047 --step S10 --reason "Integration tests timed out after 300 seconds (479 tests collected, test_code_sse.py::TestCodeSSEStream::test_sse_returns_idle_when_no_running_job was in progress)"
warning: `VIRTUAL_ENV=/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.venv` does not match the project environment path `.venv` and will be ignored; use `--active` to target the active environment instead
Failed F-00047 step S10: Integration tests timed out after 300 seconds (479 tests collected, test_code_sse.py::TestCodeSSEStream::test_sse_returns_idle_when_no_running_job was in progress)
[0m
**FAIL** - Integration tests timed out after 300 seconds. 479 tests were collected, and the failure occurred during `test_code_sse.py::TestCodeSSEStream::test_sse_returns_idle_when_no_running_job`. The SSE test likely hangs waiting for an event stream that never connects.

```

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
