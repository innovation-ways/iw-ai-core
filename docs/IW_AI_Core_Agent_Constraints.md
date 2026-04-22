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

### R2. (reserved for future rules)

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