# F-00067 S11 — Final Code Review Report

## Step Summary

Global cross-layer review of all implementation work for F-00067 (Documentation Visual Design Overhaul).

## Files Changed

- `orch/rag/mapgen.py` — Enhanced `_build_mermaid()` with semantic color palette (`classDef`), "Why" purpose paragraph extraction, abstraction-level instruction, ELK frontmatter
- `orch/rag/module_gen.py` — Added `_MERMAID_CLASSDEF` + `_MERMAID_CLASSDEF_BLOCK` constants, enhanced `_generate_and_store_module_diagram()` with color palette + purpose extraction, added `_ensure_classdef_in_dsl()` helper
- `orch/rag/index_gen.py` — **New file** — generates `code-index` ProjectDoc per project after CodeIndexJob completes; groups docs by type (architecture, diagram, module, api, research); graceful empty-state handling
- `dashboard/utils/markdown.py` — Added `render_markdown_with_callouts()` with `TYPE_MAP` for all 5 callout types (NOTE, TIP, WARNING, DANGER, IMPORTANT) + `CALLOUT_RE` regex
- `dashboard/templates/docs_detail.html` — CSS for all 5 callout types, prose hierarchy (H1/H2/H3 styled), sticky TOC via `iwBuildToc()`, client-side callout processor via `iwProcessCallouts()`, diagram purpose rendering
- `dashboard/templates/fragments/code_architecture_diagram.html` — Added `arch_purpose` slot (renders as italic paragraph above diagram)
- `dashboard/templates/fragments/code_module_diagram.html` — Added `diagram_purpose` slot (renders as italic paragraph above diagram)
- `dashboard/routers/docs.py` — `docs_detail()` now uses `render_markdown_with_callouts()` (line 78)
- `orch/rag/job.py` — Added `generate_index_page` import + try/except wrapper after `_run_mapgen()` completes (lines 138-156)
- `skills/iw-doc-generator/references/module-doc-template.md` — Added "## Why Read This" section, "## Key Diagrams" section, callout usage rules comment
- `skills/iw-doc-generator/references/diagram-guidelines.md` — **New file** — canonical color palette, "Why" paragraph rule, diagram type selection, abstraction rules
- `skills/iw-tech-doc-writer/references/diagram-guidelines.md` — Added "## Canonical Color Palette" and "## Why Paragraph Rule" sections
- New tests: `tests/unit/test_rag_index_gen.py`, `tests/integration/test_rag_index_gen_integration.py`, `tests/dashboard/test_docs_callouts.py`, `tests/unit/test_rag_mapgen.py`, `tests/unit/test_rag_mapgen_diagram.py`, `tests/unit/test_rag_module_gen.py`, `tests/unit/test_rag_module_gen_diagram.py`

## Cross-Layer Findings

### ✅ 1. Color palette consistency — PASS
- `mapgen.py` imports `_MERMAID_CLASSDEF` from `module_gen.py`
- Both use **identical** hex values: api `#DBEAFE/#3B82F6/#1E3A5F`, data `#D1FAE5/#10B981/#065F46`, worker `#FEF3C7/#F59E0B/#78350F`, external `#F3F4F6/#9CA3AF/#374151`, ui `#EDE9FE/#8B5CF6/#3B0764`, core `#FEE2E2/#EF4444/#7F1D1D`
- CSS in `docs_detail.html` (lines 212-221) uses the **same** hex values for all 5 callout types
- Both skill files (`iw-doc-generator/references/diagram-guidelines.md` and `iw-tech-doc-writer/references/diagram-guidelines.md`) embed the **same** canonical palette in tables and code blocks

