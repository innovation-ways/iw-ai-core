# F-00067_S06_CodeReview_Template_prompt

**Work Item**: F-00067 — Documentation Visual Design Overhaul
**Step Being Reviewed**: S03 (Skills/Template updates)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

---

## Input Files

- `ai-dev/active/F-00067/F-00067_Feature_Design.md` — Design doc
- `ai-dev/active/F-00067/reports/F-00067_S03_Template_report.md` — S03 implementation report
- `skills/iw-doc-generator/references/module-doc-template.md`
- `skills/iw-doc-generator/references/diagram-guidelines.md`
- `skills/iw-tech-doc-writer/references/diagram-guidelines.md`

## Output Files

- `ai-dev/active/F-00067/reports/F-00067_S06_CodeReview_Template_report.md`

---

## Context

Review the skill file updates made in S03. Focus on: completeness of the color palette, "Why paragraph" rule presence, callout usage guidance, and whether `iw skills sync` was run.

## Review Checklist

### 1. Color palette completeness
- Verify all 6 color classes (api, data, worker, external, ui, core) are in `diagram-guidelines.md` with correct hex values matching the canonical palette in the design doc.
- Verify the same palette appears in `iw-tech-doc-writer/references/diagram-guidelines.md`.

### 2. "Why" paragraph rule
- Verify the rule is present in BOTH skill files' diagram guidelines.
- Verify an example is provided.

### 3. Module doc template
- Verify `## Why Read This` section is present at the top with the `[!NOTE]` callout.
- Verify `## Key Diagrams` section exists.
- Verify callout usage guidance is present as a comment.

### 4. iw skills sync
- Verify S03 report confirms `iw skills sync` was run.
- Check if sync errors are noted (non-blocking — should be reported, not failed).

### 5. Formatting quality
- Verify Markdown tables are aligned and render correctly.
- Verify code blocks in skill files use appropriate fences.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "F-00067",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "N/A — markdown files",
  "notes": ""
}
```
