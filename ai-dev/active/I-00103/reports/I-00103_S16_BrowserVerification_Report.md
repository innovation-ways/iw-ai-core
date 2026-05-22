# I-00103-S16 Browser Verification Report

**Step**: S16 — Browser Verification (qv-browser agent)
**Work Item**: I-00103 — `merge_auto_resolution_failed` event drops per-file error string
**Base URL used**: `http://localhost:9926`
**Date**: 2026-05-22

---

## Pass/Fail Summary

| ID | Name | Status | Failure Class | Notes |
|----|------|--------|---------------|-------|
| V0 | Pre-flight page sanity | ✅ PASS | — | Auto-merge page loaded at `http://localhost:9926/project/iw-ai-core/auto-merge` without login |
| V1 | `per_file_errors` section visible when field is present (AC3) | ✅ PASS | — | Modal for `I-00103-fixture` event shows labelled "Per-file errors" section with file path, runtime, and error substring |
| V2 | Historical event renders without per-file-errors section (AC4 — backward compat) | ✅ PASS | — | Modal for `I-00091` (daemon_event id 80689, seeded as historical) opens with HTTP 200, no "Per-file errors" heading present, only "Metadata" with 7 keys |
| V3 | No regressions | ✅ PASS | — | All filter chips present; `merge_auto_resolved` event (I-00097) modal renders correctly with verdict buttons and no per-file-errors section; project home page loads cleanly |

**Overall**: ✅ ALL PASS

---

## Test Data

The E2E DB was seeded with three per-item fixtures:

| Fixture file | Event ID | `per_file_errors` key | Purpose |
|---|---|---|---|
| `001_seed_failed_event_with_per_file_errors.py` (pre-existing) | `I-00103-fixture` | ✅ Present | V1 — exercises the new "present" render path |
| `001_historical_failed_event_no_per_file_errors.py` | `I-00091` (daemon_event.id=80689) | ❌ Absent | V2 — exercises backward-compat "absent" render path |
| `002_historical_resolved_event.py` | `I-00097` (daemon_event.id=80528) | N/A (resolved type) | V3 — regression: resolved modal must not show per-file-errors |

---

## Screenshots Captured

All saved under `ai-dev/active/I-00103/evidences/post/`:

| Filename | Verification | What's shown |
|---|---|---|
| `I-00103_v1_per_file_errors_visible.png` | V1 | Modal for `I-00103-fixture` event: "Per-file errors" section visible with `tests/dashboard/test_auto_merge_routes.py`, `pi/minimax/MiniMax-M2.7`, and error substring |
| `I-00103_v2_per_file_errors_hidden_historical.png` | V2 | Modal for `I-00091` (pre-fix event): only "Message" and "Metadata" (7 keys) sections — no "Per-file errors" heading |
| `I-00103_v3_no_regressions.png` | V3 | Modal for `merge_auto_resolved` event (I-00097): verdict buttons + notes textbox — no per-file-errors section |
| `I-00103_v3b_project_home_page.png` | V3 | Project home page: service health, active batches, recent activity — clean, no errors |

---

## No Regressions Observed

The following were verified in V3:

1. **Event list view**: all 7 filter chips (`all / resolved / attempted / failed / skipped / health_probe / config_updated`) are present and functional.
2. **`merge_auto_resolved` modal (I-00097)**: renders correctly with Message section, Metadata section (7 keys), verdict buttons (pending/correct/wrong/partial), notes textbox, and Close/Save buttons — the new per-file-errors section does NOT appear.
3. **Project home page**: service health panel, active batches panel, recent activity panel all render correctly with no new console errors.
4. **Page navigation**: modal close (✕) works; navigating to project Dashboard link works cleanly.

---

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "I-00103",
  "overall_status": "pass",
  "overall_failure_class": null,
  "base_url_used": "http://localhost:9926",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass", "failure_class": null, "screenshot": "", "notes": "Auto-merge page loaded without login at http://localhost:9926/project/iw-ai-core/auto-merge"},
    {"id": "V1", "name": "per_file_errors visible (AC3)", "status": "pass", "failure_class": null, "screenshot": "I-00103_v1_per_file_errors_visible.png", "notes": "Modal shows 'Per-file errors' heading with file path tests/dashboard/test_auto_merge_routes.py, runtime pi/minimax/MiniMax-M2.7, and error substring LLM call timed out after 600s"},
    {"id": "V2", "name": "historical event renders without section (AC4)", "status": "pass", "failure_class": null, "screenshot": "I-00103_v2_per_file_errors_hidden_historical.png", "notes": "Modal opens HTTP 200 for I-00091 (id 80689, no per_file_errors key). No 'Per-file errors' heading visible. Metadata section present with 7 keys."},
    {"id": "V3", "name": "no regressions", "status": "pass", "failure_class": null, "screenshot": "I-00103_v3_no_regressions.png", "notes": "All 7 filter chips present. merge_auto_resolved modal (I-00097) renders correctly with verdict buttons + notes. Project home page loads cleanly."}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "I-00103_v1_per_file_errors_visible.png",
    "I-00103_v2_per_file_errors_hidden_historical.png",
    "I-00103_v3_no_regressions.png",
    "I-00103_v3b_project_home_page.png"
  ],
  "notes": "E2E DB was seeded with 3 per-item fixtures to cover V1 (per_file_errors present), V2 (per_file_errors absent), and V3 (resolved event regression check). All verifications passed cleanly."
}
```