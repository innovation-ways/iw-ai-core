# I-00107_S13_SelfAssess_prompt

**Work Item**: I-00107 -- daemon reload does not apply `.iw-orch.json` changes for an already-running project
**Step**: S13
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

Standard policy. Read-only docker introspection only. Testcontainer fixtures in tests are exempt.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step ANALYZES; it does not modify the database. Read-only alembic commands only.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; canonical source).
- **Worktree logs** — `.worktrees/I-00107/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00107/reports/` — step reports for S01..S05 + the QV gate reports.

## Output Files

- `ai-dev/active/I-00107/reports/I-00107_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/I-00107/reports/I-00107_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for **I-00107**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process-improvement findings. This step is **soft** — its failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## What's worth looking for in this item specifically

I-00107 is a small, two-file daemon fix with a single new unit test file. Things worth flagging if you see them in the run logs:

- Fix cycles that thrash on the `make typecheck` or `make lint` gates — the daemon code is densely typed; a missing `from dataclasses import fields` import or a wrong type annotation on the new `BatchManager` rebuild path could cause repeated mypy failures.
- The `test_reload_emits_project_config_reloaded_event` test depending on a specific `emit_event` call signature — if S01 used `_emit_event` (the private helper inside `batch_manager.py` line 2224) instead of `emit_event` (the public daemon helper imported in `main.py:639`), S03's patch target may be wrong and the test would catch it as a flaky / mis-patched failure. That's a coordination issue worth surfacing.
- Any `make test-integration` invocation inside S01 or S03 — those are not part of the steps' Test Verification scope and routinely blow step timeouts (I-00073/S03 post-mortem).

## Soft-Step Semantics

This step's failure does NOT block merge. Produce a usable report anyway. If analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

For each behaviour-implementing step (notably S01 Backend) whose report claims new behavioural tests were added:

- The report should contain `tdd_red_evidence`. For I-00107 specifically, S01 delegates behavioural tests to S03, so its `tdd_red_evidence` should be the `"n/a — reproduction + regression tests delegated to S03 …"` form. That is correct.
- S03 (`tests-impl`) is exempt from the RED-first requirement — its `tdd_red_evidence` should be the `"n/a — tests-impl step …"` form.

Flag any deviation as a finding (severity LOW unless it indicates a missing test).

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "self-assess-impl",
  "work_item": "I-00107",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00107/reports/I-00107_self_assess_report.md",
    "ai-dev/active/I-00107/reports/I-00107_self_assess_findings.json"
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
