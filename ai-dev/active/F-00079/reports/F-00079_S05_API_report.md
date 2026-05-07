# F-00079 S05 — API Implementation Report

## What Was Done

Implemented the API surface for F-00079: Files view. Added four new routes in
`dashboard/routers/items.py` and removed the legacy `/tab/artifacts` route and its
associated helper functions.

## Files Changed

### `dashboard/routers/items.py`

**Removed:**
- `ArtifactNode` dataclass (line 103–112)
- `_build_artifact_tree()` (line 168–207)
- `_list_artifact_tree()` (line 210–217)
- `item_tab_artifacts` route handler (lines 1034–1056)

**Preserved (still used by `/artifact-raw`):**
- `_detect_file_type()` (line 115)
- `_resolve_artifact_root()` (line 147)

**Added:**
- `_get_diff_text_and_summary()` — shared helper that resolves diff and prefers
  stored `diff_summary` over re-parsing
- `_step_options_from_item()` — builds step dropdown options from completed
  step_runs with `RunStatus` enum
- `_render_diff_hunks()` — Pygments DiffLexer rendering for PDF export, respects
  100-file cap and 5000-line cap
- `item_tab_files` — GET `/project/{project_id}/item/{item_id}/tab/files`
- `item_files_diff` — GET `/project/{project_id}/item/{item_id}/files/diff?step=`
- `item_files_untracked` — GET `/project/{project_id}/item/{item_id}/files/untracked`
- `item_files_export_pdf` — GET `/project/{project_id}/item/{item_id}/files/export.pdf?step=`

**Design decisions:**
- Uses `resolve_diff()` from `orch/diff_service.py` (never inline logic)
- Stored `diff_summary` used when available (avoids re-parsing)
- Error handling: TemplateNotFound wrapped to 500 (S07 creates the template)
- Git subprocess uses `noq S603,S607` noqa (same pattern as `diff_service.py`)
- All ValueError raises use `from err` (B904 fix)

### `tests/unit/test_artifact_browser.py`

- Removed `TestBuildArtifactTree` class (lines 145–319)
- Updated module docstring to remove `_build_artifact_tree` reference
- Kept `TestDetectFileType` and `TestResolveArtifactRoot` (needed by `/artifact-raw`)

### `tests/integration/test_files_tab.py` (new file)

15 smoke tests covering:
- `item_tab_files`: 404 for nonexistent item/project
- `item_files_diff`: 200 text/plain, 404, 400 malformed step, X-Diff-Empty header,
  text/plain content type
- `item_files_untracked`: 200, 404, X-Untracked-Disabled for archived, JSON content type
- `item_files_export_pdf`: 404, 400 malformed step, 500 when template missing (S07)
- Removed route: `GET /tab/artifacts` → 404

## Test Results

**Integration tests (`tests/integration/test_files_tab.py`):** 15 passed ✓

**Dashboard integration tests (excluding artifacts tab):** 63 passed ✓

**Unit tests (`tests/unit/test_artifact_browser.py`):** 41 failed — pre-existing
`LiveDbConnectionRefusedError` at collection time (the module imports
`dashboard.dependencies` which triggers `SessionLocal` at import). All failures
are at `from dashboard.routers.items import _detect_file_type` inside test
functions — the same pattern the existing test file has always used. Tests
pass when run with testcontainers via `make test-integration`.

**Note:** `test_dashboard_pages.py::test_item_artifacts_tab_no_artifacts` now
returns 404 (expected — we removed the route). This test needs updating in S09
to test the new Files tab instead of Artifacts.

## Pre-flight Checks

- `make format`: ✓ 622 files already formatted
- `make lint`: ✓ All checks passed
- `make typecheck`: ✓ 0 new errors in modified files (pre-existing unused-ignore
  errors in `orch/` are unrelated)

## Blocker / Observation

- The `test_dashboard_pages.py::test_item_artifacts_tab_no_artifacts` test
  expects 200 from `/tab/artifacts` which now returns 404. This is an expected
  regression that S09's test work should address by switching that test to
  exercise the new Files tab.