# I-00100_S03_Tests_prompt

**Work Item**: I-00100 — Cascade thrashing detector is dead code in the production daemon path
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state. The ONLY allowed docker usage in tests is via `testcontainers` fixtures. Read-only `docker ps` / `docker inspect` are fine. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds an integration test only. Do not run any alembic command outside the testcontainer fixture path.

## Input Files

- `uv run iw item-status I-00100 --json`
- `ai-dev/active/I-00100/I-00100_Issue_Design.md` — read **Test to Reproduce** and **AC1/AC2/AC3** in full
- `ai-dev/active/I-00100/reports/I-00100_S01_Backend_report.md`
- `ai-dev/active/I-00100/reports/I-00100_S02_CodeReview_report.md`
- `orch/daemon/fix_cycle.py` — focus on `check_active_fix_cycles`, `_check_fix_cycle_health`, `_complete_fix_cycle`, `_detect_thrashing`, `_cascade_reset_upstream_qv_gates`, and `_emit_event` for `cascade_thrashing_detected`
- `tests/conftest.py` and `tests/CLAUDE.md` — testcontainer + `db_session` fixture conventions; FTS DDL bootstrap rules; live-DB guard
- `tests/integration/daemon/` — directory layout for existing daemon integration tests; use the same fixtures and helpers if they fit

## Output Files

- New file: `tests/integration/daemon/test_cascade_thrashing_detector_wiring.py`
- `ai-dev/active/I-00100/reports/I-00100_S03_Tests_report.md`

## Context

S01 threaded `project_config` through the daemon's fix-cycle completion path so the existing `_detect_thrashing` function is now reachable from `check_active_fix_cycles`. Your job is to write the regression test that proves it — and would have failed before S01.

The test MUST exercise the **production seam**, not `_complete_fix_cycle` in isolation. Calling `_complete_fix_cycle(..., project_config=cfg)` directly would have passed even before S01's fix (because the keyword default makes the function callable with a config). That would be a worthless test. Drive the seam from the top of the chain.

## Requirements

### 1. The test file

Create `tests/integration/daemon/test_cascade_thrashing_detector_wiring.py`. It must:

