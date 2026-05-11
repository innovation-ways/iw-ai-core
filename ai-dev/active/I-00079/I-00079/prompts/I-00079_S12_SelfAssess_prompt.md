# I-00079_S12_SelfAssess_prompt

**Work Item**: I-00079 — Empty-state CTA links point to non-existent `/docs/<name>.md` route (404)
**Step**: S12
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state.
Allowed: testcontainers via pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` / `make` targets.
If a task seems to require a prohibited command, STOP and raise a blocker.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database or apply migrations. (This item touched no database/migrations anyway.)

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (canonical source).
- **Worktree logs** — `ai-dev/logs/` (run logs, fix-cycle logs) and the step logs for this item.
- **Item reports dir** — `ai-dev/active/I-00079/reports/` — existing step reports (secondary evidence).
- **Design doc** — `ai-dev/active/I-00079/I-00079_Issue_Design.md`.

## Output Files

- `ai-dev/active/I-00079/reports/I-00079_self_assess_report.md` — human-readable narrative analysis.
- `ai-dev/active/I-00079/reports/I-00079_self_assess_findings.json` — structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00079**. This step invokes the `iw-item-analyze` skill to analyze the just-completed item's execution history (retries, fix cycles, agent thrash, repeated tool failures, prompt gaps, manifest issues) and surface concrete, evidence-anchored process-improvement findings. This step is **soft** — its failure does NOT block merge. Produce the best report you can even if the analysis is partial.

**Use the `iw-item-analyze` skill** to perform the analysis (in Claude Code: the `Skill` tool with `skill: "iw-item-analyze"`; in OpenCode: it's loaded by default). Do NOT re-implement the analysis inline — the skill is the source of truth for the two-file output contract. The skill NEVER reviews the generated code itself and NEVER edits any file — it reports only.

This item was a small, well-scoped template fix (six `primary_href` string edits + a regression test). If the evidence supports it, pay particular attention to:
- whether S03's `empty-state__cta-primary` href-extraction regex matched what the `empty_state` macro actually emits on the first try, or needed adjustment (a brittleness signal worth a finding if it caused S03/S04 churn);
- whether the S03 regression tests' `client.get(...)` resolves-to-200 checks behaved the same under the TestClient as under the live dashboard, or surfaced any route/anchor surprise (especially `/system/docs/implementation/00_INDEX` — CR-00044's subdir doc serving);
- whether the qv-browser step (S11) could find a project with an empty Queue/History/Batches/Docs/Research in the prod-seeded E2E DB, or had to add an `e2e_fixtures/001_empty_project.py` — and if a fixture was needed, whether that should be a standing fixture in `scripts/e2e_seed.py` so future empty-state verifications don't repeat the work;
- whether this bug should have been caught earlier — e.g. a note about the `tests/dashboard/test_empty_states.py` "markers only, never follow the href" gap, and whether CR-00042's scope should have included the empty-state CTAs (the same class of broken link).

## Soft-Step Semantics

Failure here does NOT block merge — but produce a usable report anyway. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "self-assess-impl",
  "work_item": "I-00079",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00079/reports/I-00079_self_assess_report.md",
    "ai-dev/active/I-00079/reports/I-00079_self_assess_findings.json"
  ],
  "preflight": {"format": "ok|skipped:no-code-changes", "typecheck": "ok|skipped:no-code-changes", "lint": "ok|skipped:no-code-changes"},
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
