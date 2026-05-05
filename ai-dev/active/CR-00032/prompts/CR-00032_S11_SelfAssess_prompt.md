# CR-00032_S11_SelfAssess_prompt

**Work Item**: CR-00032 — Add test-location and assertion-scoping guidance to Issue Design Template
**Step**: S11
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following or any command that changes Docker
container/volume/network state. Allowed: testcontainers spun up by pytest
fixtures, read-only introspection (`docker ps`, `docker inspect`,
`docker logs`), and invoking `./ai-core.sh` / `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Not applicable. Your job is to ANALYZE the item's execution, not to modify
the database.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; this is the canonical source).
- **Worktree logs** — `.worktrees/CR-00032/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/CR-00032/reports/` — existing step reports.

## Output Files

- `ai-dev/active/CR-00032/reports/CR-00032_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/CR-00032/reports/CR-00032_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for CR-00032. This step invokes the
`iw-item-analyze` skill on the just-completed item to surface any process
improvement findings (agent thrash, repeated tool failures, prompt gaps,
manifest issues, etc.).

This CR is markdown-only and very small (one implementation step, one
per-step review, one final review, seven QV gates). Most CRs of this shape
complete cleanly on first try, in which case the report's "Bottom line"
should reflect that and the findings list may be empty.

Do **not** review the produced markdown content here — that's the job of S02
and S03. Your job is to analyze the *execution*: how many runs each step
took, how many fix cycles fired, what tool errors appeared in logs.

## Method

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is
auto-discovered by both Claude Code (via
`.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code,
invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode,
the skill is loaded by default.

Do NOT re-implement the analysis procedure inline — the skill is the source
of truth for the output contract (two files: `_self_assess_report.md` +
`_self_assess_findings.json`).

## Soft-Step Semantics

This step's failure does NOT block merge. Produce a usable report anyway. If
the analysis can't complete (e.g., logs missing), write a stub report
explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "self-assess-impl",
  "work_item": "CR-00032",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00032/reports/CR-00032_self_assess_report.md",
    "ai-dev/active/CR-00032/reports/CR-00032_self_assess_findings.json"
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
