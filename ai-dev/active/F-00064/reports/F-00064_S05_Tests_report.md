# F-00064 S05 — Tests Report

## Summary

Added unit test coverage for the code mapping diagram generation pipeline (F-00064).

## Files Changed

- `tests/unit/rag/test_diagram_render.py` — already existed with 14 passing tests (pre-existing from S04)
- `tests/unit/rag/test_mapgen_mermaid.py` — **new** file

## New Test File: `tests/unit/rag/test_mapgen_mermaid.py`

Tests the `MapGenerator._build_mermaid` ELK frontmatter injection logic:

| Test | What It Verifies |
|------|------------------|
| `test_elk_frontmatter_injected_when_llm_omits_it` | When LLM returns mermaid without `layout: elk`, it is injected exactly once |
| `test_elk_frontmatter_not_duplicated_when_llm_includes_it` | When LLM already includes `layout: elk`, it is NOT duplicated |
| `test_fallback_dsl_when_no_fenced_block` | When LLM returns prose with no fenced block, fallback DSL is returned with ELK frontmatter injected |

All 3 tests use `unittest.mock.patch` to mock `Ollama.complete` so no real LLM calls are made.

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ok |
| `make typecheck` | ok |
| `make lint` | ok |
| `make test-unit` | **1932 passed, 2 skipped, 0 failed** |

## Test Results

```
tests/unit/rag/test_diagram_render.py  — 14 passed (pre-existing)
tests/unit/rag/test_mapgen_mermaid.py  —  3 passed (new)
```

## Observations

- Existing `test_diagram_render.py` already covered all the `render_mermaid`, `render_d2`, `render` dispatcher, and `check_diagram_tools` cases per spec — no changes needed.
- The `_build_mermaid` method is `@staticmethod` but constructs an `Ollama` LLM internally, so patching `orch.rag.mapgen.Ollama` works cleanly.
- The test for fallback DSL (`test_fallback_dsl_when_no_fenced_block`) required a small adjustment: the fallback `"graph TD\n  A[System]"` gets the ELK frontmatter prepended, so the result starts with `---\nconfig:\n  layout: elk\n---\n` rather than `graph TD`. Updated assertion to check `"graph TD" in result` instead of `result.startswith("graph TD")` to match actual behavior.
