# I-00114_S04_Tests_prompt

**Work Item**: I-00114 -- pi narration-exit escapes step-done contract, burns retry budget
**Step**: S04
**Agent**: Tests

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures only. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00114 --json` — runtime step state.
- `ai-dev/active/I-00114/I-00114_Issue_Design.md` — design, esp. "Test to Reproduce" and "TDD Approach" sections.
- `ai-dev/active/I-00114/reports/I-00114_S0{1,2,3}_*_report.md` — confirms what S01/S02/S03 actually built (helper names, flag names, file paths).
- `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` — testing standards, assertion-strength rules, the live-DB write guard, cross-project isolation.
- `tests/conftest.py` and any `tests/integration/conftest.py` — fixture inventory (db_session, monkeypatch, tmp_path patterns).
- `tests/integration/daemon_chaos/conftest.py` (recent, F-00089) — closest prior art for "simulate a daemon-like scenario with a controlled subprocess".
- Existing pi session JSONLs at `/home/sergiog/.pi/agent/sessions/--*-iw-ai-core-.worktrees-F-00089--/2026-05-25T15-{08,11}-*.jsonl` — read these (READ ONLY) to copy real-world JSONL shapes into your test fixtures.

## Output Files

- `ai-dev/active/I-00114/reports/I-00114_S04_Tests_report.md` — Step report.

## Context

You are implementing **S04: the full test suite for the narration-exit guard.** S02 added one anchoring unit test. Your job is to round it out into a complete suite that proves the guard does what AC1..AC5 say it does — and to write a reproduction integration test that would fail against pre-fix HEAD.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

In our case, that means:

- BAD: `assert len(narration_events) > 0` (just shape)
- GOOD: `assert len(narration_events) == 5` (exact value)
- GOOD: `assert narration_events[-1].metadata["reprompt_attempt"] == 5` (specific value)
- GOOD: `assert "I'll now" in narration_events[0].metadata["last_assistant_text"]` (specific captured text)
- GOOD: `assert "narration_guard" not in built_command` for the opencode regression test (specific absence)

## Requirements

### 1. Unit tests in `tests/unit/test_pi_narration_guard.py`

(S02 created this file with one test; you are extending it.) Add:

- `test_classify_narration_shape_text_only_returns_NARRATION` (already exists from S02 — verify and keep).
- `test_classify_narration_shape_with_toolcall_returns_TOOL_CALL` — fixture with a `[thinking, toolCall]` final assistant message.
- `test_classify_with_text_and_toolcall_returns_TOOL_CALL` — `[thinking, text, toolCall]`. Presence of any `toolCall` wins.
- `test_classify_empty_session_returns_NO_ASSISTANT` — JSONL with only the session/model_change events, no `message` events with role=assistant.
- `test_classify_missing_file_returns_PARSE_ERROR` — pass a non-existent path.
- `test_classify_malformed_jsonl_returns_PARSE_ERROR` — file with a bad JSON line.
- `test_find_latest_pi_session_picks_most_recent` — populate a tmp session dir with multiple JSONLs of different mtimes; assert the newest is returned.
- `test_find_latest_pi_session_returns_None_for_empty_dir`.
- `test_build_reprompt_message_includes_last_text_truncated` — assert the message contains a quoted snippet of last_text capped at 300 chars (or whatever cap S02 chose; read S02's report).
- `test_build_reprompt_message_handles_None_last_text` — works when JSONL parse failed.

Test-file location: `tests/unit/` per `tests/CLAUDE.md` (pure-Python helpers, no DB).

### 2. Integration tests in `tests/integration/test_pi_narration_guard.py`

Five tests total, all driving the guard via `subprocess.run(["python", "executor/pi_narration_guard.py", ...])` with a **stub pi binary** that you place under `tmp_path` and prepend to `PATH` via monkeypatch. Stub pi behaviours per test:

- `test_narration_exit_emits_event_and_reprompts` (AC1, AC2, AC5 — this is the reproduction test). Stub pi writes a synthesised `[thinking, text]` JSONL into the session dir and exits 0. The guard must:
  - Emit exactly **5** `step_narration_exit` daemon_events rows.
  - Each row's `metadata.reprompt_attempt` increases 1→5.
  - Each row's `metadata.max_reprompts == 5`.
  - The first event's `metadata.last_assistant_text` contains a recognisable snippet from the stub's JSONL (semantic check, not shape).
  - The guard's exit code matches the stub's last exit code (0).
  - **Only one row** in `step_runs` exists for this step (reprompts are in-process; the daemon's launch counter is not incremented).
- `test_clean_exit_with_step_done_does_not_reprompt` (AC3). Seed the step in `StepStatus.completed` (or simulate the agent calling `iw step-done` between launches by transitioning the step via the iw CLI inside the stub). Stub pi exits 0. The guard must:
  - Exit 0 immediately after pi.
  - Emit **zero** `step_narration_exit` events.
- `test_non_zero_pi_exit_does_not_reprompt`. Stub pi exits 42. The guard must:
  - Exit 42 immediately.
  - Emit zero `step_narration_exit` events.
- `test_guard_falls_back_after_5_reprompts` (AC2 boundary). Same as the reproduction test but assert that after attempt 5, the guard exits without spawning a 6th pi invocation. Verify by counting stub-pi invocation marker files.
- `test_opencode_launch_does_not_use_guard` (AC4). Call `_build_initial_command("opencode", ...)` and `_build_initial_command("claude", ...)`. Assert the returned strings do NOT contain `pi_narration_guard` and DO start with `opencode run` / `claude -p` respectively.

### 3. Stub-pi pattern

Write a tiny Python script (`tests/integration/_stub_pi.py` or inline as a `tmp_path` fixture) that the guard will invoke as if it were pi. Configure it per-test via env vars (e.g., `STUB_PI_EXIT_CODE`, `STUB_PI_WRITE_SESSION=1`, `STUB_PI_SESSION_KIND=narration|toolcall|completed`). Make it deterministic and bounded (no real network, no sleep > 0.1s).

### 4. Assertion strength

Every assertion must hit one of:
- A real `daemon_events` row (DB).
- A real `step_runs` row count (DB).
- The guard's actual exit code (subprocess.returncode).
- The actual content of a real session JSONL the stub wrote.

No mocking of `iw daemon-event`. The full DB chain must work end-to-end.

### 5. Determinism

The reprompt loop must terminate in bounded time (< 30s wall clock per integration test). The stub pi must not delay; the guard's `subprocess.run` calls must time out at e.g. 10s with a clear test error if pi hangs.

### 6. Cross-project isolation

Use the testcontainer's per-test schema or the same `chaos_db`-style pattern F-00089 used (per `tests/CLAUDE.md`). Never connect to the live DB on port 5433.

## TDD Requirement

For each new test:

1. **RED (design-time)**: the bug was already proven to exist before this work item was approved (see the Root Cause Analysis section of the design doc, which quotes the actual pi session JSONLs from F-00089 S05). Treat that as the pre-fix RED evidence — do NOT `git stash`, `git checkout`, or otherwise revert any S01/S02/S03 source files at runtime to re-create the failure. The harness owns "before/after" comparisons; your job is just to write tests that pass against the post-fix tree.
2. **GREEN**: write each test against the current (S01+S02+S03) implementation and confirm it passes. Make sure each assertion is specific enough that it would have failed against pre-fix HEAD (e.g. asserting `len(narration_events) == 5` would have produced `0` against pre-fix HEAD because the module didn't exist).

Record in `tdd_red_evidence` the design-time evidence anchor (e.g. *"pre-fix RED evidence is the two F-00089 S05 pi sessions quoted in I-00114 Root Cause Analysis; the `test_narration_exit_emits_event_and_reprompts` assertion `len(narration_events) == 5` would have observed `0` against pre-S02 HEAD because `executor/pi_narration_guard.py` did not exist"*) — quote the design doc, do not re-run the failure.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint` on the new test files.

## Test Verification (NON-NEGOTIABLE)

Run ONLY the new test files:

```bash
uv run pytest tests/unit/test_pi_narration_guard.py tests/integration/test_pi_narration_guard.py -v
```

Do NOT run `make test-integration` here — the QV gate downstream owns that.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "Tests",
  "work_item": "I-00114",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_pi_narration_guard.py",
    "tests/integration/test_pi_narration_guard.py",
    "tests/integration/_stub_pi.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "N passed, 0 failed",
  "tdd_red_evidence": "Design-time RED anchor: I-00114 Root Cause Analysis quotes F-00089 S05 pi sessions 2026-05-25T15-08-10-…jsonl and 2026-05-25T15-11-34-…jsonl (both [thinking,text] with no toolCall, both consumed a retry slot). Test `test_narration_exit_emits_event_and_reprompts` would observe `len(narration_events) == 0` against pre-S02 HEAD because executor/pi_narration_guard.py did not exist.",
  "blockers": [],
  "notes": "Document any flaky-timing risk in the stub-pi pattern and the exact subprocess.run timeout chosen."
}
```
