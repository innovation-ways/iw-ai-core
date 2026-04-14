# F-00041 S03 Tests Report

## Summary

Created integration test file `tests/integration/api/test_docs_ide_api.py` covering all 9 htmx endpoints for the F-00041 IDE tab. All 13 tests pass.

## Files Changed

| File | Change |
|------|--------|
| `tests/integration/api/test_docs_ide_api.py` | New file — 13 integration tests for IDE tab endpoints |

## Test Coverage

All 9 endpoints covered:

| Test | Endpoint | What it verifies |
|------|----------|------------------|
| `test_ide_tab_loads` | GET `/ide` | Fragment loads with "Guide Editor" heading |
| `test_get_type_guide_panel` | GET `/guide/type` | Returns textarea element |
| `test_get_type_guide_panel_content_round_trip` | GET `/guide/type` | Type guide pre-populated for doc_type |
| `test_save_type_guide` | POST `/guide/type` | Saves guide_md, response contains exact saved content |
| `test_save_type_guide_empty` | POST `/guide/type` | Empty save is valid (empty string) |
| `test_get_instance_guide_panel_no_override` | GET `/guide/instance` | Shows "Inheriting from type guide" when no instance guide |
| `test_save_instance_guide` | POST `/guide/instance` | Saves instance guide with exact content round-trip |
| `test_delete_instance_guide` | DELETE `/guide/instance` | DELETE returns 200; subsequent GET shows "Inheriting" state |
| `test_get_sections_panel_with_h2_headings` | GET `/guide/sections` | Panel returns valid HTML (sections populated after F-00039 merge) |
| `test_get_sections_panel_no_h2_sections` | GET `/guide/sections` | Panel returns valid HTML for plain prose docs |
| `test_save_section_guide` | POST `/guide/sections/{section_name}` | Section name and saved content appear in response |
| `test_save_section_guide_url_encoded_special_chars` | POST `/guide/sections/{section_name}` | `&` in section name renders as `&amp;` in textarea |
| `test_delete_section_guide` | DELETE `/guide/sections/{section_name}` | Returns 204 on delete |

## Semantic Correctness (I003 Lesson Applied)

Tests verify **specific content values** rather than mere response shape:

- `test_save_type_guide`: asserts exact `saved_content` in response (not just "textarea exists")
- `test_delete_instance_guide`: asserts "Inheriting from type guide" appears after DELETE
- `test_save_instance_guide`: asserts exact saved content round-trips
- `test_save_section_guide_url_encoded_special_chars`: accounts for HTML entity encoding (`&amp;`)

## Known Limitation

`extract_sections()` from `orch.doc_sections` (F-00039) is not yet merged. Section extraction tests (`test_get_sections_panel_with_h2_headings`) verify the endpoint is wired and returns valid HTML structure; section content assertions are documented as pending F-00039 merge.

## Test Results

```
13 passed in 5.50s
```
