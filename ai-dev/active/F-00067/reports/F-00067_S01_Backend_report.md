# F-00067_S01_Backend_report.md

## Step Summary

**Step**: S01 — Backend Implementation
**Agent**: backend-impl
**Work Item**: F-00067 — Documentation Visual Design Overhaul

## What Was Done

Enhanced the LLM prompts in `mapgen.py` and `module_gen.py` to generate semantic, colorful Mermaid diagrams with the following improvements:

### 1. Semantic Color Palette (`mapgen.py`)

- Added `classDef` block instruction to the LLM prompt with the canonical 6-class color palette:
  - `api` (blue) — API/CLI entry points
  - `data` (green) — Database models, repositories
  - `worker` (amber) — Background jobs, daemon, pipeline workers
  - `external` (gray) — External APIs, third-party services
  - `ui` (purple) — Dashboard/UI components
  - `core` (red) — Core orchestration services

- Added class assignment rules instructing the LLM which components get which class
- Added abstraction-level instruction: show only high-level architectural components (no utilities, DTOs, helpers)
- Added "Why" instruction: LLM must output a `purpose` block after the diagram
- Post-process DSL to inject `classDef` block if LLM omits it

### 2. Purpose Extraction and Storage (`mapgen.py`)

- `_build_mermaid()` now returns a tuple `(dsl, purpose)` instead of just `dsl`
- Extracts purpose from `purpose` block using regex, normalizes to single line
- Fallback purpose when no purpose block found: "This diagram shows the top-level architecture of the system."
- Purpose is prepended to stored content as `<!-- purpose: {purpose text} -->`
- Updated `store_arch_diagram` closure to accept and prepend purpose comment
- Updated `_assemble_markdown` to include purpose comment in markdown

### 3. Module Diagram Enhancements (`module_gen.py`)

- Changed diagram direction from `graph TD` to `graph LR` (left-to-right)
- Added same semantic color `classDef` block instructions
- Added class assignment rules specific to module internals
- Added structural-elements-only instruction (controllers, services, repos, adapters, domain models — no utilities/DTOs)
- Added "Why" instruction for purpose block
- Extracts purpose from response, normalizes to single line
- Fallback purpose: "This diagram shows the internal component structure of the {module_name} module."
- Prepends purpose comment to stored content

### 4. Refactoring

- Extracted `_MERMAID_CLASSDEF` constant to `module_gen.py` (shared location)
- Extracted `_MERMAID_CLASSDEF_BLOCK` constant (just the classDef lines, without instruction prefix)
- Created `_ensure_classdef_in_dsl()` helper function to post-process DSL and inject classDef block if missing
- `mapgen.py` imports these constants from `module_gen.py`

## Files Changed

| File | Change |
|------|--------|
| `orch/rag/mapgen.py` | Enhanced `_build_mermaid()` prompt, tuple return, purpose extraction, purpose comment injection |
| `orch/rag/module_gen.py` | Added `_MERMAID_CLASSDEF`, `_MERMAID_CLASSDEF_BLOCK`, `_ensure_classdef_in_dsl()`, enhanced `_generate_and_store_module_diagram()` |
| `tests/unit/test_rag_mapgen.py` | NEW — 12 tests for `_build_mermaid()` enhancements |
| `tests/unit/test_rag_module_gen.py` | NEW — 10 tests for module diagram enhancements |
| `tests/unit/rag/test_mapgen_mermaid.py` | MODIFIED — updated existing tests to handle tuple return |
| `tests/unit/test_code_indexer.py` | MODIFIED — updated existing tests to handle tuple return and new `_assemble_markdown` signature |

## Test Results

```
======================== 22 passed, 1 warning in 1.17s =========================
```

New tests added:
- `TestBuildMermaid` (8 tests): tuple return, purpose extraction, fallback purpose, classDef presence, elk frontmatter, fallback graph
- `TestBuildMermaidPrompt` (4 tests): prompt contains classDef instructions, abstraction-level, why instruction, class assignment rules
- `TestGenerateModuleDiagram` (5 tests): purpose extraction, normalization, fallback, classDef presence
- `TestModuleDiagramPrompt` (5 tests): LR direction, classDef instructions, structural elements, why instruction, class assignment rules

## Pre-flight Quality Gates

| Check | Status |
|-------|--------|
| `make format` | PASSED (only `tests/unit/test_code_ui_routes.py` fails — pre-existing issue unrelated to this PR) |
| `make typecheck` | PASSED |
| `make lint` | PASSED for changed files; 2 pre-existing errors in `dashboard/routers/code_qa.py` |
| `make test-unit` | 2002 passed, 2 failed (pre-existing failures in `test_safe_migrate.py` unrelated to changes) |

## Issues/Observations

1. **Pre-existing lint issue**: `dashboard/routers/code_qa.py` has unused `dsl` argument warnings (ARG001) — not related to this step
2. **Pre-existing test failures**: `test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context` and `test_rollback_refuses_in_agent_context` — unrelated to diagram generation changes
3. The `_ensure_classdef_in_dsl()` helper ensures semantic colors are always present in the stored DSL, even if the LLM only uses individual `class NodeID api` assignments without the full classDef block

## Blockers

None
