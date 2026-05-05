# I-00070_S04_CodeReview_Tests_prompt

**Work Item**: I-00070 -- Copy paste prompt button silently fails over plain HTTP from a non-localhost hostname
**Step**: S04
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Standard policy. No container operations are required for this step. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does NOT touch Alembic migrations.

## Input Files

- `ai-dev/active/I-00070/I-00070_Issue_Design.md` — Design document
- `ai-dev/active/I-00070/reports/I-00070_S03_Tests_report.md` — S03 report
- `tests/dashboard/test_i00070_clipboard_fallback.py` — server-side tests under review
- `tests/dashboard/browser/test_i00070_clipboard_fallback.py` — Playwright tests under review
- `dashboard/static/clipboard.js` — the helper the tests target
- `dashboard/templates/fragments/item_execution_report.html` — sample target template

## Output Files

- `ai-dev/active/I-00070/reports/I-00070_S04_CodeReview_Tests_report.md` — review findings + verdict

## Review Checklist (every item is a hard-fail if not met)

1. **Falsifiability — server-side**: temporarily revert `dashboard/templates/fragments/item_execution_report.html` to the pre-fix `navigator.clipboard.writeText(...)` form (mentally, or by checking out main for that file in a scratch worktree) and confirm `test_self_assess_button_does_not_use_inline_navigator_clipboard` would FAIL on that revision. The test is useless if it can't fail on the bug.
2. **Falsifiability — Playwright**: mentally trace what happens if the helper is replaced with the original buggy `onclick`. The test MUST fail (no "Copied" label, console TypeError captured).
3. **Semantic correctness**: every assertion checks a SPECIFIC value, not just shape. List every `assert` line and confirm it would fail on the buggy code.
4. **No shape-only assertions**: no `assert <button> in html` style. No `assert len(...) > 0`. Each must check a specific known value.
5. **No flaky timing**: Playwright `wait_for_selector(..., timeout=...)` is used with sane timeouts (2-5s). No bare `sleep(...)` polls. The test does NOT assert on the absence of "Copied" before the click happens.
6. **Console capture is correct**: the Playwright test attaches the `console` listener BEFORE the click that might trigger the error.
7. **isSecureContext patch lands BEFORE the click**: confirm the order `evaluate(... isSecureContext = false ...) → evaluate(... delete navigator.clipboard ...) → click`. If the click happens first, the test will pass on broken code.
8. **Fixtures clean up**: any DB rows / tmp files created by the tests are torn down via fixtures (no orphan state).
9. **Test isolation**: tests do NOT depend on global state from earlier tests; each creates its own work item.
10. **Pre-flight gates passed**: S03's report shows `format`, `typecheck`, `lint` all `ok`/`fixed` and `tests_passed: true`.

## Findings & Verdict

Produce a markdown report listing each checklist item with CHECK / ISSUE / N/A and a 1-line justification. End with:

```
Verdict: PASS | FIX_REQUIRED
```

If `FIX_REQUIRED`, list the specific changes the test author must make (file:line).

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00070",
  "review_target_step": "S03",
  "verdict": "pass|fix_required",
  "findings": [
    {"severity": "high|med|low", "file": "path:line", "issue": "...", "fix": "..."}
  ],
  "notes": ""
}
```
