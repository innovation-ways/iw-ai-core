# I{NNN}: {Issue Title}

**Type**: Issue
**Severity**: {Critical / High / Medium / Low}
**Created**: {YYYY-MM-DD}
**Reported By**: {Person or system that reported the issue}
**Status**: Draft | Approved | In Progress | Done

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. State whether this item adds, modifies, or leaves migrations unchanged.)

## Description

{What is broken and the user-visible impact. 2-3 sentences.}

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.

## Steps to Reproduce

1. {Step 1}
2. {Step 2}
3. {Step 3}

**Expected**: {What should happen}

**Actual**: {What happens instead}

## Root Cause Analysis

{Explain why the bug occurs. Reference specific code paths, data conditions, or timing issues. If the root cause is unknown at draft time, state "TBD — requires investigation."}

## Affected Components

| Component | Impact |
|-----------|--------|
| {e.g., API layer} | {e.g., Returns 500 instead of 400} |
| {e.g., Database} | {e.g., Missing index causes slow query} |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | {Agent} | {What this agent fixes} | — |
| S02 | CodeReview | Review S01 output | — |
| S03 | Tests | Regression tests | — |
| S04 | CodeReview | Review S03 output | — |
| S05 | CodeReview_Final | Global review of all work | — |
| S06..S16 | QV Gates | lint, format, typecheck, unit-tests, integration-tests | — |

Adjust steps based on fix complexity. Simple fixes may need fewer steps.
Agent slugs: `database-impl`, `backend-impl`, `api-impl`, `frontend-impl`, `tests-impl`, `pipeline-impl`, `template-impl`.

### Database Changes

- **New tables**: {table names or "None"}
- **Modified tables**: {table names or "None"}
- **Migration notes**: {any special considerations}

### Code Changes

- **Files to modify**: {file paths or "TBD"}
- **Nature of change**: {e.g., Add validation, fix query, correct logic}

## File Manifest

All files for this work item live under `ai-dev/design/active/{ID}/`:

| File | Type | Purpose |
|------|------|---------|
| `{ID}_Issue_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/{ID}_S01_{Agent}_prompt.md` | Prompt | S01 fix instructions |
| ... | ... | ... (one per step) |

Reports are created during execution in `ai-dev/work/{ID}/reports/`.

## Test to Reproduce

Write a failing test that demonstrates the bug before fixing it.

```python
def test_{issue_id}_reproduces_bug():
    """This test should FAIL before the fix and PASS after."""
    # Arrange
    {setup that triggers the bug}

    # Act
    {action that exhibits the bug}

    # Assert
    {assertion that captures the correct behavior}
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given {the conditions that trigger the bug}
When {the action is performed}
Then {the correct behavior occurs}
```

### AC2: Regression test exists

```
Given the fix is applied
When the test suite runs
Then the reproducing test passes
```

## Regression Prevention

{What structural changes, validations, or tests will prevent this class of bug from recurring? Consider: input validation, type constraints, database constraints, automated checks.}

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

- Reproducing test: {Test that fails before fix}
- Unit tests: {What to test}
- Integration tests: {What to test}

## Notes

{Additional context, risks, or decisions.}
