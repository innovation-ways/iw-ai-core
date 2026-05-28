# CR-00092_S15_SelfAssess_prompt

**Work Item**: CR-00092 -- Column-docs baseline scrub
**Step**: S15
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker commands that change container/volume/network state. Read-only introspection (`docker ps`, `docker inspect`, `docker logs`) is allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

Your job is to ANALYZE the item's execution, not modify the database. Allowed for agents: `alembic history / current / show` (read-only). Allowed for operators only: `uv run iw migrations *`. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (= `CR-00092`).
- **Worktree logs** — `.worktrees/CR-00092/ai-dev/logs/`.
- **Item reports dir** — `ai-dev/work/CR-00092/reports/`.

## Output Files

- `ai-dev/work/CR-00092/reports/CR-00092_self_assess_report.md` — narrative.
- `ai-dev/work/CR-00092/reports/CR-00092_self_assess_findings.json` — structured findings.

## Context

You are running the self-assessment for **CR-00092 — Column-docs baseline scrub + gate flip**.

This is a soft step — failure does NOT block merge. Use the `iw-item-analyze` skill to perform the analysis. Do NOT re-implement the analysis procedure inline.

## Item-Specific Questions to Anchor the Analysis

Apart from the standard iw-item-analyze checks (agent thrash, tool failures, prompt gaps, redundant env steps), pay attention to:

1. **Did the four-wave split hold up?** Each wave (S01–S03) was 90–130 columns. Did any wave time out, run out of context, or need to be re-split? If so, document the actual sizing the next analogous baseline scrub should target. If the splits were comfortable, note that "~120 columns of mechanical doc= editing per wave" is a working size for this codebase.
2. **`DaemonEvent.event_metadata` rename trap**: did S04 correctly put `doc=` on the `Column(...)` declaration (not on the python attribute alias)? The scanner reports the SQL column name (`metadata`), not the python attribute name (`event_metadata`). Mishandling this was the structural risk called out in CR-00085's lessons.
3. **Description sourcing**: how often did agents fall back to inferred descriptions vs sourcing from `docs/IW_AI_Core_Database_Schema.md`? If the inferred-fraction is high, that suggests the schema doc has rotted relative to the model — a future Phase 4 doc-quality CR could be filed.
4. **Scope discipline**: did any wave touch `docs/IW_AI_Core_Database_Schema.md` accidentally? Did any wave touch `orch/db/migrations/versions/**`? Both were explicitly forbidden in the prompts; finding either in the diff is a process leak.
5. **Wave-count math**: did S01+S02+S03+S04 sum exactly to 450? If not, why — was the baseline drift between design-time (where 450 was measured) and S01 launch (where the actual count was read)? Note the drift size if any.
6. **Gate flip ordering**: did S04 correctly do the scrub THEN delete the baseline THEN flip the gate? Reversing that order makes the gate fail immediately and burns fix cycles. Confirm the report's narrative reflects the correct ordering.
7. **AC8 deliberate-break demonstration**: was it actually run, or did S04 hand-wave it? The demonstration is the only behavioural proof that the gate flip works.
8. **Comparable prior work**: compare against CR-00081 (78-entry assertion-baseline scrub, one CR) and CR-00085 (the scanner-kit CR that created this baseline). Time, fix cycles, and gate failures vs each — same/better/worse, and why.
9. **TDD RED evidence**: every wave's `tdd_red_evidence` should be the `"n/a — content-only doc= additions ..."` form. Any wave that misreported (e.g. claimed a behavioural RED that doesn't exist) → process finding.

## Soft-Step Semantics

This step's failure does NOT block merge — but produce a usable report. If the analysis can't complete, write a stub report explaining why and a `findings: []` JSON.

## TDD RED Evidence

This CR adds no behavioural tests. All four implementation steps (S01–S04) should report `tdd_red_evidence` in the `"n/a — content-only ..."` form. Flag any deviation as a process finding (not a blocking one).

## Subagent Result Contract

```json
{
  "step": "S15",
  "agent": "self-assess-impl",
  "work_item": "CR-00092",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "ai-dev/work/CR-00092/reports/CR-00092_self_assess_report.md",
    "ai-dev/work/CR-00092/reports/CR-00092_self_assess_findings.json"
  ],
  "preflight": {
    "format": "skipped:no-code-changes",
    "typecheck": "skipped:no-code-changes",
    "lint": "skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "skipped: no tests for analysis step",
  "blockers": [],
  "notes": "Analysis completed; findings written to two output files."
}
```
