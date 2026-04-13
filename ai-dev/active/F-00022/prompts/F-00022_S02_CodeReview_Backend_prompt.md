# F-00022_S02_CodeReview_Backend_prompt

**Work Item**: F-00022 — iw-research Skill
**Step**: S02
**Reviewing**: S01 Backend (skill files)
**Agent**: code-reviewer

---

## Input Files

- `ai-dev/active/F-00022/F-00022_Feature_Design.md`
- `ai-dev/active/F-00022/reports/F-00022_S01_Backend_report.md`
- `skills/iw-research/SKILL.md`
- `skills/iw-research/references/modes.md`
- `skills/iw-research/references/output_format.md`

## Output Files

- `ai-dev/active/F-00022/reports/F-00022_S02_CodeReview_Backend_report.md`

## Context

Review the `iw-research` skill files against the IW skill creation guide and design spec.

**Reference**: `skills/40-GUIDE_TO_CREATE_CLAUDE_SKILLS.md`

## Review Checklist

### SKILL.md Frontmatter

- [ ] `name` is `iw-research` (≤ 64 chars, no "anthropic"/"claude")
- [ ] `description` includes WHAT (produces filed research doc, 4 modes) AND WHEN (research X, investigate Y, /iw-research)
- [ ] `description` ≤ 1024 chars
- [ ] `allowed-tools` lists all tools used in the workflow
- [ ] `argument-hint` present

### SKILL.md Body

- [ ] ≤ 500 lines (count with `wc -l`)
- [ ] Step 1 is `iw next-id --type research` (immediate, before anything else)
- [ ] Step 2 is mandatory user interaction (mode + scope)
- [ ] GO checkpoint is explicit before any web tool calls
- [ ] All 4 modes documented (tech, market, deep, general)
- [ ] Mode → tool mapping clear (context7 for tech/deep, not for market/general)
- [ ] `iw register` + `iw doc-update --doc-type research` both present in Step 6
- [ ] Editorial category mapping documented (tech→technical, market→marketing, deep/general→functional)
- [ ] Constraints section with MUST/NEVER rules

### Output format requirements

- [ ] Mandatory source citations (URL inline per claim) specified
- [ ] Confidence markers `[HIGH/MEDIUM/LOW]` specified as required
- [ ] Output document template references `references/output_format.md`

### IW Pattern Compliance

Compare with `iw-new-feature/SKILL.md` pattern:
- [ ] Same discipline: `iw next-id` first, user interaction second, GO checkpoint third
- [ ] Same constraint style: MUST/NEVER rules at the end
- [ ] NEVER implement code — skill only produces documentation
- [ ] OpenCode compatibility noted (OPENCODE_ENABLE_EXA=1)

### Progressive Disclosure

- [ ] Core workflow in SKILL.md; details in references/
- [ ] References are one level deep (no nested references)
- [ ] All referenced files exist

### Quality

- [ ] No time-sensitive information
- [ ] Forward slashes in all paths
- [ ] Consistent terminology (no mixing "mode" and "type")
- [ ] No verbose explanations — concise, Claude is smart

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview_Backend",
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
