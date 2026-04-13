# F-00012_S05_CodeReview_Final_prompt

**Work Item**: F-00012 — Project-Level Documentation System — AI Generation (Phase 2)
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01, S02, S03, S04

---

## Input Files

- `ai-dev/active/F-00012/F-00012_Feature_Design.md` — Design document
- All implementation reports: `ai-dev/work/F-00012/reports/F-00012_S0{1,2,3,4}_*_report.md`
- All files listed in all implementation reports' `files_changed`
- `CLAUDE.md`, `orch/CLAUDE.md`, `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/work/F-00012/reports/F-00012_S05_CodeReview_Final_report.md`

## Context

Final cross-agent review for **F-00012: AI Documentation Generation**. Verify the complete system — daemon poller, CLI commands, SSE stream, frontend — integrates correctly and satisfies all acceptance criteria and invariants from the design document.

## Review Checklist

### 1. Completeness

- [ ] All 6 Acceptance Criteria implemented and tested
- [ ] All 5 Invariants enforced in code
- [ ] All Boundary Behavior rows have tests
- [ ] `DocJobPoller` wired into main daemon poll loop
- [ ] Concurrent job limit (MAX=2) enforced
- [ ] Stall detection (10 min timeout) implemented

### 2. Daemon Integration

- [ ] `DocJobPoller.poll()` called in the correct place in the daemon loop
- [ ] Does not break existing batch polling behavior
- [ ] Uses same session management as existing daemon components
- [ ] Subprocess launch matches executor patterns from `executor/CLAUDE.md`

### 3. CLI Commands

- [ ] `iw doc-job-start`: transitions queued→running, sets pid + skill_used
- [ ] `iw doc-job-done`: transitions running→completed/failed, computes duration
- [ ] Both are idempotent (re-running on completed job is safe)
- [ ] Exit codes match spec (0/1/2)
- [ ] Output is JSON to stdout; errors to stderr

### 4. SSE Stream

- [ ] Follows same pattern as existing `dashboard/routers/sse.py`
- [ ] Cleans up generator on client disconnect (no resource leak)
- [ ] Emits `status`, `completed`, and `failed` events
- [ ] 15-minute timeout with `timeout` event
- [ ] `Cache-Control: no-cache` and `X-Accel-Buffering: no` headers set

### 5. Frontend

- [ ] Generate button is disabled when job already running
- [ ] SSE connection established correctly after Generate click
- [ ] Card refreshes on completion (not just spinner → nothing)
- [ ] Job history shows all 3 statuses with correct colors
- [ ] Error message is shown when job fails

### 6. Security

- [ ] SSE endpoint: is `project_id` validated before streaming? (no unauthorized job status leakage)
- [ ] `iw doc-job-done --error` input: is error string length bounded? (no OOM from huge error payload)
- [ ] Subprocess launch: are arguments properly escaped? (no command injection via doc source_paths or project_id)

### 7. Test Coverage

- [ ] Full job lifecycle (success path) tested end-to-end
- [ ] Full job lifecycle (failure path) tested
- [ ] Concurrent limit tested
- [ ] Stall detection tested
- [ ] SSE stream tested (at least one test that connects and receives an event)

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass
2. `make test-integration` — pass
3. `make quality` — ruff + mypy pass

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "F-00012",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
