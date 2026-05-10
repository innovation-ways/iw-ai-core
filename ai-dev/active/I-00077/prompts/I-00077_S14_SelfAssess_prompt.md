# I-00077_S14_SelfAssess_prompt

**Work Item**: I-00077 — Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page
**Step**: S14
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
If a task seems to require a prohibited command, STOP and raise a blocker.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database or apply migrations.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `ai-dev/logs/` (run logs, fix-cycle logs) and the step logs for this item.
- **Item reports dir** — `ai-dev/active/I-00077/reports/` — existing step reports (secondary evidence).
- **Design doc** — `ai-dev/active/I-00077/I-00077_Issue_Design.md`.

## Output Files

- `ai-dev/active/I-00077/reports/I-00077_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/active/I-00077/reports/I-00077_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00077**. This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history (retries, fix cycles, agent thrash, repeated tool failures, prompt gaps, manifest issues) and surface concrete, evidence-anchored process-improvement findings. This step is **soft** — its failure does NOT block merge. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis (in Claude Code: the `Skill` tool with `skill: "iw-item-analyze"`; in OpenCode: it's loaded by default). Do NOT re-implement the analysis inline — the skill is the source of truth for the two-file output contract. The skill NEVER reviews the generated code itself and NEVER edits any file — it reports only.

Pay particular attention, if the evidence supports it, to: whether the S01 skill-wording change and the S03 dashboard change interacted cleanly across fix cycles; whether the S13 browser fixture (`e2e_fixtures/001_failed_doc_job.py`) needed iteration; and whether the `_default`-not-seeded-in-tests gotcha (tests use `create_all()`, not migrations) tripped up the integration test.

## Soft-Step Semantics

Failure here does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "I-00077",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00077/reports/I-00077_self_assess_report.md",
    "ai-dev/active/I-00077/reports/I-00077_self_assess_findings.json"
  ],
  "preflight": {"format": "ok|skipped:no-code-changes", "typecheck": "ok|skipped:no-code-changes", "lint": "ok|skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
