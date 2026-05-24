# F-00090_S17_SelfAssess_prompt

**Work Item**: F-00090 -- Regression-rate tracking
**Step**: S17
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy applies. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade head` (or downgrade/stamp) against the live orch DB. Your job is to ANALYZE, not to modify the database. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; canonical source).
- **Worktree logs** — `.worktrees/F-00090/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/F-00090/reports/` — existing step reports (secondary evidence).

## Output Files

- `ai-dev/active/F-00090/reports/F-00090_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/F-00090/reports/F-00090_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **F-00090**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process-improvement findings. This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

For each **behaviour-implementing step** (notably Backend) whose report claims new behavioural tests were added:

- The report contains `tdd_red_evidence` — the field records `run the new failing test` (the RED run) and shows a plausible failure snippet (`AssertionError` / `NotImplementedError`, not an import/collection error).
- If the step added no behavioural test, the report says so with a one-line justification (e.g. `"n/a — template/markdown edits only"`).

**Dedicated coverage steps (`tests-impl`) are exempt** — they add tests after the code exists and are not RED-first by nature. For F-00090, S02 / S03 / S04 are the behaviour-implementing steps to check; S01 and S05 should use the `n/a — ...` form.

## Subagent Result Contract

```json
{
  "step": "S17",
  "agent": "self-assess-impl",
  "work_item": "F-00090",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/F-00090/reports/F-00090_self_assess_report.md",
    "ai-dev/active/F-00090/reports/F-00090_self_assess_findings.json"
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
