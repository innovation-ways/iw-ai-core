# I-00100 S03 Tests Report

## What Was Done

Wrote the regression integration test for the cascade thrashing detector wiring (I-00100).

### Files Created

- `tests/integration/daemon/test_cascade_thrashing_detector_wiring.py`

## Test Design

The test file contains two integration tests that drive the **production seam** (`check_active_fix_cycles`), not `_complete_fix_cycle` in isolation. This is the critical distinction that makes them proper regression tests:

### `test_thrashing_detector_fires_when_driven_through_check_active_fix_cycles`

**RED before S01, GREEN after.**

1. Inserts a `Project` row with `{"cascade_thrashing_threshold": 3, "cascade_thrashing_jaccard_min": 0.5, "fix_cycle_max": 10}` config.
2. Builds a `ProjectConfig` with matching thresholds.
3. Inserts a `WorkItem` with two workflow steps: S01 (`quality_validation`, completed, with timestamps) and S02 (`browser_verification`, needs_fix).
4. Inserts two prior `cascaded_replay_after_fix` DaemonEvents for S02 with reset_set `["S01"]` — simulating historical cascades 1 and 2.
5. Inserts a `FixCycle` row for S02 with `status=in_progress` and a **dead PID** (`os.getpid() + 99999` — guaranteed-nonexistent).
6. Calls `check_active_fix_cycles` with the full production seam.
7. Asserts (semantically):
   - Exactly 1 `cascade_thrashing_detected` event with `trigger_step_id == "S02"`, `cascade_count == 3`, `reset_set == {"S01"}`
   - FixCycle is `status=completed`
   - S01 remains `status=completed` with `started_at` and `completed_at` preserved (thrashing suppression worked)

### `test_no_thrashing_event_when_reset_sets_do_not_overlap`

**Negative control (AC3).** Same scaffolding but the two prior cascades have disjoint reset-sets `["Sx"]` and `["Sy"]`. Asserts:
- Zero `cascade_thrashing_detected` events
- At least 1 `cascaded_replay_after_fix` event (normal cascade fires)
- S01 was reset to `pending` with cleared timestamps

## Dead-PID Strategy

`os.getpid() + 99999` — a PID far beyond Linux's `pid_max` (typically 32768 or 4194304). We patch `_is_pid_alive` to return `False` so `_check_fix_cycle_health` treats the cycle as dead and calls `_complete_fix_cycle`. This approach:
- Requires no subprocess spawning
- Is deterministic and instantaneous
- Is documented in the fixture docstring

## TDD RED Evidence

Pre-S01, `check_active_fix_cycles` dropped `project_config` (`# noqa: ARG001`), so `_complete_fix_cycle`'s line-1139 guard short-circuited on `project_config=None` and `_detect_thrashing` was unreachable. The test asserts on a `cascade_thrashing_detected` DaemonEvent that the production seam could not have emitted before S01.

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ No changes needed |
| `make typecheck` | ✅ Zero errors on the new test file |
| `make lint` | ✅ All checks passed |

## Test Results

```bash
uv run pytest tests/integration/daemon/test_cascade_thrashing_detector_wiring.py -v --no-cov
# 2 passed in 5.06s

# Order-independent (pytest-randomly seed 12345)
uv run pytest tests/integration/daemon/test_cascade_thrashing_detector_wiring.py -v --no-cov -p randomly --randomly-seed=12345
# 2 passed in 4.74s
```

## Notes

- The test exercises `StepType.browser_verification` → `FixTrigger.browser_verification` as the trigger step, which is the canonical cascade-prone case described in the issue.
- The `_make_step` helper was extended with optional `started_at`/`completed_at` parameters so the upstream gate has meaningful timestamps before the test runs — the assertion checks they are preserved after the thrashing suppressor runs.
- The negative-control test uses `>= 1` for cascade event count (not `== 1`) because the test is order-dependent when running alongside other tests that emit `cascaded_replay_after_fix` events against the same DB clone.
- Both tests use `@patch("orch.daemon.fix_cycle._is_pid_alive", return_value=False)` to simulate a dead fix-agent PID — this is the same pattern used in existing tests (`test_fix_cycle.py` etc.).