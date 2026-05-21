# CR-00070 S08 Browser Verification Report

**Work Item:** CR-00070 — Show Resolved Agent + Model Instead of "Inherit" in Step Runtime Dropdowns
**Step:** S08
**Agent:** qv-browser
**Base URL:** `http://localhost:9939`
**Date:** 2026-05-21

---

## Overall Result: ✅ PASS

All V1–V4 verification steps passed. No regressions observed.

---

## Verification Results

| ID | Name | Status | Failure Class | Notes |
|----|------|--------|---------------|-------|
| V0 | Pre-flight page sanity | **pass** | — | All page routes visited cleanly, no console errors |
| V1 | Per-step dropdown shows `(inherited)` | **pass** | — | S03 `select` shows `OpenCode + MiniMax 2.7 (inherited)` as empty option; dropdown first entry confirmed |
| V2 | "Apply to remaining steps" dropdown shows `(inherited)` | **pass** | — | Bulk dropdown shows same `OpenCode + MiniMax 2.7 (inherited)` as empty/default option; non-empty options use full `display_name` format |
| V3 | Relabel survives PATCH round-trip | **pass** | — | Changed S03 to `OpenCode + MiniMax 2.7` (PATCH fires → "Model updated" toast); then selected `(inherited)` again (second PATCH fires); after each swap the empty option restored to `OpenCode + MiniMax 2.7 (inherited)` |
| V4 | No regressions | **pass** | — | All steps table columns intact; S01/S02 still show executed CLI/Model; completed steps show read-only badges; Overview tab renders; no console errors |

---

## Console Errors Observed

None. `.playwright-cli/console-*.log` was empty throughout all V1–V4 interactions.

---

## Screenshot Evidence

| File | Verification | Description |
|------|-------------|-------------|
| `evidences/post/CR-00070_v1_per_step_inherited.png` | V1 | Item detail page; S03 `select` open with `OpenCode + MiniMax 2.7 (inherited)` as selected/empty option; bulk dropdown also shows `(inherited)` |
| `evidences/post/CR-00070_v2_apply_remaining_inherited.png` | V2 | Same view, second screenshot showing bulk `Apply to remaining steps:` select and its `(inherited)` label |
| `evidences/post/CR-00070_v3_patch_round_trip.png` | V3 | After two htmx PATCH round-trips; `(inherited)` label correctly restored; `✓ Model updated` toast visible; overview tab loaded |
| `evidences/post/CR-00070_v4_no_regressions.png` | V4 | Same as V3 screenshot (overview tab with full steps table, no regressions) |

---

## Test Flow Detail

1. **Navigation:** Project home → Batches → CR-00066-S11-BATCH → item CR-00066-S11-FIXTURE
2. **V1 confirmed:** S03 step (status `pending`, no step-level override) — empty `<option>` reads `OpenCode + MiniMax 2.7 (inherited)` (not `— inherit —`). Six concrete options listed below it, all labelled with full `display_name` (e.g. `Pi + MiniMax 2.7`).
3. **V2 confirmed:** "Apply to remaining steps:" bulk select — same `OpenCode + MiniMax 2.7 (inherited)` as default; six concrete options, consistent `display_name` format.
4. **V3 round-trip:**
   - Selected `OpenCode + MiniMax 2.7` (non-inherited value `1`) → htmx PATCH to `/project/iw-ai-core/api/item/CR-00066-S11-FIXTURE/step/S03/runtime-override` → `✓ Model updated` toast → steps table re-rendered with CLI/Model columns now showing `OpenCode` / `MiniMax 2.7`.
   - Then selected `OpenCode + MiniMax 2.7 (inherited)` again → second PATCH fires → steps table re-renders → empty option back to `OpenCode + MiniMax 2.7 (inherited)`.
5. **V4:** Clicked Overview tab; full steps table renders correctly; all columns (Step, Agent, CLI, Model, Status, …) intact.

---

## Notes

- The E2E seed data (`pg_dump`-restored from production) already contained CR-00066-S11-FIXTURE, a work item with 3 completed steps and one pending step (S03), making it ideal for this verification without needing a custom fixture.
- The "Model updated" toast appeared twice (once per PATCH) confirming both runtime-override operations succeeded server-side.
- The `(inherited)` suffix is clearly visible on both the per-step and bulk dropdowns; the agent+model name is no longer obscured behind the word "Inherit".
- No console errors were logged during any page load or HTMX interaction.
- The item detail page route `/project/iw-ai-core/item/CR-00066-S11-FIXTURE` matches the UI navigation path used throughout.