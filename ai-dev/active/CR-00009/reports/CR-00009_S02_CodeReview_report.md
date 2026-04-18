# CR-00009 S02 Code Review Report

## What was done

Reviewed S01 (backend-impl) changes to `orch/rag/qa.py`.

## Files changed

- `orch/rag/qa.py`

## Test results

- `make test-unit`: **795 passed, 0 failed**
- `uv run ruff check orch/rag/qa.py`: **All checks passed**
- `uv run mypy orch/rag/qa.py`: **Success: no issues found**

## Architecture Compliance

- ✅ Change stays inside `orch/rag/qa.py`; no leakage into routers, other RAG modules, or DB layer.
- ✅ No new public helpers; all new logic is either inside `_build_system_prompt` or inside `answer_stream`.
- ✅ LanceDB calls remain wrapped in the existing `try/except Exception` block.

## Contract Correctness

### AC5 (no-module behavior unchanged) — CRITICAL
- ✅ With `module_path=None`, `_build_system_prompt` produces a byte-identical string to the pre-change version.
- Verified by comparing against `HEAD~1:orch/rag/qa.py:136-197`:
  - Pre-change return: `"You are a codebase expert assistant. Answer questions about the codebase accurately and concisely.\n\n## Architecture Context\n\n..."`
  - Post-change return (with defaults): same prefix, module_block="", retrieval_note="", identical rest.
- The module block (`module_block`) is an empty string when `module_path` is falsy; retrieval_note is empty when `fallback_triggered=False`. The base template is identical.

### AC3 (module block content)
- ✅ When `module_path="orch/daemon/"` and `module_name="Orchestration Daemon"`, the prompt contains:
  - `"## Current Focus — Module"` (line 154)
  - `` `orch/daemon/` `` (line 156)
  - `"Orchestration Daemon"` (line 156)
  - Prioritization instruction: "Prioritize this module in your answer" (line 157-158)
- When `module_name` is None/empty, module block is still emitted with path only (lines 161-168).

### AC4 (fallback triggers on empty chunks only) — HIGH
- ✅ Fallback is fired ONLY when ALL three conditions are met:
  1. `context_level == "module"` (line 90)
  2. `module_path` is truthy (line 90)
  3. `not chunks` — filtered search returned zero rows (line 90)
- No other trigger path exists.

### AC5 (no fallback when filtered yields results)
- ✅ The fallback condition at line 90 is `and not chunks` — so if filtered search returns ≥1 row, the condition is `False` and fallback is skipped.

### AC4/AC5 (exception handling)
- ✅ If the outer `try` block fails (LanceDB unavailable), `fallback_triggered` stays `False` (initialized at line 69 before the `try`). The fallback does not run.

## Code Quality

- ✅ Duplication between filtered and unfiltered search is minimal and acceptable — both use the same `embedding_vector`, `TOP_K`, and `seed_filter`. Control flow is easy to follow.
- ✅ String concatenation uses f-strings consistently, matching the rest of the function.
- ⚠️ One comment at line 80 (`"# Filter out the indexer's seed row..."`) only restates the code (`seed_filter` variable name already conveys this). Flagged as LOW.

## Project Conventions

- ✅ Read `CLAUDE.md` + `orch/CLAUDE.md` — no violations.
- ✅ Type hints on all new parameters: `module_path: str | None`, `module_name: str | None`, `fallback_triggered: bool`.
- ✅ `mypy` passes with no issues.

## Security

- ✅ No hardcoded secrets.
- ✅ `seed_filter` and the existing `LIKE` quoting pattern are preserved. The `module_path` interpolation in the SQL-like `where` clause is unchanged from pre-change code (lines 79-83); no injection surface broadening.

## Testing

- ⚠️ S07 owns the full test suite. The existing `test_qa_engine.py` does NOT exercise the new branches (module_block, retrieval_note, fallback path). No inline tests were added by S01. This is expected — S07 will add coverage. No finding here.

## Verdict

```
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00009",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [
    {
      "type": "low",
      "file": "orch/rag/qa.py",
      "line": 80,
      "description": "Comment '# Filter out the indexer's seed row' only restates the code already expressed by the seed_filter variable name."
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "795 passed, 0 failed",
  "notes": "AC5 byte-identical output verified. Fallback trigger conditions are correct. Exception handling preserves fallback_triggered=False on LanceDB failure. S07 will add unit coverage for new branches."
}
```