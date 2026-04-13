# F-00023: iw-research-quick Skill

**Type**: Feature
**Phase**: IW AI Core — Research System
**Priority**: High
**Created**: 2026-04-13
**Status**: Draft
**Repository**: `iw-ai-core` — `skills/iw-research-quick/`

---

## Description

Creates the `iw-research-quick` skill — a lightweight online research skill that provides
fast answers inline without producing a saved document or allocating a database ID. It uses
WebSearch + WebFetch (max 4 sources), responds with mandatory source citations and confidence
markers, and suggests upgrading to `/iw-research` for topics that warrant a full document.
Compatible with both Claude Code and OpenCode.

## Architecture References

| Document | Section | Relevance |
|----------|---------|-----------|
| `skills/40-GUIDE_TO_CREATE_CLAUDE_SKILLS.md` | Full file | Skill structure rules |
| `skills/iw-research/SKILL.md` | Full file | Sister skill — same tool chain, no workflow |
| `skills/deep-research/SKILL.md` | Full file | Existing generic reference |

## Scope

### In Scope

- `skills/iw-research-quick/SKILL.md` — complete skill (single file, ≤ 300 lines)
- Synced to `.claude/skills/iw-research-quick/` via `iw sync-skills`

### Out of Scope

- No references/ directory needed (single-file skill)
- No database registration, no file output, no ID allocation
- No modes — always uses WebSearch + WebFetch, context7 optional if topic is a library

## Implementation Plan

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Write SKILL.md | — |
| S02 | CodeReview_Final | Review + sync | — |
| S03 | QV: validate | Frontmatter + line count | — |
| S04 | QV: sync | `iw sync-skills` + verify | — |

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `F-00023_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/F-00023_S01_Backend_prompt.md` | Prompt | Write skill |
| `prompts/F-00023_S02_CodeReview_Final_prompt.md` | Prompt | Review + sync |

## Detailed Skill Specification

### SKILL.md frontmatter

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

### Workflow

```
1. Get topic from $ARGUMENTS or ask (one question)
2. If topic is a library/framework → try context7 first for current docs
3. WebSearch (2-3 queries) → identify best sources
4. WebFetch (max 4 sources) → extract targeted answers
5. Respond inline with:
   - Direct answer (2-3 paragraphs)
   - [HIGH/MEDIUM/LOW] confidence on the answer
   - Inline source citations per claim
   - Sources section at the end
6. If topic warrants deeper investigation:
   "This looks like a topic worth filing. Run `/iw-research {topic}` for a full document."
```

### Output format (inline response)

```
## Quick Research: {topic}

{Direct answer with [confidence level]}

{Paragraph 2 if needed}

**Sources**
- [Title](url) — credibility note
- [Title](url) — credibility note
```

## Acceptance Criteria

### AC1: Fast answer with citations

```
Given user asks "is bun faster than node for our use case?"
When iw-research-quick activates
Then it responds inline (no file created) with WebSearch + WebFetch results
And every factual claim has an inline source URL
And the answer has a [HIGH/MEDIUM/LOW] confidence marker
```

### AC2: Upgrade suggestion

```
Given the topic is complex (e.g., "research all queue systems for 4M/month volume")
When the skill completes its quick answer
Then it suggests running /iw-research for a full document
```

### AC3: No side effects

```
Given any quick research completes
Then no files are created
And no `iw next-id` is called
And the answer is fully inline
```

## Invariants

1. No `iw next-id` call ever — this skill never allocates IDs
2. Max 4 WebFetch calls per invocation
3. Every factual claim has a source URL citation
4. Confidence marker on every direct answer
5. Upgrade suggestion when topic exceeds 3 main questions

## Boundary Behavior

N/A — this is a skill instruction file, not executable code. No data boundaries to define.
Edge-case behavior is encoded as invariants (see above) and enforced by QV gates.

## TDD Approach

N/A — SKILL.md is a skill instruction document, not executable code. Quality is verified by:
- QV gate S03: frontmatter schema + line count ≤ 300
- QV gate S04: `iw sync-skills` deploys and file is present in `.claude/skills/`

## Dependencies

- **Depends on**: Nothing (no F-00020 dependency — no ID allocation)
- **Blocks**: Nothing

## Notes

This skill is intentionally minimal. The SKILL.md should be ≤ 300 lines — if it grows
beyond that, content is moving to the wrong skill (use `iw-research` for complexity).

**Skill sync scope**: `skills/` in iw-ai-core is the master copy. S04 syncs to all
registered projects: `iw-ai-core` (current project) and `innoforge`. If new projects
are registered in future, they will pick up the skill via `iw sync-skills` at init time.
