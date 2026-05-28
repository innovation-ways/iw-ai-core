# I-00116_S06_CodeReview_Backend_prompt

**Work Item**: I-00116
**Step**: S06
**Agent**: CodeReview (reviewing S05 — prompt-template scoping)

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy.

## Scope of review

ONLY `agents/code-review-impl.md`, `commands/code-review-impl.md`, `skills/iw-workflow/SKILL.md`. Flag any other change as CRITICAL scope violation.

## Input Files

- **Runtime state**: `uv run iw item-status I-00116 --json`
- **Design**: `ai-dev/active/I-00116/I-00116_Issue_Design.md`
- **S05 report**: `ai-dev/active/I-00116/reports/I-00116_S05_Backend_report.md`
- **The changed files** (read all three)
- **Reference**: `executor/worktree_commit.sh` Step 2.25 (the merge-time enforcement the prompt change aligns with)

## Output Files

- Review report: `ai-dev/active/I-00116/reports/I-00116_S06_CodeReview_report.md`

## Review Checklist

| # | Check |
|---|-------|
| 1 | Both `agents/code-review-impl.md` AND `commands/code-review-impl.md` are modified (synced master + daemon copy) |
| 2 | Both files now reference `scope.allowed_paths` as the authoritative diff scope source |
| 3 | Neither file still instructs the reviewer to use un-bounded `git diff HEAD` / `git status` |
| 4 | The two prompt files are CONGRUENT (their diff-scoping guidance is functionally identical — minor wording variation OK, but the rule must be the same) |
| 5 | `skills/iw-workflow/SKILL.md` documents the convention with a clear cross-reference to `executor/worktree_commit.sh` Step 2.25 |
| 6 | The new SKILL.md section is placed under the existing "Code Review" structure (not in an unrelated section) |
| 7 | Existing markdown formatting and structure are preserved in all three files |
| 8 | No daemon code, no test files, no other files were touched |

## Required Pre-flight Gates

```bash
make lint
make format-check
```

## Verdict Contract

Same JSON contract block as S02. Verdict `pass` or `fail`. Findings array empty if pass.

## Step Done Contract

Call `iw step-done S06 --report ai-dev/active/I-00116/reports/I-00116_S06_CodeReview_report.md` before exit. Never exit without calling `iw step-done` or `iw step-fail`.
