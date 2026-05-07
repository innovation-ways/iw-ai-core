# F-00079_S08_CodeReview_API_FE_Tmpl_prompt

**Work Item**: F-00079 — Files view: per-item git changes explorer with step drilldown and PDF export
**Steps Being Reviewed**: S05 (api-impl), S06 (frontend-impl), S07 (template-impl)
**Review Step**: S08

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Do not run alembic.

## Input Files

- `ai-dev/active/F-00079/F-00079_Feature_Design.md`
- `ai-dev/active/F-00079/reports/F-00079_S05_API_report.md`, `F-00079_S06_Frontend_report.md`, `F-00079_S07_Template_report.md`
- All files listed in S05/S06/S07 `files_changed` and `files_deleted`

## Output Files

- `ai-dev/active/F-00079/reports/F-00079_S08_CodeReview_API_FE_Tmpl_report.md`

## Context

You are reviewing the API + Frontend + Template work as a coherent slice. The most important properties to verify are **route ↔ template ↔ JS contract consistency** (the diff endpoint returns `text/plain`, the JS expects `text/plain`, the PDF template gets the right context), the **complete removal of the legacy Artifacts UI**, and **accessibility compliance**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations in the changed files → CRITICAL findings (`category: "conventions"`).

## Review Checklist

### 1. Route Contracts

- `GET /tab/files` returns the `item_files.html` fragment with the documented context keys and types.
- `GET /files/diff?step=...` returns `Content-Type: text/plain; charset=utf-8` (NOT JSON, NOT `application/x-patch`).
- `GET /files/untracked` returns JSON with the documented shape.
- `GET /files/export.pdf?step=...` returns `Content-Type: application/pdf` and a Content-Disposition attachment header.
- `GET /tab/artifacts` returns 404 (route removed).
- `GET /artifact-raw` is preserved and used by the new untracked sub-panel.
- 404 / 400 cases handled per design.

### 2. Frontend ↔ API Wiring

- `dashboard/static/files.js` fetches `/files/diff` with the correct `step` query param.
- The JS handles the `X-Diff-Empty: 1` header (or empty body) and renders the empty state.
- Step dropdown change re-fetches and re-renders without page reload.
- Filter input filters tree rows AND diff cards consistently.
- Untracked sub-panel only renders when `worktree_alive=true`; on archived items it is absent.
- Untracked sub-panel reuses `/artifact-raw` for previews — same UX as the deleted Artifacts viewer.
- Dark-mode color scheme is synced to diff2html when the theme toggle fires.
- Export PDF link includes the current step selection in the query string.

### 3. Template Integrity

- `item_files.html` does NOT extend `base.html` (htmx fragment rule).
- `item_files_untracked.html` is also a bare fragment.
- `components/libs/diff2html.html` follows the existing libs-include pattern (matches `Highlight.js`, `Mermaid`, etc.) and serves the diff2html-ui assets from the vendored `dashboard/static/vendor/diff2html/<version>/` path — NO CDN URLs.
- `exports/diff_pdf.html` produces a complete HTML document with inline CSS (WeasyPrint constraint).
- The PDF template's status badges have both color AND letter (WCAG 1.4.1).
- The PDF template handles the empty-summary case without erroring.
- **PDF template ↔ route context shape match** — `summary_files`, `truncated_files`, `aggregate_added`, `aggregate_removed`, `aggregate_file_count`, `step_label`, `item`, `project_id`, `generated_at` are the canonical names. CRITICAL if the route uses one name (e.g., `summary`) and the template another (`summary_files`).
- **PDF item-level cap (100 files)** — route partitions changed files alphabetical-by-path: first 100 → `summary_files` with `hunks_html` populated for non-binary / <5000-line files; remainder → `truncated_files` with `hunks_html=None`. Template renders body sections only for `summary_files` and adds the "N additional files omitted" footer note when `truncated_files` is non-empty.

### 4. Accessibility

- Status badges: color + letter on every variant (A/M/D/R) in both screen and PDF.
- `+`/`−` line prefixes preserved in unified diff display.
- Adequate contrast on diff backgrounds in light AND dark modes.
- ARIA labels on the step dropdown, filter input, and Export PDF button.

### 5. Removal Completeness

- `dashboard/templates/fragments/item_artifacts.html` is deleted.
- The `item_tab_artifacts` route handler is removed from `dashboard/routers/items.py`.
- `_list_artifact_tree`, `_build_artifact_tree`, and `ArtifactNode` are either deleted (if unreferenced) or retained ONLY because the new untracked sub-panel needs them. Confirm via grep.
- `_detect_file_type` and `_resolve_artifact_root` are PRESERVED (the preserved `/artifact-raw` route depends on them).
- `tests/unit/test_artifact_browser.py` retains `TestDetectFileType` and `TestResolveArtifactRoot`; only `TestBuildArtifactTree` is removed. CRITICAL if all three classes were deleted (would lose coverage of preserved helpers) or if `TestBuildArtifactTree` still exists (would import-fail after the helpers go).
- `item_detail.html` no longer references the Artifacts tab.

### 6. Performance Smell-Test

- Diff fetch is one round-trip per step change (not per file expand). Per-file collapse toggle is purely client-side (CSS class flip) — no per-file server roundtrip.
- Generated-file glob list is the same as the backend's `GENERATED_FILE_GLOBS` (Invariant 8).
- Files >500 lines are auto-collapsed (client-side toggle); files >5000 lines fall back to a download link only.
- diff2html-ui assets are vendored under `dashboard/static/vendor/diff2html/<version>/` — NO CDN reference anywhere in the repo (`grep -r 'jsdelivr\|unpkg\|cdnjs' dashboard/templates dashboard/static` returns nothing for the diff2html assets).

### 7. Conventions

- `dashboard/CLAUDE.md`: routers thin; fragments don't extend base; htmx, not React/Vue; `playwright-cli` only.
- `CLAUDE.md`: `make css` runs cleanly OR plain CSS appended to `dashboard/static/styles.css`.
- Naming: snake_case in Python, kebab-case in CSS class names, camelCase in JS.

## Test Verification (NON-NEGOTIABLE)

```bash
make test-unit
make test-frontend
```

Smoke integration:
```bash
make test-integration
```

## Severity Levels

| Severity | Meaning | Action |
|---|---|---|
| CRITICAL | Breaks contract, accessibility, or invariant | Must fix |
| HIGH | Significant integration bug | Must fix |
| MEDIUM (fixable) | Code quality, missing edge case | Should fix |
| MEDIUM (suggestion) | Better pattern available | Optional |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "CodeReview",
  "work_item": "F-00079",
  "steps_reviewed": ["S05", "S06", "S07"],
  "verdict": "pass|fail",
  "findings": [...],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
