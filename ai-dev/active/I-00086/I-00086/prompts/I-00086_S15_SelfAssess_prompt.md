# I-00086_S15_SelfAssess_prompt

**Work Item**: I-00086 -- Runtime override controls give no UI feedback
**Step**: S15
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps`/`docker inspect`/`docker logs` allowed. No state-changing commands.

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not modify the database. No alembic commands against the live DB.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `.worktrees/I-00086/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00086/reports/` — existing step reports (secondary evidence only).

## Output Files

- `ai-dev/active/I-00086/reports/I-00086_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/I-00086/reports/I-00086_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for **I-00086 — runtime override controls give no UI feedback**.

This step invokes the `iw-item-analyze` skill to surface process improvement findings from the item's execution history. This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default for the agent. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract.

The skill produces:
- `I-00086_self_assess_report.md` — narrative analysis.
- `I-00086_self_assess_findings.json` — structured findings.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence

This work item has the following behaviour-implementing steps subject to the RED check:

- **S01 (api-impl)** — modified two endpoint response shapes (status + body + header). Its `tdd_red_evidence` should record a captured failure of an existing test that pinned `status_code == 204`, OR a `curl -i` snippet showing pre-change 204. Flag a HIGH finding if the field is empty or shows an unrelated error (ImportError, SyntaxError, collection error).
- **S03 (frontend-impl)** — template-only changes; `"n/a — template-only ..."` form is acceptable.
- **S05 (tests-impl)** — exempt from per-step RED-evidence rule (dedicated coverage step). `"n/a — coverage step..."` is acceptable.

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "self-assess-impl",
  "work_item": "I-00086",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00086/reports/I-00086_self_assess_report.md",
    "ai-dev/active/I-00086/reports/I-00086_self_assess_findings.json"
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
