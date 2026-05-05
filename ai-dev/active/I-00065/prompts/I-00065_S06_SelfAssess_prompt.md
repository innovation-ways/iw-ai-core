# I-00065_S06_SelfAssess_prompt

**Work Item**: I-00065 -- Code-view chat panel — "+ New" visible when collapsed and duplicates greeting
**Step**: S06
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY state-changing docker command. Read-only
introspection (`docker ps`, `docker inspect`, `docker logs`) is allowed.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job is to ANALYZE the item's execution, not to modify the database.

Allowed for agents (read-only): `alembic history / current / show`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical, set by the executor).
- **Worktree logs** — `.worktrees/I-00065/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00065/reports/` — existing step reports (S01..S05) as secondary evidence.
- **Item design** — `ai-dev/active/I-00065/I-00065_Issue_Design.md` and `I-00065_Functional.md`.

## Output Files

- `ai-dev/active/I-00065/reports/I-00065_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/I-00065/reports/I-00065_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00065**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process-improvement findings — agent thrashing, repeated tool failures, redundant env/install steps, prompt gaps, manifest issues. It does **NOT** review the generated code itself; only the workflow and prompts that produced it.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode (which reads the same path). In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

Special context for this incident:

- This is a **trivial frontend-only fix** (one CSS selector clause + one new JS guard line). Expect the fix-cycle count to be very low; if it isn't, that itself is a finding (the prompt may be over-prescribed or the gates over-broad for the surface area).
- The qv-browser step (S15) is the end-to-end backstop. If S15 produced ENV_DATA_MISSING failures or required fixture additions, surface it as an environment-gap finding, not a code defect.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway.
If the analysis can't complete, write a stub report explaining why and a
`findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "self-assess-impl",
  "work_item": "I-00065",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00065/reports/I-00065_self_assess_report.md",
    "ai-dev/active/I-00065/reports/I-00065_self_assess_findings.json"
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
