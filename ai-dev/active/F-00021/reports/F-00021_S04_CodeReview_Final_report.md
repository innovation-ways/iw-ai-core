# F-00021_S04_CodeReview_Final_report

## Step: S04 — CodeReview_Final
**Work Item**: F-00021 — Research Panel in AI Dashboard
**Agent**: CodeReview_Final
**Date**: 2026-04-13

---

## Verdict: NEEDS_FIX

## Findings Summary

| Severity | Count |
|----------|-------|
| Critical | 2 |
| High | 0 |
| Medium | 0 |
| Low | 0 |

---

## Critical Issues

### 1. Missing integration tests for research routes

**File**: `tests/integration/test_dashboard_pages.py`

The S03 Tests step was supposed to add integration tests for the research routes, but **no research tests exist** in the test file. The file ends at line 500 and contains no `test_research_*` functions.

**Required tests per the feature design:**
- `test_research_library_page_empty` — AC3 (empty state)
- `test_research_library_page_with_docs` — AC1 (list page with docs)
- `test_research_detail_page` — AC2 (detail with markdown)
- `test_research_detail_page_404` — AC4 (unknown doc_id)
- `test_research_detail_wrong_type_404` — boundary (non-research doc via research route)

**Required test for boundary coverage:**
- `test_research_detail_null_content` — boundary (null content)

### 2. Missing `/api/research/search` endpoint

**File**: `dashboard/routers/research.py`

The template `research_library.html` (line 19) references `/project/{project_id}/api/research/search` for filter buttons and search input htmx triggers:

```html
hx-get="/project/{{ current_project.id }}/api/research/search"
```

However, `research.py` does **not** define this endpoint. The `docs.py` router has an equivalent `/api/docs/search` endpoint (line 252), but the `research.py` router is missing its search endpoint.

**Without this endpoint**, the filter pills (by status, by category) and the search input in `research_library.html` will return 404 errors when clicked.

---

## What Passed

| Check | Status |
|-------|--------|
| `ruff check dashboard/routers/research.py` | PASS — no issues |
| `mypy dashboard/routers/research.py` | PASS — no issues |
| Research router registered in `app.py` | PASS |
| Research sidebar link in `base.html` | PASS |
| `DocType.research` filter at service layer (line 39) | PASS |
| Type mismatch guard in detail route (lines 67-68) | PASS |
| Null content guard in detail route (line 70) | PASS |
| 309 existing tests pass | PASS |

---

## Pre-existing Failure (Not Related to F-00021)

`tests/integration/test_docs_routes.py::test_docs_pdf_with_content` fails due to a weasyprint/PDF generation issue. This is unrelated to the research panel changes.

---

## Mandatory Fix Count: 2

1. Add the missing `/api/research/search` endpoint to `research.py`
2. Add the 6 required integration tests to `tests/integration/test_dashboard_pages.py`

---

## Notes

The implementation of `research.py`, `research_library.html`, and `research_detail.html` follows the `docs.py` pattern correctly. The type mismatch guard (`doc.doc_type != DocType.research`) properly handles the AC4 boundary case. The sidebar navigation link is present and uses the correct URL pattern with active-state highlighting.
