# I-00100 S04 Code Review Report

## What Was Reviewed

S03's integration test for the cascade thrashing detector wiring (`tests/integration/daemon/test_cascade_thrashing_detector_wiring.py`).

## Files Changed

| File | Status | Notes |
|------|--------|-------|
| `tests/integration/daemon/test_cascade_thrashing_detector_wiring.py` | NEW | S03's sole artifact |
| `orch/daemon/fix_cycle.py` | Modified | S01's plumbing fix (pre-existed S03) |

**Note**: `orch/daemon/fix_cycle.py` was modified by S01 (the backend-impl step), not S03. The plumbing fix threads `project_config` through the call chain and removes the `# noqa: ARG001` from `check_active_fix_cycles`. This is the pre-condition that makes the test meaningful.

## Pre-Review Gate Results

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format` | ✅ All checks passed |

No convention violations in the new test file.

## Review Checklist Findings

### 1. Production Seam — DRIVES `check_active_fix_cycles` ✅

The act phase calls `fix_cycle.check_active_fix_cycles(...)` at line 290 and 397, which is the top-of-chain function called by `BatchManager` in production. This is NOT `_complete_fix_cycle` directly, NOT `_detect_thrashing` directly, and NOT `_check_fix_cycle_health` directly.

The call chain exercised by the test:
```
check_active_fix_cycles → _check_fix_cycle_health → _complete_fix_cycle → _detect_thrashing
```

This matches the production path described in the design document §Root Cause Analysis.

### 2. Assertions Are Semantic — STRONG ✅

Every assertion in both tests is behavioural and specific:

**Positive test (`test_thrashing_detector_fires_when_driven_through_check_active_fix_cycles`):**
- `assert len(thrashing_events) == 1` — exact count, not `> 0`
- `assert meta["trigger_step_id"] == "S02"` — specific string value
- `assert meta["cascade_count"] == 3` — specific integer value
- `assert set(meta["reset_set"]) == {"S01"}` — exact set equality
- `assert cycle.status == FixStatus.completed` — specific enum value
- `assert s01.status == StepStatus.completed` — specific enum, not just truthiness
- `assert s01.started_at is not None` — specific null check with preservation intent

**Negative test (`test_no_thrashing_event_when_reset_sets_do_not_overlap`):**
- `assert len(thrashing_events) == 0` — exact zero, no false-positive path
- `assert len(cascade_events) >= 1` — normal cascade must fire
- `assert s01.status == StepStatus.pending` — upstream gate was reset (normal behaviour)
- `assert s01.started_at is None` — timestamps cleared on reset

None of these are shape-checking assertions. Each would fail if the production code regressed.

### 3. Negative Control Test Exists — AC3 Satisfied ✅

The file contains both tests:
1. `test_thrashing_detector_fires_when_driven_through_check_active_fix_cycles` — positive: 3 overlapping cascades → detector fires, upstream gate NOT reset
2. `test_no_thrashing_event_when_reset_sets_do_not_overlap` — negative: disjoint reset-sets (Jaccard = 0.0) → detector does NOT fire, upstream gate IS reset

AC3 ("no behaviour change for non-thrashing cases") is directly tested. This was the highest-risk gap identified in the review instructions.

### 4. Dead-PID Setup — `monkeypatch` Pattern ✅

The test uses `@patch("orch.daemon.fix_cycle._is_pid_alive", return_value=False)` (lines 289 and 396). This is:
- The most robust approach — no subprocess overhead, deterministic
- Consistent with existing tests in the daemon suite (e.g., `test_fix_cycle.py`)
- Belt-and-suspenders: combined with `os.getpid() + 99999` in the fixture for documentation

The fixture comment explains why `os.getpid() + 99999` is guaranteed-nonexistent (Linux `pid_max` limits). The double-layer (large PID + mock) is belt-and-suspenders but appropriate for a critical regression test.

### 5. Test Isolation — Order-Independence Confirmed ✅

Ran with `--randomly-seed=12345` (both tests pass in either order). The `dead_pid` fixture is function-scoped. Each test uses distinct `item_id` values (`I-00100-THRASH` vs `I-00100-NORMAL`), preventing cross-test contamination.

### 6. Test Placement and Naming ✅

- File path: `tests/integration/daemon/test_cascade_thrashing_detector_wiring.py` — matches the design's File Manifest exactly
- Test class: `TestCascadeThrashingDetectorWiring` — descriptive
- Test functions: `test_thrashing_detector_fires_when_driven_through_check_active_fix_cycles` and `test_no_thrashing_event_when_reset_sets_do_not_overlap` — behaviour-describing names
- Docstrings explain RED reasoning (pre-S01 failure mode) for each test

### 7. `test_project` Fixture — Declared but Unused (MEDIUM_FIXABLE)

Both test methods declare `test_project: Project` as a fixture parameter but never reference it. The tests create their own `Project` entity implicitly through helper functions (the `_make_*` helpers use `project_id="test-proj"` directly).

This is technically correct (the tests pass, isolation is maintained) but a mild fixture pollution issue. Per the testing skill §red-flag checklist, "it has 0–1 assertions for logic with 3+ code paths" doesn't apply here (there are 7+ assertions per test), and the fixture doesn't cause incorrect behaviour.

**Recommendation**: Remove `test_project: Project` from both method signatures. The fixture is harmless but unused.

### 8. Single New File, No Production Code Changes by S03 ✅

S03 created exactly one file. The `orch/daemon/fix_cycle.py` modification was S01's work, not S03's.

## Test Verification Results

```bash
uv run pytest tests/integration/daemon/test_cascade_thrashing_detector_wiring.py -v --no-cov
# 2 passed in 6.71s

# With fixed seed (order-independence check)
uv run pytest tests/integration/daemon/test_cascade_thrashing_detector_wiring.py -v --no-cov -p randomly --randomly-seed=12345
# 2 passed in 4.83s
```

## Overall Assessment

The test is **strong** — not merely present. It drives the real production seam, uses semantic assertions that would fail on regression, and includes both the positive and negative cases required by AC3. The only minor issue is the unused `test_project` fixture parameter, which is cosmetic and causes no incorrect behaviour.

## Verdict

**PASS** — The test correctly exercises the production seam and is suitable as a regression net.

## Findings

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00100",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "code_quality",
      "file": "tests/integration/daemon/test_cascade_thrashing_detector_wiring.py",
      "line": 224,
      "description": "test_thrashing_detector_fires_when_driven_through_check_active_fix_cycles declares test_project: Project fixture parameter but never references it. The test creates its own project-scoped entities via _make_* helpers using project_id='test-proj'.",
      "suggestion": "Remove test_project: Project from the method signature since it is unused. The fixture is harmless but confusing."
    },
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "code_quality",
      "file": "tests/integration/daemon/test_cascade_thrashing_detector_wiring.py",
      "line": 344,
      "description": "test_no_thrashing_event_when_reset_sets_do_not_overlap also declares test_project: Project fixture parameter but never references it.",
      "suggestion": "Remove test_project: Project from the method signature since it is unused."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "2 passed, 0 failed",
  "notes": "Both tests pass order-independently (seed 12345 confirmed). The dead_pid fixture uses os.getpid() + 99999 plus a @patch on _is_pid_alive — belt-and-suspenders but deterministic and correct. The test_project fixture is declared but unused — cosmetic only, no functional impact. The test correctly drives check_active_fix_cycles (not _complete_fix_cycle directly), uses semantic assertions (specific event metadata values, specific step statuses, exact counts), and covers both AC1 (positive case) and AC3 (negative control)."
}
```