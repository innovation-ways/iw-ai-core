# CR-00023_S08_CodeReview_Template_prompt

**Work Item**: CR-00023 — Make iw item-status the runtime source of truth for step list and per-step runtime info
**Step**: S08
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/CR-00023/CR-00023_CR_Design.md` — design (AC5)
- `ai-dev/active/CR-00023/reports/CR-00023_S07_Template_report.md` — S07 report
- 8 modified templates (4 in `templates/design/`, 4 in `ai-dev/templates/`)
- 8 templates that should NOT have changed (the FIX + Browser variants)

## Output Files

- `ai-dev/active/CR-00023/reports/CR-00023_S08_CodeReview_Template_report.md`

## Review Checklist

### Hint added correctly
- [ ] All 8 in-scope templates contain the new hint as the first bullet of "## Input Files"
- [ ] The hint text matches verbatim across all 8 files (no copy-paste drift)
- [ ] The hint mentions `iw item-status`, references `workflow-manifest.json`, and includes the CR-00023 marker
- [ ] No other lines were modified in any template (run `git diff --stat` on each — should show +1 line per file)

### Excluded files untouched
- [ ] `QualityValidation_FIX_Prompt_Template.md` (both copies) is unchanged
- [ ] `CodeReview_FIX_Prompt_Template.md` (both copies) is unchanged
- [ ] `CodeReview_FIX_Final_Prompt_Template.md` (both copies) is unchanged
- [ ] `QVBrowser_Prompt_Template.md` (both copies) is unchanged
- [ ] No `*_Design_Template.md` was modified
- [ ] No `*.py` file was modified in this step

### Directory sync (per `feedback_skills_sync.md`)
- [ ] `diff templates/design/Implementation_Prompt_Template.md ai-dev/templates/Implementation_Prompt_Template.md` returns no output
- [ ] Same for CodeReview, CodeReview_Final, QualityValidation pairs
- [ ] If any diff shows differences, that's a CRITICAL finding — the two directories must be in lockstep

### Wording quality
- [ ] The hint reads naturally as the first bullet (not jarring against the existing list)
- [ ] No markdown formatting bugs (mismatched backticks, broken bullet syntax)

### Pre-flight section in `Implementation_Prompt_Template.md` (S07 §7 — folds in I-00041 finding [3])
- [ ] BOTH copies of `Implementation_Prompt_Template.md` (`templates/design/` and `ai-dev/templates/`) contain a new section titled exactly `## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023`
- [ ] The new section is placed IMMEDIATELY BEFORE `## Test Verification (NON-NEGOTIABLE)` (not at the bottom; not after Subagent Result Contract)
- [ ] The section explicitly names all three commands: `make format`, `make typecheck`, `make lint`
- [ ] The section instructs agents that skipping wastes a fix-cycle slot (motivation is preserved so a future editor doesn't strip the section as "verbose")
- [ ] The Subagent Result Contract example in the same template now contains a `preflight` object with keys `format`, `typecheck`, `lint`
- [ ] The `preflight` object appears immediately after `files_changed` and before `tests_passed` (correct ordering)
- [ ] The two Implementation template copies are byte-identical (`diff` returns no output)
- [ ] The pre-flight section is ABSENT from the other 7 in-scope templates (CodeReview, CodeReview_Final, QualityValidation in both dirs)
- [ ] The pre-flight section is ABSENT from the FIX templates and `QVBrowser_Prompt_Template.md`
- [ ] The pre-flight section is ABSENT from `*_Design_Template.md` files

## Findings Severity

- **CRITICAL**: any in-scope template missing the hint; any out-of-scope template was modified; directory pairs not in lockstep; pre-flight section missing from Implementation template OR present in any other template; `preflight` field missing from the Implementation template's Subagent Result Contract
- **HIGH**: hint text varies between files; hint placed in the wrong section; pre-flight section placed in the wrong location within the Implementation template; `preflight` field present but missing one of `format`/`typecheck`/`lint`
- **MEDIUM**: minor wording / markdown rendering issues; pre-flight section title differs from the canonical form
- **LOW**: stylistic preferences

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "CR-00023",
  "completion_status": "complete",
  "files_reviewed": [
    "templates/design/Implementation_Prompt_Template.md",
    "templates/design/CodeReview_Prompt_Template.md",
    "templates/design/CodeReview_Final_Prompt_Template.md",
    "templates/design/QualityValidation_Template.md",
    "ai-dev/templates/Implementation_Prompt_Template.md",
    "ai-dev/templates/CodeReview_Prompt_Template.md",
    "ai-dev/templates/CodeReview_Final_Prompt_Template.md",
    "ai-dev/templates/QualityValidation_Template.md"
  ],
  "findings": {
    "critical": 0,
    "high": 0,
    "medium": 0,
    "low": 0
  },
  "verdict": "approved|fix-required",
  "blockers": [],
  "notes": ""
}
```
