# F-00022_S01_Backend_report.md

## Step: S01 — Backend (Skill Author)

**Work Item**: F-00022 — iw-research Skill
**Agent**: Backend
**Completion Status**: complete

---

## What Was Done

Created the complete `iw-research` skill in `skills/iw-research/` following the IW skill pattern (iw-new-feature, iw-blog-writer). The skill is a full-workflow online research capability with four modes, mandatory GO/NO-GO checkpoint, and IW database registration.

### Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `skills/iw-research/SKILL.md` | 240 | Main skill — 7-step workflow (≤500 line limit met) |
| `skills/iw-research/references/modes.md` | 273 | Per-mode tool chain instructions (tech/market/deep/general) |
| `skills/iw-research/references/output_format.md` | 182 | Canonical research document template |

### SKILL.md Structure

- **Frontmatter**: `name`, `version`, `description`, `allowed-tools`, `argument-hint` — all required fields per design spec
- **7-step workflow**: Reserve ID → Scope & Mode → GO/NO-GO → Execute → Write Doc → Register → Report
- **Mode mapping table**: tech/market/deep/general with tool assignments
- **Constraints section**: MUST/NEVER rules

### Key Design Decisions

1. **ID reservation first**: `iw next-id --type research` is Step 1, same discipline as `iw-new-feature`
2. **Mandatory user interaction before any web calls**: Mode and scope confirmed before Step 3 (GO/NO-GO)
3. **context7 gracefully optional**: If context7 unavailable, skill continues with WebSearch + WebFetch only
4. **All four modes fully specified**: Each has distinct query counts, source hierarchies, and confidence rules
5. **Output format enforces citations**: Every factual claim requires inline `[text](url)` citation and `[HIGH/MEDIUM/LOW]` markers

---

## Verification

```
$ wc -l skills/iw-research/SKILL.md
240 /home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00022/skills/iw-research/SKILL.md
≤ 500: PASS

$ ls -la skills/iw-research/
SKILL.md  (240 lines)
references/modes.md  (273 lines)
references/output_format.md  (182 lines)
```

---

## Notes

- The `skills/40-GUIDE_TO_CREATE_CLAUDE_SKILLS.md` and `skills/deep-research/SKILL.md` referenced in the design doc were not present in this worktree — used `iw-new-feature` and `iw-blog-writer` as primary pattern references instead
- `docs/research/` directory does not exist yet — the skill instructs agents to `mkdir -p docs/research/` before writing
- OpenCode compatibility handled via same `WebSearch`/`WebFetch` tool names (requires `OPENCODE_ENABLE_EXA=1`)
- F-00020 (iw next-id --type research) dependency noted in Prerequisites and Constraints
