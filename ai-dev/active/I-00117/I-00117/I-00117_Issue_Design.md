# I-00117: Daemon silently dead-ends a non-fixable, non-retryable failed step

**Type**: Issue
**Severity**: High
**Created**: 2026-05-29
**Reported By**: Operator (diagnosed while investigating CR-00092 stall)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This item adds **no** migration. It changes daemon control-flow and emits a new
`DaemonEvent` type (a row value, not a schema change).

## Description

When an implementation step is deliberately failed (`iw step-fail`) with a reason
that does **not** start with `SPEC_MISMATCH:`, and the step has exhausted its
implementation retries, the daemon silently gives up: it logs a warning and
returns without emitting any `DaemonEvent` or changing any status. The work item
stays `in_progress` and its batch stays `executing` indefinitely, invisible to
operators. CR-00092 sat in this state for ~9 hours (batch BATCH-00136 showed
`executing 547m`) with no dashboard signal that human action was required.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.
Daemon recovery logic lives in `orch/daemon/batch_manager.py` and
`orch/daemon/fix_cycle.py` (see `docs/IW_AI_Core_Daemon_Design.md`).

## Steps to Reproduce

1. Run a work item whose implementation step (e.g. a `database-impl` /
   `backend-impl` step) calls `iw step-fail` with a reason like
   `"Blocked: <something the agent cannot fix in scope>"` (NOT prefixed with
   `SPEC_MISMATCH:`).
2. Let the daemon retry it. Implementation steps are retried at most
   `_DEFAULT_IMPLEMENTATION_MAX_RETRIES` (= 2) times, and only when no report was
   written. After the second failed run, `should_retry_step()` returns False.
3. Observe the daemon poll loop on the next tick.

**Expected**: The daemon emits a `DaemonEvent` recording that the step exhausted
recovery and needs human action, and transitions the work item and its batch item
to a visible terminal state (`failed`) so the batch stops reporting `executing`.

**Actual**: `orch/daemon/batch_manager.py` falls into the final `else` branch,
logs `"Step %s/%s failed and cannot be auto-recovered — needs human review"` and
returns. No `DaemonEvent` is emitted; the work item remains `in_progress` and the
batch item remains `executing` forever. The only trace is a log line.

## Root Cause Analysis

In `orch/daemon/batch_manager.py` (the per-item failed-step handler, around
lines 592-630), a failed non-`needs_fix`, non-soft step is routed:

1. `SPEC_MISMATCH:` reason → `fix_cycle.handle_spec_mismatch_escalation()` (emits
   a `spec_mismatch_escalation` `DaemonEvent`). ✅ visible
2. `fix_cycle.should_attempt_fix()` True → `attempt_fix_cycle()`. Only review/QV
   step types are in `fix_cycle._FIXABLE_STEP_TYPES`; **`implementation` is not**,
   so this is False for implementation steps.
3. `fix_cycle.should_retry_step()` True → `retry_step()`. For `implementation`
   steps this returns False once a report exists OR `run_count >=
   _DEFAULT_IMPLEMENTATION_MAX_RETRIES` (2).
4. **`else`: bare `logger.warning(...)` then `return`.** ← the bug.

The `else` branch is the only failure-handling path that neither emits a
`DaemonEvent` nor changes any status. Every other terminal failure path
(`setup_failed` at `batch_manager.py:646/681/772`, dependency failure at
`:422`, spec-mismatch escalation) is visible. This one is silent, so a genuinely
blocked implementation step produces an indefinitely-`executing` batch.

`fix_cycle.handle_spec_mismatch_escalation()` (`orch/daemon/fix_cycle.py:478`) is
the pattern to mirror: it composes `_emit_event(...)` + a `logger.warning` and is
called from `batch_manager.py`.

## Affected Components

| Component | Impact |
|-----------|--------|
| Daemon — `orch/daemon/batch_manager.py` | Silent `else` branch leaves item stuck `in_progress`, batch `executing` forever |
| Daemon — `orch/daemon/fix_cycle.py` | No escalation helper exists for the "recovery exhausted" case (only spec-mismatch) |
| Operator visibility | No `DaemonEvent`, so the dashboard events table / batch view shows nothing actionable |

## Fix Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Add `handle_recovery_exhausted_escalation()` to `fix_cycle.py`; call it from the `else` branch in `batch_manager.py`. Emit a `step_recovery_exhausted` `DaemonEvent`; set `batch_item.status = failed` and `work_item.status = failed`; `db.commit()`. | — |
| S02 | CodeReview | Review S01 output | — |
| S03 | Tests | Reproduction + regression tests | — |
| S04 | CodeReview | Review S03 output | — |
| S05 | CodeReview_Final | Global review of all work | — |
| S06..S13 | QV Gates | lint, format, typecheck, assertions, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S14 | SelfAssess | Self-assessment (project `self_assess=true`) | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None. The fix only emits a new `DaemonEvent.event_type`
  string value (`step_recovery_exhausted`); `event_type` is a free-text column.

