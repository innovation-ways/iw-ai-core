# CR-00037: Add vendored-library API verification rule to frontend-impl agent

**Type**: Change Request
**Priority**: Low
**Reason**: Prevent recurrence of vendored-library API mismatches in any future frontend step (not just the F-00079 lineage). F-00079 self-assess Finding 1 traced 3 consecutive browser-verification fix cycles (~45 minutes of agent time) to assuming a non-existent `Diff2HtmlUI.create(...)` factory call against the vendored slim bundle, which only exposes the constructor `new Diff2HtmlUI(...)`. A general rule in the frontend-impl agent definition gives every future frontend step the right reflex.
**Created**: 2026-05-07
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. No Docker work in this CR.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This CR adds, modifies, or removes **no** migrations.

## Description

Add a short, project-agnostic rule to the master copies of the `frontend-impl` agent definition (`agents/claude/frontend-impl.md` and `agents/opencode/frontend-impl.md`) instructing the agent to verify a vendored or third-party JS/CSS library's actual exported surface (grep the bundled file or its `.d.ts`, or open in DevTools) before drafting initialization or call code against it. After merge, `iw sync-agents` propagates the updated master copies into every managed project's `.claude/agents/` and `.opencode/agents/` directories.

The rule is a positive instruction added to the agent's **Required Workflow**, between the existing "Identify existing patterns" and "Apply TDD where applicable" steps. The rule cites F-00079 self-assess Finding 1 as the historical motivation in a single sentence.

This change is documentation-only (markdown agent-definition files). It does not touch source code, templates, the database, the dashboard runtime, or any test suite.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. The relevant context for this CR is the agent definitions pipeline:
- Master copies live under `agents/claude/` and `agents/opencode/` and are checked into the repo.
- `iw sync-agents` (see `orch/skills/sync_agents.py`) copies `agents/claude/*.md` → `<project>/.claude/agents/` and `agents/opencode/*.md` → `<project>/.opencode/agents/` for every managed project.
- The synced copies under `.claude/agents/` and `.opencode/agents/` MUST NOT be edited directly — they are regenerated.
- Per project memory `feedback_skills_sync.md`, agent edits should also be propagated to IW-AI-DEV and InnoForge repos after merge — this is an after-merge concern outside CR-00037's scope.

## Current Behavior

The `frontend-impl` agent definition has no general rule about verifying vendored or third-party library APIs before drafting calls against them. Its Required Workflow currently reads (excerpt):

```
1. Read the implementation prompt
2. Read CLAUDE.md
3. Identify existing patterns
4. Apply TDD where applicable
5. Run checks
6. Return the result report
```

The agent therefore relies entirely on the implementation prompt for any library-specific call shape. When a prompt is silent about call shape (as F-00079_S06 was for `Diff2HtmlUI`), the agent is free to guess from the library's name. In F-00079 the agent guessed `Diff2HtmlUI.create(diffText, {...})`, which is **not** an exported symbol of the vendored `diff2html-ui-slim.min.js` bundle (which exposes only the constructor `new Diff2HtmlUI(...)`). The mismatch caused 3 consecutive S19 browser-verification fix cycles before the agent finally tried the constructor form.

## Desired Behavior

The `frontend-impl` agent definition gains a new step in its Required Workflow:

> **Verify vendored / third-party library APIs before drafting calls.** When you need to call into a vendored or third-party JS/CSS asset (files under `static/vendor/**`, `node_modules/**` exports, or any library loaded via a libs include), do NOT assume a method or factory exists from the library's name alone. Before writing initialization or call code, grep the bundled JS file (e.g., `static/vendor/<lib>/**/*.js`) for the actual exported symbols, read its `.d.ts` if present, or open it in DevTools / a REPL to confirm. The slim and full builds of the same library may export different surfaces — a method documented upstream may be absent from the slim bundle the project actually ships. Why this rule exists: F-00079 self-assess Finding 1 traced ~45 min of wasted agent time across 3 browser-verification fix cycles to assuming a non-existent `Diff2HtmlUI.create(...)` factory in the vendored slim bundle, which only exposes the constructor `new Diff2HtmlUI(...)`.

After this CR merges, `iw sync-agents` propagates the rule into every managed project's `.claude/agents/frontend-impl.md` and `.opencode/agents/frontend-impl.md`. Any future frontend step (in iw-ai-core or any other managed project, including diff-rendering, charting, syntax-highlighting, or any new vendored UI library) inherits the rule automatically.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `agents/claude/frontend-impl.md` | Required Workflow has no vendored-library verification step. | New step inserted in Required Workflow with the verification rule. |
| `agents/opencode/frontend-impl.md` | Required Workflow has no vendored-library verification step. | Same step inserted (same wording). |

### Breaking Changes

None. The agent definition is a markdown prompt; adding a step to its workflow does not change any tool surface, contract, or schema. The synced copies under `.claude/agents/` and `.opencode/agents/` are regenerated by `iw sync-agents` and are NOT touched by this CR (they will pick up the rule the next time someone runs `iw sync-agents`).

### Data Migration

None.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Edit both master copies (`agents/claude/frontend-impl.md` and `agents/opencode/frontend-impl.md`): insert the vendored-API verification step into Required Workflow. | — |
| S02 | code-review-impl | Per-agent code review of S01. | — |
| S03 | code-review-final-impl | Cross-agent final review of S01 (single-agent CR; final review still runs to satisfy the standard pipeline). | — |
| S04..S08 | qv-gate | lint, format-check, typecheck, unit-tests, integration-tests. | — |
| S09 | self-assess-impl | Self-assessment via `iw-item-analyze`. | — |

