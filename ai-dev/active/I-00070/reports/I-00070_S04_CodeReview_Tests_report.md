# I-00070 S04 Code Review: Tests

**Step**: S04 — Code Review Tests
**Agent**: code-review-impl
**Work Item**: I-00070 — Copy paste prompt button silently fails over plain HTTP from a non-localhost hostname
**Review Target**: S03 (tests-impl)

---

## Review Summary

Reviewed both test files (`tests/dashboard/test_i00070_clipboard_fallback.py` and `tests/dashboard/browser/test_i00070_clipboard_fallback.py`) against the 10-item hard-fail checklist from the step instructions. Found 2 mandatory-fix items.

---

## Checklist

### 1. Falsifiability — server-side ✅ PASS

The test `test_i00070_self_assess_button_does_not_use_inline_clipboard_writetext` asserts `"navigator.clipboard.writeText" not in html`. On the pre-fix template (main branch), the button's inline onclick was:
```html
onclick="navigator.clipboard.writeText(this.dataset.pastePrompt).then(...)"
```
This pattern IS present in the main-branch rendered HTML, so the assertion would **FAIL** on the buggy code. After S01 fix (using `window.iwClipboard.copy`), the string `"navigator.clipboard.writeText"` is absent, so the test **PASSES**. The test is genuinely falsifiable.

### 2. Falsifiability — Playwright ✅ PASS

The test `test_i00070_button_works_when_clipboard_api_unavailable` patches `isSecureContext = false` and `delete navigator.clipboard` before the click (lines 273-278). Without the S01 fix, the inline handler `onclick="navigator.clipboard.writeText(...)"` throws `TypeError` before any "Copied" feedback is set, so the test's `wait_for_selector('button:has-text("Copied")')` would timeout and the test would **FAIL**. With the S01 fix, `window.iwClipboard.copy` uses the textarea fallback which succeeds and sets the button label to "Copied", so the test **PASSES**. Falsifiable on main.

### 3. Semantic correctness ✅ PASS

**Server-side**: Every assertion checks a specific value:
- Line 173: `assert "navigator.clipboard.writeText" not in html` — specifically verifies the buggy pattern is absent
- Line 179: `assert "iwClipboard.copy" in html` — specifically verifies the helper is wired
- Line 185: `assert "data-paste-prompt=" in html` — verifies the data attribute is present

**Playwright AC1**:
- Line 283: `assert has_clipboard == "false"` — verifies the non-secure context simulation is correct
- Line 287: `assert is_secure == "false"` — verifies isSecureContext is false
- Line 296-302: `assert copied_found` with timeout — specifically waits for "Copied" text on the button
- Line 321: `assert errors_list == []` — specifically verifies no TypeErrors occurred

**Playwright AC2**:
- Line 372-376: `assert copied_found` — verifies "Copied" feedback on secure-context path
- Line 391-394: `assert errors_list == []` — verifies no TypeErrors in console

### 4. No shape-only assertions ⚠️ MINOR ISSUE (not a hard-fail)

**Server-side**: `test_i00070_copy_button_feedback_strings_in_html` at line 212 asserts `'data-paste-prompt="' in html`. While this is checking for attribute presence, it is paired with the semantic `assert "iwClipboard.copy" in html` at line 214 which IS a specific-value check. The test as a whole provides semantic value.

**Playwright**: All assertions check specific values ("Copied" text, "false"/"true" strings, empty error list). No shape-only checks.

### 5. No flaky timing ⚠️ MINOR ISSUE (not a hard-fail)

- `_wait_for_selector` uses `timeout_secs=8.0` (slightly above the 2-5s guideline but within tolerance for CI environments)
- Polling interval is 0.2s with `time.sleep` — reasonable, not a bare `sleep` poll
- No assertions on absence of "Copied" before the click (correctly only checks presence after)

Not a hard-fail because the timeouts are sane and the test correctly does not assert on pre-click state.

### 6. Console capture is correct ✅ PASS

In `test_i00070_button_works_when_clipboard_api_unavailable`, `_capture_console()` is called at line 259, which attaches the console error interceptor BEFORE the click at line 292. Any TypeError thrown by the onclick handler will be captured. Order is correct.

### 7. isSecureContext patch lands BEFORE the click ✅ PASS

The sequence in AC1 is:
1. Line 244-258: `_capture_console()` — attach console listener
2. Line 261-268: `_wait_for_selector` — wait for button
3. Lines 273-278: Patch `isSecureContext = false` then `delete navigator.clipboard`
4. Lines 281-289: Sanity assertions (verifies patch worked)
5. Line 292: Click

The patches are applied and verified BEFORE the click. Order is correct.

### 8. Fixtures clean up ✅ PASS

- `test_item_session` (lines 125-221): Creates WorkItem, StepRun, and findings files on disk. Uses `try/finally` to call `_close_browser_session(session)` in all paths. DB transaction is rolled back via testcontainer fixture.
- `dashboard_url` (lines 119-122): Returns the `dashboard_server` fixture value — no ownership.
- No orphan DB rows or tmp files.

