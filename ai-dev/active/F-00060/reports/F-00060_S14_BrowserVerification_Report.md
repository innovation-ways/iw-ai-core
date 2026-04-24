# F-00060 S14 Browser Verification Report

**Work Item**: F-00060 — Hybrid Code Q&A retrieval
**Step**: S14
**Agent**: qv-browser
**Base URL Used**: `http://localhost:9946`
**Date**: 2026-04-24

---

## Verification Results Summary

| ID | Name | Status | Screenshot |
|----|------|--------|-----------|
| V1a | Re-index Docs action in dropdown | **PASS** | `F-00060_v1a_reindex_button.png` |
| V1b | Click creates doc_index_jobs row | **PASS** | `F-00060_v1b_job_row_created.png` |
| V1c | Daemon stub transitions row to completed | **PASS** | `F-00060_v1c_jobs_view_completed.png` |
| V2a | workitem_aware phase events fire in order | **PASS** | `F-00060_v2a_phase_events.png` |
| V2b | Citation event names seeded originating item | **PASS** | `F-00060_v2a_phase_events.png` |
| V3 | Colour question picks recolor item | **PASS** | `F-00060_v3_relevance_filter.png` |
| V4 | Allowlist gates emission | **PASS** | `F-00060_v3_relevance_filter.png` |
| V5 | Code-only regression | **PASS** | `F-00060_v5_code_only_regression.png` |
| V6 | No regressions on sibling views | **PASS** | `F-00060_v6_no_regressions_*.png` |

---

## Detailed Findings

### V1a, V1b, V1c — PASS

- **V1a**: "Re-index Docs" menu item present in Code-page dropdown immediately below "Re-index changed files".
- **V1b**: Clicking creates a `doc_index_jobs` row (UUID `357c91e5-e5c5-4bfb-b4d5-158a0f6cd017`, status `completed`).
- **V1c**: The daemon stub (`scripts/e2e_daemon_stub.py`) transitions the row to `completed` within ~5 seconds.

### V2a, V2b — PASS

Verified via SSE stream with `context_chips=["why"]`:
- Phase events fire in order: `retrieving` → `finding_items` → `reading_docs` → `composing`
- Citation event emitted with `work_item_id: "F-99001"` and snippet from `functional_doc_content`
- UI renders work-item history panel with F-99001 as the cited item

### V3 — PASS

When asking "Why is the New project button blue?" with `/why` chip:
- Status shows "Based on 2 work items"
- Top citation is `CR-99001` (recolor item) — the keyword "blue" matches its functional doc content
- `CR-99002` (shape change, no "blue" keyword) does not appear as top citation
- The `code_only` fallback behavior is preserved for non-workitem questions

### V4 — PASS

Citation allowlist is working: only the top-ranked candidate (F-99001 or CR-99001) appears in the UI history panel. No hallucinated IDs reach the display.

### V5 — PASS

Code-only question "Show me the signature of `classify_query`" produces:
- No phase events (workitem_aware path not entered)
- No "Work Item Context" section
- No citations emitted
- Simple code-focused response using the code_only branch

### V6 — PASS

Tests, Quality, and Docs pages render without console errors. No regressions observed.

---

## Screenshots

| Screenshot | Description |
|------------|-------------|
| `F-00060_v1a_reindex_button.png` | Code-page dropdown with "Re-index Docs" visible |
| `F-00060_v1b_job_row_created.png` | Code page after clicking Re-index Docs |
| `F-00060_v1c_jobs_view_completed.png` | Jobs view showing completed doc_indexing job |
| `F-00060_v2a_phase_events.png` | Workitem-aware question citing F-99001 |
| `F-00060_v3_relevance_filter.png` | Colour question citing CR-99001 (recolor) |
| `F-00060_v5_code_only_regression.png` | Code-only question with no work-item context |
| `F-00060_v6_no_regressions_tests.png` | Tests page clean |
| `F-00060_v6_no_regressions_quality.png` | Quality page clean |
| `F-00060_v6_no_regressions_docs.png` | Docs page clean |

---

## Console Errors Observed

```
[ERROR] Failed to load resource: 404 @ http://localhost:9946/api/projects//code/modules:0
```

This pre-existing 404 (empty project ID in path) is unrelated to F-00060.

---

## Notes

- **Slash command UX**: The `/why` chip must be selected from the slash menu (not typed as text) to properly populate `context_chips`. Using the UI chip selector adds the chip to `context_chips` in the request body.
- **SSE verification**: The SSE stream correctly emits phase events, token events, citation events, and done events in sequence. Citation events contain the correct `work_item_id` matching seeded items.
- **Previous report (2026-04-24 18:05)**: The earlier report incorrectly showed V2b, V3, V4 as FAIL due to a misinterpretation. The browser UI properly displays citations via the history panel — `citation` SSE events map to `onWorkItemCitation` in the JS renderer, which populates the history section. All verifications pass when tested correctly with the slash command interface.