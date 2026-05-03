# F{NNN}: {Feature Title}

**Type**: Feature
**Priority**: {Critical / High / Medium / Low}
**Created**: {YYYY-MM-DD}
**Status**: Draft | Approved | In Progress | Done

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. State whether this item adds, modifies, or leaves migrations unchanged.)

## Description

{What this feature does and why it's needed. 2-3 sentences.}

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.

## Scope

### In Scope

- {Concrete deliverable 1}
- {Concrete deliverable 2}

### Out of Scope

- {What this feature explicitly does NOT include}

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | {Agent} | {What this agent builds} | — |
| S02 | CodeReview | Review S01 output | — |
| S03 | {Agent} | {What this agent builds} | — |
| S04 | CodeReview | Review S03 output | — |
| S05 | Tests | Additional test coverage | — |
| S06 | CodeReview | Review S05 output | — |
| S07 | CodeReview_Final | Global review of all work | — |
| S08..S16 | QV Gates | lint, format, typecheck, unit-tests, integration-tests | — |

Adjust steps based on feature needs. Not all features need all agents.
Agent slugs: `database-impl`, `backend-impl`, `api-impl`, `frontend-impl`, `tests-impl`, `pipeline-impl`, `template-impl`.

### Database Changes

- **New tables**: {table names or "None"}
- **Modified tables**: {table names or "None"}
- **Migration notes**: {any special considerations}

### API Changes

- **New endpoints**: {method + path or "None"}
- **Modified endpoints**: {method + path or "None"}

### Frontend Changes

- **New components**: {component names or "None"}
- **Modified components**: {component names or "None"}

## File Manifest

All files for this work item live under `ai-dev/design/active/{ID}/`:

| File | Type | Purpose |
|------|------|---------|
| `{ID}_Feature_Design.md` | Design | This document |
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

## Boundary Behavior

Define edge cases. **Every row becomes a mandatory test case.**

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| {Empty collection} | {e.g., 0 items} | {e.g., Return empty list} |
| {Invalid input} | {e.g., negative value} | {e.g., Reject with validation error} |
| {Missing reference} | {e.g., FK target deleted} | {e.g., Return 404} |

## Invariants

Conditions that **must hold true** after implementation. Each maps to a test.

1. {Invariant 1}
2. {Invariant 2}

## Dependencies

- **Depends on**: {F/I/CR numbers or "None"}
- **Blocks**: {F/I/CR numbers or "None"}

## Impacted Paths

Globs declared here populate `WorkItem.impacted_paths` and are mirrored to `workflow-manifest.json:scope.allowed_paths`. The cross-batch launch-time gate uses this list to detect overlap with in-flight items in the same project (F-00076). The merge-time scope gate uses the manifest mirror to enforce the allow-list when files are actually committed.

Parser rules:
- One glob per bullet line, OR globs inside a fenced code block.
- gitignore-style globs: `dir/**`, `*.py`, `path/to/file.py`.
- No absolute paths (must NOT start with `/`).
- No `..` segments.
- No whitespace in the glob itself.
- Test paths (`**/tests/**`, `**/__tests__/**`, `**/conftest*`, `*.test.*`, `*.spec.*`) are stored but ignored by the cross-batch gate — do NOT omit them.

Example:

- `orch/foo.py`
- `orch/bar/**`
- `dashboard/templates/components/**`
- `tests/integration/test_foo.py`

If you omit this section, `iw register` falls back to a regex sweep over the prose and stamps `WorkItem.config["scope_extraction"]["source"]="regex_fallback"`.

## TDD Approach

- Unit tests: {What to test}
- Integration tests: {What to test}
- Edge cases: {What to test}

## Notes

{Additional context, risks, or decisions.}
