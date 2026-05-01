# I-00054 S11 QV Browser Report

## What was done

Performed browser-based end-to-end verification of the coverage page toggle label fix (I-00054). Used `playwright-cli` exclusively to drive a headless Chromium browser against an isolated E2E stack at `http://localhost:9940`.

Verified 5 aspects (V1–V5):
- **V1**: Initial expand of "dashboard" row → label changed to "click to collapse" ✅
- **V2**: Collapse click → label stayed "click to collapse" (failed) ❌
- **V3**: Re-expand → label stayed "click to collapse" (failed) ❌
- **V4**: Second row (executor) → same bug manifested ❌
- **V5**: Console errors → 10+ `RangeError: Maximum call stack size exceeded` ❌

## Files changed

None — this was a verification-only step. The bug was found in existing code.

**Root cause identified:** `dashboard/templates/pages/system/coverage.html` line ~119:

```javascript
} else {
  htmx.trigger(row, 'click');  // dispatches native click → re-enters handler → ∞ recursion
}
```

The `htmx.trigger(row, 'click')` call dispatches a native click event on the row element, which re-fires the same JS click handler, creating an infinite loop. The collapse branch never executes, so the label never reverts to "click to expand".

## Test results

All 5 verifications performed; 4 failed. Report written to:
`ai-dev/active/I-00054/reports/I-00054_S11_BrowserVerification_Report.md`

## Issues found

1. **CODE DEFECT** (coverage.html:119): `htmx.trigger(row, 'click')` causes stack overflow on collapse/re-expand cycles.
2. **Console errors**: 10+ `RangeError: Maximum call stack size exceeded` errors logged on every expand/collapse interaction.
3. **V2/V3**: Toggle label does not update on collapse or re-expand — only the initial expand works.
4. **V4**: All package rows have the same bug.

## Observations

- The htmx `hx-get` / `hx-target` / `hx-trigger` attributes on the `<tr>` element are correctly set in HTML.
- The `htmx:afterSwap` listener correctly toggles `data-expanded` and the label on successful expand.
- The bug is exclusively in the else-branch of the click handler that handles the "not yet expanded" path (lines 118–120).
- Fixing `htmx.trigger(row, 'click')` to use `htmx.ajax()` directly (or removing the JS handler entirely and relying solely on htmx's native attribute-based handling) will resolve all failures.