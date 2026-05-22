# CR-00079_S12_SelfAssess_prompt

**Work Item**: CR-00079 — Generate smaller, single-concern workflow steps in the design-creation skills
**Step**: S12
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
- **Worktree logs** — `.worktrees/CR-00079/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00079/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/CR-00079/reports/CR-00079_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/work/CR-00079/reports/CR-00079_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00079**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed
item's execution history and surface process-improvement findings. This step is
**soft** — failure does NOT block the item from merging. Produce the best report
you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code,
invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the
skill is loaded by default. Do NOT re-implement the analysis procedure inline —
the skill is the source of truth for the output contract (two files:
`_self_assess_report.md` + `_self_assess_findings.json`).

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway.
If the analysis can't complete, write a stub report explaining why and a
`findings: []` JSON.

## TDD RED Evidence

CR-00079 is a Markdown guidance/template change with no production logic and no
test surface — S01 legitimately adds no behavioural test. Confirm S01's report
records `tdd_red_evidence` as an `"n/a — …"` justification, and do not flag the
absence of RED evidence as a problem.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "CR-00079",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00079/reports/CR-00079_self_assess_report.md",
    "ai-dev/work/CR-00079/reports/CR-00079_self_assess_findings.json"
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
