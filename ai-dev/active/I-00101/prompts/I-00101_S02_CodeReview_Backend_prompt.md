# I-00101_S02_CodeReview_Backend_prompt

**Work Item**: I-00101 -- Scope-violation escalations strand work items with no UI surface or remedy
**Step Being Reviewed**: S01 (Backend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps/inspect/logs` allowed; everything else forbidden.

## ⛔ Migrations: agents generate, daemon applies

No migrations were generated in S01. Verify this — if S01 produced any file under `orch/db/migrations/versions/**`, that is a **CRITICAL** scope-creep finding.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00101 --json`
- `ai-dev/active/I-00101/I-00101_Issue_Design.md` — design document (READ FIRST)
- `ai-dev/active/I-00101/reports/I-00101_S01_Backend_report.md` — S01 report
- All files listed in S01's `files_changed`:
  - `orch/daemon/fix_cycle.py`
  - `orch/daemon/scope_amendment.py`

## Output Files

- `ai-dev/active/I-00101/reports/I-00101_S02_CodeReview_Backend_report.md` — Review report

## Context

You are reviewing **S01** for I-00101. Read the design doc first (`Root Cause Analysis` and `Regression Prevention` sections especially), then S01's report, then the changed files.

## Read the Design Document FIRST

Pay special attention to:
- `## Acceptance Criteria` — AC4 is what S01 is responsible for satisfying (budget exemption).
- `## Regression Prevention` items 1 ("Filter, don't mutate") and 3 ("Two-manifest write is encapsulated").
- `## Notes` — the rationale for the filter approach.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

If either reports NEW violations in the files S01 touched (i.e., violations not on `main`), classify each as **CRITICAL** with `category: conventions` and quote the exact violation code.

## Review Checklist

### 1. Budget-exemption filter correctness

- The filter is applied to **both** the per-step `.count()` at `_max_cycles_for` (line ~482) **and** the aggregate `.count()` at `should_attempt_fix_cycle` (lines ~498-504). Missing either is **CRITICAL** (one budget would still be eaten by scope escalations).
- The filter is **narrow**: it only excludes rows where `status=escalated` AND `fix_metadata.scope_violations` is a non-empty JSONB array. If the predicate excludes any `status=escalated` row regardless of `scope_violations` content, that is **CRITICAL** — it would mask other escalation causes (spec_mismatch, future causes) from budget math.
- The predicate is defined **once** as a local helper, not copy-pasted across the two call sites. Duplication is **HIGH**.
- The predicate uses PostgreSQL JSONB operators (`jsonb_array_length`, `->`), not Python-side iteration on `.all()`. Python-side filtering on a `.all()` of all rows is **HIGH** (performance + atomicity).

### 2. `scope_amendment.py` helper purity

- `amend_allowed_paths` and `revert_paths_in_worktree` perform NO DB writes (no `Session` argument or, if argued in, no `.commit()` / `.add()` / `.execute(UPDATE/INSERT/DELETE)`). Any DB mutation here is **CRITICAL** — the dashboard endpoint owns transaction boundaries.
- `latest_scope_violation` is read-only on the DB (a single `SELECT`).
- All three helpers have full type annotations.

### 3. `amend_allowed_paths` correctness

- Writes BOTH manifest files when the parent repo is locatable. **HIGH** on single-file write.
- The parent-repo discovery reads the worktree's `.git` pointer file or walks up — verify the implementation is robust to a worktree directly cloned (no `.git` pointer) and falls back gracefully (worktree-only write + note in result).
- Idempotency: calling with paths already present in `allowed_paths` does not double-append. **HIGH** if duplicates can land.
- JSON is pretty-printed with 2-space indentation and preserves the `_note` and other top-level keys verbatim. **MEDIUM_FIXABLE** if order is mangled or the `_note` is dropped.

### 4. `revert_paths_in_worktree` correctness

- Uses `git -C <worktree_path> checkout -- <path>` (the `-C` form, not `cwd=`). **HIGH** if it relies on cwd or spawns a shell.
- Captures stderr per path and returns failed paths in `RevertResult.failed` (does NOT raise).
- No shell expansion of `paths_to_revert` — each path is passed as a separate argv element. **CRITICAL** if shell=True or string-joining is used (injection risk).

### 5. `latest_scope_violation` correctness

- Orders by `cycle_number DESC` and takes the first row. Returns the violations list from the LATEST cycle. **HIGH** if it returns the first cycle's violations or aggregates across cycles.
- Returns `None` (not `[]`) when no scope-escalation cycle exists.
- Returns `None` when the latest cycle has `scope_violations=[]` (empty list). **MEDIUM_FIXABLE** if it returns `[]` for this case — the dashboard uses truthiness.

### 6. Module docstring note

- `orch/daemon/fix_cycle.py` carries an `I-00101 (2026-05-18)` paragraph documenting the budget-exemption decision and the predicate's narrow scope. Missing is **MEDIUM_FIXABLE**.

### 7. Scope discipline

- The only files changed are `orch/daemon/fix_cycle.py` and `orch/daemon/scope_amendment.py`. Any other file is **CRITICAL** scope creep.

### 8. TDD RED Evidence

This step is exempt from the RED-first rule because S05 owns the behavioural tests. S01's report should record `tdd_red_evidence: "n/a — Backend implements helpers consumed by S05's tests"`. If the field is missing or claims behavioural tests were added in this step, that is **HIGH**.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/daemon/ -v --no-cov
```

Confirm the existing daemon-unit suite still passes. Note in the report.

## Severity Levels

Standard mapping (CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW). Anything labelled CRITICAL, HIGH, or MEDIUM_FIXABLE triggers a fix cycle.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00101",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
