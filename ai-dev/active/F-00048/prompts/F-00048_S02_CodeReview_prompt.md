# F-00048_S02_CodeReview_prompt

**Work Item**: F-00048 -- Code Understanding: Module + Symbol Views
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## Input Files

- `ai-dev/active/F-00048/F-00048_Feature_Design.md` -- Design document
- `ai-dev/work/F-00048/reports/F-00048_S01_Backend_report.md` -- S01 implementation report
- All files listed in S01 report's `files_changed`:
  - `orch/rag/parser.py`
  - `orch/rag/module_gen.py`
  - `orch/rag/symbol_gen.py`
  - `tests/unit/test_module_parser.py`
  - `tests/unit/test_module_gen.py`
  - `tests/integration/test_module_gen_integration.py`

## Output Files

- `ai-dev/work/F-00048/reports/F-00048_S02_CodeReview_report.md` -- Review report

## Context

You are reviewing the backend implementation done in S01 for **F-00048: Code Understanding: Module + Symbol Views**.

Read the design document to understand what was intended. Read the S01 report to understand what was done. Then review all changed files in detail.

## Review Checklist

### 1. Architecture Compliance

- Does `parse_modules_from_level1()` stay pure (no I/O, no DB access, no side effects)?
- Does `ModuleGenerator.get_or_generate()` correctly check for existing `ProjectDoc` before generating?
- Does `SymbolGenerator.explain_symbol()` never create or store a `ProjectDoc`?
- Does `ModuleGenerator` use `DocService` for all DB access (no raw ORM queries)?
- Are layer boundaries respected: `orch/rag/` does not import from `dashboard/`?
- Does LanceDB access match the pattern established by `CodeIndexer`/`MapGenerator`?

### 2. Correctness of parse_modules_from_level1()

- Does the parser handle the documented format variations (backtick paths, plain paths, bold name + path)?
- Does it return an empty list (not raise) when the doc has no components section?
- Is the slug derived correctly: `path.strip('/').replace('/', '-').lower()`?
- Does it handle edge cases: empty string input, malformed markdown, binary/non-UTF8 characters?
- Are all fields present: `name`, `path`, `description`, `slug`?

### 3. Correctness of ModuleGenerator

- Is the slug construction `f"{project_id}-module-{module_path.strip('/').replace('/', '-')}"` correct?
- Is the `ProjectDoc` created with the right field values (doc_type, tier, editorial_category)?
- Does LanceDB filtering use `file_path.startswith(module_path)` correctly?
- Does it format `MODULE_QUESTIONS` with `{module}` substituted with `module_name`?
- Is the Ollama HTTP call using `httpx.AsyncClient` with correct endpoint and model field?
- Is error handling in place for Ollama timeouts / connection errors?
- Is `get_or_generate()` truly idempotent — does a second call never create a duplicate?

### 4. Correctness of SymbolGenerator

- Does it correctly resolve the absolute file path using the project's repo path?
- Does tree-sitter extraction fall back to full file content on parse failure?
- Does it correctly handle `symbol_name=None` (explain whole file)?
- Does it call `DocService` or create any `ProjectDoc`? It must NOT.
- Are supported extensions correctly mapped to tree-sitter language parsers?
- Is the Ollama prompt well-formed and bounded in size (large files could overflow context)?

### 5. Code Quality

- Are there any obvious bugs, logic errors, or missed edge cases?
- Is error handling appropriate (no bare `except:`, no silent swallowing of critical errors)?
- Is async/await used correctly throughout (no blocking I/O in async functions)?
- Are type hints complete and correct (`str | None`, `tuple[ProjectDoc, bool]`, etc.)?
- Is there unnecessary duplication between `module_gen.py` and `symbol_gen.py` (Ollama call pattern)?

### 6. Project Conventions

- Read `CLAUDE.md` — are all naming conventions followed?
- Are imports organized (stdlib, third-party, internal)?
- Does the code pass `ruff check` and `mypy orch/rag/`?

### 7. Security

- No hardcoded Ollama URLs or model names (must use `config.ollama_url`, `config.resolved_llm_model()`)
- No hardcoded file paths or project paths
- User-supplied `file_path` in SymbolGenerator must be validated/sanitized to prevent path traversal

### 8. Testing

- Does `test_module_parser.py` cover all the formats documented in the design?
- Are the cache hit/miss paths in `test_module_gen.py` tested independently?
- Do integration tests mock Ollama and LanceDB external calls (not the DB itself)?
- Are test names descriptive of what they verify?
- Is the TDD red-green cycle demonstrated (tests were written before implementation)?

## Test Verification (NON-NEGOTIABLE)

Before submitting your review:

1. Run `uv run pytest tests/unit/ -v` -- verify all unit tests pass
2. Run `uv run pytest tests/integration/ -v` -- verify integration tests pass
3. Run `uv run ruff check orch/rag/ tests/unit/test_module*.py tests/integration/test_module*.py`
4. Run `uv run mypy orch/rag/`
5. Report test results accurately in the result contract

## Severity Levels

| Severity | Meaning | Action Required |
|----------|---------|-----------------|
| **CRITICAL** | Breaks functionality, data loss risk, security vulnerability | Must fix before merge |
| **HIGH** | Significant bug, missing requirement, architectural violation | Must fix before merge |
| **MEDIUM (fixable)** | Code quality issue, missing edge case, convention violation | Should fix in fix cycle |
| **MEDIUM (suggestion)** | Design improvement, better pattern available | Optional, author decides |
| **LOW** | Nitpick, style preference, minor readability | Informational only |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "F-00048",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: Use `pass` if there are zero CRITICAL or HIGH findings AND zero MEDIUM (fixable) findings. Use `fail` if any mandatory fixes are needed.
- `mandatory_fix_count`: Count of CRITICAL + HIGH + MEDIUM (fixable) findings.
