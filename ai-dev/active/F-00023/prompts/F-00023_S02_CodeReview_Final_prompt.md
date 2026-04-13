# F-00023_S02_CodeReview_Final_prompt

**Work Item**: F-00023 — iw-research-quick Skill
**Step**: S02
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/F-00023/F-00023_Feature_Design.md`
- `ai-dev/active/F-00023/reports/F-00023_S01_Backend_report.md`
- `skills/iw-research-quick/SKILL.md`

## Output Files

- `ai-dev/active/F-00023/reports/F-00023_S02_CodeReview_Final_report.md`

## Context

Review the iw-research-quick skill, then sync to project.
Reference: `skills/40-GUIDE_TO_CREATE_CLAUDE_SKILLS.md`

## Review Checklist

- [ ] `name` is `iw-research-quick`
- [ ] Description: WHAT (fast inline, no saved doc) AND WHEN (/iw-research-quick, quick question)
- [ ] `allowed-tools` matches tools actually used in instructions
- [ ] ≤ 300 lines body
- [ ] No `iw next-id` or `iw register` anywhere
- [ ] No file creation instructions
- [ ] Max 4 WebFetch calls rule stated
- [ ] `[HIGH/MEDIUM/LOW]` confidence marker on answers
- [ ] Inline source citations per claim
- [ ] Upgrade suggestion to `/iw-research` present
- [ ] Contrast with `iw-research` is clear (quick vs. full workflow)
- [ ] No time-sensitive information, forward slashes

### Sync to all projects

`skills/` in iw-ai-core is the master. The skill must be deployed to every registered project.

```bash
iw sync-skills                            # iw-ai-core (current project)
iw sync-skills --project innoforge        # InnoForge Document Platform
ls .claude/skills/iw-research-quick/SKILL.md && echo "PASS: iw-ai-core synced"
```

Both sync commands must exit 0 before reporting success.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview_Final",
  "work_item": "F-00023",
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
