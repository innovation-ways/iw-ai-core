# I-00115_S14_SelfAssess_prompt

**Work Item**: I-00115 — Amend-scope modal locks the dashboard UI after dismissal
**Step**: S14
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy — no docker mutations, testcontainer fixtures exempt. Full text in `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not modify the database.

Allowed for agents: `alembic history`, `alembic current`, `alembic show`.

If your task seems to require applying a migration, STOP and raise a blocker.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; canonical source).
- **Worktree logs** — `.worktrees/I-00115/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00115/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/active/I-00115/reports/I-00115_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/active/I-00115/reports/I-00115_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00115**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process-improvement findings. This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default; reference it by name. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

For each **behaviour-implementing step** (notably Backend) whose report claims new behavioural tests were added:

- The report contains `tdd_red_evidence` recording the RED run and a plausible failure snippet.
- If the step added no behavioural test, the report says so with a one-line justification.

**Dedicated coverage steps (`tests-impl`) are exempt** — they add tests after the code exists.

For I-00115, S01 (frontend-impl) is a template-only step, so its `tdd_red_evidence` should read `"n/a — Jinja2 template fix only; ..."`. S03 (tests-impl) is exempt.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "I-00115",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00115/reports/I-00115_self_assess_report.md",
    "ai-dev/active/I-00115/reports/I-00115_self_assess_findings.json"
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
