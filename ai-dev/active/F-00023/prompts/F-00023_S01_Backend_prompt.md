# F-00023_S01_Backend_prompt

**Work Item**: F-00023 — iw-research-quick Skill
**Step**: S01
**Agent**: Backend (Skill Author)
**Parallel With**: Can run in parallel with F-00022 S01

---

## Input Files

- `ai-dev/active/F-00023/F-00023_Feature_Design.md` — Full specification

## Output Files

- `ai-dev/active/F-00023/reports/F-00023_S01_Backend_report.md`

## Context

You are writing the `iw-research-quick` skill — a single-file, lightweight companion to
`iw-research`. No saved document, no ID, no workflow overhead. Fast answers inline.

**Repository**: `iw-ai-core` (this repository)

## Architecture References

Read before writing:

- `skills/40-GUIDE_TO_CREATE_CLAUDE_SKILLS.md` — Rules
- `skills/iw-research/SKILL.md` — Sister skill (for context/contrast)

## Requirements

### 1. Create `skills/iw-research-quick/SKILL.md`

Single file, ≤ 300 lines. Frontmatter from design doc. Body must cover:

**Frontmatter**:
```yaml
---
name: iw-research-quick
version: "1.0.0"
description: >
  Fast inline research using web search and fetch — answers directly in the conversation
  without saving a document or allocating an ID. Use when asked a quick research question,
  "what is X", "is Y still maintained", "compare A vs B briefly", or "/iw-research-quick".
  For research that should be filed as a project document, use /iw-research instead.
allowed-tools: WebSearch, WebFetch, mcp__context7__resolve-library-id, mcp__context7__query-docs
argument-hint: <question or topic>
---
```

**Body must include**:
1. Quick workflow (6 steps, concise)
2. When to use context7 (library/framework topics only)
3. Max 4 WebFetch calls rule
4. Output format (inline, with confidence marker + citations)
5. Upgrade suggestion trigger (when to recommend `/iw-research`)
6. Constraints section (NO `iw next-id`, NO file creation, max 4 fetches)

**Key rules to encode**:
- `[HIGH/MEDIUM/LOW]` confidence on the answer
- Every factual claim has inline source URL
- `Sources` section at the end of every response
- Suggest `/iw-research {topic}` if: topic has >3 main questions, user seems to want depth,
  or findings contradict each other requiring synthesis

## Verify

```bash
wc -l skills/iw-research-quick/SKILL.md
# Must be ≤ 300
```

## Constraints

- Single SKILL.md file — no references/ directory
- ≤ 300 lines
- No IW workflow (no iw next-id, no iw register)
- No file output

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "F-00023",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "skills/iw-research-quick/SKILL.md"
  ],
  "tests_passed": true,
  "test_summary": "SKILL.md: N lines (≤300)",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
