# I-00114: pi narration-exit escapes step-done contract, burns retry budget

**Type**: Issue
**Severity**: High
**Created**: 2026-05-25
**Reported By**: sergiog (discovered while investigating F-00089 S05 failure)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This Incident does not touch any docker artefacts.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This Incident does NOT add or modify any Alembic migration. `daemon_events.event_type` is a plain TEXT column (no enum), so a new `step_narration_exit` value needs no schema change. The reprompt counter is stored inside `daemon_events.metadata` (JSONB), again no schema change.

## Description

When the Codex `pi` CLI used as the agent runtime (`cli_tool=pi`, model `openai-codex/gpt-5.3-codex`) emits a final assistant turn containing only `[thinking, text]` blocks (no `toolCall`), it treats the turn as complete and exits cleanly. The agent's promise — typically *"I'll now run the tests and call `iw step-done`"* — is never executed. The daemon's `step_monitor` polls 60s later, sees the bash wrapper's PID dead with `StepRun.status==running`, and marks the run `step_crashed`. Each such occurrence consumes one of the implementation step's two retry slots even though the run wasn't a real failure. F-00089 S05 hit this pattern on both of its two retry attempts and stalled, requiring manual intervention.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Critical agent-runtime invariants live in `executor/CLAUDE.md` (no docker / no alembic from executor scripts) and `orch/CLAUDE.md` (daemon ownership of state transitions).

## Steps to Reproduce

1. Approve any implementation work item whose project resolves to `cli_tool=pi`, e.g. iw-ai-core (`default_runtime = "pi"` in `projects.toml`).
2. Daemon picks the item up, launches the step. The first prompt usually triggers a tool call (`iw step-start`), so the agent does not exit immediately.
3. After some tool use, the agent emits a final assistant message of the shape `[thinking, "I'll now run …"]` — no `toolCall` content block.
4. `pi` exits with code 0.
5. The bash wrapper (built by `_build_initial_command` in `orch/daemon/batch_manager.py:2113-2144`) had only `pi -p …` as its body, so the wrapper exits immediately too.
6. Daemon polls on its 60s schedule, observes `pid_alive==False` while `StepRun.status==running`, and emits `step_crashed: Process exited without reporting completion (PID dead)`.
7. `should_retry_step` (`orch/daemon/fix_cycle.py:586-627`) decrements the budget; after 2 such failures (`_DEFAULT_IMPLEMENTATION_MAX_RETRIES = 2` at line 314) the step settles into `failed`.

**Expected**: pi narrating an intent (*"I'll now do X"*) without executing should be detected, the agent should be reprompted to actually execute the next step, and the implementation retry budget should be spent only on genuine failures.

**Actual**: pi exit-on-text is indistinguishable from a real crash. Every implementation step under pi has a one-shot retry penalty for this; steps that hit the pattern twice stall the entire item.

## Root Cause Analysis

The pi launch path bypasses the executor's step-done fallback. Specifically:

1. **Daemon command builder** — `_build_initial_command` (`orch/daemon/batch_manager.py:2135-2144`) returns a bare `pi -p "$(cat <prompt>)" --model <model> --no-context-files --append-system-prompt …`. The corresponding fix-cycle builder `_build_fix_inner_command` in `orch/daemon/fix_cycle.py` mirrors this shape (an explicit `# Keep in sync …` comment at `batch_manager.py:2122-2123` documents the pairing).
2. **No fallback** — opencode and claude branches also lack the fallback, but the `executor/step_executor.sh` wrapper script (lines 281-292) DOES contain one (`iw_step_done` is called on `STEP_OUTCOME=="success"`). That wrapper, however, is reserved for a different launch path and is **not** invoked when the daemon launches `pi`/`claude`/`opencode` directly via `_build_initial_command`. The pi process is launched as the first and only command of the shell that `subprocess.Popen(..., shell=True, start_new_session=True)` spawns at `orch/daemon/batch_manager.py:1593-1602` — when pi exits, the shell exits, the StepRun PID dies.
3. **Crash detection** — `_check_step_health → _handle_crashed` (`orch/daemon/step_monitor.py:228-298`) treats *every* `pid_alive==False AND status==running` as a crash and emits `step_crashed`.
4. **Retry counting** — `should_retry_step` counts StepRun rows; it does not distinguish "real failure" from "agent narrated and exited", so both burn the same retry budget.

Evidence from the F-00089 S05 failure today (timestamps in UTC):

