# I-00116: Daemon marks code-review step as PID-dead when reviewer exits without `iw step-done`, looping the entire downstream review chain unboundedly

**Type**: Issue
**Severity**: High
**Created**: 2026-05-27
**Reported By**: Operator (diagnosed while investigating why I-00112 had been "executing" for ~2.5 hours without progress on 2026-05-27)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt. This incident does not touch docker.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This incident does NOT add or modify any Alembic migration.** All changes are to daemon runtime code, the workflow-prompt template, and tests.

## Description

When a code-review agent completes its work and exits cleanly **without calling `iw step-done`**, the daemon's `step_monitor._check_step_health` marks the run as crashed with `"Process exited without reporting completion (PID dead)"`. A fix cycle is then launched with that phantom finding, finds nothing to fix (`fix_cycle scope: in_scope=0`), and the daemon re-launches the same review step plus all downstream review steps. The loop continues until a destructive fix-agent action breaks something visible (in I-00112's case, a fix agent deleted the design's reproduction tests; another reverted previous-step work). I-00112 burned ~40 review-agent runs in 2.5 hours via this loop while the per-step fix-cycle cap (5) was never reached because each step kept being re-launched fresh after a different step's fix cycle finished.

This is a **sibling** of I-00113 (which added `_probe_for_child` to `step_monitor.py` for the "wrapper PID dead but agent alive" case). I-00113's fix does NOT cover this scenario: here, both the wrapper AND the agent have exited cleanly, but the agent simply forgot to call `iw step-done` before exiting. The daemon currently has no signal that the agent's work actually completed (the report file on disk is the signal; nothing checks for it).

Three compounding sub-bugs make the loop unbreakable:

1. **Primary** — `step_monitor._check_step_health` has no "report-file-exists" guard before declaring crash for `code_review` steps.
2. **Secondary** — re-launched reviewers diff against `git HEAD`, so on the second pass they see un-committed changes from later steps and attribute them to the step they're reviewing (flip-flopping PASS↔FAIL).
3. **Tertiary** — `fix_cycle.py` caps re-runs per step (5) but not cumulatively per work-item, so the downstream review chain can be re-launched indefinitely as long as upstream cycles still have budget.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Relevant points for this incident:

- `orch/daemon/step_monitor.py` is the polling-loop health probe (see `orch/CLAUDE.md`); it is the file I-00113 modified to add `_probe_for_child`.
- `orch/daemon/fix_cycle.py` is the fix-cycle launcher; budget is per-step today.
- `commands/code-review-impl.md` (mastered in `agents/` → synced to projects) is the per-step review prompt the daemon hands to reviewers.
- Append-only `step_runs` and `fix_cycles` tables give us the full audit trail for diagnostics (see `orch/db/models.py`).
- pytest-randomly is on — every new test must be order-independent.

## Steps to Reproduce

1. Approve any work item whose review steps use a reviewer model that doesn't reliably call `iw step-done` on exit (in production, `minimax/MiniMax-M2.7` via option_id=7/8). Any model that can finish in <60 s and exit cleanly works.
2. Wait for a `code_review` step to launch. Tail `logs/daemon.log` — observe the reviewer agent producing a well-formed verdict report file at `ai-dev/active/<ITEM>/reports/<ITEM>_<STEP>_*_report.md` then exiting normally.
3. Within one poll cycle (~60 s) `step_monitor` logs:
   ```
   WARNING orch.daemon.step_monitor: step_run NNNN crashed: Process exited without reporting completion (PID dead)
   ```
4. The orchestrator launches a fix cycle. The fix prompt's "Diagnostic Hypothesis" section reads literally `Process exited without reporting completion (PID dead)`. The fix agent has nothing to act on; the cycle ends with `in_scope=0`.
5. The orchestrator re-runs the failed review step plus every downstream review step in the workflow.
6. The loop repeats.

**Expected**: When a reviewer agent has exited and a well-formed verdict report file (matching `ai-dev/active/<ITEM>/reports/<ITEM>_<STEP>_*_report.md` with mtime > `step_runs.started_at`) is present on disk, the daemon parses the verdict from the report's JSON contract block and treats the run as completed instead of crashed. If the reviewer's `verdict` field is `pass`, advance the step; if `fail`, transition into the normal fix-cycle path. Either way, the spurious "PID dead" loop never starts.

