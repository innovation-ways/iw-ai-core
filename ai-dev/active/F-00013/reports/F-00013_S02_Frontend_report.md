# F-00013_S02_Frontend_report.md

## Step: S02 - Frontend Implementation

**Work Item**: F-00013 — Project-Level Documentation System — Automation (Phase 3)
**Agent**: Frontend
**Status**: Complete

---

## What Was Done

Implemented all frontend components for the documentation automation UI:

### 1. Staleness Badge on Doc Cards (`docs_card.html`)
- Added staleness indicator badge (yellow warning) that appears on the top-right corner when `doc.doc_id in stale_doc_ids`
- Badge tooltip shows: "Source changed: {path}"
- Route context updated to pass `stale_doc_ids: set[str]` and `stale_source_map: dict[str, str]`

### 2. Staleness Summary Row (`docs_stale_summary.html`)
- New fragment showing banner: "N documents are stale — their source files have changed since last generation."
- "Regenerate All Stale" button (`hx-post="/api/project/{id}/docs/regenerate-stale"`)
- "Dismiss" button with 24h localStorage-based dismissal
- Success message replaces banner after POST

### 3. Lint Warnings Callout (`docs_lint_warnings.html`)
- New fragment with amber styling showing `lint_warnings` from most recent completed job
- Each warning shows rule name (monospace) and message
- htmx-loaded on doc detail page

### 4. Doc Configuration Panel (`docs_config_panel.html`)
- New settings panel with:
  - Auto-trigger toggle (on/off)
  - Staleness threshold (hours, 1-720)
  - Forbidden phrases (comma-separated text input)
- Opens via settings gear icon in docs library header
- POST saves to `Project.config["doc_generation"]`

### 5. Settings Gear Icon in Library Header (`docs_library.html`)
- Added gear icon (top-right of page header)
- `hx-get="/api/project/{id}/docs/config"` targets `#docs-config-overlay`
- Fixed overlay container added

### 6. New Routes in `docs.py`
- `GET /api/project/{id}/docs/config` — render config panel
- `POST /api/project/{id}/docs/config` — save config (async)
- `GET /api/project/{id}/docs/stale` — render stale summary
- `POST /api/project/{id}/docs/regenerate-stale` — queue jobs for all stale docs
- `GET /api/project/{id}/docs/{doc_id}/lint-warnings` — render lint warnings

### 7. Updated Existing Routes
- `docs_library`: now passes `stale_doc_ids` and `stale_source_map`
- `docs_search`: now passes `stale_doc_ids` and `stale_source_map`
- `docs_card`: now passes `stale_doc_ids` and `stale_source_map`

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/templates/fragments/docs_card.html` | Modified: added staleness badge |
| `dashboard/templates/docs_library.html` | Modified: stale summary row + settings icon |
| `dashboard/templates/fragments/docs_stale_summary.html` | New |
| `dashboard/templates/fragments/docs_config_panel.html` | New |
| `dashboard/templates/fragments/docs_lint_warnings.html` | New |
| `dashboard/templates/docs_detail.html` | Modified: added lint warnings htmx trigger |
| `dashboard/routers/docs.py` | Extended with config routes + stale summary route |

---

## Test Results

- **Ruff**: All checks passed on modified files
- **Mypy**: 1 pre-existing error (unused type: ignore at line 131, not my code)
- **Unit Tests**: 15/15 passed (`tests/unit/test_doc_automation.py`)

---

## Manual Verification Points

1. **Staleness badge**: Appears on doc cards when source files are newer than `generated_at`
2. **Config panel**: Opens via gear icon, saves settings to `Project.config["doc_generation"]`
3. **Lint warnings**: Appears on doc detail page when job has non-empty `lint_warnings`
4. **Regenerate All**: Creates jobs for all stale docs, shows success message

---

## Notes

- The mypy error at line 131 (`Unused "type: ignore" comment`) is pre-existing in the PDF generation code, not introduced by S02
- Ruff errors in `orch/doc_service.py` are from S01 (Backend) changes, not S02 frontend changes
- All lint errors in my changed files are resolved
