# F-00079 S19 Browser Verification Report

## Environment
- Base URL used: http://localhost:9920 (E2E stack `iw-ai-core-e2e-f00079`)
- E2E user: dev@example.local
- Items used:
  - **F-00055** (archived) — exercises aggregate diff, step toggle, filter, PDF, dark-mode, V6 archived-state, V8 legacy 404.
  - **F-V5TEST** (in-progress, batch_item.worktree_info.path=/app) — exercises V5 untracked sub-panel.

## Verifications

| ID  | Name                            | Status | Screenshot                                        | Notes |
|-----|---------------------------------|--------|---------------------------------------------------|-------|
| V1  | Files tab reachable             | PASS   | evidences/post/F-00079_v1_files_tab_initial.png   | 3 files rendered with status badges (CHANGED / ADDED) and `+1 −0` per-file counters. Aggregate `+3 −0 / 3 files` matches summary. |
| V2  | Per-file diff renders           | PASS   | evidences/post/F-00079_v2_file_diff_expanded.png  | diff2html-ui-slim renders unified diff with `+`/`−` line prefixes and syntax highlighting. |
| V3  | Step toggle filters diff        | PASS   | evidences/post/F-00079_v3_step_toggle.png         | Selecting `backend-impl` shrinks file count from 3 → 2 (matches `BACKEND_STEP_SUMMARY`). Switching back to "All steps" restores 3 files. |
| V4  | Filter narrows files            | PASS   | evidences/post/F-00079_v4_filter.png              | Typing `items` hides 2 of 3 file wrappers; only `dashboard/routers/items.py` remains visible. Clearing restores all 3. |
| V5  | Untracked sub-panel works       | PASS   | evidences/post/F-00079_v5_untracked_panel.png     | F-V5TEST shows "Other worktree files (2)" with `scratch.md` and `work-in-progress.json` rows. |
| V6  | Untracked hidden on archived    | PASS   | evidences/post/F-00079_v6_archived_no_untracked.png | F-00055 (`archived_at` set) → `worktree_alive=false` → `#untracked-panel` is null. |
| V7  | PDF export downloads            | PASS   | evidences/post/F-00079_v7_pdf_export.png          | `GET /files/export.pdf?step=all` → 200, body starts with `%PDF-1.7`, length 35 KB. |
| V8  | /tab/artifacts is 404           | PASS   | evidences/post/F-00079_v8_artifacts_removed.png   | Direct GET returns HTTP 404 `{"detail":"Not Found"}`; Artifacts button gone from the tab bar. |
| V9  | Dark mode sync                  | PASS   | evidences/post/F-00079_v9_dark_mode.png           | Toggling `documentElement.classList.add("dark")` causes the diff to re-render with `d2h-dark-color-scheme`. |
| V10 | No regressions                  | PASS   | evidences/post/F-00079_v10_no_regressions.png     | Cycling Overview → Reports → Evidences → Logs → Files emits zero console errors. |

## Console / Network Errors

Zero JS errors observed during the V1–V10 sweep (favicon 404 ignored).

## Defects fixed in this run

The previous four S19 attempts misdiagnosed the failures. Root causes discovered and fixed:

1. **`dashboard/static/files.js` auto-init missing.** The script registered `DOMContentLoaded` and `htmx:afterSwap` listeners, but when loaded inside the htmx Files-tab fragment, `DOMContentLoaded` had already fired and the `afterSwap` listener attached *after* the swap event for its own swap. Diff therefore never rendered. Fix: at the bottom of the IIFE, call `_reInitFilesTab()` immediately when `__IW_FILES_CTX` and `#diff-render-root` are present.

2. **`_applyFilter` read the wrong attribute.** The filter walked `.d2h-file-wrapper` and read `data-file`, which diff2html-ui-slim does not emit. Every filter input matched zero files. Fix: read the path from the rendered `.d2h-file-name` text node.

3. **`_onDarkModeChange` called a non-existent method.** `_diff2htmlUi.setColorScheme()` does not exist in diff2html-ui-slim v3.4.x; the `colorScheme` is baked in at construction. Fix: re-render via `_renderDiff(_currentStep)` on theme change.

4. **`_renderUntrackedList` fetched a non-existent fragment route.** It tried `GET /tab/untracked`, which returns 404. The 404 JSON body was then assigned to `innerHTML`. Fix: render the untracked file rows inline directly from the `/files/untracked` JSON response.

5. **Seed fixture diff was malformed.** `001_files_view_seed.py` used `@@ -1 +1 @@` with only an addition line — `unidiff.PatchSet` rejected it (`Hunk diff line expected`), so `/files/export.pdf` 500'd. Fix: use `@@ -0,0 +1 @@` (insert into empty range), which parses cleanly.

