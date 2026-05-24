# F-00089_S05_Backend_prompt

**Work Item**: F-00089 -- Daemon chaos / fault-injection test layer
**Step**: S05
**Agent**: Backend

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures only. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations added or applied. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status F-00089 --json` — runtime step state.
- `ai-dev/work/F-00089/F-00089_Feature_Design.md` — Design document (AC5, Invariant 7, Boundary Behavior "Squash-merge conflict but main is empty").
- `ai-dev/work/F-00089/reports/F-00089_S01_Backend_report.md` — Harness API (`inject_squash_merge_conflict_on_main()`).
- `tests/integration/daemon_chaos/harness.py` + `conftest.py`.
- `orch/daemon/merge_queue.py` and `orch/daemon/auto_merge.py` — the squash-merge code paths.
- F-00084 design doc (if present at `ai-dev/active/F-00084/` or `ai-dev/archive/F-00084/`) — auto-merge-resolution hooks. Your test must work whether F-00084 has merged or not.

## Output Files

- `ai-dev/work/F-00089/reports/F-00089_S05_Backend_report.md` — Step report.

## Context

You are implementing **S05: Scenario 4 — squash-merge conflict**. The harness writes a conflicting commit to the testcontainer's simulated `main` branch immediately before the daemon attempts squash-merge. Your tests assert the merge fails cleanly and `main` is not left half-merged.

**Test-only scope.** Do NOT modify production code anywhere. This step's tests are expected to run for slightly longer than S02–S04 (1800s timeout) because they exercise real git operations inside the testcontainer.

## Requirements

### 1. Create `tests/integration/daemon_chaos/test_squash_merge_conflict.py`

Tests required:

- `test_squash_merge_conflict_returns_recognised_error` — arm injection; advance daemon to merge attempt; assert the merge fails with a recognised git-merge-conflict error (caught exception, logged with the file/line of the conflict).
- `test_item_status_after_merge_conflict` — assert WorkItem.status is `merge_failed` (or routes to F-00084's auto-merge hook if those are present on `main` — detect dynamically by importing the auto-merge module and checking for its hook function).
- `test_main_is_not_half_merged` — after the conflict, assert `git status main` reports a clean tree: no `MERGE_HEAD`, no `ORIG_HEAD` leftovers, no uncommitted changes. Run `git status --porcelain` and assert empty output.
- `test_conflicting_upstream_commit_is_head_of_main` — assert the conflicting commit (the one the harness wrote) is the latest commit on `main` (its SHA matches `git rev-parse main`).
- `test_squash_merge_conflict_empty_main_boundary` — boundary-behavior row: repo with no `main` commits. The test must `xfail`-pin with `strict=True` and a recorded reason ("environmental precondition not met — main has no commits"); do not assert anything else.

### 2. F-00084 graceful dual-path

The test for `test_item_status_after_merge_conflict` must pass whether F-00084 is merged or not. Pattern:

```python
try:
    from orch.daemon import auto_merge_resolution  # F-00084 module name; adjust if different
    has_f00084 = True
except ImportError:
    has_f00084 = False

if has_f00084:
    # Assert routes to auto-merge hook
    ...
else:
    # Assert status is merge_failed (or whichever status the daemon currently sets)
    ...
```

Verify the actual F-00084 module name by checking `ai-dev/active/F-00084/` or the daemon package — don't guess.

### 3. Assertion strength

Every test must assert against either a daemon-mutated DB row, the actual git state of `main`, or a daemon-emitted event row. No assertion-only-against-injection-hook tests.

### 4. Determinism

The harness's hook + the testcontainer's git operations are the only control flow. No real network, no real wall-clock dependencies.

### 5. Follow project conventions

Read `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md`.

## TDD Requirement

Red-Green-Refactor:

1. **RED**: Write `test_main_is_not_half_merged` first (it's the strongest invariant). Run it. Confirm it fails for the right reason (`AssertionError` — `git status --porcelain` is not empty, OR there's no conflict yet because the injection isn't armed). Capture the failing line.
2. **GREEN**: Arm injection correctly; advance daemon to merge attempt.
3. **REFACTOR**: Add remaining tests.

Record the captured RED failure line in `tdd_red_evidence`.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint` — all must pass.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/daemon_chaos/test_squash_merge_conflict.py -v
```

Only this file. If you uncover a daemon bug, `xfail`-pin (`strict=True`), file an Incident, note in `notes`.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "Backend",
  "work_item": "F-00089",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/integration/daemon_chaos/test_squash_merge_conflict.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "5 passed, 0 failed (1 xfail)",
  "tdd_red_evidence": "tests/integration/daemon_chaos/test_squash_merge_conflict.py::test_main_is_not_half_merged — AssertionError: <captured RED line>",
  "blockers": [],
  "notes": "Document whether F-00084 was present at execution and which dual-path branch was exercised."
}
```
