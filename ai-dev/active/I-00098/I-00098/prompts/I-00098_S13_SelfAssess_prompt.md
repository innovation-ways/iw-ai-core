# I-00098_S13_SelfAssess_prompt

**Work Item**: I-00098 -- Keep-alive scheduler re-fires successful slots around UTC midnight (TZ mismatch in `get_due_slots`)
**Step**: S13
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps` / `docker inspect` / `docker logs` is allowed.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp`. This item touches no migrations; read-only `alembic history / current / show` is allowed but not relevant.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical; set by the executor).
- **Worktree logs** — `.worktrees/I-00098/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00098/reports/` — step reports (secondary evidence only).

## Output Files

- `ai-dev/active/I-00098/reports/I-00098_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/I-00098/reports/I-00098_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00098**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process improvement findings. This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## Soft-Step Semantics

This step's failure does NOT block merge. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (item-specific guidance)

When applying the skill's TDD-RED checklist to this item's steps:

- **S01 (`backend-impl`)** — `tdd_red_evidence` is expected to be `"n/a — behavioural regression test added in S03 (tests-impl); production logic change only"`. This is an explicit design decision (the bug lives in SQL semantics and a mocked unit test cannot demonstrate it), so the standard Backend-must-have-RED-test rule is replaced by "S03 owns RED for this item." Note this exemption in your findings if you flag it; do NOT raise it as a deficiency.
- **S03 (`tests-impl`)** — exempt from runtime-RED requirement (dedicated coverage step). The report should record per-test reasoning about whether each new test would have failed against pre-fix code.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "self-assess-impl",
  "work_item": "I-00098",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00098/reports/I-00098_self_assess_report.md",
    "ai-dev/active/I-00098/reports/I-00098_self_assess_findings.json"
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
