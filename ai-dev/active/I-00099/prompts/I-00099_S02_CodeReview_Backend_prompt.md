# I-00099_S02_CodeReview_Backend_prompt

**Work Item**: I-00099 -- Scope-overlap sibling-dir rule generates false-positive cross-batch holds
**Step Being Reviewed**: S01 (Backend)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy. Read-only docker introspection (`docker ps`, `docker inspect`, `docker logs`) is allowed; mutating commands are not.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch migrations. Do not run any `alembic upgrade/downgrade/stamp`.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00099 --json`.
- `ai-dev/active/I-00099/I-00099_Issue_Design.md` — design document
- `ai-dev/work/I-00099/reports/I-00099_S01_Backend_report.md` — S01 step report
- `orch/daemon/scope_overlap.py` — the file S01 modified

## Output Files

- `ai-dev/work/I-00099/reports/I-00099_S02_CodeReview_report.md` — Review report

## Context

You are reviewing S01's Backend work on **I-00099**. The fix is purely subtractive: remove `_same_parent` and its caller branch from `orch/daemon/scope_overlap.py`. Your review confirms the deletion is clean, complete, and limited to scope.

## Read the Design Document FIRST

Read `ai-dev/active/I-00099/I-00099_Issue_Design.md`:

- **Acceptance Criteria AC1, AC3, AC4** are S01's responsibility (the code change). AC2 is S03's. Verify the implementation satisfies AC1/AC3/AC4 by construction.
- **Affected Components** table names exactly one production file: `orch/daemon/scope_overlap.py`. Anything else in `files_changed` is scope creep — flag as CRITICAL.
- **Root Cause Analysis** specifies which lines must change: `_same_parent` (lines 128–132) deleted; sibling fallback inside `find_blocking_items` (lines 160–168) removed; `globs_intersect` and `_strip_test_globs` untouched.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files in S01's report's `files_changed`:

```bash
make lint
make format-check
```

Any NEW violation against `main` is a CRITICAL `conventions` finding.

## Review Checklist

### 1. Subtractive Fix Verification (CRITICAL anchors)

- **`_same_parent` is FULLY DELETED.** `grep -n "_same_parent\|def _same_parent" orch/daemon/scope_overlap.py` must return zero matches. Commented-out code or a stub is CRITICAL.
- **The sibling fallback inside `find_blocking_items` is REMOVED.** `find_blocking_items` should now end with: build `intersecting` from `globs_intersect`; append to result if non-empty; return. No `if not intersecting` block, no `_same_parent` calls.
- **`globs_intersect` body is byte-identical to pre-fix.** Diff the function body against `main`'s version — only the import list / module docstring / surrounding code may differ. Any incidental rewrite to `globs_intersect` is HIGH.
- **`_strip_test_globs` body is byte-identical to pre-fix.** Same check.

### 2. Docstring update

- The module's top docstring carries an I-00099 note explaining the sibling-rule removal, the two motivating cases (CR-00057 ↔ CR-00060 docs and daemon modules), and the remaining safety nets. Missing or vague note is MEDIUM (fixable).

### 3. Scope compliance

- `files_changed` lists ONLY `orch/daemon/scope_overlap.py`. Anything else is CRITICAL `architecture` finding (scope creep).
- `orch/daemon/batch_manager.py` is NOT in `files_changed`. S01 was told to verify the caller contract READ-ONLY. Any modification there is CRITICAL.

### 4. Caller-contract verification

- The S01 report's `notes` field must confirm the agent inspected `batch_manager.py:_launch_pending_items` and verified the event-emission site still receives accurate globs from `find_blocking_items` (now that the only source is `globs_intersect`). Missing confirmation is MEDIUM (fixable) — the agent must amend the report.

### 5. TDD RED evidence

- The S01 report's `tdd_red_evidence` field must be `"n/a — pure code removal; reproduction + regression tests are added in S03 by tests-impl"` or equivalent. The S03 step owns the new behavioural tests.

### 6. Code quality

- Read `CLAUDE.md` and `orch/CLAUDE.md`.
- Imports: if `fnmatch` or any other import was used ONLY by `_same_parent`, confirm it is removed from the import block. Unused imports are a `ruff` violation and would have surfaced at lint, but flag explicitly.

## Test Verification (NON-NEGOTIABLE)

Run the targeted unit tests:

```bash
uv run pytest tests/unit/daemon/test_scope_overlap.py -v
```

Expected:
- All glob-intersect and I-00071 test-path-stripping tests pass.
- `test_non_test_sibling_still_blocks` FAILS — this is the documented behavioural change. S03 deletes this test. If it passes, the sibling rule was NOT removed cleanly — CRITICAL finding.

## Severity Levels

Standard table — CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00099",
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
  "test_summary": "X passed, 1 failed (test_non_test_sibling_still_blocks — expected; S03 deletes it)",
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL/HIGH and zero MEDIUM (fixable).
