# I-00053 S10 QV Fix Cycle 2/5

Quality gate S10 for work item I-00053 failed. Fix the issues below so the gate passes on re-run.

## Errors to Fix

**Error**: integration-tests failed: exit=143 — command timed out after 300s (128 tests passed before timeout)

**Command output**:
```
...(truncated)...
SseRowUpdateEvents::test_row_update_event_data_shape PASSED [ 77%]
tests/integration/test_oss_dashboard_sse.py::TestSseRowUpdateEvents::test_stream_emits_complete_event_at_end PASSED [ 77%]
tests/integration/test_oss_dashboard_sse.py::TestSseEmitsStatusProgressCompleteInOrder::test_stream_emits_status_before_complete PASSED [ 77%]
tests/integration/test_oss_dashboard_sse.py::TestSseEmitsStatusProgressCompleteInOrder::test_stream_emits_progress_events_for_stdout_tail PASSED [ 78%]
tests/integration/test_oss_dashboard_sse.py::TestSseReconnectReplaysTail::test_stream_replay_on_reconnect_precedes_live_events PASSED [ 78%]
tests/integration/test_oss_dashboard_sse.py::TestSseReconnectReplaysTail::test_reconnect_replays_before_live_stream PASSED [ 78%]
tests/integration/test_oss_dashboard_sse.py::TestSseHeartbeatEvery20s::test_heartbeat_emitted_at_20s_interval PASSED [ 78%]
tests/integration/test_oss_dashboard_sse.py::TestSseHeartbeatEvery20s::test_heartbeat_comment_format PASSED [ 78%]
tests/integration/test_oss_dashboard_templates_extras.py::TestPillColorParityInvariant::test_pill_color_green_renders_correct_css_class PASSED [ 78%]
tests/integration/test_oss_dashboard_templates_extras.py::TestPillColorParityInvariant::test_pill_color_yellow_renders_correct_css_class PASSED [ 78%]
tests/integration/test_oss_dashboard_templates_extras.py::TestPillColorParityInvariant::test_pill_color_red_renders_correct_css_class PASSED [ 78%]
tests/integration/test_oss_dashboard_templates_extras.py::TestPillColorParityInvariant::test_pill_color_gray_renders_correct_css_class PASSED [ 78%]
tests/integration/test_oss_dashboard_templates_extras.py::TestPillColorParityInvariant::test_stale_pill_has_warning_annotation make: *** [Makefile:54: allure-integration] Error 143


<bash_metadata>
bash tool terminated command after exceeding timeout 300000 ms. If this command is expected to take longer and is not waiting for interactive input, retry with a larger timeout value in milliseconds.
</bash_metadata>
[0m
[0m$ [0mmkdir -p ai-dev/active/I-00053/reports
(no output)
[0m
[0m← [0mWrite ai-dev/active/I-00053/reports/I-00053_S10_QvGate_report.md
Wrote file successfully.
[0m
[0m$ [0muv run iw step-fail I-00053 --step S10 --reason "integration-tests failed: exit=143 — command timed out after 300s (128 tests passed before timeout)"
Failed I-00053 step S10: integration-tests failed: exit=143 — command timed out after 300s (128 tests passed before timeout)
[0m
The integration tests timed out after ~300 seconds. Exit code was 143 (SIGTERM from timeout). The test suite completed 128 tests (78%) before the timeout killed it. No test failures were observed in the output — the run was still progressing when terminated.

```json
{
  "step": "S10",
  "agent": "qv-gate",
  "work_item": "I-00053",
  "gate": "integration-tests",
  "command": "make allure-integration",
  "exit_code": 143,
  "result": "fail",
  "report": "ai-dev/active/I-00053/reports/I-00053_S10_QvGate_report.md"
}
```

```


## Gate Command

The quality gate that failed runs:
```bash
make allure-integration
```

After applying fixes, re-run this command to verify the issues are resolved.

## Constraints

1. **Only fix the reported errors.** Do not refactor unrelated code.
2. **Preserve existing behavior.** Fixes must not break working functionality.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. **Run the gate command after every fix** to verify resolution.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator handles the rest.
