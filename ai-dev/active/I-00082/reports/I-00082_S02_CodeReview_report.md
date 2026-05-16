# I-00082 S02 — Code Review Report

**Work Item**: I-00082 — Fix-cycle agent has no allowed_paths enforcement
**Step**: S02 (code-review-impl)
**Status**: needs-fix

---

## Scope

Reviewed `orch/daemon/fix_cycle.py` (I-00082 additions) and
`tests/integration/test_fix_cycle_scope_enforcement.py` against the four
acceptance criteria in `I-00082_Issue_Design.md`.

---

## Findings

### CRITICAL

#### C1 — Escalated cycles counted toward the fix-cycle budget

**Files**: `orch/daemon/fix_cycle.py:482`, `499–504`

**Rule violated**: Design doc §Fix Plan step 4: "Do NOT increment the cycle budget
toward the 5-cycle cap." Review checklist CRITICAL: "a cycle with
`FixCycle.status == FixStatus.escalated` must NOT increment
`fix_cycles.cycle_count` toward the 3/5 cap."

**Evidence**:

```python
# line 482 — per-step cap
existing = db.query(FixCycle).filter(FixCycle.step_id == step.id).count()
if existing >= max_cycles:
    return False

# lines 499-504 — aggregate cap
aggregate_used = (
    db.query(FixCycle)
    .join(WorkflowStep, FixCycle.step_id == WorkflowStep.id)
    .filter(WorkflowStep.work_item_id == step.work_item_id)
    .filter(WorkflowStep.project_id == step.project_id)
    .count()
)
```

Both counts include `FixStatus.escalated` rows. If the operator amends
`allowed_paths` and restarts the step, every prior escalation cycle will burn
budget that should have remained free — exactly the deadlock the design is
meant to prevent.

**Suggested fix**:

```python
# line 482
existing = (
    db.query(FixCycle)
    .filter(FixCycle.step_id == step.id, FixCycle.status != FixStatus.escalated)
    .count()
)

# lines 499-504
aggregate_used = (
    db.query(FixCycle)
    .join(WorkflowStep, FixCycle.step_id == WorkflowStep.id)
    .filter(
        WorkflowStep.work_item_id == step.work_item_id,
        WorkflowStep.project_id == step.project_id,
        FixCycle.status != FixStatus.escalated,
    )
    .count()
)
```

---

### HIGH

#### H1 — Step left in zombie `needs_fix` after escalation

**File**: `orch/daemon/fix_cycle.py:1122`

**Rule violated**: Correctness / state-machine contract. After `_complete_fix_cycle`
returns early on a scope violation, `step.status` remains `StepStatus.needs_fix`
(set by `attempt_fix_cycle:701`) with no active fix cycle. The daemon's
`check_active_fix_cycles` queries for `FixStatus.in_progress` cycles only; the
escalated cycle is invisible to it. The step is stuck permanently unless the
operator manually transitions it — and the dashboard shows "in progress" rather
than "blocked."

**Evidence**: `_fail_fix_cycle:1277` correctly transitions the step to
`StepStatus.failed` on ordinary cycle failure; the escalation path lacks the
equivalent transition.

**Suggested fix**: Before the `return` at line 1122:

```python
if step is not None and step.status == StepStatus.needs_fix:
    step.status = StepStatus.failed
    step.started_at = None
    step.completed_at = None
return  # Do NOT advance the step — operator must intervene
```

This makes the step visible on the dashboard as a failed/blocked item, and
ensures that if the operator restarts the step after amending `allowed_paths`,
the daemon picks it up on the next poll.

#### H2 — No-violation log line in `run_fix_cycle` missing `violations=[...]`

**File**: `orch/daemon/fix_cycle.py:256–263`

