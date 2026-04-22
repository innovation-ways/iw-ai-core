# CR-00016_S02_CodeReview_prompt

**Work Item**: CR-00016 — Agent prompt hardening
**Step Being Reviewed**: S01 (template-impl)
**Review Step**: S02

---

## Input Files

- `ai-dev/active/CR-00016/CR-00016_CR_Design.md`
- `ai-dev/active/CR-00016/reports/CR-00016_S01_Template_report.md`
- All files in S01's `files_changed`

## Output Files

- `ai-dev/active/CR-00016/reports/CR-00016_S02_CodeReview_report.md`

## Review Checklist

### 1. Policy doc correctness

- `docs/IW_AI_Core_Agent_Constraints.md` exists.
- Structure supports future rules: R1 is labeled, the "Adding rules" section explains the pattern, marker-phrase convention is documented.
- Rule R1 text matches the design doc's **Rule Text** section verbatim (compare character-by-character).
- Cross-references resolve: the link to `docs/IW_AI_Core_DB_Setup.md` works.

### 2. All 11 prompt templates updated

Full list:
- `Implementation_Prompt_Template.md`
- `CodeReview_Prompt_Template.md`
- `CodeReview_FIX_Prompt_Template.md`
- `CodeReview_Final_Prompt_Template.md`
- `CodeReview_FIX_Final_Prompt_Template.md`
- `QualityValidation_Template.md`
- `QualityValidation_FIX_Prompt_Template.md`
- `QVBrowser_Prompt_Template.md`
- `CR_Design_Template.md`
- `Feature_Design_Template.md`
- `Issue_Design_Template.md`

For each: confirm the marker phrase `⛔ Docker is off-limits` appears at least once, the text block matches verbatim (no drift), and the section is at a sensible position (near the top, not buried at the bottom).

Reviewer command:
```bash
for f in ai-dev/templates/*.md; do
  grep -q "⛔ Docker is off-limits" "$f" || echo "MISSING: $f"
done
```

### 3. Rule text verbatim check

Diff the rule block from one template against the design-doc rule block:

```bash
# Extract the section from a template and from the design doc, diff them.
```

Any character-level drift → HIGH severity, fix in place.

### 4. `iw-workflow` SKILL.md

- Contains a constraints section that references `docs/IW_AI_Core_Agent_Constraints.md`.
- Has the summary bullet list of the Docker rule.
- Positioned at a sensible place (top of file, before step-specific guidance).

### 5. Master-copy sync

- If `skills/iw-workflow/SKILL.md` exists: confirm it received the same edit as `.claude/skills/iw-workflow/SKILL.md` (allow for format differences, but the rule content must be present in both).
- If it does NOT exist: the S01 report should explicitly note this.

### 6. Scope creep

- No CLAUDE.md file was touched in S01 (that's S03's scope). Check the git diff — any `CLAUDE.md` under `files_changed` is an HIGH violation.
- No changes to `orch/`, `dashboard/`, `tests/` code (non-prompt files).
- No docs outside `docs/IW_AI_Core_Agent_Constraints.md` were touched.

### 7. Formatting

- Markdown parses cleanly (no unclosed code fences, no broken tables).
- Section numbering / heading levels don't collide with existing sections in each template.
- Link style relative paths.

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW — standard. Fix in place.

## Subagent Result Contract

Same pattern as prior S02 reviews.

## Lifecycle commands

```bash
uv run iw step-start CR-00016 --step S02
uv run iw step-done CR-00016 --step S02 --report ai-dev/active/CR-00016/reports/CR-00016_S02_CodeReview_report.md
```
