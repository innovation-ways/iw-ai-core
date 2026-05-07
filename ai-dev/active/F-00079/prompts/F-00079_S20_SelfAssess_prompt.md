# F-00079_S20_SelfAssess_prompt

**Work Item**: F-00079 — Files view: per-item git changes explorer with step drilldown and PDF export
**Step**: S20
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

Standard policy. Read-only docker introspection allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Read-only inspection only. Your job is ANALYSIS, not modification.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/F-00079/ai-dev/logs/` — run logs and fix-cycle logs.
- **Item reports dir** — `ai-dev/active/F-00079/reports/` — all step reports (S01..S19).
- Database telemetry via `uv run iw item-status F-00079 --json`.

## Output Files

- `ai-dev/active/F-00079/reports/F-00079_self_assess_report.md` — narrative analysis.
- `ai-dev/active/F-00079/reports/F-00079_self_assess_findings.json` — structured findings.

## Context

You are running the self-assessment step for **F-00079: Files view**. This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process improvement findings — agent thrashing, repeated tool failures, redundant env/install steps, prompt gaps, manifest issues.

This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## What to look for, specific to F-00079

This was a multi-layer feature with 20 steps spanning database, backend, API, frontend, template, tests, six QV gates, browser verification, and self-assess. Specific things worth flagging if they happened:

- Did agents struggle with the diff2html-ui CDN-vs-vendored decision? If they flip-flopped, the design's S06 prompt should be updated.
- Did the PDF export require a Chrome-headless fallback (because WeasyPrint couldn't render Pygments output)? If so, the design's library choice was wrong and S07 should have been more explicit.
- Did the `_list_artifact_tree` removal trigger downstream breakage? If so, S05 should have run a wider grep.
- Did the per-step diff capture in `iw step-done` cause any test flakiness? If so, the best-effort try/except in S03 should have been wider or narrower.
- Did the migration apply cleanly the first time? If not, what made it fail?
- Did agents repeatedly run the same env-setup commands across fix cycles (e.g., `uv sync`, `make css`)? If yes, those should be moved to a project-level setup script.
- Did the QV gate ordering (lint → format → typecheck → security-sast → tests) catch anything the per-agent reviews missed? If so, the per-agent CodeReview prompts may need stronger pre-flight gates.

Report findings even if the item ran cleanly — surfacing "ran cleanly" patterns is also valuable.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S20",
  "agent": "self-assess-impl",
  "work_item": "F-00079",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/F-00079/reports/F-00079_self_assess_report.md",
    "ai-dev/active/F-00079/reports/F-00079_self_assess_findings.json"
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