**Actual**: The daemon marks the run as crashed, launches a fix cycle with the bogus finding, fix cycle finds nothing to do, and the entire downstream review chain re-launches. With nothing breaking the loop except per-step cycle budgets (each capped at 5) being exhausted across separate steps, the work item can churn for hours before something visible breaks.

**Observed in production**: I-00112 (BATCH-00130), 2026-05-27 08:46 → 11:21. Cumulative agent launches in that window: S02×11, S04×10, S06×5, S08×6, S09×5 + 11 fix-cycle launches. Two fix agents made destructive changes (S02 fix cycle 1 reverted S03's work; S04 fix cycle 3 deleted the design's six reproduction tests). The operator paused the batch at 11:31 and merged I-00112 manually (`162e86b8`).

## Root Cause Analysis

Three compounding flaws in three distinct files.

### Root cause 1 — `step_monitor._check_step_health` has no report-file-exists guard

`orch/daemon/step_monitor.py:317` `_check_step_health` runs every poll for every alive `StepRun`. The relevant block is:

```python
if not alive:
    # I-00113: probe child processes before declaring crash.
    if _probe_for_child(run.pid):
        run.pid_alive = True
        run.last_heartbeat = now
        ...
        return
    _handle_crashed(db, run, project_id, now, project_config)
    return
```

After I-00113's `_probe_for_child` returns False (no live child), `_handle_crashed` fires unconditionally. There is no inspection of the report file on disk that the reviewer actually produced. For `code_review` step types the verdict report at `ai-dev/active/<ITEM>/reports/<ITEM>_<STEP>_*_report.md` is the authoritative signal that the agent did its work — but the daemon ignores it.

### Root cause 2 — review prompt template scopes the diff to `git diff HEAD` (un-bounded)

