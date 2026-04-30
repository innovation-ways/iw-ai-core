# CR{NNN}: {Change Request Title}

**Type**: Change Request
**Priority**: {Critical / High / Medium / Low}
**Reason**: {Why this change is needed — e.g., performance, maintainability, new requirement, deprecation}
**Created**: {YYYY-MM-DD}
**Status**: Draft | Approved | In Progress | Done

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. State whether this item adds, modifies, or leaves migrations unchanged.)

## Description

{What is being changed and why. 2-3 sentences.}

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.

## Current Behavior

{Describe how the system works today in the area being changed.}

## Desired Behavior

{Describe how the system should work after this change request is implemented.}

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| {e.g., API endpoint} | {e.g., Returns flat list} | {e.g., Returns paginated response} |
| {e.g., Database table} | {e.g., VARCHAR(100)} | {e.g., VARCHAR(255)} |

### Breaking Changes

- {List any breaking changes to APIs, data formats, or behavior, or "None"}

### Data Migration

- {Describe any data migration needed, or "None"}
- {Include whether migration is reversible}

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | {Agent} | {What this agent changes} | — |
| S02 | CodeReview | Review S01 output | — |
| S03 | {Agent} | {What this agent changes} | — |
| S04 | CodeReview | Review S03 output | — |
| S05 | Tests | Updated and new tests | — |
| S06 | CodeReview | Review S05 output | — |
| S07 | CodeReview_Final | Global review of all work | — |
| S08..S16 | QV Gates | lint, format, typecheck, unit-tests, integration-tests | — |

Adjust steps based on change scope. Simple changes may need fewer steps.
Agent slugs: `database-impl`, `backend-impl`, `api-impl`, `frontend-impl`, `tests-impl`, `pipeline-impl`, `template-impl`.

### Database Changes

- **New tables**: {table names or "None"}
- **Modified tables**: {table names or "None"}
- **Migration notes**: {any special considerations}

### API Changes

- **New endpoints**: {method + path or "None"}
- **Modified endpoints**: {method + path or "None"}
- **Removed endpoints**: {method + path or "None"}

### Frontend Changes

- **New components**: {component names or "None"}
- **Modified components**: {component names or "None"}
- **Removed components**: {component names or "None"}

## File Manifest

All files for this work item live under `ai-dev/design/active/{ID}/`:

| File | Type | Purpose |
|------|------|---------|
| `{ID}_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/{ID}_S01_{Agent}_prompt.md` | Prompt | S01 implementation instructions |
| ... | ... | ... (one per step) |

Reports are created during execution in `ai-dev/work/{ID}/reports/`.

## Acceptance Criteria

### AC1: {Criteria title}

```
Given {precondition}
When {action}
Then {expected result}
```

### AC2: {Criteria title}

```
Given {precondition}
When {action}
Then {expected result}
```

## Rollback Plan

{How to revert this change if something goes wrong. Include:}

- **Database**: {e.g., Reverse migration available / manual SQL needed / not applicable}
- **Code**: {e.g., Revert commit / feature flag disable}
- **Data**: {e.g., No data loss on rollback / requires restore from backup}

## Dependencies

- **Depends on**: {F/I/CR numbers or "None"}
- **Blocks**: {F/I/CR numbers or "None"}

## TDD Approach

- Unit tests: {What to test}
- Integration tests: {What to test}
- Updated tests: {Existing tests that need modification}

## Notes

{Additional context, risks, or decisions.}