**Rule violated**: Review checklist HIGH: "Daemon log line shape must match the
spec exactly." Spec: `fix_cycle scope: item=<ID> step=<SXX> cycle=<N>
allowed=<K> in_scope=<M> out_of_scope=<P> violations=[...]`

**Evidence** — no-violation branch in `run_fix_cycle`:

```python
logger.info(
    "fix_cycle scope: item=%s step=%s cycle=%d allowed=%d in_scope=%d out_of_scope=0",
    item_id, step_id, cycle_number, len(allowed), len(agent_touched),
)
```

`violations=[...]` is absent. The production path (`_complete_fix_cycle:1076–1086`)
correctly emits it in both violation and no-violation branches.

**Suggested fix**: Unify both branches in `run_fix_cycle`:

```python
logger.info(
    "fix_cycle scope: item=%s step=%s cycle=%d allowed=%d "
    "in_scope=%d out_of_scope=%d violations=%r",
    item_id, step_id, cycle_number, len(allowed),
    len(agent_touched), 0, [],
)
```

---

### MEDIUM

#### M1 — TDD RED evidence is AttributeError, not assertion failure

**File**: `ai-dev/work/I-00082/reports/I-00082_S01_Pipeline_report.md`

**Rule violated**: Review checklist MEDIUM: "must capture the exact failing line
from running the reproduction test pre-fix (the assertion will reference
`FixStatus.escalated` vs. whatever the pre-fix path returned, typically
`FixStatus.completed`)."

**Evidence**: The S01 report records `AttributeError: module
'orch.daemon.fix_cycle' has no attribute 'run_fix_cycle'`. This is technically
a RED (the test could not run), but the spec expected an assertion-level
failure demonstrating the semantic gap between pre-fix and post-fix behavior.

**Assessment**: The agent created both the test and the production code in the
same step. The AttributeError is the correct RED when `run_fix_cycle` doesn't
exist yet, so the TDD sequence was followed. The finding is recorded but does
not block S03.

---

### LOW

#### L1 — No `_compute_violations` helper extracted

**File**: `orch/daemon/fix_cycle.py` (various)

**Rule violated**: Review checklist LOW: "Naming: `_compute_violations(...)` or
similar pure helper extracted for unit testing."

The violation computation (`agent_touched - pre_cycle` + pattern matching) is
duplicated inline in both `run_fix_cycle` (lines 228–237) and
`_complete_fix_cycle` (lines 1058–1065). Extracting to a single pure function
would simplify unit testing and eliminate the duplication.

**Suggested fix**: Extract a `_compute_violations(agent_touched, allowed,
item_id)` helper (no I/O, pure set arithmetic) and call it from both sites.

---

## Acceptance-Criteria Verification

| AC | Description | Status |
|----|-------------|--------|
| AC1 | Bug fixed: out-of-scope edit → `FixStatus.escalated` + event | ✅ Pass |
| AC2 | Regression test exists and passes | ✅ Pass |
| AC3 | Operator pre-edits preserved (pre-cycle snapshot subtract) | ✅ Pass |
| AC4 | In-scope cycles still complete normally | Not blocked by any finding |

---

## Checklist Summary

| Checklist item | Result |
|----------------|--------|
| No auto-revert (git checkout / restore / stash) | ✅ Clean |
| Operator pre-edits excluded from violation set | ✅ Correct |
| No new enum value invented | ✅ `FixStatus.escalated` reused |
| Escalated cycles excluded from budget count | ❌ CRITICAL — C1 above |
| `DaemonEvent` `scope_violation_escalation` emitted | ✅ Present |
| Manifest loaded via existing helper (not ad-hoc) | N/A — no module-level helper exists; ad-hoc JSON load is acceptable |
| `_scope_match` is exact 4-line mirror of `scope_gate.py:_matches()` | ✅ Identical |
| Implicit allows include `ai-dev/work/<ID>/**` | ✅ Present |
| Daemon log line shape matches spec | ❌ HIGH — H2 (test path only; production path is correct) |
| Empty `allowed_paths` skips reconciliation | ✅ Correct |
| `FixStatus.escalated` used consistently | ✅ |
| S01 leaves exactly one test in test file | ✅ |

---

## Verdict

`verdict: needs-fix`

**CRITICAL and HIGH findings to address before S03:**

1. **C1** (`fix_cycle.py:482`, `499–504`): Add `FixCycle.status != FixStatus.escalated`
   filter to both budget counts in `should_attempt_fix`.

2. **H1** (`fix_cycle.py:1122`): Set `step.status = StepStatus.failed` in
   `_complete_fix_cycle` before returning early on scope violation.

3. **H2** (`fix_cycle.py:256–263`): Add `violations=%r` to the no-violation log
   line in `run_fix_cycle` to match the spec's stable log format.
