# IW AI Core — Agent Constraints

This document is the authoritative policy for what AI agents running inside
this project are allowed and forbidden to do. Every agent-prompt template
and every `CLAUDE.md` references this file. Rules here take precedence over
step-specific instructions that contradict them.

## Scope

Applies to every agent invoked by the IW workflow, including:
- Step agents run by the daemon (`database-impl`, `backend-impl`, `api-impl`,
  `frontend-impl`, `tests-impl`, `pipeline-impl`, `template-impl`).
- Review agents (`code-review-impl`, `code-review-final-impl`).
- Quality-gate agents (`qv-gate`, `qv-browser`).
- Any sub-agent spawned via `Agent(...)` tool calls.

## Rules

### R1. ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

```
docker kill | docker stop | docker rm | docker restart
docker compose up | docker compose down | docker compose restart
docker-compose up | docker-compose down | docker-compose restart
docker volume rm | docker volume prune
docker system prune | docker container prune | docker image prune
```

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

### R2. ⛔ Migrations: agents generate, daemon applies

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

### R3. (reserved for future rules)

---

## Adding rules

New rules must:
- Have an ID (R2, R3, ...) for stable cross-referencing.
- Name a unique marker phrase used by the grep sanity test in
  `tests/integration/test_agent_constraints_coverage.py`.
- Link from every touch-point (templates + CLAUDE.md files).

## Related

- `docs/IW_AI_Core_DB_Setup.md` — the 2026-04-22 data-loss incident that
  motivated R1.
- `CLAUDE.md` (and sub-CLAUDE.md files) — per-layer critical rules.