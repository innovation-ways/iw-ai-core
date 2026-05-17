# I-00089_S12_SelfAssess_prompt

**Work Item**: I-00089 -- AI Assistant panel — in-header collapse button is unusable in both states
**Step**: S12
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network
state. Read-only `docker ps` / `docker inspect` / `docker logs` is allowed.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp. Your job is to ANALYZE the
item's execution, not to modify state. Read-only `alembic history / current /
show` is allowed but not needed for a frontend-only item.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical; set by the executor).
- **Worktree logs** — `.worktrees/I-00089/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00089/reports/` — step reports (secondary evidence only).

## Output Files

- `ai-dev/active/I-00089/reports/I-00089_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/I-00089/reports/I-00089_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00089**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process improvement findings. This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## Soft-Step Semantics

This step's failure does NOT block merge. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence

This item has NO behaviour-implementing step (S01 is `frontend-impl`, which edits HTML/CSS only and is template-only by nature). The skill's TDD-RED checklist applies only to Backend / behaviour-implementing agents — apply this rule when scanning S01:

- S01 (`frontend-impl`) — `tdd_red_evidence` is expected to be `"n/a — template + CSS edits only, no production logic; behavioural tests added in S03 (tests-impl)"`. This is acceptable per the skill template's exemption list.
- S03 (`tests-impl`) — exempt from runtime-RED requirement; the report should reference the design-time RED reproduced via playwright-cli at incident intake (see `ai-dev/active/I-00089/evidences/pre/`).

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "I-00089",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00089/reports/I-00089_self_assess_report.md",
    "ai-dev/active/I-00089/reports/I-00089_self_assess_findings.json"
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
