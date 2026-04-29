# I-00051_S03_CodeReview_Final_prompt

**Work Item**: I-00051 — Code review steps do not run linters — ARG and format errors reach QV gates
**Step**: S03
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00051/I-00051_Issue_Design.md` — full bug description and acceptance criteria
- `ai-dev/active/I-00051/reports/I-00051_S01_Template_report.md` — template edits report
- `ai-dev/active/I-00051/reports/I-00051_S02_CodeReview_Template_report.md` — per-agent review
- `ai-dev/templates/CodeReview_Prompt_Template.md`
- `ai-dev/templates/CodeReview_Final_Prompt_Template.md`
- `templates/design/CodeReview_Prompt_Template.md`
- `templates/design/CodeReview_Final_Prompt_Template.md`

## Output Files

- `ai-dev/active/I-00051/reports/I-00051_S03_CodeReview_Final_report.md` — final review report

## Context

Global review of all I-00051 work. The fix is a template-only change adding a mandatory lint/format pre-check to code review prompt templates.

## Review Checklist

### Completeness
- [ ] AC1: `make lint` instruction present and NON-NEGOTIABLE in `CodeReview_Prompt_Template.md`
- [ ] AC2: `make format` present in `CodeReview_Prompt_Template.md` (Makefile `format` target = `ruff format --check`, check-only)
- [ ] AC3: Both ACs also satisfied in `CodeReview_Final_Prompt_Template.md`
- [ ] AC4: Both `templates/design/` master copies are identical to their `ai-dev/templates/` counterparts (run `diff` to verify)

### Critical Distinctions
- [ ] The section uses `make format` — this is correct: the Makefile `format` target runs `ruff format --check .` (check-only, does NOT auto-fix). If the template instead calls `ruff format` directly without `--check`, agents will auto-fix and mask violations — that is the CRITICAL error to catch.
- [ ] The CRITICAL classification instruction specifies all three required fields: `"category": "conventions"`, `"file"`, `"line"` — without `"line"`, the finding is not actionable

### Regression Risk
- [ ] No other sections of the templates were accidentally modified (check diffs)
- [ ] The removed "2. Run lint and type checking" line from Test Verification is not missed elsewhere (the new section fully replaces it)

### Skills Sync
- [ ] `iw skills sync` was run (confirmed in S01 report)

## Severity Rubric

| Severity | Meaning |
|----------|---------|
| CRITICAL | Template calls `ruff format` without `--check` (would auto-fix); or master copies not updated |
| HIGH | Section absent from one of the two templates; or CRITICAL classification not specified |
| MED | Missing one of the three required finding fields |
| LOW | Minor phrasing |

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "code-review-final-impl",
  "work_item": "I-00051",
  "overall_status": "pass|fail",
  "mandatory_fix_count": 0,
  "findings": []
}
```

Then call:
```bash
uv run iw step-done I-00051 --step S03 \
  --report ai-dev/active/I-00051/reports/I-00051_S03_CodeReview_Final_report.md
```