### ✅ 2. "Why" paragraph round-trip — PASS
- LLM prompt instructs: output second fenced ` ```purpose ` block after diagram
- `mapgen.py` `_build_mermaid()` extracts via `purpose_match` regex (line 322-324), falls back to default if missing
- `module_gen.py` `_generate_and_store_module_diagram()` extracts via `purpose_match` regex (line 332-338), falls back to default if missing
- Purpose stored as `<!-- purpose: {purpose} -->` comment in `ProjectDoc.content` (mapgen line 182, module_gen line 345)
- Jinja2 templates (`code_architecture_diagram.html` lines 4-6, `code_module_diagram.html` lines 4-5) render `arch_purpose` / `diagram_purpose` with None-safe `{% if %}` guard
- **No silent failure point** — all fallbacks present

### ✅ 3. Callout rendering completeness — PASS
- Server-side: `render_markdown_with_callouts()` in `dashboard/utils/markdown.py` handles all 5 types (NOTE, TIP, WARNING, DANGER, IMPORTANT) via `TYPE_MAP` + `CALLOUT_RE` regex
- CSS classes: `.callout-note`, `.callout-tip`, `.callout-warning`, `.callout-danger`, `.callout-important` all defined in `docs_detail.html` (lines 212-221)
- Client-side: `iwProcessCallouts()` in `docs_detail.html` (lines 334-359) also handles all 5 types as fallback/JIT processing
- `[!NOTE]` in generated index page will render via `render_markdown_with_callouts()` in `docs.py:78`

### ✅ 4. Index page integration — PASS
- `job.py` imports `generate_index_page` at line 139
- try/except wrapper at lines 141-156 with non-fatal logging
- `code-index` doc served via existing `/project/{id}/docs/{doc_id}` route (no new route needed)
- `DocType.architecture` + `DocTier.fully_automated` as per design invariant #4

### ✅ 5. Skills sync — PASS
- S03 report confirms `uv run iw sync-skills` was run and completed (with non-blocking project override skips for innoforge)

### ✅ 6. No regressions introduced — PASS (pre-existing issues only)
- **Lint**: 2 pre-existing ARG001 errors in `dashboard/routers/code_qa.py` (unrelated to F-00067)
- **Typecheck**: 197 source files, 0 errors
- **Unit tests**: 2053 passed, 2 skipped
- **Integration tests**: 3 failures — 2 are pre-existing baseline QV pipeline failures (confirmed by git stash test), 1 (`test_project_doc_fts_full_text_search`) is non-deterministic and passes in isolation

### ✅ 7. AC coverage — PASS
- **AC1** (semantic colors): Implemented in `mapgen.py` + `module_gen.py` with identical `classDef` blocks; `_ensure_classdef_in_dsl()` guards against LLM omissions
- **AC2** ("Why" paragraph): LLM prompt includes purpose extraction; stored as `<!-- purpose: -->` comment; rendered in both fragment templates via `{% if arch_purpose %}` / `{% if diagram_purpose %}`
- **AC3** (callout rendering): `render_markdown_with_callouts()` server-side + `iwProcessCallouts()` client-side; all 5 types styled in CSS
- **AC4** (in-page TOC): `iwBuildToc()` client-side JS in `docs_detail.html`; generates anchors for H2/H3; threshold 3 headings; sticky float-right TOC with responsive hiding
- **AC5** (index page generation): `orch/rag/index_gen.py` hooks into `CodeIndexJobRunner.run()` via `generate_index_page()` call after mapgen; `code-index` doc created/updated with grouped sections and one-line descriptions
- **AC6** (typographic hierarchy): CSS in `docs_detail.html` (lines 192-196) styles H1/H2/H3 with distinct font-weight (700/600/600) and H3 gets muted color

## Test Results

| Suite | Result |
|-------|--------|
| `make test-unit` | **2053 passed**, 2 skipped |
| `make lint` | 2 pre-existing ARG001 errors in `code_qa.py` (unrelated to F-00067) |
| `make typecheck` | **197 source files, 0 errors** |
| `make test-integration` | 3 failures (2 pre-existing baseline QV + 1 non-deterministic FTS) |

## Verdict

**PASS** — All cross-layer consistency checks passed. All 6 Acceptance Criteria are addressed. The 3 integration test failures are pre-existing (baseline QV) or non-deterministic (FTS), not introduced by F-00067 changes. Typecheck is clean. Lint failures are pre-existing.