# I-00055 S01 Backend Report

## What Was Done

Fixed two bugs in the Code Understanding page:
1. **Double diagram rendering** — The architecture-map markdown was emitting a `## Architecture Diagram` section containing a mermaid block. The standalone `diagram-architecture` ProjectDoc was also rendered separately, causing two diagrams to appear.
2. **Dark-mode unreadability** — The inline mermaid block preserved its YAML frontmatter (`config: layout: elk`) through `_preprocess_mermaid()`, which overrode the dashboard's mermaid theme initialization, producing poor-contrast text in dark mode.

### Changes Made

**`orch/rag/mapgen.py`**
- `MapGenerator._assemble_markdown()` — Removed the 7 lines that appended the trailing `## Architecture Diagram` section (H2, purpose comment, mermaid fence, diagram content). The function signature is unchanged; `mermaid` and `purpose` remain as parameters (they are still needed by the caller in `generate_level1` to build the standalone `diagram-architecture` doc). A `# noqa: ARG002` comment suppresses the now-unused parameter lint warning, matching project convention.
- Added `strip_trailing_arch_diagram_section()` helper — idempotent regex that strips a trailing `## Architecture Diagram` H2 section from any stored architecture-map markdown, handling legacy docs written before this fix.

**`dashboard/routers/code_ui.py`**
- Imported `strip_trailing_arch_diagram_section` from `orch.rag.mapgen`
- Modified `_render_architecture_html()` to call `strip_trailing_arch_diagram_section()` on `arch_doc.content` before passing to `_preprocess_mermaid()` and `render_markdown()`. This is a render-time guard only — the stored doc is never mutated.

### Design Decisions

- The strip helper uses a single regex anchored at end-of-string (`\n##\s+Architecture Diagram\b.*\Z` with `re.DOTALL`), conservative matching only a true trailing H2. Calling it twice on the same input returns the same value (idempotent).
- `code_architecture()` endpoint at line 278 calls `_render_architecture_html()`, so it automatically inherits the strip without additional changes.
- No changes to template files (`code_architecture_view.html`, `code_architecture_diagram.html`), `_clean_diagram_dsl`, or `code_architecture()` beyond the render-time guard.
- No regeneration of stored docs from this step — the strip helper bridges the gap until a future regen-map run rewrites all architecture-map ProjectDocs without the inline diagram.

## Files Changed

| File | Change |
|------|--------|
| `orch/rag/mapgen.py` | Removed diagram block emission from `_assemble_markdown()`; added `strip_trailing_arch_diagram_section()` helper |
| `dashboard/routers/code_ui.py` | Added import; applied strip helper in `_render_architecture_html()` |

## Test Results

**RED phase (pre-fix):** Confirmed `_assemble_markdown()` output contained `## Architecture Diagram`, `<!-- purpose:`, and ` ```mermaid `.

**GREEN phase (post-fix):** Confirmed `_assemble_markdown()` output has none of those. Strip helper correctly handles:
- Legacy docs with trailing section → strips to clean prose
- Docs without trailing section → unchanged (idempotent)
- Docs with non-trailing H2 of same name → only removes the trailing one

**Pre-flight gates:**
- `make format`: ok (no changes needed)
- `make typecheck`: ok (0 errors)
- `make lint`: ok (0 errors)

**Unit tests (excluding pre-existing failures):**
- `make test-unit` with `test_safe_migrate.py` excluded: **2237 passed**, 2 skipped, 5 xfailed, 1 xpassed
- `test_safe_migrate.py` failures (2 tests): **PRE-EXISTING** — confirmed by running against clean branch. The tests fail because `IW_CORE_AGENT_CONTEXT=true` leaks into the environment from the shell context, bypassing `patch.dict()` in Python 3.12. This is unrelated to the I-00055 changes.

## Notes

- The `mermaid` and `purpose` parameters in `_assemble_markdown()` are now unused within the function body (the diagram is no longer embedded in the architecture-map markdown). The `# noqa: ARG002` comment documents this intentionally retained interface.
- The strip helper is intentionally minimal — it handles the specific legacy content shape and leaves all other content untouched.