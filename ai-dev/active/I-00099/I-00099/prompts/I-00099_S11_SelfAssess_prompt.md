# I-00099_S11_SelfAssess_prompt

**Work Item**: I-00099 -- Scope-overlap sibling-dir rule generates false-positive cross-batch holds
**Step**: S11
**Agent**: SelfAssess

---

## ⛔ Docker is off-limits

Standard policy. Read-only docker introspection is allowed; mutating commands are not.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does NOT touch migrations. Your job is to ANALYZE the item's execution, not modify the database.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var.
- **Worktree logs** — `.worktrees/I-00099/ai-dev/logs/`.
- **Item reports dir** — `ai-dev/work/I-00099/reports/`.

## Output Files

- `ai-dev/work/I-00099/reports/I-00099_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/work/I-00099/reports/I-00099_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for work item **I-00099 — Scope-overlap sibling-dir rule generates false-positive cross-batch holds**.

Invoke the **`iw-item-analyze`** skill. Do NOT re-implement the analysis procedure inline. The skill is the source of truth for the two-file output contract.

I-00099-specific signals to surface in your report:

1. **Subtractive-fix pattern** — this was a small, purely subtractive Backend change (one production file, ~40 lines deleted). Did the workflow shape (Backend → CodeReview → Tests → CodeReview → CodeReview_Final → 5 QV gates) feel right for a subtractive change, or did any step feel like ceremony? Surface to inform whether a "minor-subtractive" workflow template is worth defining.
2. **Obsolete test deletion** — S03 had to delete a unit test (`test_non_test_sibling_still_blocks`) that pinned the very behaviour being removed. Did the agent execute the deletion cleanly, or did it try to "rescue" the test by adapting it? The first reviewer (S04) was explicitly instructed to flag a non-deletion as CRITICAL — was that pre-emptive guard needed?
3. **Cross-reference accuracy** — the design's reproduction tests reference exact path strings from real items (CR-00057, CR-00060). Did S03 use the exact strings, or did the agent paraphrase / abbreviate (e.g., `docs/A.md` instead of the real `docs/IW_AI_Core_Testing_Strategy.md`)? Paraphrasing here would weaken the regression net.
4. **Caller-contract verification** — S01 was asked to inspect `orch/daemon/batch_manager.py` read-only to confirm the event message becomes accurate. Did the agent record that finding in its report, or did it skip the read-only verification? Surface for future "read-only cross-check" prompts.

## Soft-Step Semantics

This step's failure does NOT block merge. Produce a usable report even if partial.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "self-assess-impl",
  "work_item": "I-00099",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/I-00099/reports/I-00099_self_assess_report.md",
    "ai-dev/work/I-00099/reports/I-00099_self_assess_findings.json"
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
