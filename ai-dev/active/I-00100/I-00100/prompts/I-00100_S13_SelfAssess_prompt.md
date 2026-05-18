# I-00100_S13_SelfAssess_prompt

**Work Item**: I-00100 — Cascade thrashing detector is dead code in the production daemon path
**Step**: S13
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps` / `docker inspect` allowed; nothing else. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step is read-only analysis. No alembic commands.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor).
- **Worktree logs** — `.worktrees/I-00100/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00100/reports/` — every step report from S01..S12.

## Output Files

- `ai-dev/active/I-00100/reports/I-00100_self_assess_report.md` — human-readable narrative.
- `ai-dev/active/I-00100/reports/I-00100_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for I-00100. This step invokes the `iw-item-analyze` skill on the just-completed item.

**Use the `iw-item-analyze` skill** (auto-discovered via `.claude/skills/iw-item-analyze/SKILL.md` or its opencode equivalent). Do NOT re-implement the analysis procedure inline — the skill is the source of truth for both the analysis methodology and the output contract.

**Specific things worth flagging for I-00100 if they show up in the logs:**

- Whether the S01 plumbing patch had to fix-cycle (it shouldn't — it's a 3-line change with no behavioural risk).
- Whether the S03 integration test fix-cycled because the dead-PID setup was flaky (this is the most likely source of false failures and is worth a note for future tests in the daemon module).
- Whether any QV gate (S06..S12) consumed a fix cycle. If yes, name the gate and the cause; this is exactly the kind of avoidable cost the I-00100 fix is designed to prevent for *future* items, so a clean run here is itself useful evidence.
- Whether the manifest's `scope.allowed_paths` matched what was actually changed (the merge gate enforces this; deviations are an operator-facing signal).

## Soft-Step Semantics

This step's failure does NOT block merge. Produce a usable report even if the analysis is partial; in the worst case, write a stub report explaining why and emit `findings: []`.

## TDD RED Evidence Audit

For each behaviour-implementing step that claimed new tests:
- S01 (backend-impl) — expected `tdd_red_evidence == "n/a — pure plumbing fix; behavioural regression test added in S03 by tests-impl"`. The dedicated coverage step is S03. If S01's report instead claims a behavioural test, flag it as inconsistent.
- S03 (tests-impl) — exempt from RED-first; the `tdd_red_evidence` should be a reasoning statement ("would have failed because the production seam dropped project_config…"), not a runtime stash-recheck.

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "self-assess-impl",
  "work_item": "I-00100",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00100/reports/I-00100_self_assess_report.md",
    "ai-dev/active/I-00100/reports/I-00100_self_assess_findings.json"
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