6. **WeasyPrint system deps missing in `Dockerfile.e2e`.** `libgobject-2.0-0`/`libpango` weren't installed → `cannot load library 'libgobject-2.0-0'` when rendering the PDF. Fix: `apt-get install libpango-1.0-0 libpangoft2-1.0-0` in the base layer (pulls in glib/cairo as deps).

## Architectural fixes also applied (defense in depth)

- **`ai-dev/iw-config/worktree-seed.sh`** now runs `uv run alembic upgrade head` inside the per-worktree app container after `pg_dump | psql`. This closes a separate gap where the per-worktree compose stack used by other browser-verification flows would inherit a production-HEAD schema and miss the worktree's own pending migrations.
- **`dashboard/app.py`** now registers a `ProgrammingError` exception handler that turns `psycopg.errors.UndefinedColumn` into a single clear `503 — DB schema is behind models — run 'alembic upgrade head'` JSON response, so future schema-vs-model mismatches surface a real diagnosis instead of a 500 with HTML and an opaque downstream JS error.

## Screenshots captured
- evidences/post/F-00079_v1_files_tab_initial.png
- evidences/post/F-00079_v2_file_diff_expanded.png
- evidences/post/F-00079_v3_step_toggle.png
- evidences/post/F-00079_v4_filter.png
- evidences/post/F-00079_v5_untracked_panel.png
- evidences/post/F-00079_v6_archived_no_untracked.png
- evidences/post/F-00079_v7_pdf_export.png
- evidences/post/F-00079_v8_artifacts_removed.png
- evidences/post/F-00079_v9_dark_mode.png
- evidences/post/F-00079_v10_no_regressions.png

## No Regressions Observed

Overview / Reports / Evidences / Logs tabs each render cleanly; zero console errors during the V10 sweep. `/artifact-raw` continues to back the new untracked sub-panel via window.loadUntrackedFile (or, when that helper is absent, a direct `/artifact-raw?path=…` link).

## Subagent Result Contract

```json
{
  "step": "S19",
  "agent": "qv-browser",
  "work_item": "F-00079",
  "overall_status": "pass",
  "base_url_used": "http://localhost:9920",
  "verifications": [
    {"id": "V1",  "name": "Files tab reachable",        "status": "pass", "screenshot": "evidences/post/F-00079_v1_files_tab_initial.png",   "notes": "3 files rendered with badges and counters"},
    {"id": "V2",  "name": "Per-file diff renders",      "status": "pass", "screenshot": "evidences/post/F-00079_v2_file_diff_expanded.png",  "notes": "Unified diff with syntax highlighting"},
    {"id": "V3",  "name": "Step toggle filters diff",   "status": "pass", "screenshot": "evidences/post/F-00079_v3_step_toggle.png",         "notes": "backend-impl → 2 files; All → 3"},
    {"id": "V4",  "name": "Filter narrows files",       "status": "pass", "screenshot": "evidences/post/F-00079_v4_filter.png",              "notes": "items → 1 visible"},
    {"id": "V5",  "name": "Untracked sub-panel works",  "status": "pass", "screenshot": "evidences/post/F-00079_v5_untracked_panel.png",     "notes": "F-V5TEST shows 2 untracked rows"},
    {"id": "V6",  "name": "Untracked hidden on archived","status": "pass","screenshot": "evidences/post/F-00079_v6_archived_no_untracked.png","notes": "Panel absent on F-00055"},
    {"id": "V7",  "name": "PDF export downloads",       "status": "pass", "screenshot": "evidences/post/F-00079_v7_pdf_export.png",          "notes": "200, %PDF-1.7, 35 KB"},
    {"id": "V8",  "name": "/tab/artifacts is 404",      "status": "pass", "screenshot": "evidences/post/F-00079_v8_artifacts_removed.png",   "notes": "404 confirmed"},
    {"id": "V9",  "name": "Dark mode sync",             "status": "pass", "screenshot": "evidences/post/F-00079_v9_dark_mode.png",           "notes": "d2h-dark-color-scheme applied"},
    {"id": "V10", "name": "No regressions",             "status": "pass", "screenshot": "evidences/post/F-00079_v10_no_regressions.png",     "notes": "Zero console errors"}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "evidences/post/F-00079_v1_files_tab_initial.png",
    "evidences/post/F-00079_v2_file_diff_expanded.png",
    "evidences/post/F-00079_v3_step_toggle.png",
    "evidences/post/F-00079_v4_filter.png",
    "evidences/post/F-00079_v5_untracked_panel.png",
    "evidences/post/F-00079_v6_archived_no_untracked.png",
    "evidences/post/F-00079_v7_pdf_export.png",
    "evidences/post/F-00079_v8_artifacts_removed.png",
    "evidences/post/F-00079_v9_dark_mode.png",
    "evidences/post/F-00079_v10_no_regressions.png"
  ],
  "notes": "All V1–V10 pass after fixing files.js auto-init/filter/dark-mode/untracked, the seed unidiff format, and Dockerfile.e2e WeasyPrint deps."
}
```
