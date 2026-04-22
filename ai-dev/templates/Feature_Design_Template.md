# F{NNN}: {Feature Title}

**Type**: Feature
**Priority**: {Critical / High / Medium / Low}
**Created**: {YYYY-MM-DD}
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

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

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

## TDD Approach

- Unit tests: {What to test}
- Integration tests: {What to test}
- Edge cases: {What to test}

## Notes

{Additional context, risks, or decisions.}
