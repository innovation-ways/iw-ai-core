# CR-00020 S05 API Report

## What was done

Reviewed CR-00020's API surface to determine what API layer changes (if any) are needed for the `WorkItemEvidence` BLOBs feature.

**Finding: No new API implementation required.**

CR-00020 is a pure database-schema change. The `WorkItemEvidence` table is defined in `orch/db/models.py:760-810` and migration `d6b67d4ecb9f_add_work_item_evidences.py` is applied. No new API endpoints, CLI commands, or service-layer code are needed because:

1. **Dashboard evidence browser** — `dashboard/routers/items.py:1202-1226` (`item_tab_evidences`) and `item_evidence_file` (line 1229) — already serve evidence files from the filesystem (`ai-dev/active/{id}/evidences/{pre,post}/`). The template `dashboard/templates/fragments/item_evidences.html` renders PRE and POST evidence grids with download/image-view links.

2. **`iw approve` does not ingest pre-evidences** — per S04 CodeReview observation, `iw approve` (`orch/cli/item_commands.py:389`) only transitions work item status; it does not capture files into `work_item_evidences`. This is a known gap but outside CR-00020's scope (schema only, not the ingestion pipeline).

3. **`iw step-done` validates browser evidence presence** — `orch/cli/step_commands.py:300-305` checks `ai-dev/active/{id}/evidences/post/` exists for `browser_verification` steps, but does NOT write to the `work_item_evidences` table.

4. **No `EvidenceService` or ingestion API** exists yet. The `WorkItemEvidence` table is present and ready, but the code that would write to it does not yet exist. This is the expected next step after CR-00020 (a separate CR for the evidence ingestion pipeline).

## Review of existing API surface

| Component | Status |
|-----------|--------|
| `dashboard/routers/items.py:item_tab_evidences` | ✅ Renders PRE/POST evidence tabs |
| `dashboard/routers/items.py:item_evidence_file` | ✅ Serves evidence images from filesystem |
| `dashboard/templates/fragments/item_evidences.html` | ✅ Grid UI with image/download support |
| `orch/db/models.py:WorkItemEvidence` | ✅ ORM model defined, table exists |
| `orch/cli/step_commands.py` | ✅ `validate_browser_evidence_present()` enforces post-evidence capture |
| `orch/cli/item_commands.py:approve` | ⚠️ Does not ingest pre-evidences (known gap) |
| Evidence ingestion pipeline (write to DB) | ❌ Not implemented yet |

## Conclusion

S05 is a no-op for CR-00020. The schema is complete; the API/integration layer for actually ingesting evidence BLOBs into the table is a separate work item. All existing endpoints work correctly for the filesystem-based evidence browsing that the dashboard uses today.

**Step status: complete (no action needed)**

**(End of file)**