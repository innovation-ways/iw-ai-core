# I-00051_S01_Template_prompt

**Work Item**: I-00051 — Code review steps do not run linters — ARG and format errors reach QV gates
**Step**: S01
**Agent**: template-impl

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/I-00051/I-00051_Issue_Design.md` — full description, affected files, exact section to add
- `ai-dev/templates/CodeReview_Prompt_Template.md` — per-agent review template to update
- `ai-dev/templates/CodeReview_Final_Prompt_Template.md` — global review template to update
- `templates/design/CodeReview_Prompt_Template.md` — master copy (must match)
- `templates/design/CodeReview_Final_Prompt_Template.md` — master copy (must match)

## Output Files

- `ai-dev/active/I-00051/reports/I-00051_S01_Template_report.md` — step report

## Context

Code review agents currently perform textual review only. They do not run `make lint` or `make format` on changed files, so `ARG001` (unused args) and format violations pass undetected into QV gates, where each burns a fix cycle.

The fix is to add a mandatory **Pre-Review Lint & Format Gate** section to the code review prompt templates so every future code-review-impl and code-review-final-impl agent runs linters before beginning textual inspection.

## Requirements

### 1. Add `Pre-Review Lint & Format Gate` to `CodeReview_Prompt_Template.md`

Insert the following section **immediately before** the existing `## Review Checklist` heading in `ai-dev/templates/CodeReview_Prompt_Template.md`:

```markdown
## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading any code, run these two commands on the files listed in the
implementation report's `files_changed`. Fix nothing yourself — only report.

```bash
make lint          # ruff check — catches ARG001, F811, unused imports, etc.
make format  # ruff format --check — catches formatting drift (does NOT auto-fix)
```

If either command reports NEW violations in the changed files (i.e., violations
that do not appear on the `main` branch before this step), classify each one as
a **CRITICAL** finding in your review result contract with:
- `"category": "conventions"`
- `"file"` and `"line"` from the tool output
- `"description"` quoting the exact violation code and message

If a command is unavailable (e.g., `make` not found), STOP and raise a blocker.
Do NOT skip this step or mark it as optional.
```

Also update the existing `## Test Verification (NON-NEGOTIABLE)` section: remove the vague line "2. Run lint and type checking" since it is now replaced by the explicit gate above.

### 2. Apply the same change to `CodeReview_Final_Prompt_Template.md`

Apply the identical `Pre-Review Lint & Format Gate` section to `ai-dev/templates/CodeReview_Final_Prompt_Template.md` in the same position (before `## Review Checklist` or equivalent). Remove the duplicate vague "Run lint and type checking" line from its `Test Verification` section.

### 3. Sync master copies in `templates/design/`

Copy the updated content to the master copies:
- `templates/design/CodeReview_Prompt_Template.md` — must be identical to `ai-dev/templates/CodeReview_Prompt_Template.md`
- `templates/design/CodeReview_Final_Prompt_Template.md` — must be identical to `ai-dev/templates/CodeReview_Final_Prompt_Template.md`

Use diff to confirm the master copies match before completing.

### 4. Run `iw skills sync`

After updating all four template files, run:

```bash
uv run iw skills sync
```

This propagates the updated templates to managed projects. Report the command output in your step report.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting completion:

1. `make format` — ensure no formatting drift in any modified Markdown (Markdown is not auto-formatted by ruff, but run anyway to catch any accidental .py changes)
2. `make lint` — must report zero new errors
3. Diff the `ai-dev/templates/` and `templates/design/` copies to confirm they are identical

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "template-impl",
  "work_item": "I-00051",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/templates/CodeReview_Prompt_Template.md",
    "ai-dev/templates/CodeReview_Final_Prompt_Template.md",
    "templates/design/CodeReview_Prompt_Template.md",
    "templates/design/CodeReview_Final_Prompt_Template.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "N/A — template-only change",
  "blockers": [],
  "notes": ""
}
```

Then call:
```bash
uv run iw step-done I-00051 --step S01 \
  --report ai-dev/active/I-00051/reports/I-00051_S01_Template_report.md
```
