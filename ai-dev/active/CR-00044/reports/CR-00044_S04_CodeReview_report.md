# CR-00044 S04 Code Review Report

## Review Summary

Reviewed S03 (tests-impl) implementation against CR-00044 design document.

**Files Changed by S03:**
- `tests/dashboard/test_system_docs_route.py` — extended with `TestSystemDocsSubdirectory` (AC1/AC2/AC3/AC6)
- `tests/dashboard/test_help_router.py` — added `TestHelpRouterSlugMappingCR00044`, `TestHelpRouterAnchorPinning`, `TestHelpRouterNoHardcodedOldLinks`
- `tests/dashboard/test_favicon.py` — verified as already complete (AC5)

---

## Pre-Review Lint & Format Gate

| Gate | Result | Detail |
|------|--------|--------|
| `make lint` | ✅ PASS | All checks passed (ruff, check_templates.py) |
| `make format` | ❌ FAIL | `dashboard/routers/help.py` would be reformatted |

**Format violation:** Two lines in `item_detail` value are concatenated using Python implicit string literal concatenation (lines 42–44). Ruff would flatten this to one line, changing:

```python
"item_detail": (
    "/system/docs/IW_AI_Core_Dashboard_Design"
    "#45-work-item-detail-projectiditemitem_id"
),
```

to:

```python
"item_detail": (
    "/system/docs/IW_AI_Core_Dashboard_Design#45-work-item-detail-projectiditemitem_id"
),
```

This is a **CRITICAL** finding — format gate is non-negotiable per the review instructions.

---

## Acceptance Criteria Coverage

| AC | Description | Coverage | Test(s) |
|----|-------------|----------|---------|
| AC1 | Subdirectory docs render | ✅ Complete | `test_subdir_doc_claude_md_returns_200` (200, "Code Understanding"), `test_subdir_doc_implementation_index_returns_200` (200, "Implementation Plan") |
| AC2 | Existing top-level URLs still work | ✅ Complete | `test_existing_top_level_doc_still_works` (200, "Daemon") |
| AC3 | Path traversal rejected, no content leak | ✅ Complete | 10 negative tests covering `..`, leading `/`, `.`, non-.md, unknown path, url-encoded traversal — all assert 404 + no content leak |
| AC4 | Five generic help mappings retargeted | ✅ Complete | `TestHelpRouterSlugMappingCR00044` (individual asserts for code→rag, item_detail/research/search→Dashboard_Design, projects→Architecture), `TestHelpRouterAnchorPinning` (parametrized anchor→id verification), `TestHelpRouterNoHardcodedOldLinks` (regression guard) |
| AC5 | `/favicon.ico` returns SVG | ✅ Complete | 3 tests: 200, `image/svg+xml` content-type, byte-for-byte SVG match |
| AC6 | Page title from H1 | ✅ Complete | `test_h1_derived_title_for_subdir_doc` ("Implementation Plan" present, "implementation/00 INDEX" absent), `test_valid_doc_slug_shows_doc_title` updated to check "Complete Architecture" |

---

## TDD Coverage

| TDD Test | Status | Test Function |
|----------|--------|--------------|
| `orch/rag/CLAUDE.md` → 200 with RAG heading | ✅ | `test_subdir_doc_claude_md_returns_200` |
| `implementation/00_INDEX` → 200 | ✅ | `test_subdir_doc_implementation_index_returns_200` |
| `IW_AI_Core_Daemon_Design` flat form regression | ✅ | `test_existing_top_level_doc_still_works` |
| `../etc/passwd`, `..%2f..%2fREADME`, non-.md, unknown path → 404 | ✅ | `test_traversal_etc_passwd_returns_404`, `test_traversal_url_encoded_returns_404`, `test_non_md_path_returns_404`, `test_unknown_subdir_path_returns_404` |
| `<title>` reflects first H1 | ✅ | `test_h1_derived_title_for_subdir_doc`, `test_valid_doc_slug_shows_doc_title` |
| Favicon → 200, `image/svg+xml`, SVG bytes | ✅ | `test_favicon_ico_returns_200`, `test_favicon_ico_content_type_is_svg`, `test_favicon_ico_returns_svg_bytes` |
| `code` help → `/system/docs/orch/rag/CLAUDE.md` | ✅ | `test_code_slug_maps_to_rag_claude_md` |
| `item_detail`/`research`/`search` → `Dashboard_Design` | ✅ | `test_item_detail_slug_maps_to_dashboard_design`, `test_research_slug_maps_to_dashboard_design`, `test_search_slug_maps_to_dashboard_design` |
| `projects` → Architecture (unchanged) | ✅ | `test_projects_slug_still_maps_to_architecture` |
| No hardcoded `/docs/IW_AI_Core` or bare `/orch/` hrefs | ✅ | `TestHelpRouterNoHardcodedOldLinks` |

---

## Test Execution Results

```
uv run pytest tests/dashboard/test_system_docs_route.py tests/dashboard/test_help_router.py tests/dashboard/test_favicon.py -v --no-cov
======================== 99 passed, 1 warning in 17.81s ========================
```

All 99 tests pass. No failures. No live DB, no Docker, no network I/O — pure TestClient tests.

---

## Findings

### CRITICAL

1. **Conventions Violation — String Literal Concatenation in `item_detail` value**
   - **File:** `dashboard/routers/help.py`, lines 42–44
   - **Severity:** CRITICAL
   - **Category:** conventions
   - **Description:** `_SLUG_TO_DOC["item_detail"]` uses Python implicit string literal concatenation across two source lines (`"/system/docs/IW_AI_Core_Dashboard_Design"` on one line, `"#45-work-item-detail-projectiditemitem_id"` on the next). Ruff format would flatten these to a single line. This is a new violation introduced by S03.
   - **Suggested fix:** Replace the two-line string literal concatenation with a single concatenated string:
     ```python
     "item_detail": "/system/docs/IW_AI_Core_Dashboard_Design#45-work-item-detail-projectiditemitem_id",
     ```

---

## Verdict

**verdict: FAIL**

The format violation in `dashboard/routers/help.py` introduced by S03 blocks the gate. The `make format` check would reformat the file. All 99 tests pass correctly and coverage is complete — the only issue is the string concatenation style in the `item_detail` entry.

**mandatory_fix_count: 1**

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00044",
  "step_reviewed": "S03",
  "verdict": "fail",
  "mandatory_fix_count": 1,
  "findings": [
    {
      "severity": "CRITICAL",
      "category": "conventions",
      "file": "dashboard/routers/help.py",
      "line": 42,
      "description": "String literal concatenation in _SLUG_TO_DOC['item_detail'] value — two source lines joined by implicit concatenation. Ruff would reformat to a single line. This is a new conventions violation introduced by S03's implementation of the item_detail mapping.",
      "suggestion": "Replace the two-line string literal concatenation with a single string: \"item_detail\": \"/system/docs/IW_AI_Core_Dashboard_Design#45-work-item-detail-projectiditemitem_id\","
    }
  ],
  "tests_passed": true,
  "test_summary": "99 passed, 0 failed",
  "notes": "All test coverage is complete and correct. AC1-AC6 all have adequate assertions. The only issue is the format violation in help.py which must be fixed before the gate can pass."
}
```