### Code Changes

- **Files to modify**: `orch/daemon/fix_cycle.py`, `orch/daemon/batch_manager.py`
- **Nature of change**: Replace a silent `else: logger.warning(); return` with an
  escalation helper that emits a `DaemonEvent` and transitions the work item +
  batch item to `failed`.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00117_Issue_Design.md` | Design | This document |
| `I-00117_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00117_S01_Backend_prompt.md` | Prompt | S01 fix implementation |
| `prompts/I-00117_S02_CodeReview_Backend_prompt.md` | Prompt | Review S01 |
| `prompts/I-00117_S03_Tests_prompt.md` | Prompt | Reproduction + regression tests |
| `prompts/I-00117_S04_CodeReview_Tests_prompt.md` | Prompt | Review S03 |
| `prompts/I-00117_S05_CodeReview_Final_prompt.md` | Prompt | Global review |
| `prompts/I-00117_S14_SelfAssess_prompt.md` | Prompt | Self-assessment |

Reports are created during execution in `ai-dev/active/I-00117/reports/`.

## Test to Reproduce

The reproduction test drives the daemon's failed-step handler against a real
testcontainer DB (FOR UPDATE locking + status transitions cannot be mocked — see
`tests/CLAUDE.md`). It belongs in `tests/integration/` alongside
`test_fix_cycle.py`.

```python
def test_exhausted_implementation_step_escalates_visibly():
    """An implementation step that exhausted retries with a non-SPEC_MISMATCH
    reason must escalate visibly, not silently dead-end.

    FAILS before the fix (no event, statuses unchanged); PASSES after.
    """
    # Arrange: a batch_item whose implementation step is `failed`, with 2 StepRun
    # rows (retries exhausted) and a step-fail reason NOT starting with
    # "SPEC_MISMATCH:".
    {seed work item + batch item + failed implementation step + 2 StepRun rows}

    # Act: run the daemon's per-item failed-step handler one tick.
    {invoke the handler}

    # Assert (semantic — specific values, not shape):
    assert work_item.status == WorkItemStatus.failed
    assert batch_item.status == BatchItemStatus.failed
    event = {query DaemonEvent for entity_id == item, event_type == "step_recovery_exhausted"}
    assert event is not None
    assert event.event_metadata["step_id"] == failed_step.step_id  # the seeded impl step
```

## Acceptance Criteria

### AC1: Exhausted implementation step escalates visibly

```
Given an implementation step that is `failed`, has exhausted its retries, and
      whose failure reason does NOT start with "SPEC_MISMATCH:"
When  the daemon's failed-step handler processes it
Then  a `step_recovery_exhausted` DaemonEvent is emitted for the work item,
      AND work_item.status becomes `failed`,
      AND batch_item.status becomes `failed`
```

### AC2: SPEC_MISMATCH path is unchanged

```
Given an implementation/verification step failed with a "SPEC_MISMATCH:" reason
When  the daemon's failed-step handler processes it
Then  it still routes to handle_spec_mismatch_escalation (a `spec_mismatch_escalation`
      event), NOT the new recovery-exhausted path
```

### AC3: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the reproducing test passes and asserts specific event/status values
```

## Regression Prevention

- The reproduction test pins the escalation behavior so the silent branch cannot
  return without a `DaemonEvent` + status transition.
- A structural assertion in the test: after the handler runs on a failed
  non-recoverable step, the work item must be in a **terminal** status (not
  `in_progress`) — guards against any future branch re-introducing a silent return.

## Dependencies

- **Depends on**: None
- **Blocks**: None (related to I-00118 — pre-existing-red-gate poisoning — but
  independently shippable)

## Impacted Paths

- `orch/daemon/fix_cycle.py`
- `orch/daemon/batch_manager.py`
- `tests/integration/test_recovery_exhausted_escalation.py`

## TDD Approach

- Reproducing test: `test_exhausted_implementation_step_escalates_visibly` — fails
  before the fix (no event, status stays `in_progress`/`executing`), passes after.
- Unit/integration tests: the SPEC_MISMATCH branch still routes correctly; the
  new event carries `step_id` and `failure_reason` in `event_metadata`.

## Notes

- There is no `needs_attention` status in `WorkItemStatus`. Adding one is a
  larger schema/UX change and is **out of scope**; `failed` is the existing
  visible terminal state and is consistent with how `setup_failed` and
  fix-cycle/QV exhaustion already terminate. The `DaemonEvent` is what makes the
  cause actionable.
- `DaemonEvent.metadata` is named `event_metadata` in Python (SQLAlchemy reserves
  `metadata`) — the test and helper must use `event_metadata`.
- Keep the fix minimal: do not refactor the surrounding failure-routing ladder.
