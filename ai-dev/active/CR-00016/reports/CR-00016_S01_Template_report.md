# CR-00016 S01 — Template Report

## What was done

1. Created `docs/IW_AI_Core_Agent_Constraints.md` — the authoritative policy document with R1 (Docker rule, verbatim from design doc) and a skeleton for future rules (R2 reserved).

2. Inserted the Docker rule block verbatim into all 11 prompt templates in `ai-dev/templates/`:
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

3. Updated `.claude/skills/iw-workflow/SKILL.md` with a "Global agent constraints" section near the top, referencing the policy doc and summarizing the Docker rule.

4. Updated `skills/iw-workflow/SKILL.md` (master copy) with the same constraint block.

## Files changed

| File | Action |
|------|--------|
| `docs/IW_AI_Core_Agent_Constraints.md` | Created |
| `ai-dev/templates/Implementation_Prompt_Template.md` | Modified |
| `ai-dev/templates/CodeReview_Prompt_Template.md` | Modified |
| `ai-dev/templates/CodeReview_FIX_Prompt_Template.md` | Modified |
| `ai-dev/templates/CodeReview_Final_Prompt_Template.md` | Modified |
| `ai-dev/templates/CodeReview_FIX_Final_Prompt_Template.md` | Modified |
| `ai-dev/templates/QualityValidation_Template.md` | Modified |
| `ai-dev/templates/QualityValidation_FIX_Prompt_Template.md` | Modified |
| `ai-dev/templates/QVBrowser_Prompt_Template.md` | Modified |
| `ai-dev/templates/CR_Design_Template.md` | Modified |
| `ai-dev/templates/Feature_Design_Template.md` | Modified |
| `ai-dev/templates/Issue_Design_Template.md` | Modified |
| `.claude/skills/iw-workflow/SKILL.md` | Modified |
| `skills/iw-workflow/SKILL.md` | Modified |

## Verification

- `grep -l "⛔ Docker is off-limits" ai-dev/templates/*.md` → all 11 files listed
- `grep -c "⛔ Docker is off-limits" ai-dev/templates/Implementation_Prompt_Template.md` → 1
- `grep "Docker" .claude/skills/iw-workflow/SKILL.md` → constraint block confirmed
- `make lint` → pre-existing lint errors (unrelated to this CR: ARG001 in `orch/cli/item_commands.py:593` and E501 in `tests/integration/test_code_qa_routes.py:226`)

## Notes

- Lint errors are pre-existing and not caused by this step.
- `skills/iw-workflow/SKILL.md` existed and was updated (both `.claude/skills/` and `skills/` now in sync).
- CLAUDE.md files untouched (S03 responsibility).
- `docs/IW_AI_Core_DB_Setup.md` cross-reference left as-is (S03 responsibility).