# I-00048_S04_CodeReview_Tests_prompt

**Work Item**: I-00048 — Prompts and manifest not copied into worktree — agents thrash on orientation every step
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

## Input Files

- Design document: `ai-dev/active/I-00048/I-00048_Issue_Design.md`
- S03 report: `ai-dev/active/I-00048/reports/I-00048_S03_Tests_report.md`
- New test file: `tests/unit/test_worktree_setup_context_copy.py`
- Test conventions: `tests/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00048/reports/I-00048_S04_CodeReview_Tests_report.md`

---

## Context

You are reviewing the tests written in S03 for I-00048. The tests verify that `worktree_setup.sh` Step 7 correctly copies `ai-dev/active/<ID>/` context files into the worktree and excludes them from git tracking.

---

## Review Checklist

### 1. Reproduction test exists and targets the bug scenario

- Is there a test that would FAIL if Step 7 were removed from `worktree_setup.sh`?
- Does the test verify a specific file exists (not just a directory)?
- Does the test verify file CONTENT, not just existence?

### 2. Semantic correctness — specific assertions, not shape checks

- BAD: `assert (worktree / "ai-dev").exists()` — shape only
- GOOD: `assert (worktree / "ai-dev/active/I-00048/prompts/I-00048_S01_Backend_prompt.md").exists()` — specific
- BAD: `assert exclude_content` — non-empty check only
- GOOD: `assert "ai-dev/active/I-00048/prompts/" in exclude_content` — specific pattern
- Does every `assert` verify a specific expected value, not just presence?

### 3. Git staging test — the merge-safety invariant

- Is there a test that runs `git add -A` in the worktree and verifies the copied files do NOT appear in `git status --porcelain`?
- This is the most important test — without it, the exclude mechanism could silently regress.
- Does the test check that SPECIFIC filenames (e.g., `I-00048_S01_Backend_prompt.md`) are absent from staged output?
- Does it also verify that reports (`reports/`) are NOT excluded (i.e., they DO appear as untracked/staged)?

### 4. Exclude file content test

- Is there a test that reads the `info/exclude` file and checks for all three required patterns?
- Does it verify that `reports/` is NOT in the exclude file?

### 5. No-op / idempotency test

- Is there a test that verifies the step skips silently when `ai-dev/active/<ID>/` doesn't exist?
- Does it verify the worktree remains clean (no error raised, no unexpected files created)?

### 6. Real git repos — no mocking

- Do the tests use real git repos (via `subprocess` + `git init` + `git worktree add`)?
- Is `git rev-parse --git-dir` called against the actual worktree (not the main repo)?
- Are there any mocked git operations? (Should be none — git behavior must be real.)

### 7. Test isolation and naming

- Does each test use `tmp_path` to avoid polluting the repo?
- Do test function names clearly describe the specific invariant they check?
- Are tests independent (no shared mutable state between tests)?

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make lint
make typecheck
```

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00048",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
