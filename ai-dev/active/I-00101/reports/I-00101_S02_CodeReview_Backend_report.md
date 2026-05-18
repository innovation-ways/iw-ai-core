# I-00101 S02 CodeReview_Backend Report

## Review Scope

Reviewed S01 (Backend) implementation for I-00101 — Scope-violation escalations strand work items with no UI surface or remedy.

## What Was Reviewed

- Design doc: `I-00101_Issue_Design.md` (read first; Root Cause Analysis + Regression Prevention sections)
- S01 report: `reports/I-00101_S01_Backend_report.md`
- Changed files: `orch/daemon/fix_cycle.py`, `orch/daemon/scope_amendment.py`
- Pre-flight gates: `make lint`, `make format`, `make typecheck`
- Unit test suite: `pytest tests/unit/daemon/ -v --no-cov`

---

## Pre-Flight Gates

| Gate | Result | Notes |
|------|--------|-------|
| `make lint` | PASS | All checks passed — zero new violations |
| `make format` | PASS | 759 files already formatted |
| `make typecheck` | PASS | No errors on `fix_cycle.py` or `scope_amendment.py` |

---

## Review Checklist

### 1. Budget-exemption filter correctness

**File**: `orch/daemon/fix_cycle.py`

The `_is_scope_escalation()` helper is defined once at line 335 and used at both call sites:
- Line 507: per-step `.count()` in `should_attempt_fix()`
- Line 530: aggregate per-work-item `.count()` in `should_attempt_fix()`

**Predicate narrowness**: The helper matches only rows where:
- `status == FixStatus.escalated`
- `fix_metadata->'scope_violations'` is not null
- `jsonb_array_length(...) > 0`

A vanilla `escalated` cycle (e.g. future `spec_mismatch` cause, no `scope_violations` key) is **not** exempt — correct.

**Implementation**: Uses SQLAlchemy `func.jsonb_array_length` and `op("->")` JSONB operators — pure DB-side predicate, no Python iteration on `.all()`. Correct.

**Idempotency**: The predicate is defined once as a function, not copy-pasted. Correct.

✅ PASS

### 2. `scope_amendment.py` helper purity

**File**: `orch/daemon/scope_amendment.py`

- `amend_allowed_paths`: No `Session` argument, no `.commit()`/`.add()`/`.execute(UPDATE/INSERT/DELETE)`. Pure file I/O. Correct.
- `revert_paths_in_worktree`: No `Session` argument. Pure subprocess. Correct.
- `latest_scope_violation(db, step_id)`: Read-only `.query().first()` — no writes. Correct.

All three helpers have full type annotations. Correct.

✅ PASS

### 3. `amend_allowed_paths` correctness

**File**: `orch/daemon/scope_amendment.py`

- **Both manifests**: Worktree manifest always written (line 82–104); parent manifest written only when `_resolve_parent_manifest()` succeeds (line 107–137). Correct.
- **Parent discovery**: Reads `.git` pointer file (line 212–224). Robustness: returns `None` if `.git` absent, not a worktree pointer, or parent manifest missing. Correct.
- **Idempotency**: Line 86–89 checks `if path not in existing` before appending. No duplicates. Correct.
- **JSON preservation**: Line 93 uses `json.dumps(..., indent=2, sort_keys=False)` — 2-space indent, preserves key order, preserves `_note` and other top-level keys (not overwritten). Correct.
- **Note in result when parent missing**: Line 132–137 logs an info message when parent cannot be resolved. The `manifests_updated` list in `AmendResult` will contain only the worktree path, allowing the caller to detect partial updates. Correct.

✅ PASS

### 4. `revert_paths_in_worktree` correctness

**File**: `orch/daemon/scope_amendment.py`

- **Uses `-C <worktree_path>`**: Line 157 uses `["git", "-C", str(worktree_path), "checkout", "--", path]` — correct form, not `cwd=`. Correct.
- **No shell expansion**: `subprocess.run` with `check=False` and a list of arguments — no shell=True, no string joining. Correct.
- **Captures stderr per path**: Line 158 `capture_output=True`; failed paths stored with stderr in log (line 166–171). Correct.
- **Returns failed paths**: Returns `RevertResult(reverted=..., failed=...)` — does not raise. Correct.

✅ PASS

### 5. `latest_scope_violation` correctness

**File**: `orch/daemon/scope_amendment.py`

- **Orders by `cycle_number DESC`**: Line 188 `.order_by(FixCycle.cycle_number.desc())`. Correct — returns the latest cycle.
- **Returns `None` for no cycles**: Line 191–192 checks `if cycle is None`. Correct.
- **Returns `None` when not escalated**: Line 193–194 checks `cycle.status != FixStatus.escalated`. Correct.
- **Returns `None` when `scope_violations` is empty list**: Line 197 `len(violations) == 0` check. Correct — truthiness used by caller.

✅ PASS

### 6. Module docstring note

**File**: `orch/daemon/fix_cycle.py`

Lines 8–12 document the I-00101 budget-exemption decision and the narrow scope of the predicate. Present. Correct.

✅ PASS

### 7. Scope discipline

The only files modified are `orch/daemon/fix_cycle.py` (modified) and `orch/daemon/scope_amendment.py` (created). No other files touched. Correct.

✅ PASS

### 8. TDD RED Evidence

S01 report records `tdd_red_evidence: "n/a — Backend implements helpers consumed by S05's tests; S05 owns the RED-first runs"`. S05 (Tests) is indeed the RED-first step per the design doc. Correct.

✅ PASS

---

## Test Verification

```
uv run pytest tests/unit/daemon/ -v --no-cov
============================= 172 passed in 0.77s ==============================
```

All 172 existing daemon unit tests pass. No regressions.

---

## Migrations Check

No files under `orch/db/migrations/versions/` were created or modified. Correct — this step is exempt from migrations per the design doc note.

---

## Findings

No critical, high, or medium_fixable issues found.

---

## Verdict

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00101",
  "step_reviewed": "S01",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "172 passed, 0 failed",
  "findings": [],
  "notes": "S01 Backend is clean. Budget-exemption filter correctly applied to both per-step and aggregate counts. scope_amendment.py helpers are pure and correct. No migrations generated. All pre-flight gates pass. S05 (Tests) is the correct owner for RED-first behavioural tests."
}
```
