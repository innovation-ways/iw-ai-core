# QV Gate Report: unit-tests

**Gate:** unit-tests
**Command:** `make test-unit`
**Result:** FAIL

## Summary

Executed `make test-unit` — 7 tests failed, 2062 passed.

## Failed Tests

| Test | File |
|------|------|
| `test_elk_frontmatter_injected_when_llm_omits_it` | `tests/unit/rag/test_mapgen_mermaid.py` |
| `test_elk_frontmatter_not_duplicated_when_llm_includes_it` | `tests/unit/rag/test_mapgen_mermaid.py` |
| `test_fallback_dsl_when_no_fenced_block` | `tests/unit/rag/test_mapgen_mermaid.py` |
| `test_build_mermaid_elk_frontmatter_preserved` | `tests/unit/test_rag_mapgen.py` |
| `test_stored_content_starts_with_purpose_comment` | `tests/unit/test_rag_mapgen_diagram.py` |
| `test_purpose_extracted_and_normalized_to_single_line` | `tests/unit/test_rag_module_gen.py` |
| `test_module_diagram_prompt_elk_frontmatter_required` | `tests/unit/test_rag_module_gen_diagram.py` |

## Root Cause

All 7 failures are related to **ELK frontmatter (`layout: elk`)** injection in the Mermaid diagram generation pipeline. The tests expect the `MapGenerator._build_mermaid()` and `ModuleGenerator` to inject or preserve `layout: elk` in the YAML frontmatter of generated Mermaid diagrams. The current implementation appears to have removed or altered this behavior.

## Observations

- All failures are in RAG mapgen/module_gen related tests
- The pattern: tests assert `layout: elk` is present in DSL or prompts, but it is absent
- The classDef color scheme block is still being injected, but the ELK layout frontmatter is missing
- This likely represents a regression from a prior change to the diagram generation logic

## Recommendation

Investigate `orch/rag/mapgen.py` and `orch/rag/module_gen.py` for changes to the ELK frontmatter injection logic. Restore the `layout: elk` frontmatter handling to match the test expectations.