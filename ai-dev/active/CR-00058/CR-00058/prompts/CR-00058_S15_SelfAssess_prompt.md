# CR-00058_S15_SelfAssess_prompt

**Work Item**: CR-00058 — Configurable per-project scope-overlap gate with block/allow policy
**Step**: S15
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

Standard policy. Read-only analysis.

## ⛔ Migrations: agents generate, daemon applies

Read-only `alembic history/current/show` is fine. No mutations.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/CR-00058/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/CR-00058/reports/` — existing step reports (secondary evidence).

## Output Files

- `ai-dev/active/CR-00058/reports/CR-00058_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/CR-00058/reports/CR-00058_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for **CR-00058**. Invoke the `iw-item-analyze` skill to analyze the just-completed item's execution history (retries, fix cycles, agent thrash, repeated tool failures, prompt gaps). This step is **soft** — failure does NOT block merge. Produce the best report you can even if the analysis is partial.

The `iw-item-analyze` skill is auto-discovered by Claude Code (`Skill` tool, `skill: "iw-item-analyze"`) and OpenCode (loaded by default). Do NOT re-implement the analysis procedure inline — the skill is the source of truth.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report. If the analysis cannot complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

Check S01's report:

- `tdd_red_evidence` field present and shows a plausible failure snippet (`AssertionError` / `NotImplementedError`, not an import/collection error).
- If absent: flag as a finding so future runs include it.

Dedicated coverage steps (`tests-impl` in S02) are exempt — they add tests after the code exists.

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "self-assess-impl",
  "work_item": "CR-00058",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00058/reports/CR-00058_self_assess_report.md",
    "ai-dev/active/CR-00058/reports/CR-00058_self_assess_findings.json"
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
