# F-00065 S01 API Report

## What was done

Implemented the API layer for diagram display in code view:

### `dashboard/routers/code.py`
Added new endpoint:
```
GET /api/projects/{project_id}/code/modules/{slug}/diagram
```
- Validates project exists (404 if not)
- Looks up `ProjectDoc` with `doc_id=f"diagram-module-{slug}"` via `DocService(db).get_doc()`
- Renders `fragments/code_module_diagram.html` with `project_id`, `slug`, `diagram_dsl`
- Returns empty-state fragment (200) when no diagram doc exists — not a 404

### `dashboard/routers/code_ui.py`
- **`code_page` handler**: Added `arch_diagram_dsl` retrieval alongside `arch_doc` loading. Passes `arch_diagram_dsl` to `project_code.html` template context.
- **`code_architecture` handler**: Added `arch_diagram_doc` lookup and `arch_diagram_dsl` to template context for `code_architecture_view.html`.

## Files changed

- `dashboard/routers/code.py` — added `GET .../modules/{slug}/diagram` endpoint
- `dashboard/routers/code_ui.py` — added `arch_diagram_dsl` to both `code_page` and `code_architecture` template contexts

## Preflight results

| Gate | Result |
|------|--------|
| format (changed files) | ok |
| typecheck (dashboard/) | ok — 0 errors in 196 source files |
| lint (changed files) | ok |

Note: `make format` and `make lint` reported pre-existing failures in unrelated files (e.g., `tests/unit/rag/test_mapgen_mermaid.py`, `CR-99025` fixtures). The changed files pass cleanly.

## Notes

- The fragment templates (`code_module_diagram.html`, `code_architecture_diagram.html`) will be created in S03 (frontend-impl) per the step ordering in the design doc.
- The `_preprocess_mermaid` fix (changing `<div class="mermaid">` to `<pre data-lang="mermaid">`) is out of scope for S01 — that's in `code_ui.py` but the fragment/JS work is S03.
- Followed existing patterns: `_get_project_or_404` for validation, `DocService(db).get_doc()` for DB access, `TemplateResponse` for HTML fragments.