# I-00084 S04 — Code Review: Tests

**Step**: S04
**Agent**: code-review-impl
**Date**: 2026-05-15
**Verdict**: pass

---

## Files Reviewed

- `tests/integration/test_worktree_setup_origin_main_sync.py`
- `executor/worktree_setup.sh` (implementation under test)
- `Makefile` (diff-coverage target)
- `ai-dev/active/I-00084/I-00084_Issue_Design.md` (AC definitions)
- `ai-dev/active/I-00084/reports/I-00084_S03_Tests_report.md` (TDD red evidence)

---

## Note on Prior Report

A prior run of this step produced a `needs-fix` verdict citing three issues:
(CRITICAL) misleading docstring in test 2, (HIGH) missing structural guard
comments, (MEDIUM) missing `test_i00084_` prefix. Reading the actual current
test file confirms all three issues were addressed before this review ran:

- All five test methods carry the `test_i00084_` prefix.
- Test 2 docstring correctly states: "This test exercises the git command in
  isolation (not via worktree_setup.sh)."
- Tests 4 and 5 docstrings include "code-path presence check (structural guard),
  not a behavioral test."

The verdict below reflects the current state of the file.

---

## Checklist Results

### CRITICAL

**C1 — Reproduction test would fail pre-fix**: PASS

Tests 4 (`test_i00084_makefile_diff_coverage_sync_command_is_present`) and
5 (`test_i00084_worktree_setup_sh_sync_command_is_present`) are structural guards
that assert the substring `"fetch . main:refs/remotes/origin/main"` is present in
the Makefile and `executor/worktree_setup.sh` respectively. Both would FAIL against
pre-S01 code. Confirmed by S01 TDD red evidence:

```
FAILED test_i00084_makefile_diff_coverage_sync_command_is_present
FAILED test_i00084_worktree_setup_sh_sync_command_is_present
2 failed, 3 passed in 10.61s (before fix)
```

**C2 — Semantic assertions only (no shape checks)**: PASS

All behavioral tests assert on git SHA values:
- `assert origin_main_in_worktree == stale_sha` (test 1)
- `assert origin_main_after == current_main_sha` (tests 2 and 3)

The structural guards (tests 4 and 5) are explicitly documented as
"code-path presence check (structural guard), not a behavioral test."
The checklist permits structural guards when documented as such; it only
prohibits undocumented shape checks presented as semantic tests.

---

### HIGH

**H1 — Both ACs covered (sync happens, idempotent)**: PASS

| AC | Test(s) |
|----|---------|
| AC1 — sync happens | `test_i00084_origin_main_matches_local_main_after_sync` (behavioral) + `test_i00084_worktree_setup_sh_sync_command_is_present` (structural) |
| AC1 — idempotent | `test_i00084_sync_is_idempotent` |
| AC2 — regression test in suite | `test_i00084_worktree_setup_sh_sync_command_is_present` |
| AC3 — Makefile fix | `test_i00084_makefile_diff_coverage_sync_command_is_present` |

**H2 — Test cleans up `tmp_path`**: PASS

All five tests receive `tmp_path` from pytest. Pytest auto-cleanup is sufficient. ✓

**H3 — No live DB / network**: PASS

Tests use only `subprocess.run(["git", ...])` under `tmp_path`. No DB access,
no real network, no testcontainer. ✓

---

### MEDIUM

**M1 — Test naming (`test_i00084_<scenario>`)**: PASS

All five tests carry the `test_i00084_` prefix. ✓

**M2 — Helper for fake-repo setup is small / readable**: PASS

`_make_repo_with_stale_origin_main` (~35 lines) is clean:
- Creates a repo under `tmp_path` (no global state)
- Sets up stale `origin/main` via `git update-ref`
- Adds 5 commits to advance local main
- Asserts the precondition inline before returning
- Returns `(repo, stale_sha, current_main_sha)` — clean tuple ✓

---

## Observations (Not Findings)

**Behavioral/structural split**: Tests 1–3 are behavioral and test the git command
in isolation via `_apply_origin_main_sync()`; they do not invoke `worktree_setup.sh`
directly. The regression guard for the script fix is the structural test 5. This
separation exists because testing `worktree_setup.sh` end-to-end requires `iw
item-status` (which needs a DB), making it unsuitable for the testcontainer layer.
The split is correctly documented in every docstring.

**Structural guard scope**: Tests 4 and 5 assert the fix string appears anywhere in
the target file — not that it's in the correct position or uncommented. In practice
the fix is on line 90, immediately after `git worktree add` (line 85), with an
`# I-00084:` comment. Positioning is not at risk of accidental drift.

---

## Summary

All CRITICAL, HIGH, and MEDIUM criteria are satisfied. The five tests are well-named,
well-documented, use semantic SHA comparisons in behavioral paths, use properly
labeled structural guards for code-path checks, and two of them (tests 4 and 5)
would fail against pre-S01 code.

**Verdict: PASS — no changes required.**
