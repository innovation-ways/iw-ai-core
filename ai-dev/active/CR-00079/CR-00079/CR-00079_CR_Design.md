# CR-00079: Generate smaller, single-concern workflow steps in the design-creation skills

**Type**: Change Request
**Priority**: High
**Reason**: Process-side half of the agent context-overflow fix. CR-00076 step S01 was a monolith — one `backend-impl` step bundling 3 new test modules, a Makefile target, 3 documentation/skill/plan updates, quality-gate runs and TDD demonstrations. Running all of that in a single agent step accumulated tool output until the runtime's context window overflowed and the step failed. The runtime-side mitigations (tool-output capping, effective-budget meter, compaction calibration) are tracked in I-00105; the research is R-00078. This CR addresses the upstream cause: the design-creation skills emit oversized steps because nothing tells them not to.
**Created**: 2026-05-22
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. This CR touches only Markdown skill and template files — no Docker interaction at all.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This CR leaves migrations unchanged** — no schema change, no migration file.

## Description

The IW design-creation skills (`iw-new-feature`, `iw-new-incident`, `iw-new-cr`) and the design templates generate each work item's `workflow-manifest.json` with no guidance on how large an implementation step should be. As a result a single step can bundle many files and unrelated concerns. This CR adds an explicit step-granularity rule and checklist to those skills, to `iw-workflow`, and to the design templates so generated packages default to small, single-concern steps — bounding the per-step context an agent accumulates.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Relevant: skills master copies live in `skills/` and are synced to `.claude/skills/` (and to project worktrees) via `iw sync-skills`; design-doc templates live in `templates/design/` and are copied to `ai-dev/templates/` via `iw sync-templates`. `skills/iw-workflow/SKILL.md` holds the workflow orchestration rules and the manifest schema. Per the project's skill-sync rule, skill edits must also be propagated to the sibling repos (IW-AI-DEV, InnoForge).

## Current Behavior

- `skills/iw-new-feature/SKILL.md`, `skills/iw-new-incident/SKILL.md`, and `skills/iw-new-cr/SKILL.md` instruct the author to produce a Fix/Implementation Plan and a `workflow-manifest.json`, but give **no rule on step size**. `iw-new-incident` says "Most incidents need only 1-2 implementation agents. Don't over-scope." — agent *count* guidance, not step *scope* guidance.
- `skills/iw-workflow/SKILL.md` defines the manifest schema and agent contracts but does not state a step-granularity expectation.
- The design templates (`templates/design/`, mirrored to `ai-dev/templates/`) have an "Agents and Execution Order" table with no sizing rule.
- Consequence: a step description like CR-00076 S01's — "(1) package marker (2) FTS test module (3) revision-skew module (4) DB-identity module (5) Makefile target (6) update strategy doc + skill + plan" — passes review as one step. The agent then reads, edits, and tests across all of it in one runtime session, and per-step context grows without bound.

## Desired Behavior

- The three design-creation skills and `iw-workflow` carry an explicit, concrete **step-granularity rule**: an implementation step should target **one cohesive concern** — roughly one module or one closely-related file group — and multi-concern work is split across multiple steps rather than bundled. Many small steps are explicitly preferred over one large step.
- The skills include a short **step-sizing checklist** the author applies when drafting the manifest (e.g. "Does this step touch more than one unrelated area? → split it"; "Would the step's own description need more than ~N numbered sub-deliverables? → split it"; "Do docs/skill/plan updates ride along with code changes? → give them their own step").
- The design templates' "Agents and Execution Order" section references the rule so it is visible at authoring time.
- The guidance is **advisory at authoring time** — it shapes how packages are generated. It does **not** change the orchestrator/daemon execution engine, the manifest schema, or any already-registered work item.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `skills/iw-new-feature/SKILL.md` | No step-size guidance | + step-granularity rule + sizing checklist |
| `skills/iw-new-incident/SKILL.md` | Agent-count guidance only | + step-granularity rule + sizing checklist |
| `skills/iw-new-cr/SKILL.md` | No step-size guidance | + step-granularity rule + sizing checklist |
| `skills/iw-workflow/SKILL.md` | Manifest schema, no sizing expectation | + canonical step-granularity rule referenced by the others |
| `templates/design/**` (design-doc templates) | "Agents and Execution Order" table, no sizing rule | + a one-line pointer to the rule |
| `ai-dev/templates/**` | Mirror of `templates/design/` | Re-synced after the master edit |
| `.claude/skills/**` (synced copies) | Mirror of `skills/` | Re-synced via `iw sync-skills` |

### Breaking Changes

- None. No code, no API, no schema, no manifest-schema change. Existing registered work items are untouched. The change is additive guidance in Markdown.

### Data Migration

- None. No schema change, nothing to reverse.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Add the step-granularity rule + checklist to the 3 design-creation skills and `iw-workflow`; add the template pointer; `iw sync-skills` + `iw sync-templates` | — |
| S02 | code-review-impl | Per-agent review of S01 | — |
| S03 | code-review-final-impl | Global review | — |
| S04..S11 | qv-gate | lint, assertions, format, typecheck, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S12 | self-assess-impl | Self-assessment via the `iw-item-analyze` skill | — |

