# F-00089_S02_Backend_prompt

**Work Item**: F-00089 -- Daemon chaos / fault-injection test layer
**Step**: S02
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures only. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`. STOP and raise a blocker if your task seems to require a prohibited Docker command.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations added or applied in this step. Allowed: alembic inside testcontainer fixtures, `alembic history/current/show`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status F-00089 --json` — runtime step state (canonical).
- `ai-dev/work/F-00089/F-00089_Feature_Design.md` — Design document (read AC2, Boundary Behavior rows 3 + 4, Invariant 1).
- `ai-dev/work/F-00089/reports/F-00089_S01_Backend_report.md` — S01 report; read in full to learn the harness API (hook names, fixture lifecycle).
- `tests/integration/daemon_chaos/harness.py` and `conftest.py` — harness implementation from S01.

## Output Files

- `ai-dev/work/F-00089/reports/F-00089_S02_Backend_report.md` — Step report.

## Context

You are implementing **S02: Scenario 1 — worktree-setup mid-failure**. The harness from S01 is your foundation. Use the `inject_worktree_setup_failure_after_clone()` hook (and its `stage=` argument for the "fail before git worktree add" boundary case).

**Test-only scope.** Do NOT modify any production code under `orch/`, `dashboard/`, `executor/`, or anywhere else outside `tests/integration/daemon_chaos/**`.

## Requirements

### 1. Create `tests/integration/daemon_chaos/test_worktree_setup_mid_failure.py`

Implement at least the following tests (one assertion per row of AC2 / Boundary Behavior):

- `test_worktree_setup_uv_sync_failure_marks_item_terminal_error` — injection fires after `git worktree add` succeeds; assert WorkItem.status is a terminal-error state with non-null `failure_reason`.
- `test_worktree_setup_failure_does_not_leave_zombie_directory` — same injection; assert the worktree directory either does not exist or contains only a `setup_failed.flag` marker (no checked-out source tree).
- `test_worktree_setup_failure_does_not_poison_batch` — batch with three items A, B, C; arm injection on item A only; advance daemon through several poll cycles; assert items B and C remain pickable and one of them gets picked successfully (or at least gets a worktree-setup attempt).
- `test_worktree_setup_failure_before_git_worktree_add` — boundary-behavior row: arm with `stage="before_git_worktree_add"`; assert item failed, worktree directory was never created (no cleanup needed), batch siblings still pickable.

### 2. Assertion strength

Every test must include at least one **positive assertion against a daemon-mutated DB row or daemon-emitted log line** — not just "the injection hook was called". Examples:

- `assert work_item.status == WorkItemStatus.FAILED` (or whichever terminal-error status the daemon actually sets).
- `assert work_item.failure_reason is not None and "uv sync" in work_item.failure_reason`.
- `assert daemon_events.filter(event_type="worktree_setup_failed").count() == 1`.

Never assert only "the hook fired". Assert what the **daemon** did about it.

### 3. Determinism

No `time.sleep` > 5s, no `random.*`, no wall-clock dependencies, no `os.kill`. All control through the harness's deterministic hooks.

### 4. Follow project conventions

Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md`. Strong-assertion rules apply.

## TDD Requirement

Red-Green-Refactor:

1. **RED**: Write the first test (`test_worktree_setup_uv_sync_failure_marks_item_terminal_error`). Run it (`uv run pytest tests/integration/daemon_chaos/test_worktree_setup_mid_failure.py::test_worktree_setup_uv_sync_failure_marks_item_terminal_error -v`). Confirm it fails for the **right reason** (the daemon, not yet exercised by the injection, leaves the item in a non-terminal state — `AssertionError`, not `ImportError`/collection error). Capture the failing line.
2. **GREEN**: Refine the test + arm the injection correctly until it passes.
3. **REFACTOR**: Extract shared setup into helpers; add the remaining three tests using those helpers.

Record the captured RED failure line in `tdd_red_evidence`.

If your RED test passes immediately without the injection (i.e. the daemon already exhibits the asserted behaviour for unrelated reasons), that means the test is not testing what you think — diagnose and fix the test before proceeding.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — auto-fix and re-stage if needed.
2. `make typecheck` — zero errors in your touched files.
3. `make lint` — zero errors.

## Test Verification (NON-NEGOTIABLE)

Run only this step's test file:

```bash
uv run pytest tests/integration/daemon_chaos/test_worktree_setup_mid_failure.py -v
```

Do NOT run the full integration or unit suite. Do NOT report `tests_passed: true` unless your targeted tests pass.

If a scenario surfaces a genuine daemon bug, **do not "fix" the daemon** — `xfail`-pin the test (with `strict=True`), record the reason, file an Incident with `iw new incident`, and reference the Incident ID in the `xfail` reason. Note this in your step report's `notes`.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "Backend",
  "work_item": "F-00089",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/integration/daemon_chaos/test_worktree_setup_mid_failure.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "4 passed, 0 failed",
  "tdd_red_evidence": "tests/integration/daemon_chaos/test_worktree_setup_mid_failure.py::test_worktree_setup_uv_sync_failure_marks_item_terminal_error — AssertionError: <captured RED line>",
  "blockers": [],
  "notes": "Note any daemon bugs surfaced + xfail-pin / Incident IDs filed."
}
```