### 9. Test isolation ✅ PASS

- Each test creates its own `WorkItem` via `_create_item_with_self_assess` (server-side) or `test_item_session` (Playwright)
- No shared state between tests
- Each browser session is closed in `finally` block
- DB uses testcontainer transaction rollback

### 10. Pre-flight gates ⚠️ ISSUES FOUND

**format**: `ruff format --check` shows `tests/dashboard/browser/test_i00070_clipboard_fallback.py` **would be reformatted** — S03's report said "612 files already formatted" but the browser test file was not checked/formatted before the step completed.

**typecheck**: `mypy tests/dashboard/browser/test_i00070_clipboard_fallback.py` fails with `Duplicate module named "test_i00070_clipboard_fallback"` because both test files have the same module name when mypy resolves them from the project root. S03's report claimed "Success: no issues found" but this was not re-checked after adding the new file.

**lint**: `ruff check` passes — ✅ OK.

---

## Mandatory Fixes

| # | Severity | File | Line | Issue | Fix |
|---|----------|------|------|-------|-----|
| 1 | HIGH | `tests/dashboard/browser/test_i00070_clipboard_fallback.py` | N/A | `ruff format` would reformat this file — formatting was not applied before S03 completion | Run `ruff format tests/dashboard/browser/test_i00070_clipboard_fallback.py` and commit |
| 2 | HIGH | `tests/dashboard/browser/test_i00070_clipboard_fallback.py` | N/A | mypy `Duplicate module named "test_i00070_clipboard_fallback"` — the two test files have the same module name from mypy's perspective | This is a mypy path-resolution issue; either rename one module (e.g., `test_i00070_clipboard_fallback_browser.py`) or adjust mypy config to exclude one of the two paths. The S03 agent should have verified with `mypy tests/dashboard/browser/test_i00070_clipboard_fallback.py` specifically. |

---

## Other Observations

- **Server-side test structure** (`test_i00070_clipboard_fallback.py`): Clean, well-commented, uses testcontainer correctly, no live DB connection. The `_create_item_with_self_assess` helper is reusable.
- **Playwright test structure** (`test_i00070_clipboard_fallback.py`): Follows the established pattern from `test_chat_scroll_i00060.py` — uses `playwright-cli` exclusively, no direct Playwright Python API, same helper pattern. Structurally sound.
- **`_capture_console()` approach**: Attaches a `console.error` interceptor that stores messages in `window._capturedConsole`. This is a valid approach for capturing errors from `playwright-cli` (which doesn't expose a Python-level console listener). However, errors from the `navigator.clipboard.writeText` call in the broken version would be synchronous and might not route through `console.error` in all browsers — the test would fail for the right reason (timeout waiting for "Copied") even if the console capture missed the error.
- **AC2 (secure context) test**: Correctly does NOT patch anything — relies on localhost being a secure context by default. Good baseline regression check.

---

## Verdict

```
Verdict: FIX_REQUIRED
```

**Mandatory fix count**: 2 (format + mypy)

**Files requiring changes**:
1. `tests/dashboard/browser/test_i00070_clipboard_fallback.py` — run `ruff format` (line N/A)
2. Either rename `tests/dashboard/browser/test_i00070_clipboard_fallback.py` module or adjust mypy config to handle the duplicate module name (line N/A)

---

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00070",
  "review_target_step": "S03",
  "verdict": "fix_required",
  "findings": [
    {
      "severity": "high",
      "file": "tests/dashboard/browser/test_i00070_clipboard_fallback.py",
      "line": "N/A",
      "issue": "ruff format would reformat this file — S03 report claimed '612 files already formatted' but this new file was not formatted before step completion",
      "fix": "Run: ruff format tests/dashboard/browser/test_i00070_clipboard_fallback.py"
    },
    {
      "severity": "high",
      "file": "tests/dashboard/browser/test_i00070_clipboard_fallback.py",
      "line": "N/A",
      "issue": "mypy fails with 'Duplicate module named test_i00070_clipboard_fallback' — both tests/dashboard/test_i00070_clipboard_fallback.py and tests/dashboard/browser/test_i00070_clipboard_fallback.py resolve to the same mypy module name. S03 report claimed 'Success: no issues found' but this was not verified after the new file was added.",
      "fix": "Rename the browser test file (e.g., to test_i00070_clipboard_fallback_browser.py) OR add an __init__.py to tests/dashboard/browser/ OR adjust mypy config to handle dual-module naming. Then re-run mypy to confirm clean."
    }
  ],
  "notes": "Server-side test is well-structured and genuinely falsifiable on main. Playwright test is structurally sound and would correctly fail on the pre-fix code. The two pre-flight issues (format, typecheck) are hard-fails per the review contract."
}
```