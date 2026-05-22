# CR-00076_S12_SelfAssess_prompt

**Work Item**: CR-00076 — Data-Layer Test Module — Migrations, FTS, DB Identity
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
migration. CR-00076 has no migration. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; canonical source).
- **Worktree logs** — `.worktrees/CR-00076/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00076/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/CR-00076/reports/CR-00076_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/work/CR-00076/reports/CR-00076_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00076**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed
item's execution history and surface process-improvement findings. This step is
**soft** — failure does NOT block the item from merging. Produce the best report
you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code,
invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT
re-implement the analysis procedure inline — the skill is the source of truth
for the output contract (two files: `_self_assess_report.md` +
`_self_assess_findings.json`).

When analysing CR-00076 specifically, pay attention to:

- Did S01's `test_migration_revision_skew.py` cleanly reproduce the I-00075 /
  I-00076 failure (an absent revision ID making `alembic upgrade head` fail with
  the `Can't locate revision` error), or did it need fix cycles to land a
  deterministic assertion on the resolution error?
- Did the `tsvector`-column enumeration require S01 to inspect `orch/db/models.py`
  deeply? Were any of the three `tsvector` columns missed on the first pass and
  caught in review (S02/S03)? If so, note it as a gap in the design doc's guidance.
- Did the `integration-tests` gate (S09) need fix cycles from newly-surfaced
  data-layer bugs? Each fix cycle burns time and may indicate the test modules
  were not verified locally before reporting completion.
- Were all three `tdd_red_evidence` demonstrations present in the S01 report, or
  did S02/S03 need to request them? A missing demonstration is a process gap
  — S01 should never report completion without the evidence.
- Did `make data-layer-check` succeed end-to-end on first attempt in S03, or
  did the `migration-check` prerequisite surface a latent issue?

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway.
If the analysis can't complete, write a stub report explaining why and a
`findings: []` JSON.

## TDD RED Evidence

CR-00076 is a test-infrastructure CR. S01's `tdd_red_evidence` should record
**three deliberate-break demonstrations** (FTS trigger dropped → tsvector empty;
skew DB pointed at a valid head → `alembic upgrade head` succeeds and the
expected error is not raised; identity mismatch vacuated → mismatch case does
not fire) rather than a classic RED run. Confirm the S01 report contains all
three demonstrations and that all injections were reverted before S01 reported
completion.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "CR-00076",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00076/reports/CR-00076_self_assess_report.md",
    "ai-dev/work/CR-00076/reports/CR-00076_self_assess_findings.json"
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
