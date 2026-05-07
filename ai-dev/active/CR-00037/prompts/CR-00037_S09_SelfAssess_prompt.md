# CR-00037_S09_SelfAssess_prompt

**Work Item**: CR-00037 — Fix Diff2HtmlUI initialization guidance in F-00079_S06 prompt
**Step**: S09
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. Read the full text in any sibling implementation prompt. Do not run any docker mutating command. Read-only `docker ps`, `docker inspect`, `docker logs` are fine.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You are NOT modifying the database. Read-only `alembic history / current / show` is fine. Anything that changes DB state is forbidden.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/CR-00037/ai-dev/logs/` — run logs and any fix-cycle logs.
- **Item reports dir** — `ai-dev/active/CR-00037/reports/` — step reports (secondary evidence).

## Output Files

- `ai-dev/active/CR-00037/reports/CR-00037_self_assess_report.md` — narrative analysis.
- `ai-dev/active/CR-00037/reports/CR-00037_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for **CR-00037**, a deliberately tiny documentation-only CR (single markdown file, 9 steps, no QV-browser). This step invokes the `iw-item-analyze` skill on the just-completed item to surface process improvement findings.

Because the CR is small, expect a low finding count — the most likely report is "ran cleanly, no notable findings". That is a valid outcome; do not invent findings. If, however, you see signs of disproportionate fix-cycle activity (e.g., S02 or S03 caught real issues, QV gates triggered fix cycles for a markdown-only edit, or the implementing agent over-edited the target file), surface those — they are exactly the process signal this step exists to catch.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered at `.claude/skills/iw-item-analyze/SKILL.md` (Claude Code: invoke via the `Skill` tool with `skill: "iw-item-analyze"`; OpenCode: reference by name in your reasoning). The skill is the canonical source of truth for the output contract — do NOT re-implement the analysis procedure inline.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis cannot complete (e.g., logs unavailable), write a short stub `_self_assess_report.md` explaining why and emit `findings: []` in the JSON.

## Subagent Result Contract

```json
{
  "step": "S09",
  "agent": "self-assess-impl",
  "work_item": "CR-00037",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00037/reports/CR-00037_self_assess_report.md",
    "ai-dev/active/CR-00037/reports/CR-00037_self_assess_findings.json"
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
