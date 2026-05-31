# I-00121_S14_SelfAssess_prompt

**Work Item**: I-00121 — Allure reports & summaries missing for make-based test categories
**Step**: S14
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

You MUST NOT run any command that changes Docker state. Allowed: testcontainer fixtures,
read-only `docker ps|inspect|logs`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Analyze only — do not modify the database or run `alembic upgrade|downgrade|stamp`. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical).
- **Worktree logs** — `.worktrees/I-00121/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00121/reports/` — existing step reports (secondary evidence).

## Output Files

- `ai-dev/active/I-00121/reports/I-00121_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/I-00121/reports/I-00121_self_assess_findings.json` — Structured findings JSON.

## Context

Run the self-assessment step for **I-00121**. This step is **soft** — failure does NOT block
merge. Produce the best report you can even if analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis (invoke it via the `Skill` tool with
`skill: "iw-item-analyze"`). Do NOT re-implement the analysis inline — the skill is the source
of truth for the output contract (the two files above). It analyzes execution history (retries,
fix cycles, agent thrash, tool failures) and surfaces process-improvement findings. It NEVER
reviews the generated code itself and NEVER edits code.

## Soft-Step Semantics

If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

Check that the S01 (Backend) report carries `tdd_red_evidence` recording the RED run with a
plausible failure snippet (`AssertionError`, not an import/collection error). `tests-impl` (S03)
is exempt (tests authored after code exists).

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "I-00121",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00121/reports/I-00121_self_assess_report.md",
    "ai-dev/active/I-00121/reports/I-00121_self_assess_findings.json"
  ],
  "preflight": {"format": "skipped:no-code-changes", "typecheck": "skipped:no-code-changes", "lint": "skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
