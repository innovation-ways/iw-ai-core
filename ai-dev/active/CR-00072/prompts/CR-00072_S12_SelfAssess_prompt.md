# CR-00072_S12_SelfAssess_prompt

**Work Item**: CR-00072 — Contract / No-5xx Route Sweep + schemathesis Fuzzing
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
migration. CR-00072 has no migration. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; canonical source).
- **Worktree logs** — `.worktrees/CR-00072/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00072/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/CR-00072/reports/CR-00072_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/work/CR-00072/reports/CR-00072_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00072**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed
item's execution history and surface process-improvement findings. This step is
**soft** — failure does NOT block the item from merging. Produce the best report
you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code,
invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT
re-implement the analysis procedure inline — the skill is the source of truth
for the output contract (two files: `_self_assess_report.md` +
`_self_assess_findings.json`).

When analysing CR-00072 specifically, pay attention to:

- Did S01 fix harness artefacts itself, or did it lean heavily on the
  `EXPECTED_5XX` allowlist? A large allowlist means the route table is more
  broken than expected — note it for follow-up.
- Did the `integration-tests` gate (S09) need fix cycles? The route sweep is the
  first test to exercise the *whole* route table — latent failures it surfaces
  burn S09 cycles.
- Did the `contract_fuzz` marker exclusion work first time, or did `diff-coverage`
  / `unit-tests` accidentally collect the fuzzer?
- Were any genuine 5xx allowlisted in `EXPECTED_5XX`? Each carries a
  `TODO(file-incident)` placeholder for the operator to file on `main`
  post-merge — surface them as follow-up work.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway.
If the analysis can't complete, write a stub report explaining why and a
`findings: []` JSON.

## TDD RED Evidence

CR-00072 is a test-infrastructure CR. S01's `tdd_red_evidence` should record the
**deliberate-break demonstration** (a route case failing on a throwaway 5xx
route registered on the test app; schemathesis reporting a 5xx on a throwaway
JSON route) rather than a classic RED run. Confirm the S01 report contains that
demonstration and that the throwaway routes were removed.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "CR-00072",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00072/reports/CR-00072_self_assess_report.md",
    "ai-dev/work/CR-00072/reports/CR-00072_self_assess_findings.json"
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
