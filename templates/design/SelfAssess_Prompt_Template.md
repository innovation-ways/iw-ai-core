# {TYPE}{NNN}_S{NN}_SelfAssess_prompt

**Work Item**: {ID} -- {Title}
**Step**: S{NN}
**Agent**: SelfAssess

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

Your job is to ANALYZE the item's execution, not to modify the database.

Allowed for agents:
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

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; this is the canonical source).
- **Worktree logs** — `.worktrees/{ID}/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/{ID}/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/{ID}/reports/{ID}_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/work/{ID}/reports/{ID}_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **{ID}**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's
execution history and surface process improvement findings. This step is **soft** —
failure does NOT block the item from merging. Produce the best report you can even
if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered
by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode (which
reads the same path). In Claude Code, invoke it via the `Skill` tool with
`skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default for the agent
and you can reference it by name in your reasoning. Do NOT re-implement the analysis
procedure inline — the skill is the source of truth for the output contract (two files:
`_self_assess_report.md` + `_self_assess_findings.json`).

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway.
If the analysis can't complete, write a stub report explaining why and a
`findings: []` JSON.

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S{NN}",
  "agent": "self-assess-impl",
  "work_item": "{ID}",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/{ID}/reports/{ID}_self_assess_report.md",
    "ai-dev/work/{ID}/reports/{ID}_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```