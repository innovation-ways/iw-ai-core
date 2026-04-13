# F-00022_S03_CodeReview_Final_prompt

**Work Item**: F-00022 — iw-research Skill
**Step**: S03
**Agent**: code-reviewer

---

## Input Files

- `ai-dev/active/F-00022/F-00022_Feature_Design.md`
- `ai-dev/active/F-00022/reports/F-00022_S01_Backend_report.md`
- `ai-dev/active/F-00022/reports/F-00022_S02_CodeReview_Backend_report.md`
- `skills/iw-research/SKILL.md`
- `skills/iw-research/references/modes.md`
- `skills/iw-research/references/output_format.md`

## Output Files

- `ai-dev/active/F-00022/reports/F-00022_S03_CodeReview_Final_report.md`

## Context

Final review of the iw-research skill. Verify completeness against design spec.
**Note**: Deployment (sync to `.claude/skills/`) happens in QV S05 — not here.

## Final Checklist

### Completeness against design spec

- [ ] All 7 workflow steps present (reserve ID, scope, GO, research, write, register, report)
- [ ] All 4 modes with distinct tool chains
- [ ] Source citation requirement documented
- [ ] Confidence markers documented
- [ ] `iw register` + `iw doc-update --doc-type research` both present
- [ ] Editorial category mapping (tech/market/deep/general → technical/marketing/functional)
- [ ] OpenCode compatibility note present
- [ ] Prerequisites section notes F-00020 dependency

### Cross-check with S02 findings

- [ ] All CRITICAL and HIGH findings from S02 have been addressed by S01
- [ ] No new issues introduced

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview_Final",
  "work_item": "F-00022",
  "completion_status": "complete",
  "verdict": "PASS|NEEDS_FIX",
  "findings": {
    "critical": 0,
    "high": 0,
    "medium_fixable": 0,
    "medium_suggestion": 0,
    "low": 0
  },
  "mandatory_fix_count": 0,
  "finding_details": [],
  "notes": ""
}
```
