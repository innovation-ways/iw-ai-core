# I-00075_S14_SelfAssess_prompt

**Work Item**: I-00075 -- Add E2E seed fixture with `fix_cycle_count >= 1` for browser verification of fix-cycle amber pills
**Step**: S14
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

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run any alembic command. Your job is to ANALYZE the item's
execution, not to modify the database.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; canonical source).
- **Worktree logs** — `.worktrees/I-00075/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00075/reports/` — existing step reports (secondary evidence).

## Output Files

- `ai-dev/active/I-00075/reports/I-00075_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/I-00075/reports/I-00075_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00075**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process improvement findings. This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default for the agent and you can reference it by name in your reasoning. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

I-00075 is itself a *post-mortem of CR-00039's S08 environment gap* — the analysis here is one level removed: did the fix flow itself thrash, did agents drift away from the design doc, did fix cycles fire on what should have been deterministic data assertions, etc. Lean on those signals.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway.
If the analysis can't complete, write a stub report explaining why and a
`findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "I-00075",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00075/reports/I-00075_self_assess_report.md",
    "ai-dev/active/I-00075/reports/I-00075_self_assess_findings.json"
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
