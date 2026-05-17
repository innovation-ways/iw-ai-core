# I-00088_S11_SelfAssess_prompt

**Work Item**: I-00088 — Auto-merge health probe always fails — CLI-shape mismatch with step_executor.sh
**Step**: S11
**Agent**: SelfAssess (`self-assess-impl`)

---

## ⛔ Docker is off-limits

You MUST NOT change docker container/volume/network state. Read-only
`docker ps` / `inspect` / `logs` is OK.

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You are analysing the item's execution — not modifying any database state.
Read-only `alembic history / current / show` is OK.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/I-00088/ai-dev/logs/`.
- **Item reports dir** — `ai-dev/work/I-00088/reports/`.

## Output Files

- `ai-dev/work/I-00088/reports/I-00088_self_assess_report.md`
- `ai-dev/work/I-00088/reports/I-00088_self_assess_findings.json`

## Context

You are running the self-assessment step for I-00088. The project has
`self_assess = true` in `projects.toml`, so this step runs as the LAST
step of the workflow — after all QV gates and after CodeReview_Final.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is
auto-discovered by Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`)
and OpenCode. Do NOT re-implement the analysis procedure inline.

## Soft-Step Semantics

This step's failure does NOT block merge. Produce the best report you can
even if the analysis is partial. If the analysis can't complete, write a
stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence

For each behaviour-implementing step (in this item: S01 Backend):

- Verify the S01 report's `tdd_red_evidence` field records a plausible RED
  run (an `AssertionError` snippet, not an `ImportError` or collection error).
- The S03 Tests step is a **dedicated coverage step** — exempt from RED
  evidence (its job is to add tests after the code already exists).

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "self-assess-impl",
  "work_item": "I-00088",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/I-00088/reports/I-00088_self_assess_report.md",
    "ai-dev/work/I-00088/reports/I-00088_self_assess_findings.json"
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
