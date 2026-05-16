# I-00082 S05 — Code Review Final Report

**Work Item**: I-00082 — Fix-cycle agent has no allowed_paths enforcement  
**Step**: S05 (code-review-final-impl)  
**Date**: 2026-05-16  
**Verdict**: **needs-fix**

---

## What Was Done

Cross-agent final review covering:

1. Test suite run (`pytest tests/integration/test_fix_cycle_scope_enforcement.py -v`)
2. Diff scope verification (`git diff --stat`)
3. AC coverage mapping
4. All design-doc confirmation checkpoints from the step prompt

---

## Test Results

```
tests/integration/test_fix_cycle_scope_enforcement.py::test_i00082_fix_cycle_escalates_on_out_of_scope_edit PASSED
tests/integration/test_fix_cycle_scope_enforcement.py::test_i00082_operator_pre_edit_outside_scope_is_preserved PASSED
tests/integration/test_fix_cycle_scope_enforcement.py::test_i00082_in_scope_fix_cycle_completes_normally PASSED

3 passed
```

Coverage failure (`total 3% < fail-under=50`) is expected when running only 3 focused tests against
the full codebase. All three tests exercise real behavior and assert on semantics, not shape.

---

## Diff Scope

```
git diff --stat (unstaged):
  orch/daemon/fix_cycle.py  |  347 +++++++++++++++++++++++++++++++++++++++++++++-
  1 file changed, 342 insertions(+), 5 deletions(-)

git diff --stat origin/main...HEAD (committed):
  (no committed diff — implementation is unstaged)

Untracked:
  tests/integration/test_fix_cycle_scope_enforcement.py  (new)
```

**Scope is clean.** Only `orch/daemon/fix_cycle.py` and
`tests/integration/test_fix_cycle_scope_enforcement.py` are in the diff.
No other files touched. No scope-creep CRITICAL triggered.

---

## Confirmation Checklist

| Check | Result |
|-------|--------|
| `FixStatus.escalated` reused from `models.py:170` — no new string outcome | ✅ PASS |
| `DaemonEvent` of type `scope_violation_escalation` emitted on violation | ✅ PASS (lines 1095–1112) |
| No `git stash` / `git checkout` / `git revert` in pre/post-cycle paths | ✅ PASS |
| Operator-preservation uses set-diff (`post_cycle - pre_cycle`), not stash | ✅ PASS |
| Empty / missing `scope.allowed_paths` is fail-open (legacy items work) | ✅ PASS (`_load_allowed_paths` returns `[]`; reconciliation skipped) |
| Budget counter NOT incremented for `FixStatus.escalated` | ❌ **FAIL** — see Finding 1 |
| Daemon log line shape matches design doc | ⚠️ PARTIAL — see Finding 2 |

---

## AC Coverage

| AC | Assertion | Test | Result |
|----|-----------|------|--------|
| AC1: out-of-scope edit → `FixStatus.escalated` | `cycle.status == FixStatus.escalated`; `scope_violations` set; agent edit preserved | `test_i00082_fix_cycle_escalates_on_out_of_scope_edit` | ✅ PASS |
| AC2: regression test exists and passes | test file present, 3 tests pass | — | ✅ PASS |
| AC3: operator carry-over edit not reverted | `cycle.status == FixStatus.completed`; operator file unchanged | `test_i00082_operator_pre_edit_outside_scope_is_preserved` | ✅ PASS |
| AC4: in-scope cycle completes normally | `cycle.status == FixStatus.completed`; no scope_violations | `test_i00082_in_scope_fix_cycle_completes_normally` | ✅ PASS |

All four acceptance criteria are covered by passing tests.

---

## Findings

### Finding 1 — HIGH: Budget counter IS incremented for escalated cycles

**Location**: `orch/daemon/fix_cycle.py:482` (`should_attempt_fix`)

```python
# Current (wrong):
existing = db.query(FixCycle).filter(FixCycle.step_id == step.id).count()

# Same gap in aggregate budget check, lines 498-503:
aggregate_used = (
    db.query(FixCycle)
    .join(WorkflowStep, FixCycle.step_id == WorkflowStep.id)
    .filter(WorkflowStep.work_item_id == step.work_item_id)
    .filter(WorkflowStep.project_id == step.project_id)
    .count()
)
```

**Problem**: Both `existing` (per-step budget) and `aggregate_used` (per-item aggregate budget)
count ALL FixCycle rows regardless of status. Escalated cycles — which are operator-intervention
events, not agent failures — therefore burn slots in the 5-cycle cap.

**Design doc requirement** (Code Changes §4): "do NOT increment the cycle budget toward the 5-cycle cap."

**Impact**: After a scope-violation escalation, if the operator amends `allowed_paths` and resets
the step, the daemon will correctly start another cycle BUT the escalated row is already counted
against the budget. On the final cycle slot, a scope violation would cause the budget to appear
exhausted, permanently blocking recovery without operator manual override.

**Required fix**:

```python
# Per-step budget (line 482):
existing = (
    db.query(FixCycle)
    .filter(
        FixCycle.step_id == step.id,
        FixCycle.status != FixStatus.escalated,
    )
    .count()
)

# Aggregate budget (lines 498-503):
aggregate_used = (
    db.query(FixCycle)
    .join(WorkflowStep, FixCycle.step_id == WorkflowStep.id)
    .filter(WorkflowStep.work_item_id == step.work_item_id)
    .filter(WorkflowStep.project_id == step.project_id)
    .filter(FixCycle.status != FixStatus.escalated)
    .count()
)
```

---

### Finding 2 — LOW: Log line field names differ from design doc spec

**Location**: `orch/daemon/fix_cycle.py:240–249`, `1076–1086`

**Design doc spec**: `fix_cycle scope: allowed_paths=N edits_in_scope=K out_of_scope_violations=M`

**Actual output**:
```
fix_cycle scope: item=X step=Y cycle=Z allowed=N in_scope=K out_of_scope=M violations=[...]
```

The implementation is more verbose (adds `item=`, `step=`, `cycle=`, `violations=`) and uses
abbreviated field names (`allowed=` vs `allowed_paths=`, `in_scope=` vs `edits_in_scope=`,
`out_of_scope=` vs `out_of_scope_violations=`). The extra fields are operationally valuable.
The mismatch is minor — no operator tooling is known to parse this log format — but the step
instructions require exact shape confirmation.

**Recommended**: Align field names to the spec or update the design doc. Not blocking on its own,
but flagged because the review prompt requires exact confirmation.

---

## Verdict

**needs-fix**

Finding 1 (HIGH) is a clear, unambiguous gap: the design doc explicitly requires that escalated
cycles do not count toward the fix-cycle budget cap, but `should_attempt_fix` and the aggregate
budget check count all cycles regardless of status. The fix is a two-line filter addition and does
not affect any of the four ACs (which all pass). Loop back to pipeline fix cycle to address it.

Finding 2 (LOW) can be addressed in the same fix cycle or deferred — it does not affect behavior.
