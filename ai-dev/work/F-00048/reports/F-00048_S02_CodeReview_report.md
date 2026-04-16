# F-00048 S02 Code Review Report

## Summary

Reviewed S01 (backend-impl) implementation for F-00048: Code Understanding: Module + Symbol Views. The implementation is mostly correct but has several issues requiring fixes before merge.

## Files Changed (S01)

| File | Purpose |
|------|---------|
| `orch/rag/parser.py` | `parse_modules_from_level1()` - parses Level 1 markdown |
| `orch/rag/module_gen.py` | `ModuleGenerator` - Level 2 doc generation |
| `orch/rag/symbol_gen.py` | `SymbolGenerator` - Level 3 symbol explanation |
| `tests/unit/test_module_parser.py` | Parser unit tests |
| `tests/unit/test_module_gen.py` | ModuleGenerator unit tests |
| `tests/integration/test_module_gen_integration.py` | Generator integration tests |

## Test Results

**Unit tests**: 13 passed (all F-00048 tests)
**Integration tests**: 2 passed (all F-00048 tests)
**ruff check**: 7 errors (unused imports, unsorted imports)
**mypy**: No issues

## Findings

### CRITICAL

None identified.

### HIGH

1. **Path traversal vulnerability in SymbolGenerator**
   - **File**: `orch/rag/symbol_gen.py:55`
   - **Description**: `file_path` is joined with `repo_root` via `Path(repo_root) / file_path` but never validated to ensure the resolved path stays within `repo_root`. A malicious `file_path` containing `..` sequences could read files outside the project.
   - **Design says**: "User-supplied `file_path` in SymbolGenerator must be validated/sanitized to prevent path traversal"
   - **Suggestion**: Add validation after constructing `absolute_path`:
     ```python
     absolute_path = Path(repo_root) / file_path
     absolute_path = absolute_path.resolve()
     repo_root_resolved = Path(repo_root).resolve()
     if not str(absolute_path).startswith(str(repo_root_resolved)):
         raise ValueError("Invalid file path: path traversal detected")
     ```

2. **DB access not via DocService**
   - **File**: `orch/rag/module_gen.py:52-54`
   - **Description**: `_get_by_slug()` uses raw `session.execute(select(ProjectDoc).where(...))` instead of going through DocService. The design requires "all DB access goes through DocService."
   - **Note**: S01 report acknowledges this: "DocService.get_by_slug was not available, so implemented _get_by_slug() directly"
   - **Suggestion**: Either add `get_by_slug()` to DocService and use it, or confirm that a private query method is acceptable for this case.

### MEDIUM (fixable)

3. **SQL LIKE injection in module filter**
   - **File**: `orch/rag/module_gen.py:83`
   - **Description**: `file_path LIKE '{module_path}%'` does not escape special LIKE characters (`%`, `_`) in `module_path`. A module path containing `%` or `_` would match unintended files.
   - **Suggestion**: Escape special characters before using in LIKE clause:
     ```python
     escaped_path = module_path.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
     table.search(embedding).where(f"file_path LIKE '{escaped_path}%'")
     ```

4. **Unused imports in integration tests**
   - **File**: `tests/integration/test_module_gen_integration.py:78`
   - **Description**: `DocTier`, `DocType`, `EditorialCategory`, `ProjectDoc` imported but unused.
   - **Suggestion**: Remove unused imports.

5. **Unused import in unit test**
   - **File**: `tests/unit/test_module_parser.py:8`
   - **Description**: `pytest` imported but unused. Also unsorted import block.
   - **Suggestion**: Remove `pytest` (tests don't need it explicitly) and sort imports.

### MEDIUM (suggestion)

6. **LanceDB access pattern inconsistency**
   - **File**: `orch/rag/module_gen.py:68`
   - **Description**: `module_gen.py` uses raw `lancedb.connect()` while `indexer.py` and `mapgen.py` use `LanceDBVectorStore` from llama_index. The design asks for consistency with established patterns.
   - **Note**: This may be intentional as `ModuleGenerator` needs lower-level vector search with WHERE filters that `LanceDBVectorStore` may not expose directly.
   - **Suggestion**: Consider if the higher-level API could be used, or document why the lower-level API is necessary.

## Architecture Compliance

| Check | Status |
|-------|--------|
| `parse_modules_from_level1()` is pure (no I/O, no DB) | ✅ Pass |
| `ModuleGenerator.get_or_generate()` checks existing before generating | ✅ Pass |
| `SymbolGenerator.explain_symbol()` never creates ProjectDoc | ✅ Pass |
| `ModuleGenerator` uses DocService for all DB access | ❌ Fail (uses raw ORM) |
| Layer boundaries respected (`orch/rag/` no imports from `dashboard/`) | ✅ Pass |
| LanceDB access pattern consistent with CodeIndexer/MapGenerator | ⚠️ Partial |

## Correctness Checklist

| Check | Status |
|-------|--------|
| Parser handles backtick format | ✅ |
| Parser handles bold name + path format | ✅ |
| Parser handles plain format | ✅ |
| Returns empty list when no components section | ✅ |
| Slug derivation correct (`path.strip('/').replace('/', '-').lower()`) | ✅ |
| `ModuleGenerator` slug construction correct | ✅ |
| `ProjectDoc` created with correct fields | ✅ |
| `ModuleGenerator` uses `DocService.create_doc()` | ✅ |
| `SymbolGenerator` resolves absolute file path correctly | ✅ |
| tree-sitter fallback to full file on parse failure | ✅ |
| `symbol_name=None` explains whole file | ✅ |
| `symbol_gen.py` never creates ProjectDoc | ✅ |

## Verdict

**fail** — 2 HIGH findings require fixes before merge.

- `SymbolGenerator` must validate `file_path` against path traversal
- `ModuleGenerator` should use DocService for DB access (or have justification for not doing so)

## Mandatory Fix Count

2

## Notes

- The design uses `AsyncSession` in signatures but the codebase uses synchronous SQLAlchemy. This is an inconsistency in the design doc, not the implementation.
- The `_get_by_slug` issue is acknowledged in the S01 report as a workaround for missing DocService method.
- All tests pass, mypy is clean. Quality issues are limited to unused imports.
