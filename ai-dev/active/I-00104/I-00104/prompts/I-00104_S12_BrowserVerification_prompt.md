# Browser Verification Prompt: I-00104-S12-BrowserVerification

**Work Item**: I-00104 -- Batch planner false-negative overlap analysis + Max Parallel display mismatch
**Step**: S12
**Agent**: qv-browser

---

## ⛔ Docker is off-limits
(The orchestrator's E2E stack is already running.)

## ⛔ Migrations: agents generate, daemon applies
This Incident adds no migration.

## Environment

- `$IW_BROWSER_BASE_URL`
- `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
- `$IW_ITEM_ID` / `$IW_STEP_ID`

Use `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/I-00104/I-00104_Issue_Design.md`
- `orch/batch_planner.py` (fixed)
- `dashboard/routers/actions.py` (fixed)

## Output Files

- `ai-dev/active/I-00104/reports/I-00104_S12_BrowserVerification_Report.md`
- `ai-dev/active/I-00104/evidences/post/` — screenshots.

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

The seed DB is `pg_dump`-restored from production; BATCH-00127 with its overlapping items SHOULD be present. If not, seed via fixture (see template).

### Seed gap fallback

If no batch in the e2e DB has two items with overlapping globs, add `ai-dev/active/I-00104/e2e_fixtures/001_overlapping_batch.py`: a Project, a Batch with `max_parallel=5`, two WorkItems with `impacted_paths=["dashboard/**"]` and `impacted_paths=["dashboard/static/foo.js"]`, two BatchItems. Re-run seed inside the app container.

## Verification Steps

### V1: Overlap detection — Dependency Analysis shows the conflict

1. Navigate via UI to a batch detail Plan tab where two items have overlapping globs (BATCH-00127 if present, else the fixture-seeded batch).
2. Snapshot.
3. **Verify:** The Dependency Analysis table has at least one row with a non-empty `Overlap With` column (NOT `None`). The conflicting items mutually appear in each other's `Overlap With` cells.
4. **Screenshot:** `I-00104_v1_overlap_detected.png`.

### V2: Warnings section reflects the overlap

1. Same page; scroll to the Warnings section.
2. **Verify:** The Warnings section is NOT the bare line "None — all items are independent." It either lists the overlap pair OR — if the implementation chose to encode the warning via the `depends_on` serialization (so the overlap becomes a serial group) — at least one Group is no longer Group 0 parallel for those items.
3. **Screenshot:** `I-00104_v2_warnings_or_groups.png`.

### V3: Max Parallel matches between plan markdown and header

1. Same page; capture the page header chip (likely showing `Max parallel: 5` for BATCH-00127, or whatever the fixture set).
2. Capture the plan markdown's `**Max Parallel**: N` line (rendered under the Plan tab body).
3. **Verify:** N == header value. Exact equality. If the fixture set max_parallel=5, both must read 5.
4. **Screenshot:** `I-00104_v3_max_parallel_consistent.png`.

### V4: No regression on a clean (no-overlap) batch

1. Navigate to a different batch where items have strictly disjoint globs (any new batch with 2+ items from different projects in the seed will do).
2. **Verify:** Items are correctly listed as independent. `Overlap With: None` everywhere. Warnings section: `None — all items are independent.` (this IS the correct message in this case). Max Parallel matches the header.
3. **Screenshot:** `I-00104_v4_no_regression.png`.

### V5: No Regressions — adjacent flows

1. Open the Items tab of the same batch from V1; assert the Held items (if any) still show their `Held: …` pill (CR-00077/CR-00078 modal is unaffected by this fix).
2. Verify no JS console errors in `.playwright-cli/console-*.log`.
3. **Screenshot:** `I-00104_v5_items_tab_unaffected.png`.

## Pass Criteria

All V1..V5 must pass. V1/V2/V3 may legitimately fall back to `ENV_DATA_MISSING:` only if the e2e DB has zero batches with overlapping items AND fixture seeding fails for an environment reason.

## Report

Standard `iw step-done` / `iw step-fail` per the template.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "qv-browser",
  "work_item": "I-00104",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "<concrete URL>",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Overlap detected in Dependency Analysis", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Warnings section reflects overlap", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Max Parallel consistent", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "No regression on no-overlap batch", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions on Items tab", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
