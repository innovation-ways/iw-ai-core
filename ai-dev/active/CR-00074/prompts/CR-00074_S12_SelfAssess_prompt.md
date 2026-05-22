# CR-00074_S12_SelfAssess_prompt

**Work Item**: CR-00074 — Cross-Project Isolation Test Matrix
**Step**: S12
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

Your job is to ANALYZE the item's execution, not to modify the database or any
migration. CR-00074 has no migration. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; canonical source).
- **Worktree logs** — `.worktrees/CR-00074/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00074/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/CR-00074/reports/CR-00074_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/work/CR-00074/reports/CR-00074_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00074**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed
item's execution history and surface process-improvement findings. This step is
**soft** — failure does NOT block the item from merging. Produce the best report
you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code,
invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT
re-implement the analysis procedure inline — the skill is the source of truth
for the output contract (two files: `_self_assess_report.md` +
`_self_assess_findings.json`).

When analysing CR-00074 specifically, pay attention to:

- Did S01 discover genuine isolation leaks (entries in `KNOWN_LEAK`)? A non-empty
  allowlist means real cross-project data leaks exist in production today — those
  Incidents are high-priority and should be surfaced prominently.
- Did S01 fix harness artefacts itself before allowlisting, or did it allowlist
  too eagerly? A large `KNOWN_LEAK` relative to the total routes/commands asserted
  is a red flag.
- Did the `integration-tests` gate (S09) need fix cycles? The isolation matrix
  is the first test to systematically exercise two-project seeding — latent
  fixture issues it surfaces burn S09 cycles.
- Did the `second_project` fixture introduce any order-dependency issues under
  `pytest-randomly`? A test that passes in fixed order but fails under a random
  seed is a test-isolation bug.
- Were the `tdd_red_evidence` demonstrations both present and convincing (Axis 1
  isolation fail + Axis 4 boundary fail), or was the evidence thin?

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway.
If the analysis can't complete, write a stub report explaining why and a
`findings: []` JSON.

## TDD RED Evidence

CR-00074 is a test-infrastructure CR. S01's `tdd_red_evidence` should record the
**deliberate-break demonstration** (an isolation case failing when a `project_id`
filter is removed; a boundary case failing when `orch/config.py`'s env-var
resolution is broken) rather than a classic RED run. Confirm the S01 report
contains that demonstration and that both injections were reverted.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "CR-00074",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00074/reports/CR-00074_self_assess_report.md",
    "ai-dev/work/CR-00074/reports/CR-00074_self_assess_findings.json"
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
