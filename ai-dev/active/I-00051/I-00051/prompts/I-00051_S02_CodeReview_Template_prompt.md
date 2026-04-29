# I-00051_S02_CodeReview_Template_prompt

**Work Item**: I-00051 — Code review steps do not run linters — ARG and format errors reach QV gates
**Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00051/I-00051_Issue_Design.md` — acceptance criteria
- `ai-dev/active/I-00051/reports/I-00051_S01_Template_report.md` — S01 report
- `ai-dev/templates/CodeReview_Prompt_Template.md` — updated template
- `ai-dev/templates/CodeReview_Final_Prompt_Template.md` — updated template
- `templates/design/CodeReview_Prompt_Template.md` — master copy
- `templates/design/CodeReview_Final_Prompt_Template.md` — master copy

## Output Files

- `ai-dev/active/I-00051/reports/I-00051_S02_CodeReview_Template_report.md` — review report

## Context

Review the template edits made in S01. The fix adds a `Pre-Review Lint & Format Gate (NON-NEGOTIABLE)` section to both code review templates.

## Review Checklist

### Correctness
- [ ] The new section appears **before** the `## Review Checklist` (or first review section) — agents must run linters before reading code
- [ ] The section is titled `## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)` — the NON-NEGOTIABLE label must be present
- [ ] The section instructs: `make lint` AND `make format` (the Makefile `format` target runs `ruff format --check` — check-only, does NOT auto-fix)
- [ ] New violations are classified as **CRITICAL** findings with `"category": "conventions"`, `"file"`, `"line"`, and `"description"` fields
- [ ] A blocker instruction exists for when `make` is unavailable
- [ ] The vague "2. Run lint and type checking" line has been removed from `Test Verification` (no duplication)

### AC Verification
- [ ] AC1: `make lint` instruction is present and NON-NEGOTIABLE (not soft/optional language)
- [ ] AC2: `make format` instruction is present (Makefile `format` target = `ruff format --check`, check-only)
- [ ] AC3: The Final template has the same section
- [ ] AC4: `diff ai-dev/templates/CodeReview_Prompt_Template.md templates/design/CodeReview_Prompt_Template.md` returns no diff
- [ ] AC4: `diff ai-dev/templates/CodeReview_Final_Prompt_Template.md templates/design/CodeReview_Final_Prompt_Template.md` returns no diff

### Skills Sync
- [ ] S01 report confirms `iw skills sync` was run and succeeded

### Format / Lint
- [ ] `make lint` reports no new violations (Markdown changes don't affect ruff)
- [ ] No accidental Python file edits

## Severity Rubric

| Severity | Meaning |
|----------|---------|
| CRITICAL | Section missing, or the format command is `ruff format` (direct, no `--check`) — agents must use `make format` which already runs `--check` |
| HIGH | Section present but labelled optional, or CRITICAL classification missing |
| MED | Wording unclear, or master copy not synced |
| LOW | Minor phrasing nit |

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00051",
  "overall_status": "pass|fail",
  "mandatory_fix_count": 0,
  "findings": []
}
```

Then call:
```bash
uv run iw step-done I-00051 --step S02 \
  --report ai-dev/active/I-00051/reports/I-00051_S02_CodeReview_Template_report.md
```
