# CR-00091_S12_SelfAssess_prompt

**Work Item**: CR-00091 — Alembic PENDING Sentinel
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

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures (they self-label and self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which commands are safe.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT apply migrations to the live DB. Your role is analysis, not execution.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; this is the canonical source).
- **Worktree logs** — `.worktrees/CR-00091/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00091/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/CR-00091/reports/CR-00091_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/work/CR-00091/reports/CR-00091_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00091** — Alembic PENDING Sentinel.

Use the `iw-item-analyze` skill to perform the analysis. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline.

## Specific angles to investigate for this CR

In addition to the standard iw-item-analyze checks, pay attention to:

a. **Did the rewrite script's regex handle all three forms** (plain, type-annotated, None)? Check S01 TDD evidence and S03 findings to see if any edge case was missed.

b. **Did the resolver's head-computation correctly exclude PENDING files** from the chain before determining the real head? Look for S02's test 2 (single PENDING at chain end) — was the asserted value the immediate predecessor (B), not the initial revision (A)?

c. **Did `make migration-check` break for existing pipelines** (AC4)? Look for any fix cycles on S06/S10/S11 that suggest the resolver script's "nothing to do" path was not clean.

d. **Did the skills sync produce divergence** between `skills/` and `.claude/skills/`? The S04 report should show `iw sync-skills` was run. Check if the mirror files match.

e. **Was the documentation consistent across all three skills** (iw-new-cr, iw-new-feature, iw-new-incident)? Compare the three insertions — they should be identical in wording.

## Soft-Step Semantics

This step's failure does NOT block merge. Produce the best report you can even if the analysis is partial.

## TDD RED Evidence (behaviour-implementing steps only)

For each **behaviour-implementing step** (S01 and S02) whose report claims new behavioural tests were added:

- The report contains `tdd_red_evidence` — the field records a plausible failure snippet (`AssertionError`, not an import/collection error).
- S04 is exempt (documentation-only step).

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "CR-00091",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00091/reports/CR-00091_self_assess_report.md",
    "ai-dev/work/CR-00091/reports/CR-00091_self_assess_findings.json"
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
