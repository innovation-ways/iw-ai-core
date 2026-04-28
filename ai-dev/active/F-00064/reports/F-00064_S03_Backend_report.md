# F-00064 S03 Backend Report

## What was done

Implemented the backend for the code mapping diagram generation pipeline (F-00064 S03):

1. **Created `orch/diagram/` package:**
   - `__init__.py` — package marker with public exports
   - `render.py` — `render_mermaid(dsl)`, `render_d2(dsl)`, `render(dsl, dsl_type)` — server-side DSL→SVG rendering via `mmdc` and `d2` binaries; never raises, returns `None` on any failure
   - `install.py` — `check_diagram_tools() → dict[str, bool]` checking binary availability

2. **Updated `orch/rag/mapgen.py`:**
   - `_build_mermaid` prompt updated to require ELK YAML frontmatter (`--- config: layout: elk ---`) and max 15 nodes
   - Added defensive ELK frontmatter prepend after DSL extraction
   - `generate_level1` now stores the raw Mermaid DSL as a `ProjectDoc(doc_id="diagram-architecture", doc_type=DocType.diagram)` — wrapped in `try/except`, failure is logged but never propagates

3. **Updated `orch/rag/module_gen.py`:**
   - Added `_generate_and_store_module_diagram` async method that generates a per-module Mermaid diagram with ELK frontmatter and stores it as `ProjectDoc(doc_id=f"diagram-module-{slug}", doc_type=DocType.diagram)`
   - Called from `generate_level2` after the module doc is created, wrapped in `try/except`
   - Retrieves the last round of context chunks for diagram generation context

4. **Updated `ai-core.sh` install section** — added non-blocking `mmdc`/`d2` availability check with colored notices and install instructions

5. **Wrote TDD tests** in `tests/unit/rag/test_diagram_render.py` — 14 tests covering all render/installation failure paths

## Files Changed

- `orch/diagram/__init__.py` (new)
- `orch/diagram/render.py` (new)
- `orch/diagram/install.py` (new)
- `orch/rag/mapgen.py` (modified)
- `orch/rag/module_gen.py` (modified)
- `ai-core.sh` (modified)
- `tests/unit/rag/test_diagram_render.py` (new)

## Test Results

```
make format  — ok (451 files already formatted)
make lint    — ok (all checks passed)
make typecheck — ok (no issues found in 195 source files)
make test-unit — 1929 passed, 2 skipped
```

## Notes

- `DocService.update_doc` signature does not include `doc_type`, `tier`, or `editorial_category` — only `content`, `title`, `source_paths`, and `generated_by` were passed on update; `create_doc` passes all fields
- S603 `subprocess` lint violations suppressed with `# noqa: S603` since binary paths are validated via `shutil.which` before invocation
- The `last_context_chunks` pattern (carrying context from last retrieval loop iteration into diagram generation) avoids an extra LLM call to re-fetch