# F-00067 S07 Backend Report — Index Page Generation

## What was done

Implemented `orch/rag/index_gen.py` — a module that generates (or updates) a `code-index` ProjectDoc per project after a `CodeIndexJob` completes. The index page lists all available documentation grouped by doc_type (Architecture, Module Documentation, Module Diagrams, API Reference, Research) with section headers and one-line descriptions.

### Files changed

- **`orch/rag/index_gen.py`** (new) — `generate_index_page()` function that:
  - Queries all `ProjectDoc` records for a project
  - Builds a Markdown index with proper sections and tables
  - Stores via `DocService.create_doc()` or `update_doc()`
  - Handles empty projects gracefully with a "no docs yet" note
  - Uses `_extract_first_sentence()` to get first sentence from content (stripping headers, finding first `.`/`!`/`?` terminated sentence)

- **`orch/rag/job.py`** (modified) — Added index page generation call after `code_map_completed` event, wrapped in try/except so failures never cause the job itself to fail (logged as warning)

### Tests added

- **`tests/unit/test_rag_index_gen.py`** — 22 unit tests:
  - `TestExtractFirstSentence` (9 tests): header stripping, sentence extraction, ellipsis fallback
  - `TestBuildIndexContent` (9 tests): architecture/map/diagram/module/API/research sections
  - `TestGenerateIndexPage` (4 tests): create vs update, empty project handling

- **`tests/integration/test_rag_index_gen.py`** — 5 integration tests:
  - Creates real DB records via testcontainer, calls `generate_index_page()`, verifies doc exists in DB with correct content

### Test results

```
27 passed, 0 failed
- 22 unit tests (including new index_gen tests)
- 5 integration tests (testcontainer)
```

### Quality gates

- `make format` — passed (ruff format)
- `make typecheck` — passed (mypy on orch/rag/index_gen.py)
- `make lint` — passed (ruff check on new files)
- `make test-unit` — passed (2026 tests total)

### Notes

- The `slug` field in `ProjectDoc` is NOT NULL in the schema — the `DocService.create_doc()` generates it from title via `_slugify()`. Integration test fixtures that create `ProjectDoc` rows directly must also set `slug`.
- The pre-commit hook warning on `dashboard/routers/code_qa.py` (ARG001 unused arg) is a pre-existing issue unrelated to this step.
- Integration test `test_updates_existing_code_index_doc` uses `existing_doc` with `slug` set to verify update path works (not just create path).