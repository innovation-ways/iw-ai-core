# I-00087_S12_SelfAssess_prompt

**Work Item**: I-00087 — AI Assistant chat panel does not render model responses
**Step**: S12
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any Docker container/volume/network management command. Allowed: testcontainers via pytest fixtures, read-only `docker ps/inspect/logs`, and `./ai-core.sh`/`make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade`, `alembic downgrade`, or `alembic stamp` against the live orchestration DB.

Your job is to ANALYZE the item's execution, not to modify the database.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source; expected value `I-00087`).
- **Worktree logs** — `.worktrees/I-00087/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00087/reports/` — existing step reports.
- **Design** — `ai-dev/active/I-00087/I-00087_Issue_Design.md` (for context).

## Output Files

- `ai-dev/active/I-00087/reports/I-00087_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/active/I-00087/reports/I-00087_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00087**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process improvement findings. This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default for the agent and you can reference it by name in your reasoning. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## Analysis hints specific to I-00087

This work item is small (single-file production change + single test file). Likely findings to look for:

- **Workflow efficiency** — did S01 → S02 → S03 → S04 → S05 chain run without fix cycles? An incident this size should converge in one pass; >1 fix cycle on any step is a signal.
- **Test-protocol pinning effectiveness** — the new contract test (`test_chat_js_registers_every_interesting_event`) is the regression-prevention mechanism. Did it actually fail RED before the fix (per S03's `tdd_red_evidence`)?
- **Browser verification stability** — V1 in S11 depends on opencode + the minimax model provider responding within 15 s. If S11 timed out or hit ENV_DATA_MISSING, that is a known fragility worth recording (not a defect of this fix).
- **Cross-step contract drift** — the design pinned `INTERESTING_EVENTS` as the source of truth. Did any step bypass that and hard-code the event list separately?

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence (behaviour-implementing steps only)

For each **behaviour-implementing step** (S01 frontend-impl), check its report:

- The report contains `tdd_red_evidence` with one of two acceptable values:
  - `"n/a — production fix only; dedicated tests-impl step (S03) writes and runs the failing tests"` (the value the S01 prompt explicitly recommended)
  - A real RED snippet if S01 chose to also add its own behavioural test (unusual but allowed).

S03 (`tests-impl`) is a dedicated coverage step and is the ONE place RED evidence is mandatory in the strict sense. Verify S03's `tdd_red_evidence` is a real snippet (AssertionError, not ImportError/SyntaxError/collection error).

S02, S04, S05 are review steps — RED evidence is N/A.

S11 (qv-browser) is a verification step — RED evidence is N/A.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "I-00087",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00087/reports/I-00087_self_assess_report.md",
    "ai-dev/active/I-00087/reports/I-00087_self_assess_findings.json"
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
