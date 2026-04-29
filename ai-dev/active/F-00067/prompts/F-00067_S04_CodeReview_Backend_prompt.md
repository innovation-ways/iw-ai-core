# F-00067_S04_CodeReview_Backend_prompt

**Work Item**: F-00067 — Documentation Visual Design Overhaul
**Step Being Reviewed**: S01 (Backend — diagram prompts)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

---

## Input Files

- `ai-dev/active/F-00067/F-00067_Feature_Design.md` — Design doc (§Semantic Color Palette, §Requirements for S01)
- `ai-dev/active/F-00067/reports/F-00067_S01_Backend_report.md` — S01 implementation report
- `orch/rag/mapgen.py` — Modified by S01
- `orch/rag/module_gen.py` — Modified by S01
- All test files listed in S01 report

## Output Files

- `ai-dev/active/F-00067/reports/F-00067_S04_CodeReview_Backend_report.md`

---

## Context

Review the diagram prompt enhancements implemented in S01. Focus on correctness of the LLM prompt construction, the purpose extraction regex, the stored content format, and test coverage.

## Review Checklist

### 1. Canonical palette correctness
- Verify the `classDef` hex values in `mapgen.py` and `module_gen.py` **exactly match** the canonical palette from the design doc. Any mismatch is CRITICAL.
- Verify both files use the same `_MERMAID_CLASSDEF` constant (or identical strings). Duplication without a shared constant is HIGH.

### 2. Purpose extraction
- Verify `re.search(r"```purpose\s*(.*?)\s*```", text, re.DOTALL)` is used correctly.
- Verify the fallback purpose strings are reasonable.
- Verify the stored format is `<!-- purpose: {text} -->\n{dsl}`.

### 3. Return type change in `_build_mermaid()`
- Verify callers of `_build_mermaid()` correctly unpack the new tuple return.
- Verify mypy/type annotations are updated if `_build_mermaid()` previously returned `str`.

### 4. Elk frontmatter ordering
- Verify the `<!-- purpose: -->` comment is placed BEFORE the elk frontmatter (not inside it).

### 5. Module diagram direction
- Verify `module_gen.py` uses `graph LR` direction in the prompt (not `graph TD`).

### 6. Test coverage
- Verify unit tests mock the LLM and assert on the `classDef` and `<!-- purpose:` presence.
- Verify both `mapgen.py` and `module_gen.py` are covered.

### 7. Existing behavior preserved
- Verify the fallback `graph TD\n  A[System]` still applies when the LLM returns nothing parseable.
- Verify the `asyncio.to_thread()` pattern is preserved for all LLM calls.

## Test Verification

Run `make test-unit` and report results.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "F-00067",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
