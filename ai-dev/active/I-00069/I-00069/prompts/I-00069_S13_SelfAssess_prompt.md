# I-00069_S13_SelfAssess_prompt

**Work Item**: I-00069 -- Downgrade LiveDbConnectionRefusedError to DEBUG/WARNING in test context
**Step**: S13
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Read-only docker introspection only. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database.
Read-only `alembic history|current|show` only.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; this is the canonical source).
- **Worktree logs** — `.worktrees/I-00069/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00069/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/active/I-00069/reports/I-00069_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/I-00069/reports/I-00069_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00069**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed
item's execution history (all steps S01..S12) and surface process improvement
findings. This step is **soft** — failure does NOT block merge. Produce the
best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is
auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`)
and OpenCode (which reads the same path). In Claude Code, invoke it via the
`Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the skill is loaded
by default for the agent and you can reference it by name in your reasoning.
Do NOT re-implement the analysis procedure inline — the skill is the source of
truth for the output contract (two files: `_self_assess_report.md` +
`_self_assess_findings.json`).

This is a tiny incident (~5–8 LOC of production change + ~30 LOC of tests),
so most likely there is little to assess. If S01..S12 ran cleanly with no
retries, write a short report saying so and `findings: []`. If anything
required a fix-cycle, surface the root cause and recommend an improvement
to the prompt, manifest, or convention that prevents recurrence.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway.
If the analysis can't complete, write a stub report explaining why and a
`findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "self-assess-impl",
  "work_item": "I-00069",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00069/reports/I-00069_self_assess_report.md",
    "ai-dev/active/I-00069/reports/I-00069_self_assess_findings.json"
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
