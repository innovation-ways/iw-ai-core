# I-00090_S14_SelfAssess_prompt

**Work Item**: I-00090 -- `/system/running` "Failed / Needs Attention" and "Recently Completed" tables show steps from inactive work items
**Step**: S14
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state. Read-only introspection
(`docker ps`, `docker inspect`, `docker logs`) is allowed.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run alembic upgrade/downgrade/stamp commands. Your job is
to ANALYZE the item's execution, not to modify the database.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; this is the canonical source — should resolve to `I-00090`).
- **Worktree logs** — `.worktrees/I-00090/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/I-00090/reports/` — existing step reports (secondary evidence only).
- **Design doc** — `ai-dev/active/I-00090/I-00090_Issue_Design.md`.

## Output Files

- `ai-dev/active/I-00090/reports/I-00090_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/I-00090/reports/I-00090_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00090**.

This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history and surface process improvement findings. This step is **soft** — failure does NOT block the item from merging. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis. The skill is auto-discovered by both Claude Code (via `.claude/skills/iw-item-analyze/SKILL.md`) and OpenCode. In Claude Code, invoke it via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default for the agent. Do NOT re-implement the analysis procedure inline — the skill is the source of truth for the output contract (two files: `_self_assess_report.md` + `_self_assess_findings.json`).

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence Audit (behaviour-implementing steps only)

For each **behaviour-implementing step** (notably Backend) whose report claims new behavioural tests were added:

- The report contains `tdd_red_evidence` — the field records `run the new failing test` (the RED run) and shows a plausible failure snippet (`AssertionError` / `NotImplementedError`, not an import/collection error). For I-00090, S01 (Backend) legitimately defers RED to S03 (Tests) because this is a query-helper fix; the explicit `"n/a — query-only filter; …"` form OR an inline-reproduction snippet is acceptable.
- If the step added no behavioural test, the report says so with a one-line justification.

**Dedicated coverage steps (`tests-impl`) are exempt** from the RED-first behavioural test gate. S03's `tdd_red_evidence` is still required per the S03 prompt (either an actual revert+failure run OR a textual reasoning sentence), but treat its absence as a process-quality finding, not a blocker.

Specific items to flag in your findings if you observe them on I-00090:

- S01's `tdd_red_evidence` empty/missing → MEDIUM process finding (the prompt explicitly allowed the `"n/a"` form, so it should never be blank).
- S03's `tdd_red_evidence` empty/missing → MEDIUM process finding (the S03 prompt requires either a snippet or a reasoning sentence).
- Any fix-cycle re-run on S01 that touched files outside `dashboard/routers/running.py` → HIGH "scope creep" finding.
- Any gate that exhausted fix cycles (5 retries) → CRITICAL workflow finding.
- The Failed table verification (S13 V1/V2) failing once and then passing → MEDIUM "seed sensitivity" finding (worth capturing whether the daemon's seed-refresh strategy is robust).

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "I-00090",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00090/reports/I-00090_self_assess_report.md",
    "ai-dev/active/I-00090/reports/I-00090_self_assess_findings.json"
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
