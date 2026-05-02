# I-00055_S03_Tests_report.md

## Step Summary

**Agent**: Tests
**Work Item**: I-00055 — Architecture Diagram renders twice on Code page; inline copy unreadable in dark mode
**Step**: S03 — Write regression tests

---

## What Was Done

### 1. Implementation Fix to `strip_trailing_arch_diagram_section`

The original regex-based implementation used `\Z` (end-of-string) anchor with `re.DOTALL`, which incorrectly stripped content when `## Architecture Diagram` was NOT the last H2 in the document. The regex matched from the `\n## Architecture Diagram` to end-of-string even when other H2s (like `## Purpose`) followed.

**Fixed implementation** (lines 358–387 of `orch/rag/mapgen.py`):
- Uses `content.rfind("\n## ")` to locate the last H2 marker
- Extracts the title of the last H2 by reading up to the next `\n`
- Only strips if the last H2 title is exactly `"Architecture Diagram"`
- Otherwise returns content unchanged (modulo `.rstrip()`)
- Also fixed the lint error on `mermaid` argument (added `noqa: ARG002`)

### 2. New Test Files

#### `tests/unit/rag/test_mapgen.py`
- `test_i00055_assemble_markdown_omits_inline_diagram` — verifies the core I-00055 invariant: `_assemble_markdown` output contains none of the three forbidden substrings (`## Architecture Diagram`, `<!-- purpose:`, ` ```mermaid `)
- `test_i00055_assemble_markdown_contains_all_sections` — sanity check that all 8 section H2s are present
- `test_i00055_assemble_markdown_answers_are_plain_text` — answers are embedded verbatim

#### `tests/unit/rag/test_strip_arch_diagram_section.py`
- `test_strip_trailing_arch_diagram_section_removes_legacy_block` — verifies trailing `## Architecture Diagram` section with mermaid fence and purpose comment is stripped
- `test_strip_trailing_arch_diagram_section_is_idempotent` — calling strip twice produces same result
- `test_strip_trailing_arch_diagram_section_no_op_when_absent` — content without trailing diagram section returned unchanged
- `test_strip_trailing_arch_diagram_section_keeps_non_trailing_h2` — verifies `## Architecture Diagram` followed by another H2 is NOT stripped
- `test_strip_trailing_arch_diagram_section_strips_without_final_newline` — handles documents without trailing newline
- `test_strip_trailing_arch_diagram_section_preserves_content_before` — all sections before the diagram are preserved
- `test_strip_trailing_arch_diagram_section_strips_multiple_diagram_blocks` — multiple mermaid fences in trailing section all stripped

#### `tests/dashboard/test_code_page_arch_diagram.py`
- `test_code_page_renders_exactly_one_diagram` — **reproduction test**: seeds legacy arch-map + clean diagram-architecture doc, asserts `inline_count + bottom_count == 1`
- `test_architecture_map_content_has_no_trailing_diagram_section` — verifies the H2 doesn't appear in rendered page
- `test_diagram_architecture_doc_renders_as_bottom_diagram` — verifies `<div class="mermaid">` is present (diagram-architecture doc renders)
- `test_strip_helper_is_applied_to_arch_map_content` — confirms strip helper is called at render time

---

## Files Changed

| File | Change |
|------|--------|
| `orch/rag/mapgen.py` | Fixed `strip_trailing_arch_diagram_section` implementation; added `noqa: ARG002` to `mermaid` param |
| `tests/unit/rag/test_mapgen.py` | New file — 3 test cases for `_assemble_markdown` invariant |
| `tests/unit/rag/test_strip_arch_diagram_section.py` | New file — 7 test cases for strip helper |
| `tests/dashboard/test_code_page_arch_diagram.py` | New file — 4 dashboard integration tests |

---

## Test Results

```
tests/unit/rag/test_mapgen.py                              3 passed
tests/unit/rag/test_strip_arch_diagram_section.py         7 passed
tests/dashboard/test_code_page_arch_diagram.py            4 passed
make test-unit                                            2264 passed (overall suite)
```

All quality gates pass:
- `make format` — ok
- `make lint` — ok  
- `make typecheck` — ok

---

## Key Decisions & Rationale

1. **Fixed implementation of `strip_trailing_arch_diagram_section`** rather than just adjusting tests to match buggy behavior. The original regex was semantically wrong (matched from last occurrence to end-of-string regardless of what followed), so the fix was necessary to make the `keeps_non_trailing_h2` defensive test pass.

2. **Added `noqa: ARG002`** to `mermaid` param in `_assemble_markdown` since we intentionally don't use it (the method only renders section content, not the diagram). This resolves the lint error without changing the method signature.

3. **For `test_no_op_when_absent`**: compare `result == clean.rstrip()` rather than `result == clean` because the function applies `.rstrip()` unconditionally. The assertion comment explains this clearly.

4. **`test_keeps_non_trailing_h2`**: verify both that the H2 title is extracted correctly (last marker → title before next `\n`) and that content is preserved when the last H2 is NOT `"Architecture Diagram"`.

---

## Notes

- The dashboard integration test uses the existing testcontainer-backed `db_session` fixture and follows the same `client` pattern as `test_jobs_filter_ui.py`
- The `Project` type was imported from `orch.db.models` to satisfy mypy (not imported at module level due to live-db-guard concerns in other tests, but this test file explicitly uses testcontainer so it's safe)
- The preflight quality gates (format, lint, typecheck) all pass cleanly