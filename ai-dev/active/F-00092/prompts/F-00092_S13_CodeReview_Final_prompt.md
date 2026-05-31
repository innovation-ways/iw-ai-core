# F-00092_S13_CodeReview_Final_prompt

**Work Item**: F-00092 — Tier-1 orchestration DB backups
**Step**: S13
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Read-only Docker introspection only.

## Input Files

- `uv run iw item-status F-00092 --json`.
- `ai-dev/active/F-00092/F-00092_Feature_Design.md` + `F-00092_Functional.md`.
- All step reports in `ai-dev/active/F-00092/reports/`.
- The full diff for the item.

## Output Files

- `ai-dev/active/F-00092/reports/F-00092_S13_CodeReview_Final_report.md`.

## Global Review Focus

1. **End-to-end coherence**: model (S01) → engine (S03) → retention/restore (S05) →
   daemon scheduler (S06) → Jobs UI (S08) → CLI (S09) → docs (S10) → tests (S11) fit
   together; signatures match across steps; no dead/duplicated code.
2. **The properties that make backups actually useful**:
   - Globals captured (restore into a fresh cluster gets the `iw_orch` role+password).
   - Integrity-gated success (Invariant 2).
   - Manual backups never auto-pruned (Invariant 3).
   - Restore never clobbers live prod by default (Invariant 4).
   - On-demand backup works without the daemon (Invariant 5).
   - Catch-up fires after daemon downtime (AC4).
3. **All Acceptance Criteria (AC1–AC7) satisfied**, and every **Boundary Behavior**
   row has a corresponding test.
4. **Verification Placement Rule**: no AC is mis-mapped onto a `*-impl` step as a
   "full suite/aggregate gate passes" completion gate; suite execution is in the QV
   gates / tests step.
5. **Scope discipline**: only files in the design's Files Changed / Impacted Paths
   (plus `ai-dev/active/**`) are touched; no hardcoded ports/paths/creds; clean
   composition with I-00122's `ai-core.sh`/`.env.example`/`docs/IW_AI_Core_DB_Setup.md`
   edits.
6. **Docs accuracy**: README/CLAUDE/DB-Setup/restore-guide describe the actual
   implemented config vars, commands, and the ⚠️ same-disk limitation.
7. **Residual risk**: note anything deferred (Tier-2 physical/WAL/PITR/off-host) and
   any sharp edges operators should know.

## Result Contract

```json
{
  "step": "S13",
  "agent": "code-review-final-impl",
  "work_item": "F-00092",
  "completion_status": "complete",
  "findings": [{"severity": "...", "file": "...", "issue": "...", "recommendation": "..."}],
  "approved": true,
  "notes": "Summarize residual risk + Tier-2 follow-up."
}
```
