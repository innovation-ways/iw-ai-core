# I-00120_S17_SelfAssess_prompt

**Work Item**: I-00120 -- Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid
**Step**: S17
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state. Read-only
introspection, testcontainer fixtures, and `./ai-core.sh` / `make` targets are allowed. Your job is to
ANALYZE the item's execution, not to modify anything. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations in this item. Do not run `alembic upgrade|downgrade|stamp`.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical).
- **Worktree logs** — `.worktrees/I-00120/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/I-00120/reports/` — step reports (secondary evidence).

## Output Files

- `ai-dev/work/I-00120/reports/I-00120_self_assess_report.md` — narrative analysis.
- `ai-dev/work/I-00120/reports/I-00120_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for **I-00120**. This step invokes the `iw-item-analyze`
skill to analyze the just-completed item's execution history (retries, fix cycles, agent thrash, tool
failures, prompt gaps) and surface process-improvement findings. It is a **soft** step — failure does
NOT block merge. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** (invoke via the `Skill` tool with `skill: "iw-item-analyze"` in
Claude Code; OpenCode loads it by name). Do NOT re-implement the analysis inline — the skill owns the
two-file output contract. NEVER review the generated code itself; this step is about the *process*.

## Soft-Step Semantics

Failure does not block merge — but produce a usable report anyway. If analysis can't complete, write a
stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S17",
  "agent": "self-assess-impl",
  "work_item": "I-00120",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/I-00120/reports/I-00120_self_assess_report.md",
    "ai-dev/work/I-00120/reports/I-00120_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