The plan is intentionally minimal: no Database/API/Frontend/Pipeline/Tests-impl steps because the change is to two markdown agent-definition files and exercises no code path. `backend-impl` is the project's catch-all agent for non-templated, non-frontend, non-database edits — appropriate here because we are editing markdown configuration of the frontend-impl agent, NOT writing frontend code.

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: N/A

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `CR-00037_CR_Design.md` | Design | This document |
| `CR-00037_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00037_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00037_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review of S01 |
| `prompts/CR-00037_S03_CodeReview_Final_prompt.md` | Prompt | S03 final cross-agent review |
| `prompts/CR-00037_S09_SelfAssess_prompt.md` | Prompt | S09 self-assessment |

(QV gate steps S04..S08 are command-only and have no prompt files.)

## Acceptance Criteria

### AC1: Vendored-library verification step present in both master copies

```
Given the files agents/claude/frontend-impl.md and agents/opencode/frontend-impl.md
When a reader examines the "Required Workflow" section of each
Then each file contains a numbered step that includes ALL of:
  - the phrase "vendored" (and/or "third-party") describing the libraries in scope,
  - an explicit instruction to grep the bundled JS file or read a .d.ts before drafting calls,
  - a one-sentence reference to F-00079 self-assess Finding 1 as the motivating incident,
  and the wording is substantively identical between the two files (small dialect differences
  acceptable, but the rule and its motivation must be the same).
```

### AC2: No reference to a `.create(` factory call form is recommended

```
Given the files agents/claude/frontend-impl.md and agents/opencode/frontend-impl.md
When a reader greps for "Diff2HtmlUI.create(" or any pattern that recommends a static
  ".create(" factory shape as a default
Then there are zero matches except for negative-form mentions (i.e., the rule may CITE
  Diff2HtmlUI.create(...) as the historically wrong call, but MUST NOT recommend any
  ".create(" factory form as a default).
```

### AC3: Sync surfaces NOT edited

```
Given the directories .claude/agents/ and .opencode/agents/ in this repo
When the diff for this CR is inspected
Then no file under .claude/agents/ or .opencode/agents/ is modified by this CR
  (these are sync-generated; only the masters under agents/claude/ and agents/opencode/
  are edited).
```

### AC4: No collateral changes to agent definitions

```
Given the files agents/claude/frontend-impl.md and agents/opencode/frontend-impl.md
When the diff for this CR is inspected
Then the only modifications are:
  - the insertion of one new numbered step in each "Required Workflow" section, and
  - any minimal renumbering of subsequent workflow steps required to keep the list contiguous.
No other section, frontmatter field (name, description, model, tools, permission, mode,
temperature, steps), Mission line, Safety Constraint, or Output Format detail is altered.
No other agent-definition file under agents/claude/ or agents/opencode/ is altered.
```

## Rollback Plan

- **Database**: Not applicable.
- **Code**: Revert the squash-merge commit. Because the change is markdown-only and lives in agent definitions, reverting has zero runtime impact and only restores the pre-CR Required Workflow.
- **Data**: No data loss possible — markdown-only change. Note: synced copies under `.claude/agents/` / `.opencode/agents/` in OTHER managed projects will retain the rule until the next `iw sync-agents`; if rollback needs to be propagated, run `iw sync-agents` from each affected project.

## Dependencies

- **Depends on**: F-00079 (merged) — this CR's source of truth is its self-assess report Finding 1.
- **Blocks**: None.

## Impacted Paths

- `agents/claude/frontend-impl.md`
- `agents/opencode/frontend-impl.md`

## TDD Approach

Not applicable. This CR modifies two markdown agent-definition files and exercises no code path. No unit, integration, or dashboard test is created or modified. The QV gate suite (lint, format-check, typecheck, unit-tests, integration-tests) still runs per the standard pipeline and is expected to pass with no diffs against `main` other than the two markdown edits.

## Notes

- The literal text `Diff2HtmlUI.create(diffText, {...})` does **not** appear in the current frontend-impl agent definitions — the failure mode in F-00079 was that the agent **had no general reflex** to verify a vendored library's surface before drafting calls. The fix is therefore an **addition** (a workflow step plus its motivating sentence), not a textual find-and-replace.
- F-00079's S06 prompt is left untouched. The original (narrower) version of CR-00037 proposed editing that prompt directly; we converted to the agent-definition path because (a) the F-00079 prompt is for an already-shipped feature and won't be re-run, and (b) the agent-definition change reaches every future frontend step across all managed projects, not just code that copies F-00079_S06.
- After merge, `iw sync-agents` propagates the rule to every managed project. Per project memory `feedback_skills_sync.md`, the same edits should be applied (or sync-pulled) in IW-AI-DEV and InnoForge repos as a follow-up — that follow-up is OUT OF SCOPE for this CR but should be tracked separately.
- Agent slug for S01 is `backend-impl` because there is no documentation-specific implementation agent and `backend-impl` is the project's catch-all for non-templated edits. The change is markdown-only; no Python is touched. We deliberately do NOT use `frontend-impl` for this step — the change is to the frontend-impl agent's *definition*, not to frontend code.
