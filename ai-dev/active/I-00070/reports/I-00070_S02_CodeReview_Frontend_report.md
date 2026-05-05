# I-00070 S02 Code Review — Frontend Implementation

**Step**: S02 — Code Review
**Agent**: code-review-impl
**Work Item**: I-00070 — Copy paste prompt button silently fails over plain HTTP from a non-localhost hostname
**Review Target**: S01 (frontend-impl)
**Status**: COMPLETE

---

## Review Checklist

### 1. Helper correctness — secure-context branch
**CHECK** — `clipboard.js:49-50`: When `hasModern` is true (secure context + `navigator.clipboard.writeText` exists), `navigator.clipboard.writeText(text)` is called and its promise returned directly. No textarea is created.

```js
if (hasModern) {
  p = navigator.clipboard.writeText(text);  // line 50
}
```

### 2. Helper correctness — fallback branch
**CHECK** — `clipboard.js:52-61`: When `hasModern` is false, a new Promise is created that calls `copyViaTextarea(text)`. `copyViaTextarea` (lines 8–23) creates a fixed-position off-screen `<textarea>`, appends to `document.body`, selects it, calls `document.execCommand('copy')` in a `try`/`finally` block, and removes the textarea in `finally`. Promise resolves on `ok` (truthy), rejects on `false` or thrown exception.

```js
} else {
  p = new Promise(function (resolve, reject) {
    try {
      var ok = copyViaTextarea(text);   // line 54
      if (ok) resolve();                  // line 55
      else reject(new Error('...'));       // line 56
    } catch (err) {
      reject(err);                        // line 58
    }
  });
}
```

### 3. Failure surfaces (no swallow)
**CHECK** — `clipboard.js:66-69`: The rejection path calls `applyButtonFeedback(button, 'Copy failed')` and then `throw err` — the error is rethrown, never swallowed. All 7 callsites use `.catch(function(){})` which is the external promise chain consuming the rejection, not the helper swallowing it.

```js
function (err) {
  applyButtonFeedback(button, 'Copy failed');
  throw err;   // line 68 — rethrows, not swallowed
}
```

### 4. UI feedback
**CHECK** — `clipboard.js:25-39`: `applyButtonFeedback` stores original label in `button.dataset.iwClipboardOriginal` (line 30) on first call, sets label to `Copied`/`Copy failed` (line 32), and restores after 1500ms (lines 33–38). The setTimeout checks `button.textContent === label` before restoring, preventing race conditions between rapid clicks.

### 5. No global pollution
**CHECK** — `clipboard.js:7` and `74`: Entire file is wrapped in an IIFE `(function () { ... })();`. Only `window.iwClipboard = { copy: copy }` is exposed (line 73). No other globals created.

### 6. Every callsite migrated — grep result
**CHECK** — `grep -rn "navigator.clipboard.writeText" dashboard/` returns ONLY:
- `dashboard/static/clipboard.js:2` — comment
- `dashboard/static/clipboard.js:45` — `typeof navigator.clipboard.writeText === 'function'` (guard inside helper)
- `dashboard/static/clipboard.js:50` — `navigator.clipboard.writeText(text)` (secure-context branch inside helper)
- `dashboard/CLAUDE.md:114` — documentation reference

No template files or static JS files outside `clipboard.js` contain a direct call. All 7 original callsites confirmed migrated.

### 7. OSS page local helper removed
**CHECK** — `oss.html:518-530`: The local `copyToClipboard` function has been removed. The copy button handler now delegates to `window.iwClipboard.copy(copyBtn.dataset.ossCopy, copyBtn).catch(function(){})` (line 528). The checkmark `'✓'` display logic in the OSS page is preserved and runs independently (no longer coupled to clipboard success).

### 8. base.html load order
**CHECK** — `base.html:214`: `<script src="/static/clipboard.js"></script>` is placed at line 214, after `theme-toggle.js` and `duration.js`, but crucially **before** all inline `<script>` blocks that follow (lines 215–236, 237–259, 260). There is no `defer` attribute — it is synchronous. Any inline script at line 215+ that calls `iwClipboard.copy(...)` will find the global already defined.

```html
214: <script src="/static/clipboard.js"></script>
215: <script>
     // toggleSidebar(), etc.
```

### 9. Escape safety
**CHECK** — `oss_install_modal.html:37`: The `{{ info.install_cmd }}` Jinja2 expression is in an HTML onclick attribute. FastAPI's `Jinja2Templates` uses the default Jinja2 `autoescape` which escapes `<`, `>`, `&`, and `"` for HTML contexts. The `install_cmd` values are shell commands from `TIER1_INSTALL_COMMANDS` (tool_probe.py:12–35) — plain ASCII strings with no special characters. Single quotes in commands (e.g., `'s` in paths) would be escaped to `&#x27;` or equivalent. This is safe for the onclick context.

### 10. No leaked textareas — removeChild in finally
**CHECK** — `clipboard.js:17-22`: `copyViaTextarea` has `try { ... var ok = document.execCommand('copy'); return ok; } finally { document.body.removeChild(ta); }`. If `execCommand` throws, the `finally` block executes and removes the textarea. If `execCommand` returns `false`, the `finally` block also removes it. No leak path.

```js
try {
  var ok = document.execCommand('copy');
  return ok;
} finally {
  document.body.removeChild(ta);   // line 21 — guaranteed cleanup
}
```

### 11. Accessibility
**CHECK** — The button's `textContent` changes to "Copied" or "Copy failed" on focus-visible click. This is a visible text update on the focused element itself — sufficient for screen readers without `aria-live`. No `aria-live="polite"` needed because: (a) the button is the direct focus target, (b) the text change is not a status message but a label change, (c) existing precedent in chat copy buttons (actions.js:43–44, render.js:137–139) uses the same pattern without aria-live.

### 12. CLAUDE.md updated
**CHECK** — `dashboard/CLAUDE.md:110-119`: The new `## Clipboard buttons` subsection is present, documenting the anti-pattern and directing developers to `window.iwClipboard.copy`.

### 13. Pre-flight gates
**CHECK** — S01 report confirms:
- `make format`: ✅ `ruff format` applied; 612 files already formatted
- `make lint`: ✅ `All checks passed!`
- `make typecheck`: ✅ `Success: no issues found in 224 source files`
- `make test-unit`: ✅ 2579 passed (2 pre-existing failures unrelated to this change)

---

## Findings

No mandatory fixes. All 13 checklist items pass.

---

## Verdict

```
Verdict: PASS
```

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00070",
  "reviewed_agent": "frontend-impl",
  "verdict": "PASS",
  "mandatory_fix_count": 0,
  "findings": [],
  "notes": "All 13 checklist items pass. Helper correctly handles both secure-context (navigator.clipboard.writeText) and fallback (textarea+execCommand) branches. No errors swallowed. UI feedback wired. All 7 callsites migrated. No leaked DOM nodes. Load order correct. Escape safety confirmed. CLAUDE.md updated. Pre-flight gates all ok."
}
```