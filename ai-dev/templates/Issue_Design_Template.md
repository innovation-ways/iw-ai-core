# I{NNN}: {Issue Title}

**Type**: Issue
**Severity**: {Critical / High / Medium / Low}
**Created**: {YYYY-MM-DD}
**Reported By**: {Person or system that reported the issue}
**Status**: Draft | Approved | In Progress | Done

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

  alembic upgrade head
  alembic upgrade <revision>
  alembic downgrade <anything>
  alembic stamp <anything>

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

---

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

## TDD Approach

- Reproducing test: {Test that fails before fix}
- Unit tests: {What to test}
- Integration tests: {What to test}

## Notes

{Additional context, risks, or decisions.}