- Live under `tests/integration/` so it gets the testcontainer-backed DB (see `tests/CLAUDE.md`'s testcontainers pattern).
- Use the project's existing `db_session` / per-test template-clone fixture (see `tests/conftest.py`).
- NOT call `make test-integration` or `make test-unit` from inside the test body. Targeted execution only.

### 2. The primary test — RED before S01, GREEN after

`def test_thrashing_detector_fires_when_driven_through_check_active_fix_cycles(...)`:

1. Insert a `Project` row with config `{"cascade_thrashing_threshold": 3, "cascade_thrashing_jaccard_min": 0.5, "fix_cycle_max": 10}`. Build a `ProjectConfig` (from `orch.daemon.project_registry`) with the matching thresholds.
2. Insert a `WorkItem` and a workflow of at least two `WorkflowStep` rows: one upstream QV gate (e.g. `step_id="S01"`, `step_type=quality_validation`, `status=completed`) and one downstream `browser_verification` step (e.g. `step_id="S02"`, status `needs_fix`). The downstream step is the "trigger".
3. Insert TWO prior `DaemonEvent` rows with `event_type='cascaded_replay_after_fix'`, `entity_id=item.id`, `entity_type='work_item'`, and metadata `{"trigger_step_id": "S02", "reset_step_ids": ["S01"], "reason": "code_changed_by_fix_cycle"}`. These represent the two historical cascades that already occurred. (Use the table's actual column name — `metadata` in the DB but `event_metadata` on the SQLAlchemy model. See `orch/CLAUDE.md`'s gotcha note.)
4. Insert a `FixCycle` row for the downstream step with `status=FixStatus.in_progress` and `fix_metadata={"pid": <a PID that does not exist>, "log_file": "...", "timeout_secs": 60}`. Pick a PID guaranteed to be dead (e.g. fork a `sleep 0` child, wait for it, then use its old PID; or use `os.getpid() + 1` after a brief sanity check that no such process exists; or monkeypatch `_is_pid_alive` if the codebase exposes it). Document which approach you used in the test docstring.
5. Call the production seam:
   ```python
   from orch.daemon import fix_cycle
   fix_cycle.check_active_fix_cycles(
       db_session,
       project_id=project.id,
       project_config=project_config,
       config=daemon_config,
   )
   ```
6. Assert (SEMANTIC, not shape):
   - Exactly one `DaemonEvent` with `event_type='cascade_thrashing_detected'` exists for `entity_id=item.id`.
   - Its metadata contains `trigger_step_id == "S02"`, `cascade_count >= 3`, and `set(reset_set) == {"S01"}`.
   - The upstream `WorkflowStep` with `step_id="S01"` is **still** `status=completed` (its `started_at` / `completed_at` were NOT cleared — the cascade reset was suppressed).
   - The `FixCycle` row is now `status=FixStatus.completed` (the cycle did complete; only the cascade was suppressed).

### 3. The negative-control test — proves the detector doesn't over-fire

`def test_no_thrashing_event_when_reset_sets_do_not_overlap(...)`:

Same scaffolding as above, but the two prior `cascaded_replay_after_fix` events have `reset_step_ids: ["Sx"]` and `["Sy"]` (disjoint from each other and from the current cascade's set). Drive the seam. Assert:
- Zero `cascade_thrashing_detected` events exist.
- The upstream gate WAS reset (`status=pending`, `started_at=None`, `completed_at=None`) — confirms the normal cascade path is still alive.

This protects AC3 ("no behaviour change for non-thrashing cases").

### 4. CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "cascade_thrashing_detected" in event_types` (shape only — passes if any other event somewhere happens to mention this string)
- GOOD: `assert event.event_type == "cascade_thrashing_detected"` (semantic — specific column, specific value)
- BAD: `assert events` (just checks non-empty)
- GOOD: `assert len(events) == 1 and events[0].event_metadata["cascade_count"] == 3`

Every assertion in your test file MUST be one that would fail if the production code regressed. If deleting a line in `_detect_thrashing` or in S01's plumbing edit would not break a test, that test is too weak. Strengthen it.

### 5. Test isolation

- Each test uses its own clone of the template DB (see `tests/CLAUDE.md`'s pytest-randomly section — `pgtestdbpy`-driven isolation). Do not leak state between tests.
- The two tests must be order-independent: run with `-p randomly --randomly-seed=12345` after writing them and confirm both pass.

### 6. Targeted verification only

Run only your new file:

```bash
uv run pytest tests/integration/daemon/test_cascade_thrashing_detector_wiring.py -v
```

Do NOT call `make test-integration` or `make test-unit` — full-suite execution is the QV gates' job. Duplicating it here will burn the step's budget (see I-00073/S03 post-mortem).

### 7. No manual revert RED-check

The design author already proved RED-first by tracing the production call chain in the design's **Root Cause Analysis** (the seam drops `project_config`, so the line-1139 guard short-circuits → the detector is unreachable). You do NOT need to `git checkout` or `git stash` the S01 hunks to demonstrate RED at runtime. Capture RED reasoning in your `tdd_red_evidence` field as a one-line statement of *why* the test would have failed before S01.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

```bash
make format        # auto-fix; re-stage if it changes anything
make typecheck     # zero errors on your new test file
make lint          # zero errors on your new test file
```

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00100",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/integration/daemon/test_cascade_thrashing_detector_wiring.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "2 passed, 0 failed",
  "tdd_red_evidence": "Pre-S01, check_active_fix_cycles dropped project_config (# noqa: ARG001), so _complete_fix_cycle's line-1139 guard short-circuited and _detect_thrashing was unreachable; the test asserts on a `cascade_thrashing_detected` DaemonEvent that the production seam could not have emitted before S01.",
  "blockers": [],
  "notes": "Document the dead-PID approach you used and any auxiliary helpers."
}
```
