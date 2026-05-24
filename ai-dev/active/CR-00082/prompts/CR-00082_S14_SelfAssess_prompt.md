# CR-00082_S14_SelfAssess_prompt

**Work Item**: CR-00082 -- Visual-regression test layer for rendered HTML and PDF documents
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

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; canonical source).
- **Worktree logs** — `.worktrees/CR-00082/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00082/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/CR-00082/reports/CR-00082_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/work/CR-00082/reports/CR-00082_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00082** — the visual-regression test layer.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process improvement findings. This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode (same path). In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

### Specific things to look for in this item

When reviewing CR-00082's history, pay extra attention to:

- **Pixel-tolerance churn**: did S01 pick a value that S02 had to override (sign that the InnoForge precedent doesn't map cleanly to this stack)?
- **Baseline-asset friction**: did the agent struggle to commit binary baselines (git LFS surprises, large-file warnings, encoding issues)?
- **Playwright CLI rule violations**: did any step have to retry because it reached for `chromium.launch()` / `agent-browser` / `npx playwright install` first? If yes, the agent prompts may need a stronger upfront callout.
- **`pdftoppm` / `poppler-utils` availability**: did the test skip in CI because the binary was missing, surfacing a CI-image gap?
- **QV-gate fix cycles**: which gates fired retries and why (especially `diff-coverage` — visual-regression test files are new code, so coverage on them is easy to miss).
- **Cross-agent integration friction**: did S03's CI workflow originally name a make target that S02 hadn't created (or named differently)? If yes, the prompts may need a stronger contract handoff between S01/S02 → S03.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

For each behaviour-implementing step (S01, S02 — Backend), verify the report's `tdd_red_evidence` field records the deliberate-regression demonstration (NOT a conventional unit test RED — this CR's pattern is different and documented in the design's `## TDD Approach` section). The evidence should describe: (a) the deliberate pixel-shift introduction, (b) the failing test output + `*-diff.png` path, (c) the revert + green re-run.

For S03 (CI yaml + docs + skill + tracker), `tdd_red_evidence` should be `"n/a — CI yaml + docs + skill + tracker edits only, no behavioural production logic"` or similar.

**Dedicated coverage steps (`tests-impl`) are exempt** from RED-first checks — this CR has none.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "CR-00082",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00082/reports/CR-00082_self_assess_report.md",
    "ai-dev/work/CR-00082/reports/CR-00082_self_assess_findings.json"
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
