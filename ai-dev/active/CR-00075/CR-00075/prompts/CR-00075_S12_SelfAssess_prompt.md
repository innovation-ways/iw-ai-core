# CR-00075_S12_SelfAssess_prompt

**Work Item**: CR-00075 — Security Test Module
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
migration. CR-00075 has no migration. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; canonical source).
- **Worktree logs** — `.worktrees/CR-00075/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00075/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/CR-00075/reports/CR-00075_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/work/CR-00075/reports/CR-00075_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00075**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed
item's execution history and surface process-improvement findings. This step is
**soft** — failure does NOT block the item from merging. Produce the best report
you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code,
invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT
re-implement the analysis procedure inline — the skill is the source of truth
for the output contract (two files: `_self_assess_report.md` +
`_self_assess_findings.json`).

When analysing CR-00075 specifically, pay attention to:

- Were any genuine vulnerabilities (xfailed tests with `TODO(file-incident)` placeholders) discovered during implementation? If so, surface them as high-priority follow-up work that the operator must triage before the next release — each placeholder in the S01 report's "Operator follow-up — SECURITY" section requires a separate Incident to be filed on `main` post-merge. A security vulnerability with only a placeholder and no assigned Incident yet is a risk that deserves explicit callout.
- Did the `integration-tests` gate (S09) need fix cycles? The security modules
  run new assertions against `orch/db/session.py` and the doc-render pipeline
  that may surface latent test-environment issues (e.g. the live-DB guard firing
  at collection time if env vars are set unexpectedly).
- Did the four-module tdd_red_evidence cover all four modules? A missing
  deliberate-break demonstration for any module is a process gap — note it.
- Was the `test-security-module` Makefile target correctly distinguished from
  the scanner targets in comments and docs? Confusion between asserted tests and
  advisory scanners is a recurring operator error — if the distinction was not
  clearly made, flag it for the docs team.
- Did S01 lean heavily on xfail for tests where the surface genuinely exists but
  the guard is only advisory (e.g. only logs, does not raise)? A cluster of
  xfailed tests in the live-DB guard module would indicate the guard's
  assertiveness needs improvement as a follow-up.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway.
If the analysis can't complete, write a stub report explaining why and a
`findings: []` JSON.

## TDD RED Evidence

CR-00075 is a test-infrastructure CR. S01's `tdd_red_evidence` should record the
**deliberate-break demonstrations** for all four security test modules — temporarily
inverted or weakened assertions inside the test files causing each module's cases to
fail RED, then reverted. These demonstrations must have been confined entirely to the
test files; no production guard or handler should have been patched. Confirm the S01
report contains those demonstrations and that `git diff origin/main -- orch/ dashboard/ executor/ scripts/` was empty before reporting completion.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "CR-00075",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00075/reports/CR-00075_self_assess_report.md",
    "ai-dev/work/CR-00075/reports/CR-00075_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files. Genuine vulnerabilities with TODO(file-incident) placeholders: <N or 'none'>. Operator follow-up Incidents still to be filed on main: <N or 'none'>."
}
```
