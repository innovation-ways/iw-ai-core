# CR-00056_S23_SelfAssess_prompt

**Work Item**: CR-00056 -- Surface step prompts in dashboard (Prompt column + modal viewer)
**Step**: S23
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. Read-only docker introspection only.

## ⛔ Migrations: agents generate, daemon applies

You are analysing the just-completed item, not modifying the DB. `alembic history / current / show` are fine; do NOT run upgrade/downgrade/stamp.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/CR-00056/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/CR-00056/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/CR-00056/reports/CR-00056_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/work/CR-00056/reports/CR-00056_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **CR-00056** — a multi-layer change that spans the ORM model, alembic migration, daemon hot path, dashboard route, Jinja template, CSS, and vanilla JS.

**Use the `iw-item-analyze` skill** to perform the analysis. Invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract.

Focus areas given this CR's shape:

- **Cross-layer integration friction** — did the DB column add (S01) and the daemon write (S04) land cleanly, or did downstream steps (S06/S08) discover mismatches?
- **Frontend a11y patterns** — was reusing `activity_text_modal.html`'s focus-trap/Escape pattern smooth, or did the agent re-implement what should have been factored out?
- **Test coverage gaps** — did any AC slip through to qv-browser (S22) when it could have been unit-tested earlier?
- **Fix-cycle thrash** — how many fix cycles did each step burn? Common pattern in this CR shape: an early step that touches both the ORM and a migration sometimes oscillates between drift-check and lint.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence

For each behaviour-implementing step (notably S04 Backend) whose report claims new behavioural tests were added, verify the `tdd_red_evidence` field shows a plausible `AssertionError` / `NotImplementedError` from the new test (not an import or collection error). Frontend (S08) and Tests (S11) are exempt from RED-first.

## Subagent Result Contract

```json
{
  "step": "S23",
  "agent": "self-assess-impl",
  "work_item": "CR-00056",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00056/reports/CR-00056_self_assess_report.md",
    "ai-dev/work/CR-00056/reports/CR-00056_self_assess_findings.json"
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
