# I-00070 S01 Frontend Report

**Step**: S01 — Frontend Implementation
**Agent**: frontend-impl
**Work Item**: I-00070 — Copy paste prompt button silently fails over plain HTTP from a non-localhost hostname
**Status**: ✅ Complete

## What Was Done

Implemented the shared clipboard helper and migrated all 7 affected callsites:

### 1. Created `dashboard/static/clipboard.js`

A new vanilla JS helper that:
- Tries `navigator.clipboard.writeText` when `window.isSecureContext === true` and `navigator.clipboard` exists
- Falls back to a fixed-position `<textarea>` + `document.execCommand('copy')` otherwise
- Sets button label to "Copied" on success, "Copy failed" on failure, then restores original label after 1.5s
- Exposes `window.iwClipboard.copy(text, button)` — rejects (not swallows) on failure for testability

### 2. Loaded helper from `dashboard/templates/base.html`

Added `<script src="/static/clipboard.js"></script>` synchronously before inline scripts at line ~214.

### 3. Migrated all 7 callsites

| File | Line | Change |
|------|------|--------|
| `item_execution_report.html` | ~396 | 6 identical buttons: inline `onclick` → `window.iwClipboard.copy(this.dataset.pastePrompt, this).catch(function(){})` |
| `oss_cli_block.html` | ~15 | `navigator.clipboard.writeText(...)` → `window.iwClipboard.copy(..., this).catch(function(){})` |
| `oss_install_modal.html` | ~37 | Same pattern |
| `oss.html` | ~518–534 | Removed local `copyToClipboard` function; rewired copy button click to `window.iwClipboard.copy(copyBtn.dataset.ossCopy, copyBtn).catch(function(){})` |
| `chat/actions.js` | ~40 | `navigator.clipboard.writeText(source)` → `window.iwClipboard.copy(source, null)` (existing UI feedback preserved) |
| `chat/render.js` | ~135 | CSV copy: `navigator.clipboard.writeText(csv)` → `window.iwClipboard.copy(csv, null)` |
| `chat/render.js` | ~176 | Payload copy: same pattern |

### 4. Updated `dashboard/CLAUDE.md`

Added `## Clipboard buttons` subsection documenting the anti-pattern and helper usage.

## Test: RED → GREEN

**RED phase**: `tests/dashboard/test_i00070_clipboard_fallback.py` was written first. The test `test_i00070_self_assess_button_does_not_use_inline_clipboard_writetext` initially FAILED on the unmodified template because:
- `"navigator.clipboard.writeText" in html` was `True` (the bug was present)
- `"iwClipboard.copy" in html` was `False` (helper not wired)

**GREEN phase**: After applying all changes, both tests in the file pass:
- `test_i00070_self_assess_button_does_not_use_inline_clipboard_writetext` ✅
- `test_i00070_copy_button_feedback_strings_in_html` ✅

## Pre-flight Checks

| Check | Result |
|-------|--------|
| `grep -rn "navigator.clipboard.writeText" dashboard/` | ✅ Only matches in `clipboard.js` (the helper itself) + CLAUDE.md docs |
| `make format` | ✅ `ruff format` applied to `test_i00070_clipboard_fallback.py`; 0 other changes |
| `make lint` | ✅ `ruff check .` — All checks passed! |
| `make typecheck` | ✅ `mypy orch/ dashboard/` — Success: no issues found |
| `make test-unit` | ✅ 2579 passed, 2 pre-existing failures (`test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context`, `test_safe_migrate.py::TestRollback::test_rollback_refuses_in_agent_context` — verified pre-existing via git stash, unrelated to this change) |

## Files Changed

```
dashboard/static/clipboard.js          [NEW]
dashboard/templates/base.html          [modified - added script tag]
dashboard/templates/fragments/item_execution_report.html  [modified - 6 onclick attrs]
dashboard/templates/fragments/oss_cli_block.html          [modified - onclick]
dashboard/templates/fragments/oss_install_modal.html      [modified - onclick]
dashboard/templates/pages/project/oss.html               [modified - removed copyToClipboard, rewired handler]
dashboard/static/chat/actions.js       [modified - clipboard call]
dashboard/static/chat/render.js        [modified - 2 clipboard calls]
dashboard/CLAUDE.md                    [modified - added Clipboard buttons section]
tests/dashboard/test_i00070_clipboard_fallback.py  [NEW]
```

## Notes

- The OSS page's previous local `copyToClipboard` swallowed errors with `catch(_) { /* best-effort */ }` — the new helper surfaces "Copy failed" instead, which is intentional (AC3).
- The chat render.js `attachCopyButton` uses `?.textContent` (optional chaining) — preserved since it was already in the original code.
- `make test-unit` coverage requirement (46%) was met: 52.71% total.