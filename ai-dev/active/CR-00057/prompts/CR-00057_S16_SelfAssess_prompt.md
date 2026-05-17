# CR-00057_S16_SelfAssess_prompt

**Work Item**: CR-00057 — AI Assistant chat model allowlist (per-project, with Ollama provider)
**Step**: S16
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

Standard policy. This step only reads logs and writes a report. No container mutation.

## ⛔ Migrations: agents generate, daemon applies

This step analyzes execution; it does not modify the database.

## Input Files

- Item ID — `$IW_ITEM_ID` env var (canonical source)
- `.worktrees/CR-00057/ai-dev/logs/` — run logs and fix-cycle logs
- `ai-dev/active/CR-00057/reports/` — every step report from S01..S15

## Output Files

- `ai-dev/active/CR-00057/reports/CR-00057_self_assess_report.md`
- `ai-dev/active/CR-00057/reports/CR-00057_self_assess_findings.json`

## Context

This is the mandatory final step for `iw-ai-core` (the project has `self_assess=true` in `projects.toml`). It runs the `iw-item-analyze` skill against CR-00057's full execution trace and surfaces process-level findings — agent thrash, redundant work, prompt gaps, env/install repeats, broken handoffs between layers. **It does NOT review the generated code itself** — that's what S06–S09 covered.

## Use the `iw-item-analyze` skill

Invoke the skill via the `Skill` tool with `skill: "iw-item-analyze"` (Claude Code) or by reference in OpenCode. Do **not** re-implement the analysis procedure inline; the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## Specific signals worth flagging for CR-00057

While the skill drives the analysis, the following CR-specific patterns are worth flagging if observed:

- S01 burned a fix-cycle on an `ImportError`/`SyntaxError` masquerading as RED evidence (a non-RED RED is a workflow bug).
- S02 needed multiple fix-cycles because the `_config_cache` migration from single-key to per-project broke a test the fix didn't update — that's a "test forgot to update with code" pattern worth raising.
- S03's frontend change accidentally required a server-side route addition mid-step (scope drift across agents).
- S05 had to context7-query opencode docs more than twice — points to a missing reference in CLAUDE.md or the design doc.
- The qv-browser step had to re-seed the worktree DB because the toml registry sync wasn't part of the standard seed flow — a real environment gap.

## Soft-step semantics

Failure here does NOT block merge. Produce the best report you can even if analysis is partial. If a log file is missing or unparseable, write a stub report explaining why and an empty `findings: []` JSON rather than aborting.

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "self-assess-impl",
  "work_item": "CR-00057",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/CR-00057/reports/CR-00057_self_assess_report.md",
    "ai-dev/active/CR-00057/reports/CR-00057_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
