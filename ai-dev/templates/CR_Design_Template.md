# CR{NNN}: {Change Request Title}

**Type**: Change Request
**Priority**: {Critical / High / Medium / Low}
**Reason**: {Why this change is needed — e.g., performance, maintainability, new requirement, deprecation}
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
