# I-00046_S04_CodeReview_Tests_prompt

**Work Item**: I-00046 — Code view chat panel — toggle button clipped and viewport drift on module select
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state**: `uv run iw item-status I-00046 --json`
- `ai-dev/active/I-00046/I-00046_Issue_Design.md` — design document
- `ai-dev/active/I-00046/reports/I-00046_S03_Tests_report.md` — S03 test report
- `tests/dashboard/test_chat_panel_layout_i00046.py` — new test file to review
- `tests/dashboard/test_code_layout_fixes.py` — reference: existing I-00033 tests

## Output Files

- `ai-dev/active/I-00046/reports/I-00046_S04_CodeReview_Tests_report.md`

## Context

Review the reproduction and regression tests written in S03 for I-00046. The tests must
structurally verify the two layout fixes: toggle button not clipped (bug a) and content
root containment (bug c).

## Review Checklist

### 1. Reproduction coverage

- [ ] There is a test that verifies `id="chat-panel-slot"` appears exactly ONCE in the
  rendered page (no duplicate IDs)
- [ ] There is a test that verifies `overflow-hidden` is absent from the `<aside>` tag
- [ ] There is a test that verifies `min-h-0` is present on the `<aside>` tag
- [ ] There is a test that verifies `min-h-0` is present on `#code-content-root`
- [ ] There is a regression guard verifying `#chat-toggle-tab` is still present and retains
  `left: -48px`

### 2. Semantic correctness (CRITICAL — I003 lesson)

Every assertion must target the **specific element**, not the whole page:
- [ ] GOOD: `aside_match.group(0)` — searches `<aside>` opening tag only
- [ ] GOOD: `root_match.group(0)` — searches `#code-content-root` opening tag only
- [ ] GOOD: `html.count('id="chat-panel-slot"') == 1` — counts exact occurrences
- [ ] BAD (flag as HIGH): `assert "overflow-hidden" not in html` — whole-page check
  that could pass even if the aside still has the class (another element might use it)

### 3. TDD RED phase documented

- [ ] The report documents what the failure would have looked like against pre-fix code,
  OR shows output of running tests on a pre-fix branch

### 4. Test isolation

- [ ] Tests do not rely on a live database or server
- [ ] Jinja environment fixture is properly scoped (module or function scope is fine)
- [ ] No side effects between tests

### 5. Existing tests not broken

- [ ] `tests/dashboard/test_code_layout_fixes.py` tests still pass (I-00033 not regressed)
- [ ] All other `tests/dashboard/` tests pass

### 6. Code quality

- [ ] Test names describe what they verify (`test_<element>_<condition>`)
- [ ] Assertions include descriptive failure messages referencing the bug (I-00046)
- [ ] No unnecessary setup or teardown
- [ ] `make format` and `make typecheck` passed on the test file

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| CRITICAL | Test is wrong — would not catch the bug | Must fix |
| HIGH | Semantic check missing — whole-page assertion instead of specific element | Must fix |
| MEDIUM (fixable) | Missing coverage, style issue | Fix in cycle |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00046",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