Agent slugs: `backend-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `self-assess-impl`.

### Database Changes

- **New tables**: None · **Modified tables**: None · **Migration notes**: None.

### API Changes

- **New / Modified / Removed endpoints**: None.

### Frontend Changes

- **New / Modified / Removed components**: None.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00079_CR_Design.md` | Design | This document |
| `CR-00079_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions for the orchestrator |
| `prompts/CR-00079_S01_Backend_prompt.md` | Prompt | S01 — skills + templates edit |
| `prompts/CR-00079_S02_CodeReview_prompt.md` | Prompt | S02 — per-agent review |
| `prompts/CR-00079_S03_CodeReview_Final_prompt.md` | Prompt | S03 — global review |
| `prompts/CR-00079_S12_SelfAssess_prompt.md` | Prompt | S12 — self-assessment |

### Files created/modified by the implementation

| File | Action | Purpose |
|------|--------|---------|
| `skills/iw-new-feature/SKILL.md` | Modify | + step-granularity rule + checklist |
| `skills/iw-new-incident/SKILL.md` | Modify | + step-granularity rule + checklist |
| `skills/iw-new-cr/SKILL.md` | Modify | + step-granularity rule + checklist |
| `skills/iw-workflow/SKILL.md` | Modify | + canonical step-granularity rule |
| `.claude/skills/iw-new-feature/SKILL.md` · `.claude/skills/iw-new-incident/SKILL.md` · `.claude/skills/iw-new-cr/SKILL.md` · `.claude/skills/iw-workflow/SKILL.md` | Modify | Synced copies (`iw sync-skills`) |
| `templates/design/**` (the affected design-doc templates) | Modify | One-line pointer to the rule |
| `ai-dev/templates/**` | Modify | Re-synced (`iw sync-templates`) |

## Acceptance Criteria

### AC1: The design-creation skills carry a concrete step-granularity rule

```
Given skills/iw-new-feature, skills/iw-new-incident, and skills/iw-new-cr
When their SKILL.md files are read
Then each contains an explicit step-granularity rule stating that an
     implementation step targets one cohesive concern and that multi-concern
     work is split across multiple steps
And each contains a short step-sizing checklist the author applies when
     drafting the workflow manifest
```

### AC2: The rule is canonical in iw-workflow and referenced by the templates

```
Given skills/iw-workflow/SKILL.md and the design templates
When they are read
Then skills/iw-workflow/SKILL.md states the canonical step-granularity rule
And the design templates' Agents-and-Execution-Order section points to it
And the .claude/skills copies and ai-dev/templates copies are byte-identical
     to their masters (iw sync-skills / iw sync-templates were run)
```

### AC3: No engine, schema, or registered-item change

```
Given the repository at the end of S01
When git diff origin/main is inspected
Then it touches only Markdown files under skills/, .claude/skills/,
     templates/design/, and ai-dev/templates/
And no orch/, dashboard/, or executor/ file is modified
And the workflow-manifest JSON schema is unchanged
```

## Rollback Plan

- **Database**: Not applicable — no migration, no schema change.
- **Code**: Revert the squash-merge commit. The CR adds only Markdown guidance; reverting removes it cleanly with no residue.
- **Data**: No data loss on rollback — nothing in the CR writes to any persistent store.

## Dependencies

- **Depends on**: None functionally. Informed by research R-00078 and paired with incident I-00105 (the runtime-side half).
- **Blocks**: None.
- **Shared-file note**: this CR edits `skills/iw-workflow/**` and the `iw-new-*` skills. If other in-flight items edit the same skill files, serialize them with this CR in the batch executor to avoid merge conflicts.

## Impacted Paths

- `skills/iw-new-feature/**`
- `skills/iw-new-incident/**`
- `skills/iw-new-cr/**`
- `skills/iw-workflow/**`
- `.claude/skills/iw-new-feature/**`
- `.claude/skills/iw-new-incident/**`
- `.claude/skills/iw-new-cr/**`
- `.claude/skills/iw-workflow/**`
- `templates/design/**`
- `ai-dev/templates/**`

## TDD Approach

This CR changes Markdown guidance only — there is no production logic to RED-GREEN and no automated test surface. Verification is by review:

- **S02 / S03** verify each skill and template carries the rule and checklist, the wording is concrete and actionable (not vague), and the synced copies are byte-identical to their masters.
- **Unit / integration tests**: none added — there is no code. The QV `unit-tests` / `integration-tests` gates still run and must stay green (a Markdown-only diff cannot break them; if they fail, S01 touched something out of scope).
- **Updated tests**: none.
- A mechanical enforcement check (e.g. a script that flags an oversized manifest step) is deliberately **out of scope** — see Notes.

## Notes

- **Out of scope**: model-routing (operator decision); the runtime-side context fixes (I-00105); a mechanical step-size enforcer. The CR delivers authoring-time *guidance*; if drift proves the guidance insufficient, a follow-up can add a mechanical check — not now.
- **Sibling-repo propagation**: per the project's skill-sync rule, the edited `iw-*` skills must also be copied to the IW-AI-DEV and InnoForge repos. An agent in a worktree cannot write outside it, so S01 propagates only within this repo (`iw sync-skills`); cross-repo propagation is an **operator follow-up** after merge. The S01 report must flag this explicitly.
- **Why guidance, not enforcement**: the operator's settled decision is to make steps smaller via authoring guidance. Many small steps are healthy; the failure mode is one large step. Concrete, visible guidance at authoring time is the lightest change that addresses the cause.
