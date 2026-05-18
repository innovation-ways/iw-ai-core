# I-00101 S01 Backend Report

## What was done

Two deliverables were implemented as specified in the design doc:

### 1. Budget-exemption filter in `orch/daemon/fix_cycle.py`

**Changed**: Two `.count()` queries in `should_attempt_fix()` (lines ~505 and ~527) that previously counted all FixCycle rows.

**Before**: Both the per-step count (line 506) and aggregate-per-work-item count (line 527) included every FixCycle row regardless of cause.

**After**: Both queries now filter out scope-escalated cycles using `not_(_is_scope_escalation())`. The `_is_scope_escalation()` helper predicate is defined once at `fix_cycle.py:335` and shared by both call sites. It matches rows where:
- `status == FixStatus.escalated` AND
- `fix_metadata->'scope_violations'` is non-null AND
- `jsonb_array_length(fix_metadata->'scope_violations') > 0`

A vanilla escalated cycle (e.g. from a future `spec_mismatch` cause with no `scope_violations` key) still counts. Only the narrow combination `status=escalated AND scope_violations non-empty` is exempt.

Module docstring updated to record the change (lines 8-12).

### 2. New module `orch/daemon/scope_amendment.py`

Created a pure-helper module with three public callables:

- `amend_allowed_paths(worktree_path, item_id, paths_to_add) -> AmendResult` — Appends paths to `scope.allowed_paths` in both the worktree manifest and the parent repo's design-time copy (found via `.git` pointer file). Idempotent (dedupes against existing entries). Pretty-prints with 2-space indent.

- `revert_paths_in_worktree(worktree_path, paths_to_revert) -> RevertResult` — Runs `git checkout -- <path>` per path using subprocess with `-C` flag; captures stderr per-path; returns separate reverted/failed lists.

- `latest_scope_violation(db, step_id) -> list[str] | None` — Queries the latest FixCycle on the step (ORDER BY cycle_number DESC LIMIT 1) and returns `scope_violations` list if the cycle is `status=escalated` AND `scope_violations` is a non-empty list; otherwise returns None.

`_resolve_parent_manifest()` is a private helper that reads the worktree's `.git` pointer file to find the parent repo root.

## Files changed

| File | Change |
|------|--------|
| `orch/daemon/fix_cycle.py` | Modified: `_is_scope_escalation()` helper added; two `.count()` queries in `should_attempt_fix()` now filter scope-escalated cycles; module docstring updated |
| `orch/daemon/scope_amendment.py` | Created: pure helpers `amend_allowed_paths`, `revert_paths_in_worktree`, `latest_scope_violation`, and `_resolve_parent_manifest` |

## Test results

```
uv run pytest tests/unit/daemon/ -v --no-cov
172 passed in 0.78s
```

No regressions in the existing daemon unit test suite.

## Preflight

| Gate | Result |
|------|--------|
| `make format` | ok (files auto-formatted by `uv run ruff format`) |
| `make typecheck` | ok (zero errors on `fix_cycle.py`, `scope_amendment.py`) |
| `make lint` | ok (zero errors) |

## TDD evidence

`tdd_red_evidence: "n/a — Backend implements helpers consumed by S05's tests; S05 owns the RED-first runs"` — As specified in the step instructions, no new behavioural tests were written in this step. S05 writes the RED-first tests for both deliverables.

## Blockers

None.
