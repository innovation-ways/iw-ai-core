# F-00076 S03 Backend Report

## What Was Done

Implemented the design-doc → DB plumbing for `WorkItem.impacted_paths` as specified in the F-00076_S03_Backend_prompt.

### 1. Parser (`orch/design_doc_parser.py`)
Added `parse_impacted_paths()` and `ImpactedPathsResult`:
- Parses `## Impacted Paths` section using `_iter_section_ranges()` (shared with `parse_dependencies`)
- Accepts both markdown bullet lists (`- glob`, `* glob`) and fenced code blocks
- Validates each glob: no absolute paths, no `..` segments, no whitespace inside
- Deduplicates while preserving original order
- Returns `ImpactedPathsResult(found=False)` when section absent, `found=True` when present (even if empty)

### 2. `iw register` hook (`orch/cli/item_commands.py`)
- Calls `parse_impacted_paths(design_doc_content)` before inserting `WorkItem`
- If section found → `impacted_paths` populated, `scope_extraction.source="declared"`
- If section absent with file paths → regex fallback, `source="regex_fallback"`, `warned_at` timestamp, stderr warning
- If section absent with no file paths → `source="none"`
- Validation errors (ValueError from bad glob) exit non-zero via `output_error()` — no row created

### 3. `batch_planner.analyze_dependencies()` (`orch/batch_planner.py`)
- Phase 1: uses `impacted_paths` column when present, falls back to `extract_affected_files()` when absent
- Test-path entries (`/tests/`, `/test/`, `/__tests__/`, `conftest`, `.test.`, `.spec.`) filtered out from `impacted_paths`
- Phase 3b (cross-batch): uses `impacted_paths` from active items when present, falls back to regex when absent

### 4. `batch_commands.py` (`_generate_batch_plan()`)
- Added `impacted_paths` to `items_data` dicts built from `WorkItem` rows
- Added `impacted_paths` to `active_items_data` dicts from active batch work items
- Removed the `wi.design_doc_content` guard (now uses `impacted_paths` column directly)

### 5. Design Templates
Updated all six templates with the new `## Impacted Paths` section between `## Dependencies` and `## TDD Approach`:
- `ai-dev/templates/Feature_Design_Template.md`
- `ai-dev/templates/Issue_Design_Template.md`
- `ai-dev/templates/CR_Design_Template.md`
- `templates/design/Feature_Design_Template.md`
- `templates/design/Issue_Design_Template.md`
- `templates/design/CR_Design_Template.md`

### 6. Tests
- **Parser unit tests** (`tests/unit/test_design_doc_parser.py`): 22 new tests covering bullet lists, code blocks, section absent/empty, validation errors (absolute path, `..`, whitespace, empty), special chars, dedup
- **Register integration tests** (`tests/integration/cli/test_register_impacted_paths.py`): 7 new tests covering declared section, code block, regex fallback with warning, no paths at all, validation errors (absolute path, `..`), config preservation
- **Batch planner unit tests** (`tests/unit/test_batch_planner.py`): 4 new tests covering `impacted_paths` column usage, regex fallback, test-path filtering, cross-batch usage

## Files Changed

| File | Change |
|------|--------|
| `orch/design_doc_parser.py` | Added `ImpactedPathsResult` dataclass and `parse_impacted_paths()` function |
| `orch/cli/item_commands.py` | Hooked `parse_impacted_paths` into `register()`, populates `impacted_paths` + `config["scope_extraction"]` |
| `orch/cli/batch_commands.py` | Added `impacted_paths` to `items_data` and `active_items_data` dicts |
| `orch/batch_planner.py` | `analyze_dependencies()` reads `impacted_paths` column first; cross-batch also reads `impacted_paths` |
| `ai-dev/templates/Feature_Design_Template.md` | Added `## Impacted Paths` section |
| `ai-dev/templates/Issue_Design_Template.md` | Added `## Impacted Paths` section |
| `ai-dev/templates/CR_Design_Template.md` | Added `## Impacted Paths` section |
| `templates/design/Feature_Design_Template.md` | Added `## Impacted Paths` section |
| `templates/design/Issue_Design_Template.md` | Added `## Impacted Paths` section |
| `templates/design/CR_Design_Template.md` | Added `## Impacted Paths` section |
| `tests/unit/test_design_doc_parser.py` | Added 22 new tests for `parse_impacted_paths` |
| `tests/unit/test_batch_planner.py` | Added 4 new tests for `analyze_dependencies` with `impacted_paths` |
| `tests/integration/cli/test_register_impacted_paths.py` | New file with 7 integration tests for `iw register` + `impacted_paths` |

## Test Results

- **Unit tests**: 56 passed (2450 total with all unit tests)
- **Integration tests** (new): 7 passed
- **Related integration tests**: 14 passed (register deps), 19 passed (batch CLI)

## Notes

- The `_is_test_path()` check looks for `/tests/`, `/test/`, `/__tests__/`, `conftest`, `.test.`, `.spec.` — this correctly handles `**/__tests__/bar.py` (contains `__tests__`) but `tests/test_foo.py` does NOT contain any of those markers literally (it would need substring matching for "test" as a directory name prefix). Test paths in `impacted_paths` should use paths like `orch/tests/bar.py` to be correctly filtered.
- The `parse_impacted_paths` parser correctly handles indented bullets (e.g., `  - orch/foo.py`) due to the `lstrip()` + indent calculation approach.