- **run 1** (PID 3503566, started 15:08:10, crash detected 15:10:10 — 120s detection latency = exactly 2× the 60s poll interval). Pi session `2026-05-25T15-08-10-793Z_…5fad…jsonl`, 41 events. Final assistant event at 15:10:07: `[thinking, text]` — *"Implementing S05 now: I'll add the conflict scenario tests, run the required gates/tests, then write the step report and call `step-done`."* No `toolCall`. `step-done` was never invoked.
- **run 2** (PID 3530019, started 15:11:34, crash detected 15:13:34). Pi session `2026-05-25T15-11-34-962Z_…5fb0…jsonl`, 33 events. Final assistant event at 15:13:19: `[thinking, text]` — *"Working on it. I've started S05 and captured the RED failure for `test_main_is_not_half_merged` … I'll now implement the full squash-merge conflict scenario tests, run the required gates/tests, write the step report, and finish with `iw step-done --report`."* No `toolCall`.
- **Contrast — S04 succeeded** (run 15:03:53). Session `…019e5fa9-…jsonl` event 43 contains a real `bash` toolCall: `mkdir -p ai-dev/active/F-00089/reports && uv run iw step-done F-00089 --step S04 --report ai-dev/active/F-00089/reports/F-00089_S04_Backend_report.md`. The step transitioned to `completed` before pi exited.

