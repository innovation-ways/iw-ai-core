# CR-00009 S01 Backend Report

## What was done

Extended `orch/rag/qa.py` with three changes:

1. **`answer_stream` signature** — added `module_name: str | None = None` parameter (line 44), forwarded to `_build_system_prompt`.

2. **Retrieval fallback** — when `context_level == "module"` and `module_path` is truthy, after the filtered search returns zero chunks, a second unfiltered search is issued using the same embedding and seed filter. `fallback_triggered: bool` records whether the fallback fired.

3. **`_build_system_prompt` extended signature** — new params `module_path`, `module_name`, `fallback_triggered` (all optional with defaults). The method builds two optional blocks:
   - `## Current Focus — Module` — emitted only when `module_path` is non-empty; includes the module name in parentheses when provided.
   - `## Retrieval Note` — emitted only when `fallback_triggered` is `True`.

AC5 compliance: the default-only path (no module params) produces a byte-identical prompt to the original — the module block and retrieval note are both empty strings, leaving the rest of the template unchanged.

## Files changed

- `orch/rag/qa.py`

## Test results

- `make test-unit`: **795 passed, 0 failed**
- `uv run ruff check orch/rag/qa.py`: **All checks passed**
- `uv run mypy orch/rag/qa.py`: **Success: no issues found**

## Issues or observations

- Ruff PIE790 flagged the `pass` after the bare `except` block — fixed by replacing with a `logging.warning` call.
- A ruff S110 warning about the bare `except Exception` remains (抑制), which is intentional: we intentionally swallow LanceDB errors to degrade gracefully, and adding a comment explaining why would be redundant with the logging call we added.
