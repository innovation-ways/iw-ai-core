# F-00022: iw-research Skill

**Type**: Feature
**Phase**: IW AI Core — Research System
**Priority**: High
**Created**: 2026-04-13
**Status**: Draft
**Repository**: `iw-ai-core` — `skills/iw-research/`

---

## Description

Creates the `iw-research` skill — a full-workflow online research skill that produces
saved research documents registered in the iw-ai-core database. The skill supports four
modes (tech, market, deep, general), orchestrates `WebSearch` + `WebFetch` + `mcp__context7`
tool chains, mandates source citations and confidence markers on every finding, and integrates
fully with the IW workflow (`iw next-id --type research`, `iw register`, `iw doc-update`).
It is compatible with both Claude Code and OpenCode.

## Architecture References

| Document | Section | Relevance |
|----------|---------|-----------|
| `skills/40-GUIDE_TO_CREATE_CLAUDE_SKILLS.md` | Full file | Skill structure rules |
| `skills/iw-new-feature/SKILL.md` | Full file | IW skill pattern reference |
| `skills/iw-blog-writer/SKILL.md` | Full file | IW branded skill reference |
| `skills/deep-research/SKILL.md` | Full file | Existing research framework (superseded) |
| `docs/research/00-RESEARCH_INDEX.md` | Format | Output document format for research docs |
| `docs/research/37-GIT_STRATEGY_PARALLEL_AI_AGENTS.md` | Content | Example of a well-structured research doc |

## Scope

### In Scope

- `skills/iw-research/SKILL.md` — the complete skill (max 500 lines)
- `skills/iw-research/references/modes.md` — detailed guidance per mode
- `skills/iw-research/references/output_format.md` — research doc template
- Synced to `.claude/skills/iw-research/` in this project via `iw sync-skills`

### Out of Scope

- `iw-research-quick` (F-00023)
- Any changes to the `deep-research` skill (it remains but is superseded for IW projects)
- Implementation of the `iw next-id --type research` command (F-00020)

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | Write all skill files (SKILL.md + references) | — |
| S02 | CodeReview_Backend | Review skill for quality, completeness, IW pattern compliance | — |
| S03 | CodeReview_Final | Final review + sync verification | — |
| S04 | QV: validate | Frontmatter YAML valid, body ≤ 500 lines, referenced files exist | — |
| S05 | QV: sync | `iw sync-skills` deploys to `.claude/skills/iw-research/` | — |

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `F-00022_Feature_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Orchestrator step definitions |
| `prompts/F-00022_S01_Backend_prompt.md` | Prompt | Write all skill files |
| `prompts/F-00022_S02_CodeReview_Backend_prompt.md` | Prompt | Review skill quality |
| `prompts/F-00022_S03_CodeReview_Final_prompt.md` | Prompt | Final review + sync |

## Acceptance Criteria

### AC1: Skill triggers correctly

```
Given the skill is installed in .claude/skills/iw-research/
When a user says "research redis vs rabbitmq for our queue system"
Then the skill activates and begins the workflow (reserve ID, scope session)
```

### AC2: Four modes available

```
Given a user invokes /iw-research
When the topic is clearly technical (library/framework comparison)
Then the skill auto-selects "tech" mode and uses context7 for library docs
When the topic is market/competitive
Then the skill auto-selects "market" mode
```

### AC3: Full workflow produces a filed document

```
Given user confirms GO
When research is complete
Then a file exists at docs/research/R-NNNNN-SLUG.md
And the document is registered via iw register + iw doc-update --doc-type research
And the document contains mandatory source citations (URL per claim)
And confidence markers [HIGH/MEDIUM/LOW] appear on key findings
```

### AC4: OpenCode compatibility

```
Given the skill runs in OpenCode (not Claude Code)
When WebSearch and WebFetch are available (OPENCODE_ENABLE_EXA=1)
Then the skill executes identically — same workflow, same output format
```

## Detailed Skill Specification

### SKILL.md frontmatter

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

### Workflow (SKILL.md body)

```
Step 1: Reserve ID       → iw next-id --type research → R-NNNNN
Step 2: Scope session    → Determine mode (auto or user), primary question,
                           secondary questions, depth (quick/standard/deep)
                           WAIT for user confirmation
Step 3: GO checkpoint    → Present: ID, mode, questions, tool plan
                           Only proceed on explicit GO
Step 4: Research         → Execute tool chain per mode (see references/modes.md)
                           Optionally: outline checkpoint for deep mode
Step 5: Write document   → docs/research/R-NNNNN-SLUG.md (see references/output_format.md)
Step 6: Register         → iw register R-NNNNN "Title" --type research
                           iw doc-update R-NNNNN --doc-type research \
                             --editorial-category <tech→technical|market→marketing|deep/general→functional> \
                             --title "Title" --status draft --content-file docs/research/R-NNNNN-SLUG.md
Step 7: Report           → Summary: ID, title, key findings (3 bullets), dashboard link
```

### Mode → Tool mapping

| Mode | WebSearch | WebFetch | context7 | Codebase |
|------|-----------|----------|----------|----------|
| tech | yes | yes | yes | yes |
| market | yes | yes | no | no |
| deep | yes | yes | yes | no |
| general | yes | yes | no | optional |

### Output document requirements

Every research document MUST contain:
- Title, ID, date, mode, research questions
- Executive summary (3-5 sentences)
- Findings sections with `[HIGH/MEDIUM/LOW]` confidence marker per section header
- Every factual claim linked to its source URL as `[source](url)`
- Recommendations section
- Sources list at the end

### Editorial category mapping (for iw doc-update)

| Research mode | `--editorial-category` |
|---|---|
| tech | technical |
| market | marketing |
| deep | functional |
| general | functional |

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| F-00020 not deployed | `iw next-id --type research` fails | Skill halts at Step 1 with clear error: "Requires F-00020 to be deployed" |
| User declines GO | User types "no" at checkpoint | Skill aborts cleanly, no files written, no web calls made |
| context7 unavailable | Tool not present (non-Claude Code host) | Gracefully skip context7; continue with WebSearch+WebFetch only |
| Zero web results | WebSearch returns no results | Report low-confidence finding, flag in Limitations section |
| Research ID already exists | `iw next-id` returns ID that conflicts | Not possible by design; `iw next-id` always returns a fresh monotonic ID |

## Invariants

1. `iw next-id --type research` is called before ANY other work
2. User confirms GO before any web tool calls
3. Every finding has a `[HIGH/MEDIUM/LOW]` confidence marker
4. Every factual claim has a source URL inline citation
5. `iw doc-update --doc-type research` is called at the end to register in the DB

## Dependencies

- **Depends on**: F-00020 (iw next-id --type research must exist)
- **Blocks**: Nothing

## TDD Approach

Skills do not have automated unit tests. Quality is validated by:
1. Code review against the skill creation guide (`40-GUIDE_TO_CREATE_CLAUDE_SKILLS.md`)
2. Frontmatter YAML validation
3. Line count check (≤ 500 lines for SKILL.md body)
4. Referenced files existence check
5. Manual smoke test: invoke the skill on a test topic

## Notes

**Dependency note**: The skill references `iw next-id --type research` which requires F-00020
to be deployed first. If F-00020 is not deployed, the skill will fail at Step 1. The skill
SKILL.md should include a note in its prerequisites section.

**OpenCode note**: OpenCode uses the same tool names (`WebSearch`, `WebFetch`) when
`OPENCODE_ENABLE_EXA=1` is set. No special casing needed in the skill — same instructions
work for both Claude Code and OpenCode.
