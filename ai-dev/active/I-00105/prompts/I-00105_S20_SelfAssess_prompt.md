# I-00105_S20_SelfAssess_prompt

**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Step**: S20
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state (`docker kill|stop|rm|restart`, `docker compose up|down|restart`,
`docker volume rm|prune`, `docker system|container|image prune`). Allowed:
testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`;
`./ai-core.sh` / `make` targets. STOP and raise a blocker if your task seems to
need a prohibited command. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live
orchestration DB. Your job is to ANALYZE the item's execution, not to modify
the database. Read-only `alembic history|current|show` is allowed. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; canonical source).
- **Worktree logs** — `.worktrees/I-00105/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/I-00105/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/I-00105/reports/I-00105_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/work/I-00105/reports/I-00105_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00105**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed
item's execution history and surface process-improvement findings. This step is
**soft** — failure does NOT block the item from merging. Produce the best report
you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code,
invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the
skill is loaded by default. Do NOT re-implement the analysis procedure inline —
the skill is the source of truth for the output contract (two files:
`_self_assess_report.md` + `_self_assess_findings.json`).

Note specifically: whether S02 (`migration-check`) or S17 (`integration-tests`)
needed fix cycles; whether the effective-budget formula stayed single-sourced
across S03 and S07; and whether any step itself hit a context-window limit
(the very class of bug this item fixes).

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway.
If the analysis can't complete, write a stub report explaining why and a
`findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

For each behaviour-implementing step (notably the Backend steps S03 and S07)
whose report claims new behavioural tests were added, verify the report's
`tdd_red_evidence` field records a real RED run with a plausible failure snippet
(`AssertionError` / `NotImplementedError`, not an import/collection error). If a
step added no behavioural test, the report must say so with a one-line
justification. The dedicated coverage step S09 (`tests-impl`) is exempt.

## Subagent Result Contract

```json
{
  "step": "S20",
  "agent": "self-assess-impl",
  "work_item": "I-00105",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/I-00105/reports/I-00105_self_assess_report.md",
    "ai-dev/work/I-00105/reports/I-00105_self_assess_findings.json"
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
