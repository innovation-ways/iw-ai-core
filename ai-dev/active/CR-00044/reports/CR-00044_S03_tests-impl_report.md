# CR-00044 S03 Tests Implementation Report

## Summary

Completed test implementation for CR-00044 covering all six acceptance criteria (AC1–AC6). Three test files were modified/extended, all 99 tests pass with zero failures.

## Files Changed

| File | Changes |
|------|---------|
| `tests/dashboard/test_system_docs_route.py` | Extended `TestSystemDocsSubdirectory` with AC1/AC2/AC3/AC6 tests; fixed `test_valid_doc_slug_shows_doc_title` to check actual H1 content |
| `tests/dashboard/test_help_router.py` | Added `TestHelpRouterAnchorPinning` (AC4 anchor pinning) and `TestHelpRouterNoHardcodedOldLinks` (regression guard); imported `_SLUG_TO_DOC` for parametrised tests |
| `tests/dashboard/test_favicon.py` | Already complete — verified existing tests cover AC5 fully |

## Test Coverage by Acceptance Criteria

### AC1: Subdirectory documents render
- `test_subdir_doc_claude_md_returns_200` — verifies `GET /system/docs/orch/rag/CLAUDE.md` → 200 with "Code Understanding" heading
- `test_subdir_doc_implementation_index_returns_200` — verifies `GET /system/docs/implementation/00_INDEX` → 200 with "Implementation Plan" heading

### AC2: Existing top-level doc URLs still work
- `test_existing_top_level_doc_still_works` — verifies `GET /system/docs/IW_AI_Core_Daemon_Design` → 200 with "Daemon" content (regression guard)

### AC3: Path traversal is rejected
- `test_path_with_leading_slash_returns_404`
- `test_dot_component_returns_404`
- `test_double_dot_traversal_returns_404`
- `test_non_md_path_returns_404` — verifies no file content leaked
- `test_unknown_subdir_path_returns_404`
- `test_traversal_etc_passwd_returns_404` — verifies no /etc/passwd content
- `test_traversal_url_encoded_returns_404`
- `test_docs_non_md_file_via_traversal_returns_404`
- `test_empty_doc_path_returns_404`
- `test_leading_slash_url_encoded_returns_404`

### AC4: Five generic help mappings point at content-appropriate docs
- `TestHelpRouterSlugMappingCR00044` — individual tests for code, item_detail, research, search → Dashboard_Design, projects → Architecture
- `TestHelpRouterAnchorPinning` — parametrised test that iterates over every `#anchor` in `_SLUG_TO_DOC` and verifies it appears as `id="..."` in the rendered target HTML
- `TestHelpRouterNoHardcodedOldLinks` — regression guard ensuring no `/docs/IW_AI_Core` or bare `/orch/` hrefs exist

### AC5: No more /favicon.ico console error
- `test_favicon_ico_returns_200`
- `test_favicon_ico_content_type_is_svg`
- `test_favicon_ico_returns_svg_bytes` — verifies byte-for-byte match with `dashboard/static/favicon.svg`

### AC6: Document page title comes from first H1
- `test_h1_derived_title_for_subdir_doc` — verifies title contains "Implementation Plan" (H1 of `docs/implementation/00_INDEX.md`) and does NOT contain "implementation/00 INDEX"
- `test_valid_doc_slug_shows_doc_title` — updated to check for actual H1 content "Complete Architecture" from `docs/IW_AI_Core_Architecture.md`

## Test Results

```
uv run pytest tests/dashboard/test_favicon.py tests/dashboard/test_system_docs_route.py tests/dashboard/test_help_router.py -v --no-cov
======================== 99 passed, 1 warning in 18.17s ========================
```

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `ruff format` | ok (2 files reformatted, 1 unchanged) |
| `ruff check` | ok (all checks passed) |
| `mypy` | ok (no issues found in 3 source files) |

## Decisions Made

1. **Anchor-pinning test**: `_SLUG_TO_DOC` values include the `/system/docs/` prefix (e.g., `/system/docs/IW_AI_Core_CLI_Spec#iw-approve`). The test strips the prefix before building the URL to request, so it correctly requests `GET /system/docs/IW_AI_Core_CLI_Spec`.

2. **Strict content assertions**: All tests verify specific content from the actual document (heading text, "Daemon", "Code Understanding") rather than just status codes — following the I-00003 lesson.

3. **No hardcoded old hrefs**: The `TestHelpRouterNoHardcodedOldLinks` uses a `re.findall` to detect bare `/orch/` hrefs (which would be wrong) while correctly allowing `/system/docs/orch/` subdir doc hrefs.

4. **Favicon test already complete**: The existing `test_favicon.py` fully covers AC5 — no changes needed.
