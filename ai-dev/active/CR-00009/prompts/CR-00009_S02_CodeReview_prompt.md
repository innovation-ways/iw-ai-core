# CR-00009_S02_CodeReview_prompt

**Work Item**: CR-00009 — Chat panel context awareness
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## Input Files

- `ai-dev/active/CR-00009/CR-00009_CR_Design.md` — design document
- `ai-dev/active/CR-00009/reports/CR-00009_S01_Backend_report.md` — S01 step report
- All files listed in the S01 report's `files_changed` (expected: `orch/rag/qa.py`)

## Output Files

- `ai-dev/active/CR-00009/reports/CR-00009_S02_CodeReview_report.md`

## Context

Review S01 (backend-impl) changes to `orch/rag/qa.py`. The scope is: (a) `_build_system_prompt` gains optional `module_path`, `module_name`, `fallback_triggered` kwargs and emits `## Current Focus — Module` and `## Retrieval Note` blocks conditionally; (b) `answer_stream` gains a `module_name` parameter and a one-shot unfiltered fallback search when the module-filtered search returns zero chunks.

Read the design doc (especially AC3, AC4, AC5) to understand the contract. Then review the diff.

## Review Checklist

### 1. Architecture Compliance

- Does the change stay inside `orch/rag/qa.py`? No leakage into routers, other RAG modules, or DB layer?
- Are the new helpers (if any) private (`_`-prefixed) and scoped to the class?
- Are LanceDB calls still wrapped in the existing try/except?

### 2. Contract Correctness

- **AC5 (no-module behavior unchanged)**: with `module_path=None`, does `_build_system_prompt` produce the same string as before the change? Compare against the pre-change code (see `orch/rag/qa.py:124-158` at HEAD~1). Any textual drift is a HIGH finding.
- **AC3 (module block content)**: when `module_path="orch/daemon/"` and `module_name="Orchestration Daemon"`, does the prompt contain both strings, framed so the LLM will prioritize the module?
- **AC3 (module_name optional)**: when `module_name` is `None` or empty, is the module block still emitted (with path only)?
- **AC4 (fallback triggers on empty chunks only)**: is the fallback *only* fired when (i) `context_level == "module"`, (ii) `module_path` is truthy, AND (iii) the filtered search returned zero rows? Any other trigger path is a bug.
- **AC5 (no fallback when filtered yields results)**: is the fallback suppressed when the filtered search returns ≥1 row?
- **Fallback exception handling**: if the outer `try` fails (LanceDB unavailable), the fallback must not run and `fallback_triggered` must stay `False`.

### 3. Code Quality

- Duplication between filtered and unfiltered search? Accept small duplication; reject anything that makes the control flow harder to follow.
- Is the module block built with clean string concatenation or f-strings consistent with the rest of the function?
- Any comments that only restate the code? Flag as LOW.

### 4. Project Conventions

- Read `CLAUDE.md` + `orch/CLAUDE.md`.
- Type hints on all new parameters and locals? (`Mapped[]` does not apply here — this is not ORM code; standard PEP 484 style.)
- Does `mypy` pass? Run it.

### 5. Security

- No hardcoded secrets.
- Module path is already used in a LanceDB `LIKE` filter. Confirm the change does not broaden the injection surface. The `seed_filter` and existing quoting pattern must be preserved.

### 6. Testing

- S07 owns the full test suite, but if S01 added inline tests, verify they actually exercise the new branches and aren't copy-pasted no-ops.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `uv run ruff check orch/rag/qa.py`
3. `uv run mypy orch/rag/qa.py`

## Severity Levels

Use the standard severities. Any deviation from **AC5 byte-identical no-module output** is CRITICAL. Any fallback firing outside the specified conditions is HIGH.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00009",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
