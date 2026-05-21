# I-00102_S14_SelfAssess_prompt

**Work Item**: I-00102 — iw register silently ignores design-package drift; approve must auto-refresh workflow_steps
**Step**: S14
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not to modify the database.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the daemon at launch).
- **Worktree logs** — `ai-dev/logs/` (relative to the worktree root).
- **Item reports dir** — `ai-dev/active/I-00102/reports/` and `ai-dev/work/I-00102/reports/`.

## Output Files

- `ai-dev/active/I-00102/reports/I-00102_self_assess_report.md` — human-readable narrative.
- `ai-dev/active/I-00102/reports/I-00102_self_assess_findings.json` — structured findings (see `orch/self_assess.py` for the schema).

## Context

You are running the self-assessment step for work item **I-00102**.

Use the **`iw-item-analyze`** skill. Do NOT re-implement the analysis inline. The skill reads the item's full execution history (step launches, retries, fix cycles, agent thrash, redundant tool invocations) and produces structured findings tied to recurring process issues — these become inputs for future improvements to CLAUDE.md, AGENTS.md, prompt templates, or the workflow manifest.

## Soft-Step Semantics

This step's failure does NOT block merge. (See `is_soft_step_failure` in `orch/self_assess.py`.) If the analysis cannot complete for any reason, fail loudly with a clear reason — the merge will proceed regardless, but the failure should still be recorded accurately so the next batch's analysis can pick up patterns.

## Subagent Result Contract

```bash
mkdir -p ai-dev/active/I-00102/reports
uv run iw step-done I-00102 --step S14 \
  --report ai-dev/active/I-00102/reports/I-00102_self_assess_report.md \
  --analysis-json ai-dev/active/I-00102/reports/I-00102_self_assess_findings.json
```

```json
{
  "step": "S14",
  "agent": "self-assess-impl",
  "work_item": "I-00102",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/active/I-00102/reports/I-00102_self_assess_report.md",
    "ai-dev/active/I-00102/reports/I-00102_self_assess_findings.json"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: analysis step, no tests",
  "tdd_red_evidence": "n/a — analysis step",
  "blockers": [],
  "notes": ""
}
```

If FAILED: `uv run iw step-fail I-00102 --step S14 --reason "..."` (soft — does not block merge).