The systemic frequency is approximately **one narration-exit per implementation step** under pi: every prior step of F-00089 (S01..S04) also exhibited the pattern exactly once (one `step_retry_scheduled` event each) and only succeeded on retry. S05 hit it twice in a row and burned the budget.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/daemon/batch_manager.py` (`_build_initial_command`, pi branch) | Returns a bare `pi -p …` command with no narration-exit guard. |
| `orch/daemon/fix_cycle.py` (`_build_fix_inner_command`, pi branch) | Same shape — must stay in sync with `_build_initial_command`. |
| `orch/daemon/step_monitor.py` (`_handle_crashed`) | Treats narration-exit as a crash, consumes retry budget. |
| `orch/cli/` | No CLI today emits a free-form `daemon_events` row from an external script; the guard needs one. |
| `executor/` | No guard script exists for narration-exit detection on the pi/claude/opencode direct-launch path. |
| `tests/` | No tests cover the narration-exit pattern. |

## Fix Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern. CLI command, guard script, and daemon command-builder live in three different modules, so they are split across three implementation steps.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Add `iw daemon-event` CLI command (`orch/cli/event_commands.py`) to let external scripts insert `daemon_events` rows. | — |
| S02 | Backend | Add `executor/pi_narration_guard.py` — launches pi, detects narration-exit on clean (exit 0) termination, harvests last assistant text from the pi session JSONL, emits `step_narration_exit` via `iw daemon-event`, and reprompts pi with `--continue` (up to 5 times) before exiting with the original code. | — |
| S03 | Backend | Modify `_build_initial_command` and `_build_fix_inner_command` (pi branches only) to invoke the guard wrapper instead of `pi` directly. opencode/claude branches unchanged. | — |
| S04 | Tests | Reproduction + regression tests (see "Test to Reproduce" section). | — |
| S05 | CodeReview_Backend | Review S01+S02+S03. | — |
| S06 | CodeReview_Tests | Review S04. | — |
| S07 | CodeReview_Final | Cross-step global review. | — |
| S08..S13 | QV Gates | lint, format-check, type-check, security-sast, unit-tests, integration-tests. | — |
| S14 | SelfAssess | Self-assessment via `iw-item-analyze` skill (required because `self_assess=true` for iw-ai-core in `projects.toml`). | — |

### Database Changes

- **New tables**: None.
- **Modified tables**: None.
- **Migration notes**: No migration needed. `daemon_events.event_type` is TEXT — the new value `step_narration_exit` is admissible without schema change. The reprompt-attempt counter lives in `daemon_events.metadata` JSONB.

### Code Changes

- **Files to modify**: `orch/cli/__init__.py` (register new command), `orch/daemon/batch_manager.py` (pi branch of `_build_initial_command`), `orch/daemon/fix_cycle.py` (pi branch of `_build_fix_inner_command`).
- **Files to add**: `orch/cli/event_commands.py`, `executor/pi_narration_guard.py`, `tests/unit/test_pi_narration_guard.py`, `tests/integration/test_pi_narration_guard.py`, `tests/unit/test_event_command.py`, `tests/unit/test_daemon_command_builders.py`, `tests/integration/_stub_pi.py`.
- **Nature of change**: Wrap the pi launch in a guard process that distinguishes "narrated and quit" from "real crash", emits telemetry, and reprompts in-place before yielding to the existing crash path.

## File Manifest

All files for this work item live under `ai-dev/active/I-00114/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00114_Issue_Design.md` | Design | This document |
| `I-00114_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00114_S01_Backend_prompt.md` | Prompt | Add `iw daemon-event` CLI |
| `prompts/I-00114_S02_Backend_prompt.md` | Prompt | Add `pi_narration_guard.py` |
| `prompts/I-00114_S03_Backend_prompt.md` | Prompt | Wire guard into daemon command builders |
| `prompts/I-00114_S04_Tests_prompt.md` | Prompt | Reproduction + regression tests |
| `prompts/I-00114_S05_CodeReview_prompt.md` | Prompt | Review backend implementation |
| `prompts/I-00114_S06_CodeReview_prompt.md` | Prompt | Review tests |
| `prompts/I-00114_S07_CodeReview_Final_prompt.md` | Prompt | Global cross-step review |
| `prompts/I-00114_S14_SelfAssess_prompt.md` | Prompt | Self-assessment of the item |

Reports are created during execution in `ai-dev/active/I-00114/reports/`.

## Test to Reproduce

Test-file location — `tests/integration/test_pi_narration_guard.py` (drives real subprocesses and reads real JSONL fixtures — integration territory; no FastAPI client, so neither `tests/unit/` nor `tests/dashboard/` applies). Pure logic helpers (last-assistant-block classifier, reprompt-message builder) live in `tests/unit/test_pi_narration_guard.py`.

```python
def test_I_00114_reproduces_pi_narration_exit_burns_retry_budget(
    chaos_db, tmp_path, monkeypatch
):
    """This test should FAIL before the fix and PASS after.

    Before fix: a fake `pi` that exits 0 immediately, with a synthesised
    session JSONL ending in [thinking, text], triggers _handle_crashed
    and increments the step's retry counter.

    After fix: the guard detects narration-exit, emits a
    step_narration_exit daemon_events row, reprompts up to 5 times, and
    does NOT add a StepRun row that registers as a "real" crash for
    should_retry_step.
    """
    # Arrange — seed a WorkItem + WorkflowStep in `running` status with a
    # fake StepRun whose PID points at our `pi` stub. The pi stub writes a
    # narration-shaped JSONL into the session dir, then exits 0.
    project_id, item_id, step_id = _seed_running_step(chaos_db)
    pi_stub = _install_pi_stub(monkeypatch, tmp_path, scenario="narration_exit")

    # Act — invoke the guard wrapper as the daemon would.
    rc = _run_guard(item_id=item_id, step_id=step_id, pi_bin=pi_stub)

    # Assert (semantic correctness, not shape):
    events = chaos_db.execute(
        text("SELECT event_type, metadata FROM daemon_events "
             "WHERE entity_id=:i ORDER BY created_at"),
        {"i": item_id},
    ).fetchall()
    narration_events = [e for e in events if e.event_type == "step_narration_exit"]
    assert len(narration_events) == 5, (
        f"expected 5 reprompt events, got {len(narration_events)}"
    )
    # The last assistant text must be captured in metadata for diagnosis.
    last_text = narration_events[-1].metadata.get("last_assistant_text", "")
    assert "I'll now" in last_text or "I'll do" in last_text
    # The guard must exit with the original pi code so the daemon's
    # existing crashed-path fires exactly ONCE — not five times.
    assert rc == 0
    # And no extra StepRun rows should have been created by the guard
    # itself (reprompts are in-process; the daemon only counts one launch).
    runs = chaos_db.execute(
        text("SELECT COUNT(*) FROM step_runs WHERE step_id=:s"),
        {"s": _resolve_step_pk(chaos_db, project_id, item_id, step_id)},
    ).scalar()
    assert runs == 1
