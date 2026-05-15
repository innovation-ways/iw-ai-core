# CR-00054_S19_SelfAssess_prompt

**Work Item**: CR-00054 -- Add OpenCode stub to worktree E2E stack
**Step**: S19
**Agent**: self-assess-impl

---

## ⛔ Docker is off-limits

Standard policy. Read-only introspection allowed.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does NOT modify any state — it only analyses.

## Input Files

- **Item ID** — `$IW_ITEM_ID` env var (set by the executor; this is the canonical source).
- **Worktree logs** — `.worktrees/CR-00054/ai-dev/logs/` — run logs, fix-cycle logs.
- **Item reports dir** — `ai-dev/active/CR-00054/reports/` — existing step reports.
- **Cross-item peer reference** — `ai-dev/archive/F-00083/reports/F-00083_self_assess_findings.json` (if archived) for cross-item pattern signals between CR-00054 and the F-00083 it follows up on.

## Output Files

- `ai-dev/active/CR-00054/reports/CR-00054_self_assess_report.md` — Human-readable narrative analysis.
- `ai-dev/active/CR-00054/reports/CR-00054_self_assess_findings.json` — Structured findings JSON.

## Context

You are running the self-assessment step for **CR-00054** — the CR that adds an OpenCode stub to the worktree e2e stack to follow up on F-00083's S18 SPEC_MISMATCH.

Invoke the **`iw-item-analyze`** skill to perform the analysis (auto-discovered via `.claude/skills/iw-item-analyze/SKILL.md`). Do NOT re-implement the analysis procedure inline.

## Focus areas specific to CR-00054

When `iw-item-analyze` produces findings, pay particular attention to:

1. **Stub HTTP-shape mismatches**: Did any fix-cycle in S07 / S09 burn iterations because the stub's JSON shape didn't match `OpencodeClient`'s expectations? This is the highest-risk class of bug for this CR — and a signal that the design doc's "Desired Behavior" §3 endpoint table should have been more prescriptive about exact JSON keys.

2. **SSE replay path coverage**: Did the integration tests in S04 (and the QvBrowser run in S18) actually exercise the `Last-Event-ID` replay code path? If not, that's a gap — the design's AC6 promised coverage. Recommend tightening the test plan in future stub-CR designs.

3. **S18 UX gaps**: Did the qv-browser run in S18 surface chat UX behaviour that the deterministic stub could not simulate (e.g., real markdown rendering, multi-turn planning, real tool calls)? If yes, recommend extending the stub vocabulary as a follow-up.

4. **Cross-item pattern signals (CR-00054 ↔ F-00083)**: F-00083's self-assess findings (if archived) are the upstream peer. Compare:
   - Were there prompt-template improvement signals shared between the two items (e.g., both needed a clearer "what shape does OpencodeClient expect" doc reference)?
   - Did the SPEC_MISMATCH handling in F-00083 evolve in the right direction — was the design-doc §316 "skip with a clear reason" guidance enough, or should the design template explicitly enumerate which qv-browser failures map to which class?

5. **Image build time**: Did S08's "verify build time stays under ~3 min" check actually run? If S08 deferred it, note this as a documentation gap (the AC4 acceptance criterion needs an objective measurement point).

6. **Scope discipline**: Did any fix-cycle inadvertently touch F-00083 territory (`orch/chat/**`, `dashboard/routers/chat.py`, etc.)? If yes, that's a serious scope leak — flag as a finding even if the merge-gate caught it.

## Soft-Step Semantics

This step's failure does NOT block merge. Produce a usable report even if some inputs are missing.

## Subagent Result Contract

Per the `iw-item-analyze` skill output contract.

```json
{
  "step": "S19",
  "agent": "self-assess-impl",
  "work_item": "CR-00054",
  "completion_status": "complete|partial",
  "findings_count": 0,
  "report_path": "ai-dev/active/CR-00054/reports/CR-00054_self_assess_report.md",
  "findings_json_path": "ai-dev/active/CR-00054/reports/CR-00054_self_assess_findings.json",
  "notes": ""
}
```
