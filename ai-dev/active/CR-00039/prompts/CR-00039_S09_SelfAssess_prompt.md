# CR-00039_S09_SelfAssess_prompt

**Work Item**: CR-00039 — Step Pipeline: Labeled Pill Redesign with Fix-Cycle Expansion
**Step**: S09
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
  1. Testcontainers spun up by pytest fixtures (self-label and self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

## ⛔ Migrations: agents generate, daemon applies

This CR makes no database changes. Do not touch migrations.

---

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var
- **Worktree logs** — `.worktrees/CR-00039/ai-dev/logs/`
- **Item reports dir** — `ai-dev/active/CR-00039/reports/`

## Output Files

- `ai-dev/active/CR-00039/reports/CR-00039_self_assess_report.md`
- `ai-dev/active/CR-00039/reports/CR-00039_self_assess_findings.json`

---

## Context

You are running the self-assessment step for work item **CR-00039**.

Invoke the `iw-item-analyze` skill to analyze the just-completed item's execution history
and surface process improvement findings. This step is **soft** — failure does NOT block
the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** via the `Skill` tool with `skill: "iw-item-analyze"`.
Do NOT re-implement the analysis inline.

---

## Soft-Step Semantics

This step's failure does NOT block merge. If the analysis cannot complete, write a stub
report explaining why and a `findings: []` JSON.

---

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "self-assess-impl",
  "work_item": "CR-00039",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00039/reports/CR-00039_self_assess_report.md",
    "ai-dev/active/CR-00039/reports/CR-00039_self_assess_findings.json"
  ],
  "preflight": {
    "format": "skipped:no-code-changes",
    "typecheck": "skipped:no-code-changes",
    "lint": "skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
