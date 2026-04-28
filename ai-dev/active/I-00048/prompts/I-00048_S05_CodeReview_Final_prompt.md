# I-00048_S05_CodeReview_Final_prompt

**Work Item**: I-00048 — Prompts and manifest not copied into worktree — agents thrash on orientation every step
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01, S03

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Input Files

- Design document: `ai-dev/active/I-00048/I-00048_Issue_Design.md`
- All implementation reports: `ai-dev/active/I-00048/reports/I-00048_S01_Backend_report.md`, `ai-dev/active/I-00048/reports/I-00048_S03_Tests_report.md`
- All code review reports: `ai-dev/active/I-00048/reports/I-00048_S02_CodeReview_Backend_report.md`, `ai-dev/active/I-00048/reports/I-00048_S04_CodeReview_Tests_report.md`
- Modified files: `executor/worktree_setup.sh`, `tests/unit/test_worktree_setup_context_copy.py`
- Conventions: `CLAUDE.md`, `executor/CLAUDE.md`, `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00048/reports/I-00048_S05_CodeReviewFinal_report.md`

---

## Context

You are performing the final cross-agent review of ALL work for I-00048. This fix adds Step 7 to `executor/worktree_setup.sh` and writes tests to verify the behavior. The key invariant to check is that the implementation correctly solves the problem WITHOUT introducing merge collisions.

---

## Review Checklist

### 1. Completeness vs design document

- Does the copy step handle the case where `ai-dev/active/<ID>/` does not exist (silent skip)?
- Are all three exclude patterns written: `prompts/`, `workflow-manifest.json`, `*.md`?
- Is `reports/` intentionally NOT excluded?
- Does `git -C "$WORKTREE_DIR" rev-parse --git-dir` return the per-worktree gitdir (not the main `.git/`)?
- Is the relative path resolved to absolute before writing to `info/exclude`?
- Is `mkdir -p "$WORKTREE_GITDIR/info"` called before writing?
- Does `>>` append (not overwrite) to `info/exclude`?

### 2. Merge collision invariant — critical check

This is the highest-risk area. Verify:

- After `_run_copy_and_exclude()`, running `git add -A` in the worktree must NOT stage the copied files
- The tests explicitly test this (not just file existence)
- No new stdout `echo` was added after the new step in `worktree_setup.sh` (the last stdout line must remain `echo "$WORKTREE_DIR"`)

### 3. Stdout hygiene in worktree_setup.sh

- All messages in the new step use `>&2`
- The daemon-consumed `echo "$WORKTREE_DIR"` is still the last stdout line
- No conditional could cause a different last line

### 4. Test semantic correctness

- Do tests assert specific file paths and specific content (not just directory existence)?
- Does the git-staging test assert specific filenames are absent from `git status --porcelain` output?
- Does the exclude-content test assert all three specific patterns AND that `reports/` is absent?
- Do tests use real git repos (subprocess + git init + git worktree add)?

### 5. Regression test adequacy

- Would removing the `info/exclude` write from `worktree_setup.sh` cause a test to fail? (Yes — the staging test)
- Would removing the `cp -r` call cause a test to fail? (Yes — the file-existence test)
- Is there a test for the no-op case (missing `ai-dev/active/<ID>/` directory)?

### 6. No out-of-scope changes

- Does `worktree_setup.sh` have any changes beyond Step 7?
- Are there any Python file changes outside the new test file?

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make lint
make typecheck
```

Run the full suite. Integration tests may be skipped if they require external services not available in this worktree, but report this explicitly.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00048",
  "steps_reviewed": ["S01", "S03"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