`commands/code-review-impl.md` (synced into projects' `commands/` directories at boot) instructs the reviewer to inspect "files changed by this step". The current convention is to use `git diff HEAD` or `git status`. When a reviewer is re-launched after later steps have produced un-committed work in the same worktree, the diff includes files those later steps modified — and the reviewer mis-attributes them.

Evidence: I-00112 S02 produced a `verdict=pass` report on its first run (only saw S01 work) and a `verdict=fail` report on its second run (saw S01 + S03 + S05 + S07 un-committed work, attributed S03's `keep_alive_service.py` changes to S01). The S02 fix cycle 1 then reverted those backend changes — destroying S03's work.

### Root cause 3 — `fix_cycle.py` caps per-step but not per-item

`orch/daemon/fix_cycle.py` enforces a 5-cycle cap per step (configurable via `IW_CORE_FIX_CYCLE_MAX`). But because every fix cycle in the workflow re-launches all downstream review steps, the loop can chew through ~40+ agent runs while no single step approaches its per-step cap. There is no cumulative review-relaunch cap at the work-item level.

### Why existing tests didn't catch this

I-00113's tests verify `_probe_for_child`'s positive path (live agent child found ⇒ keep alive). They do NOT cover the negative path where the agent has exited but a report file exists on disk. The bug class is "we're not checking the artifact the agent actually produced" — by definition outside the existing test boundary.

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| Daemon — step health probe | `orch/daemon/step_monitor.py:317-355` | `_check_step_health` declares review steps crashed without checking the on-disk verdict report |
| Daemon — fix-cycle budget | `orch/daemon/fix_cycle.py` | No cumulative cap per work-item; only per-step (5) |
| Daemon — batch manager | `orch/daemon/batch_manager.py` | Re-launches downstream review chain on every fix-cycle completion (consumer of the cap from S03) |
| Review prompt template (master) | `agents/code-review-impl.md` · `commands/code-review-impl.md` | Tells reviewer to use un-bounded `git diff HEAD`, exposing the flip-flop |
| Workflow skill doc | `skills/iw-workflow/SKILL.md` | Will document the new convention from S05 |
| Tests — coverage gap | `tests/unit/daemon/test_step_monitor_*.py` | No test for "agent exited cleanly + verdict report on disk" |

## Fix Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern (one module or closely-related file group). The three sub-bugs each get their own step so each is independently reviewable.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | `orch/daemon/step_monitor.py` — add `_try_recover_completed_review_step(run)` helper. When `pid_alive=False` AND `_probe_for_child=False` AND `run.step_type in ('code_review', 'code_review_final')`, look for a verdict report at `ai-dev/active/<ITEM>/reports/<ITEM>_<STEP>_*_report.md` with mtime > `run.started_at`. If found, parse the JSON contract block (`verdict`, `findings`, `mandatory_fix_count`), write it to `step_runs` via the same code path `iw step-done` uses, transition the step to `completed` (or `needs_fix` if verdict=fail), and emit a `DaemonEvent` of type `step_run_recovered_from_report`. If not found, fall through to `_handle_crashed` unchanged. Add structured INFO logging of the decision (report path, mtime, agent exit code, verdict). | — |
| S02 | CodeReview_Backend | Per-agent review of S01: report-file glob is anchored at item+step (no cross-contamination); JSON parse is robust to missing fields (returns None → falls through); `_handle_crashed` path is unchanged for non-review steps; pytest-randomly safe; no new external deps. | — |
| S03 | Backend | `orch/daemon/fix_cycle.py` and `orch/daemon/batch_manager.py` — add cumulative per-work-item review-relaunch cap. New env var `IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM` (default 15). Counter increments on every relaunch of a `code_review` or `code_review_final` step caused by a fix-cycle completion of a sibling step (the cascade-reset pattern). When exceeded, the work item is transitioned to `failed` with a `DaemonEvent` of type `review_relaunch_cap_exceeded` carrying the cap, the actual count, and the list of relaunch (step, cycle, timestamp) tuples. | S01 (parallel — different file regions) |
| S04 | CodeReview_Backend | Per-agent review of S03: cap is read from env once at module load with explicit default; counter persists across daemon restarts (i.e. is computed from `step_runs` table, not in-memory); emit-failed path is idempotent; no race with concurrent fix-cycle completions. | — |
| S05 | Backend | Reviewer-prompt diff scoping. Modify the master review prompt at `agents/code-review-impl.md` (and `commands/code-review-impl.md`) so that instead of "diff against HEAD" the reviewer is told: "the files you are responsible for are listed in `scope.allowed_paths` of `ai-dev/active/<ITEM>/workflow-manifest.json` — restrict your review to changes within those globs." Update `skills/iw-workflow/SKILL.md` to document the convention. **Do NOT modify the daemon code in this step.** | — |
| S06 | CodeReview_Backend | Per-agent review of S05: prompt change applies to BOTH master copies; SKILL.md change is congruent; no contradictory phrasing remains; the manifest's `allowed_paths` is the authoritative scope source (matches `worktree_commit.sh`'s Step 2.25 enforcement). | — |
| S07 | Tests | New unit + integration tests covering the three sub-fixes: (a) `tests/unit/daemon/test_step_monitor_i00116_review_recovery.py` — exit-cleanly-with-report → recovered; exit-cleanly-without-report → still crashed; non-review step types → unchanged path. (b) `tests/integration/test_fix_cycle_review_relaunch_cap.py` — exceed-cap transitions item to `failed` with the expected DaemonEvent; under-cap path is unchanged. (c) `tests/unit/test_review_prompt_scope.py` — verifies the master prompt now references `allowed_paths` and does NOT mention `git diff HEAD`. Tests MUST mock at the file-system and DB boundary (not at internal helpers) so the bug-class blind spot can't recur. Targeted verification only — do NOT run `make test-unit` / `make test-integration`. | — |
| S08 | CodeReview_Tests | Per-agent review of S07: semantic assertions (specific verdict values, specific DaemonEvent types, specific cap counts), pytest-randomly compatibility, no production code touched. | — |
| S09 | CodeReview_Final | Cross-layer review of S01/S03/S05/S07. Verify: (a) the report-file guard fires only for `code_review*` step types; (b) the cap is per-item, not per-step; (c) the prompt change is reflected in BOTH master + synced copies (caveat: synced copies are written by `iw sync-agents` at boot, not by S05); (d) no scope creep into unrelated daemon code paths. | — |
| S10 | qv-gate | `make lint` | — |
| S11 | qv-gate | `make format-check` | — |
| S12 | qv-gate | `make type-check` | — |
| S13 | qv-gate | `make arch-check` | — |
| S14 | qv-gate | `make security-sast` | — |
| S15 | qv-gate | `make test-unit` | — |
| S16 | qv-gate | `make allure-integration` | — |
| S17 | self-assess | iw-ai-core has `self_assess=true` in projects.toml | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No Alembic revision is added.

### Code Changes

- `orch/daemon/step_monitor.py` — add `_try_recover_completed_review_step` and wire it into `_check_step_health` before the `_handle_crashed` call for review-type steps.
- `orch/daemon/fix_cycle.py` and/or `orch/daemon/batch_manager.py` — add cumulative review-relaunch cap with new env var; emit `DaemonEvent` and transition item on overflow.
- `agents/code-review-impl.md` + `commands/code-review-impl.md` — replace "diff against HEAD" guidance with "restrict to `allowed_paths` from workflow-manifest.json".
- `skills/iw-workflow/SKILL.md` — document the new diff-scope convention.

## File Manifest

All files for this work item live under `ai-dev/active/I-00116/`:

| File | Type | Purpose |
|------|------|---------|
| `I-00116_Issue_Design.md` | Design | This document |
| `I-00116_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00116_S01_Backend_prompt.md` | Prompt | S01 — report-file recovery guard |
| `prompts/I-00116_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review of S01 |
| `prompts/I-00116_S03_Backend_prompt.md` | Prompt | S03 — cumulative relaunch cap |
| `prompts/I-00116_S04_CodeReview_Backend_prompt.md` | Prompt | S04 review of S03 |
| `prompts/I-00116_S05_Backend_prompt.md` | Prompt | S05 — review prompt scoping |
| `prompts/I-00116_S06_CodeReview_Backend_prompt.md` | Prompt | S06 review of S05 |
| `prompts/I-00116_S07_Tests_prompt.md` | Prompt | S07 — regression tests |
| `prompts/I-00116_S08_CodeReview_Tests_prompt.md` | Prompt | S08 review of S07 |
| `prompts/I-00116_S09_CodeReview_Final_prompt.md` | Prompt | S09 global review |
| `prompts/I-00116_S17_SelfAssess_prompt.md` | Prompt | S17 self-assessment |

Reports are created during execution under `ai-dev/active/I-00116/reports/`.

## Test to Reproduce

Three reproduction tests, one per sub-bug. The first is the canonical I-00116 RED test — it fails against pre-fix code and passes after S01.

```python
# tests/unit/daemon/test_step_monitor_i00116_review_recovery.py
"""I-00116 — Daemon must recover review-step run when verdict report exists on disk.

Pre-fix: when a code-review agent exits cleanly without calling `iw step-done`,
the daemon marks the run as crashed even when a well-formed verdict report file
is present on disk. This test exercises the recovery path that S01 adds.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orch.daemon.step_monitor import _check_step_health


def _make_report(tmp_path: Path, item_id: str, step_id: str, verdict: str = "pass") -> Path:
    """Write a well-formed reviewer report and return its path."""
    reports_dir = tmp_path / "ai-dev" / "active" / item_id / "reports"
    reports_dir.mkdir(parents=True)
    report = reports_dir / f"{item_id}_{step_id}_CodeReview_report.md"
    body = (
        f"# {item_id} {step_id} review\n\n"
        "```json\n"
        + json.dumps({"step": step_id, "verdict": verdict, "findings": [], "mandatory_fix_count": 0})
        + "\n```\n"
    )
    report.write_text(body)
    return report


def test_i00116_review_step_with_report_on_disk_is_recovered_not_crashed(
    tmp_path, monkeypatch
):
    """Reproduction: agent exited cleanly + report on disk → run completed, NOT crashed."""
    monkeypatch.chdir(tmp_path)
    report = _make_report(tmp_path, "I-00999", "S02", verdict="pass")
    # Make report's mtime > started_at
    started_at = datetime.now(UTC) - timedelta(minutes=5)

    db = MagicMock()
    run = MagicMock()
    run.id = 12345
    run.pid = 9999
    run.step_type = "code_review"
    run.work_item_id = "I-00999"
    run.step_id = "S02"
    run.started_at = started_at

    with (
        patch("orch.daemon.step_monitor._is_pid_alive", return_value=False),
        patch("orch.daemon.step_monitor._probe_for_child", return_value=False),
        patch("orch.daemon.step_monitor._handle_crashed") as crashed,
    ):
        _check_step_health(db, run, project_id="iw-ai-core", config=MagicMock())

    assert not crashed.called, (
        "I-00116: review step with a verdict report on disk must NOT be marked crashed."
    )


def test_i00116_review_step_without_report_still_marked_crashed(tmp_path, monkeypatch):
    """Negative path: no report on disk → original _handle_crashed still fires."""
    monkeypatch.chdir(tmp_path)
    db = MagicMock()
    run = MagicMock()
    run.id = 12346
    run.pid = 9998
    run.step_type = "code_review"
    run.work_item_id = "I-00999"
    run.step_id = "S03"
    run.started_at = datetime.now(UTC) - timedelta(minutes=5)

    with (
        patch("orch.daemon.step_monitor._is_pid_alive", return_value=False),
        patch("orch.daemon.step_monitor._probe_for_child", return_value=False),
        patch("orch.daemon.step_monitor._handle_crashed") as crashed,
    ):
        _check_step_health(db, run, project_id="iw-ai-core", config=MagicMock())

    crashed.assert_called_once()


def test_i00116_non_review_step_type_is_unchanged(tmp_path, monkeypatch):
    """Implementation step types follow the original _handle_crashed path."""
    monkeypatch.chdir(tmp_path)
    db = MagicMock()
    run = MagicMock()
    run.id = 12347
    run.pid = 9997
    run.step_type = "implementation"  # NOT code_review
    run.work_item_id = "I-00999"
    run.step_id = "S01"
    run.started_at = datetime.now(UTC) - timedelta(minutes=5)
    # Even if a report file existed, this is not a code-review step.

    with (
        patch("orch.daemon.step_monitor._is_pid_alive", return_value=False),
        patch("orch.daemon.step_monitor._probe_for_child", return_value=False),
        patch("orch.daemon.step_monitor._handle_crashed") as crashed,
    ):
        _check_step_health(db, run, project_id="iw-ai-core", config=MagicMock())

    crashed.assert_called_once()
```

Plus the cap-overflow integration test and the prompt-scope unit test described in the S07 prompt.

## Acceptance Criteria

### AC1: Bug is fixed — review steps with on-disk reports are not crashed

```
Given the daemon's step_monitor polls a code_review step run
When the wrapper PID is dead AND _probe_for_child returns False
 AND a well-formed verdict report exists at ai-dev/active/<ITEM>/reports/<ITEM>_<STEP>_*_report.md
 AND the report's mtime is newer than step_runs.started_at
Then the run is transitioned to completed (or needs_fix if verdict=fail)
 And _handle_crashed is NOT called
 And a DaemonEvent of type 'step_run_recovered_from_report' is recorded
```

### AC2: Review steps without reports still detect real crashes

```
Given the daemon's step_monitor polls a code_review step run
When the wrapper PID is dead AND _probe_for_child returns False
 AND NO verdict report exists on disk (or its mtime is older than started_at)
Then _handle_crashed fires (unchanged from pre-fix behaviour)
```

### AC3: Cumulative review-relaunch cap breaks pathological loops

```
Given the cap IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM is set to N
When N+1 cumulative re-launches of code_review steps happen for a single work item
Then the work item transitions to status='failed'
 And a DaemonEvent of type 'review_relaunch_cap_exceeded' is recorded with the cap and count
 And no further review steps for that item are launched until operator intervention
```

### AC4: Review-prompt diff scope is anchored to allowed_paths

```
Given the master review prompt at agents/code-review-impl.md
When a reviewer is launched against a step
Then the prompt instructs the reviewer to restrict its diff to files matching the step's
     scope.allowed_paths globs from workflow-manifest.json
 And the prompt does NOT instruct the reviewer to use 'git diff HEAD' unbounded
```

### AC5: Regression tests exist for all three sub-fixes

```
Given the fix is applied
When `uv run pytest tests/unit/daemon/test_step_monitor_i00116_review_recovery.py
                   tests/integration/test_fix_cycle_review_relaunch_cap.py
                   tests/unit/test_review_prompt_scope.py -v` runs
Then all tests pass
 And mocking _check_step_health's preconditions reproduces the loop without the S01 guard
 And exceeding the cap demonstrably transitions the item to failed
```

## Regression Prevention

- **Artifact-aware health probe** — `_check_step_health` now consults the artifact the reviewer actually produces (verdict report) instead of relying solely on PID liveness + the agent's compliance with calling `iw step-done`. This closes the "agent forgot the contract" failure mode at the daemon layer.
- **Per-item cumulative cap** — the new `IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM` makes any future loop bug self-terminate within N relaunches instead of running for hours. The cap default (15) is generous enough that legitimate fix cycles don't trip it but tight enough to bound the blast radius of any future loop.
- **Scope-anchored review prompt** — diff scoping by `allowed_paths` aligns the reviewer's perception of "files this step owns" with what `worktree_commit.sh` enforces at merge time, eliminating the flip-flop class of bugs.
- **DaemonEvent telemetry** — both the new recovery path and the cap-exceeded path emit structured events, so future post-mortems can grep the events table for these patterns directly.

## Dependencies

- **Depends on**: None
- **Blocks**: None (but operationally unblocks any item that hits the pattern — see I-00112, I-00113)

## Impacted Paths

- `orch/daemon/step_monitor.py`
- `orch/daemon/fix_cycle.py`
- `orch/daemon/batch_manager.py`
- `agents/code-review-impl.md`
- `commands/code-review-impl.md`
- `skills/iw-workflow/SKILL.md`
- `tests/unit/daemon/test_step_monitor_i00116_review_recovery.py`
- `tests/integration/test_fix_cycle_review_relaunch_cap.py`
- `tests/unit/test_review_prompt_scope.py`

## TDD Approach

- **Reproducing test**: `test_i00116_review_step_with_report_on_disk_is_recovered_not_crashed` (see above) — FAILS against pre-fix code (which calls `_handle_crashed` unconditionally when `_probe_for_child` returns False), PASSES after S01.
- **Unit tests**: all three tests in `test_step_monitor_i00116_review_recovery.py` plus `test_review_prompt_scope.py`.
- **Integration tests**: `test_fix_cycle_review_relaunch_cap.py` exercises the per-item cap with a real DB session.

## Notes

**Why the report-file guard is the right structural fix rather than a wrapper script that auto-calls `iw step-done`.** Adding a wrapper script that calls `iw step-done` on the agent's behalf when the agent forgot would mask the signal that an agent is not following its contract. The structural fix is to make the daemon artifact-aware: the verdict report on disk is the authoritative signal that the agent did the work, so the daemon should consult it. If the verdict is malformed or missing, the daemon falls back to the original crash path — preserving the current safety net.

**Why 15 cumulative relaunches.** With 5 review steps in a typical workflow and a per-step cap of 5 fix cycles, the worst-case relaunch count is `5 (steps) × 5 (per-step cycles)` = 25. A cumulative cap of 15 leaves room for ~3 review steps to exhaust their full budget while still breaking any pathological loop within a few minutes of CPU time. The default is tunable via `IW_CORE_MAX_REVIEW_RELAUNCHES_PER_ITEM`.

**Why this is High and not Critical.** Production daemons recover automatically when the loop pattern is detected by an operator (`iw batch-pause` + manual intervention). The blast radius is bounded by per-step caps eventually exhausting. But the cost in agent runtime, the destructive fix-agent edits the loop encourages, and the operator-time-to-detect (I-00112 ran 2.5h before catch) make this clearly High.