```

## Acceptance Criteria

### AC1: Narration-exit is classified separately from a real crash

```
Given pi exits with code 0
And the StepRun row is still RunStatus.running (no iw step-done/iw step-fail was called)
And the last assistant message in the pi session JSONL is shape [thinking?, text] with NO toolCall
When the guard wrapper observes the exit
Then it emits a daemon_events row of event_type='step_narration_exit'
And it does NOT exit immediately; instead it reprompts pi with --continue
```

### AC2: Reprompts are capped at 5

```
Given the guard has emitted N narration-exit events for the same StepRun
When N reaches 5
Then the next clean pi exit causes the guard to exit with the original pi code (typically 0)
And the daemon's existing _handle_crashed path fires exactly once, as today
```

### AC3: Successful agent runs are unaffected

```
Given the agent's final assistant turn contains a real toolCall
Or the agent called iw step-done / iw step-fail (StepRun.status != running)
When the guard observes the exit
Then it exits with the original pi code without reprompting and without emitting a narration event
```

### AC4: opencode and claude paths unchanged

```
Given a step's resolved cli_tool is "opencode" or "claude"
When the daemon builds the launch command
Then the command is the bare opencode/claude invocation (no guard wrapper)
```

### AC5: Reproduction test exists

```
Given the fix is applied
When the test suite runs
Then tests/integration/test_pi_narration_guard.py passes
And it would fail when run against pre-fix HEAD (verified at design time)
```

## Regression Prevention

- The guard isolates the failure mode to one wrapper. A future model upgrade (or a different model that doesn't narrate) does not require changes — the guard just becomes a no-op for that model.
- `daemon_events` of type `step_narration_exit` are queryable from the dashboard's Jobs view (already renders unknown event types as a generic row); operators can track the frequency without code changes.
- The unit test for the JSONL classifier pins the recognised "narration-shape" patterns; adding new pi session schema versions will require explicit test updates.

## Dependencies

- **Depends on**: None.
- **Blocks**: None directly. F-00089 (currently in_progress) is benefitting indirectly from this Incident — its S05 was the discovery vector — but F-00089's separate workaround (cherry-pick of e83777b0 + manual `iw step-restart`) does not depend on this fix.

## Impacted Paths

- `orch/cli/event_commands.py`
- `orch/cli/__init__.py`
- `executor/pi_narration_guard.py`
- `orch/daemon/batch_manager.py`
- `orch/daemon/fix_cycle.py`
- `tests/unit/test_pi_narration_guard.py`
- `tests/integration/test_pi_narration_guard.py`
- `tests/unit/test_event_command.py`
- `tests/unit/test_daemon_command_builders.py`
- `tests/integration/_stub_pi.py`

## TDD Approach

- **Reproducing test**: see "Test to Reproduce" above — the integration test asserts five `step_narration_exit` events fire, only one StepRun row is created, and the guard exits with the original pi code.
- **Unit tests** (`tests/unit/test_pi_narration_guard.py`):
  - `test_classify_narration_shape_text_only_returns_True` — `[thinking, text]` JSONL last assistant message is classified as narration.
  - `test_classify_narration_shape_with_toolcall_returns_False` — a final `[thinking, toolCall]` is NOT narration.
  - `test_classify_narration_shape_empty_session_returns_False` — empty/missing JSONL is not narration (guard should yield, not loop).
  - `test_build_reprompt_message_quotes_last_text` — the reprompt message embeds the agent's last text so the reprompt is contextual.
- **Integration tests** (`tests/integration/test_pi_narration_guard.py`):
  - `test_narration_exit_emits_event_and_reprompts` — reproduction test above (AC1, AC2, AC5).
  - `test_clean_exit_with_step_done_does_not_reprompt` (AC3).
  - `test_non_zero_pi_exit_does_not_reprompt` — pi exits with code 1 (real failure) → guard immediately exits with 1, no reprompt.
  - `test_guard_falls_back_after_5_reprompts` (AC2 boundary).
  - `test_opencode_launch_does_not_use_guard` — assert `_build_initial_command("opencode", …)` returns a command that does NOT mention `pi_narration_guard`.

**Assertion-strength rule**: each test asserts against the actual `daemon_events` rows, the actual `step_runs` row count, and the actual guard exit code — never against the injection hook alone.

## Notes

- The reprompt cap of 5 was chosen to match the existing `_DEFAULT_FIX_CYCLE_MAX = 5` ceiling in `orch/daemon/fix_cycle.py` — keeps the operator's mental model consistent.
- Detection uses the DB signal (`StepRun.status == running` AND pi exit==0) as the gate, with JSONL inspection only for telemetry. This makes the guard robust to pi JSONL schema drift: if the JSONL parse fails, telemetry simply records "last_assistant_text=None" — the reprompt loop still works correctly because it is driven by the DB signal alone.
- The fix is scoped to `cli_tool=pi`. opencode and claude have different stop-reason semantics and are out of scope for this Incident. Generalising the guard would be a separate CR if either runtime later exhibits the same pattern.
- `pi --continue` resolves the session by CWD. The guard preserves CWD across reprompts because the daemon's `subprocess.Popen(cwd=worktree_path, ...)` does not change between sub-invocations.
