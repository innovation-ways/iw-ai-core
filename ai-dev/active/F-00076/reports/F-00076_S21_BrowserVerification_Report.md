# F-00076 S21 Browser Verification Report

## Environment
- Base URL used: `http://localhost:9912` (from `$IW_BROWSER_BASE_URL`)
- E2E user: `dev@example.local` (from `$IW_BROWSER_E2E_USER`)
- Worktree: `F-00076` | Step: `S21`

## Status
**FAIL** — `ENV_DATA_MISSING`

---

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Item overview shows declared Impacted Paths | **fail** | — | `impacted_paths` column does not exist in E2E DB (schema behind head). E2E DB shows alert: "Orch DB schema is behind head — current_rev=a9861af32872 head_rev=4876b3246ff2". No items with `scope_extraction.source == "declared"` in seed data. |
| V2 | Item overview shows regex-fallback badge | **fail** | — | Same root cause: `impacted_paths` column missing, `scope_extraction` JSONB key absent from all item configs. |
| V3 | Batch detail shows "Held: overlaps with..." indicator | **fail** | — | `item_held_for_scope` DaemonEvent type does not exist in E2E DB schema. No held items in seed data. |
| V4 | Worktrees page shows in-flight scope tooltip | **fail** | — | `impacted_paths` not populated in E2E DB; worktrees table shows `—` for In-flight Scope column (expected since the column IS rendered but data is empty). |
| V5 | Dark-mode legibility | **n/a** | — | Blocked by V1/V2 failures — no Impacted Paths panel to inspect. |
| V6 | No Regressions | **fail** | — | Queue page renders correctly; no JS errors on visited pages; BUT the dashboard shows a persistent schema-behind-head alert on every page that would need to be resolved before this verification could run. |

---

## Root Cause

**CODE DEFECT / ENV_DATA_MISSING**: The E2E stack for F-00076 was provisioned **before** F-00076's S01 alembic migration (`add_impacted_paths_to_work_items`) was merged to `main`. The E2E DB schema is at revision `a9861af32872` while the worktree head is at `4876b3246ff2` — a gap of one pending revision.

The S01 migration adds:
1. `work_items.impacted_paths JSONB NOT NULL DEFAULT '[]'`
2. A backfill that runs `extract_affected_files()` over non-terminal items

Without this column existing:
- `item.impacted_paths` raises `AttributeError` in Jinja2 (the template uses `item.impacted_paths` directly)
- The `scope_extraction` key is absent from all `config` JSONB columns
- No `item_held_for_scope` DaemonEvents exist
- Worktrees router's `impacted_paths` join (`dashboard/routers/worktrees.py:427`) silently returns None for all rows

### Evidence
- Dashboard alert on every page: `"Orch DB schema is behind head — current_rev=a9861af32872 head_rev=4876b3246ff2"`
- CR-99026 item detail (draft CR with no steps) shows Impacted Paths panel with "none" badge and "No paths declared — item bypasses cross-batch conflict gate." — confirming the panel renders but has no data
- Worktrees page: In-flight Scope column present in template (`worktree_table.html` lines 122-139) but all rows show `—` because `bi_impacted_paths` dict is empty (the query at line 435 returns no rows, or the column doesn't exist)

### Investigation Notes
- `orch/db/models.py:443` — `impacted_paths` column defined in worktree but not in E2E DB
- `dashboard/routers/worktrees.py:427` — SQL join on `WorkItem.impacted_paths` would error if column missing (but SQLAlchemy lazy-loads; no error surfaced in browser)
- `dashboard/routers/worktrees.py:491` — passes `impacted_paths=bi_impacted_paths.get(bi.id)` where `bi_impacted_paths` is empty dict → all None
- `dashboard/templates/fragments/item_overview.html:129-159` — template correctly guards with `item.impacted_paths if item.impacted_paths else []` but data is `[]` from DB default, not from design doc

---

## Screenshots captured
No screenshots captured — all V1-V4 failed before screenshot step. The one page that fully rendered (CR-99026 item detail) showed the Impacted Paths panel in its "none" state but this was not saved as a screenshot since V1 requires a "declared" badge, not a "none" state.

---

## Console / Network Errors
No new JavaScript console errors observed. The dashboard shows a non-blocking alert about schema behind head (write actions disabled until `make db-migrate` is run), which is the expected state for this work item's E2E stack before S01 was merged.

---

## No Regressions
Queue, History, Batches, Jobs, Code, Docs pages all render without errors. The schema alert does not block reads. The "Impacted Paths" panel on CR-99026's item detail page rendered correctly in its empty state.

---

## Subagent Result Contract

```json
{
  "step": "S21",
  "agent": "qv-browser",
  "work_item": "F-00076",
  "overall_status": "fail",
  "base_url_used": "http://localhost:9912",
  "verifications": [
    {"id": "V1", "name": "Item overview shows declared Impacted Paths", "status": "fail", "screenshot": "", "notes": "impacted_paths column missing from E2E DB schema"},
    {"id": "V2", "name": "Item overview shows regex-fallback badge", "status": "fail", "screenshot": "", "notes": "scope_extraction key absent from all configs"},
    {"id": "V3", "name": "Batch detail shows Held indicator", "status": "fail", "screenshot": "", "notes": "item_held_for_scope event type does not exist in DB"},
    {"id": "V4", "name": "Worktrees page shows in-flight scope tooltip", "status": "fail", "screenshot": "", "notes": "impacted_paths not populated; all rows show '—'"},
    {"id": "V5", "name": "Dark-mode legibility", "status": "n/a", "screenshot": "", "notes": "blocked by V1-V4 failures"},
    {"id": "V6", "name": "No Regressions", "status": "fail", "screenshot": "", "notes": "schema behind head alert on all pages"}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": "E2E DB provisioned before S01 migration merged. Schema gap: a9861af32872 (current) vs 4876b3246ff2 (head). S01 (alembic migration adding impacted_paths column) must be applied to E2E stack before re-running this verification."
}
```

---

## Fix Required

The orchestrator must re-provision the E2E stack **after** F-00076 S01 is merged to `main`, so the `add_impacted_paths_to_work_items` alembic revision is applied to the E2E PostgreSQL before the S21 browser verification step runs.

Alternatively, a seed fixture (`ai-dev/active/F-00076/e2e_fixtures/001_held_item.py`) could be added to inject test data including items with `impacted_paths` and `scope_extraction` populated, plus a `DaemonEvent` of type `item_held_for_scope`. However, this cannot work until the column exists — the fixture would need to create the column first, which is the S01 migration's job.

**Recommendation**: Fail this step with `ENV_DATA_MISSING`, merge S01 through S20, then re-run S21 as a new step instance.