# QV Gate Report: unit-tests (S09)

## Work Item
- **ID**: I-00050
- **Step**: S09
- **Gate**: unit-tests
- **Command**: `make test-unit`

## Result: FAIL

## Summary

The `make test-unit` command completed with **7 failing tests**, 2066 passing, 2 skipped.

All 7 failures are in **RAG diagram generation** tests that assert the presence of `layout: elk` Mermaid frontmatter. The tests expect the mapgen/modulegen code to inject or preserve ELK layout frontmatter in generated Mermaid diagrams, but the code appears to have removed or never implemented this behavior.

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

## Observations

1. The failing tests all assert `layout: elk` in generated DSL, but the actual DSL output does not contain it
2. `test_module_diagram_prompt_elk_frontmatter_required` checks that the LLM prompt instructs it to include ELK frontmatter — this is also absent from the prompt
3. The pattern across all failures suggests a deliberate removal of ELK frontmatter injection from `MapGenerator` and `ModuleGenerator`

## No Code Changes

No files were modified during this step — only the quality gate was executed.