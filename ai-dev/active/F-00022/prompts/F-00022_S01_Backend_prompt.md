# F-00022_S01_Backend_prompt

**Work Item**: F-00022 — iw-research Skill
**Step**: S01
**Agent**: Backend (Skill Author)
**Parallel With**: None — first step

---

## Input Files

- `ai-dev/active/F-00022/F-00022_Feature_Design.md` — Full specification

## Output Files

- `ai-dev/active/F-00022/reports/F-00022_S01_Backend_report.md`

## Context

You are writing the `iw-research` skill for the IW AI Core skill library. This skill lives
in `skills/iw-research/` and gets deployed to projects via `iw sync-skills`.

**Repository**: `iw-ai-core` (this repository)

## Architecture References

Read these files completely before writing:

- `skills/40-GUIDE_TO_CREATE_CLAUDE_SKILLS.md` — Skill creation rules
- `skills/iw-new-feature/SKILL.md` — IW workflow skill pattern
- `skills/iw-blog-writer/SKILL.md` — Branded IW skill with modes pattern
- `skills/deep-research/SKILL.md` — Research framework reference (superseded)
- `docs/research/37-GIT_STRATEGY_PARALLEL_AI_AGENTS.md` — Example well-structured research output

## Previous Steps

This is the first implementation step.

## Requirements

### 1. Create `skills/iw-research/SKILL.md`

The SKILL.md body MUST be ≤ 500 lines. Use progressive disclosure — detailed patterns go in
`references/` files. The SKILL.md should contain:

**Frontmatter** (from design doc):
```yaml
---
name: iw-research
version: "1.0.0"
description: >
  Conducts online research and produces a filed research document registered in
  the IW AI Core database. Supports four modes: tech (library/framework evaluation),
  market (competitive landscape), deep (multi-angle investigation), general (default).
  Use when asked to "research X", "investigate Y", "evaluate Z options",
  "/iw-research", or when research output should be saved as a project document.
  Requires: iw next-id --type research (F-00020 must be deployed).
allowed-tools: WebSearch, WebFetch, mcp__context7__resolve-library-id, mcp__context7__query-docs, Read, Grep, Glob, Bash, Write, Edit
argument-hint: <topic or research question>
---
```

**Body structure:**

```markdown
# IW Research

Produces a filed research document registered in the IW AI Core database.

**Research topic**: $ARGUMENTS

---

## Prerequisites
- F-00020 must be deployed: `iw next-id --type research` must work
- OpenCode users: set `OPENCODE_ENABLE_EXA=1` for WebSearch support

## Step 1: Reserve Research ID (IMMEDIATE)
[... iw next-id --type research ...]

## Step 2: Scope & Mode Selection (MANDATORY INTERACTION)
[... 4 modes, auto-detect, user confirms ...]

## Step 3: GO/NO-GO Checkpoint
[... present plan, wait for GO ...]

## Step 4: Execute Research
[... tool chain per mode ...]

## Step 5: Write Document
[... docs/research/R-NNNNN-SLUG.md ...]

## Step 6: Register in Platform
[... iw register + iw doc-update ...]

## Step 7: Report
[... summary + dashboard link ...]

## Constraints
[... MUST/NEVER rules ...]
```

### 2. Create `skills/iw-research/references/modes.md`

Detailed tool chain instructions per mode:
- **tech**: `mcp__context7__resolve-library-id` first to get library ID, then `__query-docs`.
  WebSearch for real-world usage, benchmarks, known issues. Also Grep/Read codebase for
  current usage of candidate libraries.
- **market**: WebSearch for company/product landscape, WebFetch for feature pages, pricing,
  case studies. No codebase access needed.
- **deep**: All tools. Start broad (WebSearch landscape), then narrow (WebFetch specific
  pages), use context7 for any library/framework components.
- **general**: WebSearch + WebFetch. Reasonable default for unclassified topics.

For each mode, specify:
- Recommended number of search queries (tech: 5-8, market: 6-10, deep: 10+, general: 4-6)
- Source credibility hierarchy (official docs > conference talks > blog posts > community)
- Confidence level rules (HIGH: 2+ authoritative sources agree, MEDIUM: 1 good source,
  LOW: inference/extrapolation)

### 3. Create `skills/iw-research/references/output_format.md`

The canonical research document template:

```markdown
# {Title}

**Research ID**: R-NNNNN
**Date**: YYYY-MM-DD
**Mode**: tech | market | deep | general
**Primary Question**: {main research question}

---

## Executive Summary

{3-5 sentences covering the key finding and recommendation.}

## Background

{Why this research was needed. 2-3 sentences.}

## Findings

### {Finding Title} [HIGH confidence]

{Finding text with inline citations: [source text](url)}

### {Finding Title} [MEDIUM confidence]

{...}

## Recommendations

1. **Primary**: {main recommendation with rationale}
2. **Alternative**: {if primary not viable}
3. **Avoid**: {what not to do and why}

## Limitations

- {What this research doesn't cover}
- {Potential gaps}

## Sources

| # | Source | Credibility | URL |
|---|--------|-------------|-----|
| 1 | {title} | HIGH/MEDIUM/LOW | {url} |
```

## Mandatory Patterns

- SKILL.md body MUST be ≤ 500 lines (count carefully)
- Description must include WHAT and WHEN (already in frontmatter)
- Use forward slashes in all paths
- No time-sensitive information
- `iw next-id` call MUST be Step 1 (same discipline as `iw-new-feature`)
- User interaction MUST happen before any web tool calls
- GO checkpoint MUST happen before any files are written

## Output Requirements

After creating all files, verify:
```bash
wc -l skills/iw-research/SKILL.md
# Must be ≤ 500
ls -la skills/iw-research/
```

## Constraints

- Do NOT exceed 500 lines in SKILL.md
- Do NOT implement code — this is a documentation/skill-writing step
- SKILL.md must be self-contained for the core workflow; references/ for details
- All `iw` CLI commands must use exact syntax (verified against real CLI in our analysis)

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "F-00022",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "skills/iw-research/SKILL.md",
    "skills/iw-research/references/modes.md",
    "skills/iw-research/references/output_format.md"
  ],
  "tests_passed": true,
  "test_summary": "SKILL.md: N lines (≤500); all referenced files exist",
  "coverage": "N/A",
  "blockers": [],
  "notes": ""
}
```
