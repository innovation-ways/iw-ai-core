# I-00091_S15_SelfAssess_prompt

**Work Item**: I-00091 — Auto-merge settings form stays "Use global default" after partial-axis override
**Step**: S15
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps` / `docker logs` are fine; do not
change any container/volume/network state.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic commands. Your job is to ANALYZE the item's
execution, not to modify the database.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/I-00091/ai-dev/logs/` — run logs,
  fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00091/reports/` — all step
  reports (S01..S14).
- **Design + functional** — `ai-dev/active/I-00091/I-00091_Issue_Design.md`,
  `ai-dev/active/I-00091/I-00091_Functional.md`.

## Output Files

- `ai-dev/active/I-00091/reports/I-00091_self_assess_report.md` —
  human-readable narrative analysis.
- `ai-dev/active/I-00091/reports/I-00091_self_assess_findings.json` —
  structured findings JSON.

## Context

You are running the self-assessment step for I-00091. Invoke the
`iw-item-analyze` skill (auto-discovered at
`.claude/skills/iw-item-analyze/SKILL.md`). The skill is the source of
truth for the output contract — produce both files it specifies.

This is a **soft step**: failure does NOT block merge. Even partial
analysis is acceptable; write a stub with `findings: []` and a brief
"why partial" note if you cannot complete a full pass.

What I-00091 cares about specifically:

- Were any fix-cycles triggered by S02/S04/S06 reviews finding a
  CRITICAL/HIGH? If so, summarise the root cause and whether the
  reviewer caught a real issue or thrashed.
- Did S03 spend time fighting `make css` failures? If so, this is a
  recurring sign of I-00067 friction and should be surfaced.
- Did S05's tests hit "fixture 'client' not found" or similar
  placement errors that the CLAUDE.md mitigation should have prevented?
- Did the qv-browser step (S14) hit `ENV_DATA_MISSING` for
  `AgentRuntimeOption` rows? If so, the design's "no fixture needed"
  claim was wrong and should be flagged.
- Did any QV gate (S08..S13) catch issues that S01/S03 preflight
  should have caught (CR-00023 lesson)?

## Soft-Step Semantics

Failure does NOT block merge. Produce a usable report anyway. If the
analysis cannot complete, write a stub explaining why and a
`findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

For each behaviour-implementing step (notably S01 Backend) whose report
claims new behavioural tests were added:

- The report's `tdd_red_evidence` field is present and shows a
  plausible `AttributeError` / `AssertionError` failure snippet — NOT
  an ImportError / collection error.
- If the step added no behavioural test, the report uses
  `"n/a — <one-line reason>"`.

S05 (`tests-impl`) is a dedicated coverage step — exempt from
RED-first. Apply this checklist only to S01.

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "self-assess-impl",
  "work_item": "I-00091",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00091/reports/I-00091_self_assess_report.md",
    "ai-dev/active/I-00091/reports/I-00091_self_assess_findings.json"
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
