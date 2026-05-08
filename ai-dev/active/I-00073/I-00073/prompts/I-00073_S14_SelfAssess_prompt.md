# I-00073_S14_SelfAssess_prompt

**Work Item**: I-00073 — iw step-done/step-fail crash with UndefinedColumn when worktree ORM adds columns to step_runs/work_items
**Step**: S14
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. Allowed exceptions: testcontainers, read-only `docker ps/inspect/logs`, `./ai-core.sh` and `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Standard policy. Read-only `alembic history|current|show` only. Your job is to ANALYZE the item's execution, not to modify the database.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; canonical source).
- **Worktree logs** — `.worktrees/I-00073/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00073/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/active/I-00073/reports/I-00073_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/I-00073/reports/I-00073_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00073**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process improvement findings. This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default for the agent and you can reference it by name in your reasoning. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

Special focus for this incident: I-00073 was created as a direct response to a real failure observed during F-00079 S01. The "process learning" angle is especially interesting — was the structural collision (agent-modifies-orch-tables-then-cant-call-iw-step-done) flagged anywhere in the design phase, or did it only surface at runtime? If the design templates / agent prompts could be improved to make this kind of collision visible at design time, that's a high-value finding.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "I-00073",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00073/reports/I-00073_self_assess_report.md",
    "ai-dev/active/I-00073/reports/I-00073_self_assess_findings.json"
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
