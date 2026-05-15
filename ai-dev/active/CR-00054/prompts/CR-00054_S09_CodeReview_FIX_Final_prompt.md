# CR-00054_S09_CodeReview_FIX_Final_prompt

**Work Item**: CR-00054 -- Add OpenCode stub to worktree E2E stack
**Step**: S09
**Agent**: code-review-fix-final-impl

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds NO migrations.

## Input Files

- `ai-dev/active/CR-00054/reports/CR-00054_S08_CodeReviewFinal_report.md` — findings
- All files touched by S01–S07

## Output Files

- Modified source files (limited to `scope.allowed_paths`)
- `ai-dev/active/CR-00054/reports/CR-00054_S09_CodeReviewFixFinal_report.md`

## Context

You are applying CRITICAL and HIGH fixes from S08's cross-agent final review. If S08 was clean (no CRITICAL/HIGH findings), this step is a no-op — write a one-line pass-through report and report `completion_status: complete`.

## Requirements

Same as S07, scoped to S08's findings.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-fix-final-impl",
  "work_item": "CR-00054",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["..."],
  "preflight": {
    "format": "ok|fixed|n/a",
    "typecheck": "ok|n/a",
    "lint": "ok|n/a"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed | n/a — no-op pass-through",
  "tdd_red_evidence": "n/a",
  "blockers": [],
  "notes": ""
}
```
