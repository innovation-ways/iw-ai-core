# F-00039 S02 Backend Report

## What Was Done

Implemented the Python model, module, and service layer for section-level guides:

1. **Added `DocSectionGuide` model** to `orch/db/models.py`:
   - Table: `doc_section_guides` with columns: `id` (BIGSERIAL PK), `doc_id` (FK), `section_name`, `guide_md`, `updated_at`
   - Unique constraint on `(doc_id, section_name)`
   - Index on `doc_id`

2. **Added `section_guides_snapshot` column** to `DocGenerationJob`:
   - JSONB column storing `{section_name: guide_md, ...}` snapshot at job creation

3. **Created `orch/doc_sections.py`** module with:
   - `extract_sections(content: str) -> list[str]` - extracts H2 section names
   - `split_by_sections(content: str) -> dict[str, str]` - splits content by H2 sections

4. **Added section guide methods to `DocService`**:
   - `get_section_guide(project_id, doc_id, section_name) -> str | None`
   - `save_section_guide(project_id, doc_id, section_name, guide_md) -> DocSectionGuide`
   - `delete_section_guide(project_id, doc_id, section_name) -> bool`
   - `list_section_guides(project_id, doc_id) -> list[DocSectionGuide]`

5. **Updated `DocService.create_doc_job()`** to snapshot section guides at job creation

6. **Added imports** for `DocSectionGuide` and doc_sections utilities in doc_service.py

## Files Changed

- `orch/db/models.py` - Added `DocSectionGuide` model and `section_guides_snapshot` column
- `orch/doc_service.py` - Added section guide CRUD methods and imports
- `orch/doc_sections.py` - New module with H2 extraction utilities
- `tests/unit/test_doc_sections.py` - Unit tests for doc_sections module

## Test Results

```
11 passed in 0.02s
```

All unit tests pass:
- `test_extract_sections_with_h2_headings`
- `test_extract_sections_no_h2_returns_document`
- `test_extract_sections_empty_content`
- `test_extract_sections_h3_only_returns_document`
- `test_extract_sections_strips_whitespace`
- `test_extract_sections_preserves_inline_backticks`
- `test_split_by_sections_correct_bodies`
- `test_split_by_sections_no_h2_returns_document_key`
- `test_split_by_sections_last_section_to_end`
- `test_split_by_sections_empty_content`
- `test_split_by_sections_single_h2`

## Quality Checks

- **ruff**: All checks passed
- **mypy**: No issues found in 3 source files

## Issues/Observations

None - all implementation completed as specified.
