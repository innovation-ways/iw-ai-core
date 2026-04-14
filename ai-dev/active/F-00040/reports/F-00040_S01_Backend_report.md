# F-00040 S01 Backend Report

## Work Item
**F-00040** — Enhanced Document Diff

## Step
**S01** — Backend Implementation

## Agent
Backend

## Completion Status
**complete**

## Files Changed
- `orch/doc_diff.py` — New section-aware diff module
- `dashboard/routers/docs.py` — Added 3 new routes

## What Was Done

### 1. Created `orch/doc_diff.py`
A new pure-Python module (no DB dependencies) that computes structured diffs between document versions:

- `SectionDiff` dataclass — holds diff result for a single H2-bounded section
- `DocDiff` dataclass — holds version numbers and list of section diffs
- `diff_document_versions()` function — splits documents by H2 sections using `split_by_sections()`, diffs each section pair individually, classifies sections as `added`/`removed`/`changed`/`unchanged`

### 2. Added 3 New Routes to `dashboard/routers/docs.py`

**Route 1: `/api/docs/{doc_id}/diff/sections`** (JSON)
- Returns structured section-level diff as JSON
- Validates v1 < v2, document exists, both versions exist
- Uses `diff_document_versions()` and returns per-section status + unified diff lines

**Route 2: `/api/docs/{doc_id}/diff/sections/{section_name}`** (HTML)
- Returns HTML fragment for a single named section's unified diff
- URL-decodes section_name for safety
- Reuses existing `fragments/docs_diff.html` template

**Route 3: `/api/docs/{doc_id}/diff/ai-summary`** (204 Stub)
- Returns HTTP 204 with `X-Stub: waiting-for-F-00025` header
- Placeholder for future AI summarization (F-00025)

## Constraints Respected
- `DocService.diff_versions()` in `orch/doc_service.py` — NOT modified
- Existing `/api/docs/{doc_id}/diff` endpoint — NOT changed
- `orch/doc_diff.py` has NO imports from `orch.doc_service` or SQLAlchemy
- Lazy-imports `orch.doc_diff` inside route functions to avoid circular imports

## Test Results
```bash
ruff check orch/doc_diff.py dashboard/routers/docs.py  # PASS
mypy orch/doc_diff.py dashboard/routers/docs.py        # PASS (new code)
```
Note: mypy reports 3 pre-existing errors in `docs_guide_sections_get` (lines 1134-1135) unrelated to these changes.

## Blockers
None

## Notes
- Import order and type annotations follow existing codebase conventions
- The `_get_ver()` helper pattern matches the existing `diff_versions()` style in `DocService`
