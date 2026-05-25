# I-00110_S14_SelfAssess_prompt

**Work Item**: I-00110 -- Keep-alive slot endpoints return HTTP 500 on out-of-BIGINT slot_id path param
**Step**: S14
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

You MUST NOT execute docker container/volume/network state-changing commands.
Allowed: testcontainers via pytest fixtures, read-only introspection (`docker ps/inspect/logs`), `./ai-core.sh` and `make` targets.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp against the live orchestration DB.
Your job is to ANALYZE the item's execution, not to modify the database.

Allowed for agents:
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; this is the canonical source).
- **Worktree logs** — `.worktrees/I-00110/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/work/I-00110/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/work/I-00110/reports/I-00110_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/work/I-00110/reports/I-00110_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00110**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process improvement findings. This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode (which reads the same path). In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default for the agent and you can reference it by name in your reasoning. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

For each **behaviour-implementing step** (notably Backend) whose report claims new behavioural tests were added:

- The report contains `tdd_red_evidence` — the field records `run the new failing test` (the RED run) and shows a plausible failure snippet (`AssertionError` / `NotImplementedError`, not an import/collection error).
- If the step added no behavioural test, the report says so with a one-line justification (e.g. `"n/a — template/markdown edits only"`).

For I-00110, S01 (Backend) is the behaviour-implementing step. Its `tdd_red_evidence` MUST contain the pre-fix in-process probe output (both endpoints returning HTTP 500 with a `psycopg.errors.NumericValueOutOfRange` summary) AND the post-fix probe output (both 422 with `slot_id` in `detail[].loc`) — proving the fix transitions the actual behaviour.

**Dedicated coverage steps (`tests-impl`) are exempt** — they add tests after the code exists and are not RED-first by nature. S03 is this item's dedicated coverage step; its `tdd_red_evidence` uses the `"n/a — …"` form per the workflow contract.

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "I-00110",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/I-00110/reports/I-00110_self_assess_report.md",
    "ai-dev/work/I-00110/reports/I-00110_self_assess_findings.json"
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
