# F-00089_S19_SelfAssess_prompt

**Work Item**: F-00089 -- Daemon chaos / fault-injection test layer
**Step**: S19
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. Read-only `docker ps`/`inspect`/`logs` allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step ANALYZES execution; it does NOT modify the database. Read-only alembic commands (`history`/`current`/`show`) allowed. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `$IW_ITEM_ID` (canonical) = `F-00089`.
- `.worktrees/F-00089/ai-dev/logs/` — run logs + fix-cycle logs (primary evidence).
- `ai-dev/work/F-00089/reports/` — step reports (secondary evidence).
- DB telemetry — query via `iw item-status F-00089 --json` and the DB session.

## Output Files

- `ai-dev/work/F-00089/reports/F-00089_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/work/F-00089/reports/F-00089_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment for **F-00089: Daemon chaos / fault-injection test layer** — a 19-step Feature that added a new integration-test layer (one harness + five scenario modules + Makefile + GH workflow + workflow skill canon + testing skill + strategy doc + tracker).

This step is **soft** — its failure does NOT block merge — but produce a usable report regardless. If analysis can't complete, write a stub explaining why and a `findings: []` JSON.

**Use the `iw-item-analyze` skill** to do the work. In Claude Code, invoke via the `Skill` tool with `skill: "iw-item-analyze"`. In OpenCode, the skill is loaded by default. Do NOT re-implement the analysis inline — the skill is the source of truth for the two-file output contract.

## Item-Specific Context for the Analyzer

When you (or `iw-item-analyze`) build the report, pay particular attention to:

- **S01 harness step** — the gating step. Did the agent need multiple fix cycles to land the API? If yes, were the later scenario steps (S02..S06) re-running because of API drift, or for independent reasons? An expensive S01 + cheap S02..S06 is the expected pattern; cheap S01 + thrashy S02..S06 is a red flag (API was wrong but undiagnosed in S01).
- **S05 squash-merge step** — did the F-00084 dual-path branch fire correctly? Which branch was exercised (F-00084 present or absent)?
- **`xfail` pins filed during execution** — list every Incident ID filed by S02..S06 (if any). Cross-check each against the live DB (`iw item-status I-NNNNN --json`) to confirm the Incident was actually registered.
- **Skill-sync mirror discipline** — did S07 and S08 both invoke `iw sync-skills --force` and commit both the master + mirror? Mirror-drift was the I-00067 / earlier issue class.
- **The 9-vs-8 gate split** — confirm `daemon-chaos-smoke` appears in `skills/iw-workflow/SKILL.md` canonical chain but NOT in `ai-dev/active/F-00089/workflow-manifest.json`. If the agent accidentally added it to its own manifest mid-execution, that's a finding (Invariant 10 regression).
- **TDD RED evidence quality** — were the captured RED lines plausible (`AssertionError` for the right reason) or did the agent dump a meaningless trace? Vacuous RED evidence is a `tdd_red_evidence` quality issue worth flagging.

## TDD RED Evidence (behaviour-implementing steps only)

Apply the standard check to S01..S06 (Backend steps that added behavioural tests):

- The report contains `tdd_red_evidence` with a plausible failure snippet (`AssertionError`/`NotImplementedError`/`AttributeError`, not `ImportError`/`SyntaxError`/collection error).
- If a step legitimately added no behavioural test, the report uses `"n/a — ..."` with a one-line justification. S07 (wire-up) and S08 (docs) should use the `n/a` form.

`code-review-impl` (S09, S10) and `self-assess-impl` (this step) are exempt.

## Subagent Result Contract

```json
{
  "step": "S19",
  "agent": "self-assess-impl",
  "work_item": "F-00089",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/F-00089/reports/F-00089_self_assess_report.md",
    "ai-dev/work/F-00089/reports/F-00089_self_assess_findings.json"
  ],
  "preflight": {
    "format": "skipped:no-code-changes",
    "typecheck": "skipped:no-code-changes",
    "lint": "skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: analysis-only step, no tests",
  "blockers": [],
  "notes": "Findings written to two output files."
}
```
