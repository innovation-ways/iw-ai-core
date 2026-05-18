# I-00099_S04_CodeReview_Tests_prompt

**Work Item**: I-00099 -- Scope-overlap sibling-dir rule generates false-positive cross-batch holds
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00099 --json`.
- `ai-dev/active/I-00099/I-00099_Issue_Design.md` — design document
- `ai-dev/work/I-00099/reports/I-00099_S03_Tests_report.md` — S03 step report
- `tests/unit/daemon/test_scope_overlap.py` — file S03 modified
- `orch/daemon/scope_overlap.py` — module under test
- `skills/iw-ai-core-testing/SKILL.md` — test red-flag checklist (MUST consult)

## Output Files

- `ai-dev/work/I-00099/reports/I-00099_S04_CodeReview_report.md` — Review report

## Context

You are reviewing S03's test additions for **I-00099**. The fix is purely subtractive on the production side; this review focuses on whether the tests adequately codify the bug's reproduction and lock in the remaining behaviour.

## Read the Design Document FIRST

- **Acceptance Criteria AC2 and AC3** are S03's responsibility. AC2 says the reproducing test passes; AC3 says exact-file and glob-anchor overlaps still block. Verify both are covered.
- **TDD Approach section** lists every test S03 must produce. Cross-check against `files_changed`.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations on the changed file are CRITICAL `conventions` findings.

## Review Checklist

### 1. Coverage of the design's named tests (CRITICAL anchors)

- `TestI00099SiblingDirNoLongerBlocks` class exists.
- `test_two_different_docs_in_same_dir_do_not_block` exists and uses the **exact** path strings from the design: `docs/IW_AI_Core_Testing_Strategy.md` (candidate) and `docs/IW_AI_Core_AI_Assistant_Models.md` (in-flight). Any other strings → CRITICAL.
- `test_two_different_daemon_modules_do_not_block` exists and uses the exact strings: `orch/daemon/batch_manager.py` (candidate) and `orch/daemon/project_registry.py` (in-flight). Any other strings → CRITICAL.
- At least one test covers **exact-file match still blocks** (AC3).
- At least one test covers **glob-anchor (`dir/**`) still blocks** (AC3).
- Bonus glob-anchor "other direction" test (candidate has `**`, in-flight has specific file). MEDIUM (suggestion) if missing.

### 2. Obsolete test deletion (CRITICAL anchor)

- `grep -n "test_non_test_sibling_still_blocks" tests/unit/daemon/test_scope_overlap.py` MUST return zero matches. If it still appears (even commented out), CRITICAL — the design explicitly requires deletion.

### 3. Docstring refresh

- `TestI00071RegressionBatch00078` class docstring no longer claims the sibling-directory check is the protection. New docstring references `_strip_test_globs` as the still-meaningful guard. MEDIUM (fixable) if missing.

### 4. Semantic correctness of assertions

Per the I003 lesson and the `iw-ai-core-testing` skill:

- Each new test asserts the **specific** return value (`result == []`, `len(result) == 1`, `result[0][0] == "I-..."`, glob string in `result[0][1]`). HIGH finding for any test that asserts only `not result` or `isinstance(result, list)`.
- The "blocks" sanity tests must verify BOTH the item ID AND the conflicting glob — not just that the result is non-empty.
- The "must not block" tests must use `result == []` (exact-empty), not `not result` (which also accepts `None` and would mask a regression).

### 5. Test-file location

- All edits are in `tests/unit/daemon/test_scope_overlap.py`. No new test files; no edits to `tests/integration/` (the integration coverage of this code path lives in `tests/integration/daemon/test_batch_manager_scope_gate.py` and is checked by S05's final review + S10's QV gate).

### 6. Scope compliance

- `files_changed` lists ONLY `tests/unit/daemon/test_scope_overlap.py`. Anything else is CRITICAL.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/daemon/test_scope_overlap.py -v
```

Expected: 0 failed, all classes pass. If any failure, CRITICAL — S03 didn't verify its own work.

## Severity Levels

Standard table.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00099",
  "step_reviewed": "S03",
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
  "test_summary": "N passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL/HIGH and zero MEDIUM (fixable).
