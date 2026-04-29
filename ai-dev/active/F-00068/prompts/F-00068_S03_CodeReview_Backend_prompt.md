# F-00068_S03_CodeReview_Backend_prompt

**Work Item**: F-00068 — AI Chat Visual Improvements
**Step Being Reviewed**: S01 (Backend — system prompt update)
**Review Step**: S03

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

---

## Input Files

- `ai-dev/active/F-00068/F-00068_Feature_Design.md` — §Response Style Instructions
- `ai-dev/active/F-00068/reports/F-00068_S01_Backend_report.md`
- `orch/rag/qa.py`
- All test files listed in S01 report

## Output Files

- `ai-dev/active/F-00068/reports/F-00068_S03_CodeReview_Backend_report.md`

---

## Review Checklist

### 1. Additive change only
- Verify the existing Mermaid/D2/table/code lines in `RENDERING_CAPABILITIES_BLOCK` are untouched. Any removal is HIGH.

### 2. Callout syntax correctness
- Verify `[!NOTE]`, `[!TIP]`, `[!WARNING]`, `[!DANGER]` are all present in the block.
- Verify the description distinguishes when to use each type (WARNING vs DANGER distinction must be present).

### 3. Structure guidance
- Verify the block instructs to use H2 headings for multi-section answers.
- Verify it instructs to use bullet lists for ≥3 items.
- Verify it says NOT to start every answer with a heading.

### 4. Python string style
- Verify string concatenation style matches the existing `RENDERING_CAPABILITIES_BLOCK` pattern (no f-strings, no triple-quotes mixed in).

### 5. Test coverage
- Verify `test_rendering_capabilities_block_includes_callouts()` asserts on `[!NOTE]` and `[!WARNING]`.
- Verify `test_system_prompt_includes_capabilities()` calls `_build_system_prompt()` and checks the result.

## Test Verification

Run `make test-unit`. Report results.

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "CodeReview",
  "work_item": "F-00068",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
