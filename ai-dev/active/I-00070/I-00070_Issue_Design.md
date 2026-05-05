# I-00070: "Copy paste prompt" button silently fails over plain HTTP from a non-localhost hostname

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-05
**Reported By**: sergio (operator)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy applies — see `docs/IW_AI_Core_Agent_Constraints.md`. This incident does not require any container operations.

## ⛔ Migrations: agents generate, daemon applies

Standard policy applies. This incident does NOT add or modify any Alembic migrations — it is a pure dashboard frontend change (one new static JS file + a template/script edit per affected page).

---

## Description

The "Copy paste prompt" button on each Self-Assessment finding card in the work-item Execution Report tab silently does nothing when the dashboard is opened over plain HTTP from a non-localhost hostname (e.g. `http://iw-dev-01:9900` from another machine on the LAN). The button's inline `onclick` calls `navigator.clipboard.writeText(...)` — but `navigator.clipboard` is `undefined` in non-secure contexts, the call throws a `TypeError`, and the inline handler swallows it without any UI feedback. Six other dashboard buttons that use the same direct `navigator.clipboard.writeText(...)` pattern are affected by the identical bug.

## Project Context

Read the project's `CLAUDE.md` for architecture and hard rules. Dashboard sub-package conventions are in `dashboard/CLAUDE.md` (Jinja2 + htmx + prebuilt Tailwind via `make css`; vanilla JS only — no module bundler; static assets go under `dashboard/static/`).

There is already a half-correct precedent inside `dashboard/templates/pages/project/oss.html:518-534`: an inline `copyToClipboard(text)` helper that probes `window.isSecureContext` and falls back to a temporary `<textarea>` + `document.execCommand('copy')`. That helper is **page-local** (lives inside the OSS page's `<script>` block) and the other six callsites do not benefit from it. The fix promotes this pattern into a tiny shared `dashboard/static/clipboard.js` and makes every clipboard button use it, with explicit success / failure UI feedback (the existing OSS helper swallows errors with `catch(_) { /* best-effort */ }`, which is what made this class of bug invisible in the first place).

## Steps to Reproduce

1. From any machine on the LAN that is NOT the dashboard host, open `http://iw-dev-01:9900/project/iw-ai-core/item/I-00067` in Chromium.
2. Click the **Execution Report** tab.
3. Scroll to the **Self-Assessment** section. Each of the 5 finding cards displays a `/iw-new-cr ...` paste prompt next to a **Copy paste prompt** button.
4. Click any **Copy paste prompt** button.
5. Open the browser DevTools Console (F12) to confirm the error.

**Expected**: The full `/iw-new-cr ...` prompt is copied to the system clipboard, and the button briefly displays "Copied" before reverting to its original label.

**Actual**: Nothing visible happens. The button label does NOT change. The clipboard is unchanged. The browser console shows `TypeError: Cannot read properties of undefined (reading 'writeText')` thrown from the inline `onclick` handler.

## Browser Evidence

- Pre-fix browser console capture: `ai-dev/active/I-00070/evidences/pre/I-00070-console-typeerror.log`
- Pre-fix screenshot of the Self-Assessment section on `iw-dev-01`: `ai-dev/active/I-00070/evidences/pre/I-00070-button-on-iw-dev-01.png`

The console log contains the exact `TypeError: Cannot read properties of undefined (reading 'writeText')` thrown from `HTMLButtonElement.onclick`. The probe also confirmed `window.isSecureContext = false` and `typeof navigator.clipboard === "undefined"` for the `iw-dev-01` host on plain HTTP.

## Browser Verification Script

Reproduction (pre-fix), recorded for posterity:

```bash
playwright-cli kill-all
playwright-cli open "http://iw-dev-01:9900/project/iw-ai-core/item/I-00067"
playwright-cli eval '() => ({ isSecureContext: window.isSecureContext, hasClipboard: typeof navigator.clipboard !== "undefined" })'
# Expected output: {"isSecureContext": false, "hasClipboard": false}
playwright-cli snapshot
# locate the "Execution Report" tab button ref, click it
playwright-cli click <execution-report-tab-ref>
playwright-cli snapshot
# locate any "Copy paste prompt" button in the Self-Assessment section
playwright-cli click <copy-paste-prompt-button-ref>
# inspect the captured console log; expect a TypeError from the onclick handler
```

## Root Cause Analysis

The inline `onclick` handler at `dashboard/templates/fragments/item_execution_report.html:354` calls `navigator.clipboard.writeText(this.dataset.pastePrompt)` directly:

```html
<button type="button" ...
        onclick="navigator.clipboard.writeText(this.dataset.pastePrompt).then(...)">
  Copy paste prompt
</button>
```

The Clipboard API (`navigator.clipboard`) is exposed by Chromium-family and Firefox browsers **only in secure contexts** (per the W3C Clipboard spec and `Window.isSecureContext`). A "secure context" is one of: HTTPS, `file://`, or `localhost` / `127.0.0.1` / `::1`. Plain HTTP on any other hostname (e.g. `iw-dev-01`, an IP, or a `*.local` mDNS name) is non-secure, so `navigator.clipboard` is `undefined` and the property access on it throws synchronously.

The inline `onclick="...promise.then(...)"` form has no `.catch(...)` and no surrounding `try`, so the thrown `TypeError` becomes an unhandled rejection / synchronous error that the browser logs to the console but never surfaces to the user. The button does nothing visible.

The dashboard is intentionally bound to `0.0.0.0` (`IW_CORE_DASHBOARD_HOST=0.0.0.0`) for LAN access, so non-localhost hostnames are a first-class supported access mode — clipboard buttons must work in that mode.

The same anti-pattern exists at six other call sites:

| File | Line | Context |
|------|------|---------|
| `dashboard/templates/fragments/item_execution_report.html` | 354 | Self-Assessment paste prompt (the reported bug) |
| `dashboard/templates/fragments/oss_cli_block.html` | 15 | OSS CLI block copy button |
| `dashboard/templates/fragments/oss_install_modal.html` | 37 | OSS install command copy button |
| `dashboard/templates/pages/project/oss.html` | 520-521 | OSS page (already has `isSecureContext` guard but its `catch(_) {}` swallows the failure with no fallback feedback) |
| `dashboard/static/chat/actions.js` | 40 | Chat: copy assistant message |
| `dashboard/static/chat/render.js` | 135 | Chat: copy CSV |
| `dashboard/static/chat/render.js` | 176 | Chat: copy generic payload |

All six exhibit the same failure mode on `iw-dev-01` and similar hosts.

## Affected Components

| Component | Impact |
|-----------|--------|
| Dashboard frontend (Self-Assessment finding cards) | Reported "Copy paste prompt" button is non-functional; users have to manually select the `<code>` text and copy it themselves. |
| Dashboard frontend (OSS CLI block, OSS install modal, OSS page actions) | Other copy buttons fail silently with the identical mechanism. |
| Dashboard frontend (Chat assistant action / CSV / payload copies) | Same silent failure. |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | frontend-impl | Add `dashboard/static/clipboard.js` exposing `window.iwClipboard.copy(text, button?)`. Implementation: try `navigator.clipboard.writeText` when `window.isSecureContext && navigator.clipboard` is truthy; otherwise fall back to a temporary off-screen `<textarea>` + `document.execCommand('copy')`. Returns a Promise that resolves on success and **rejects** on failure (no swallowing). When passed a `button` element, sets its label to "Copied" on success or "Copy failed" on failure for ~1.5s, then restores the original label. Load the script from `dashboard/templates/base.html`. Replace all 7 inline `navigator.clipboard.writeText(...)` callsites to use the helper. The OSS page's local `copyToClipboard` is removed and rewired to the shared helper. | — |
| S02 | code-review-impl | Review S01 for: (a) helper correctness on both branches, (b) every callsite migrated, (c) no behaviour regression for the secure-context happy path, (d) UI feedback works, (e) no leaked DOM nodes, (f) correct ordering of textarea cleanup, (g) accessibility (`aria-live` or visible text change), (h) escape safety where text contains HTML. | — |
| S03 | tests-impl | Add `tests/dashboard/test_i00070_clipboard_fallback.py`: load the execution-report fragment via FastAPI TestClient and parse the rendered HTML to verify the button is wired through the new helper (no inline `navigator.clipboard.writeText` references in the rendered output). Add a Playwright-driven test in `tests/dashboard/browser/test_i00070_clipboard_fallback.py` that opens the dashboard via `localhost`, monkey-patches `window.isSecureContext = false` and deletes `navigator.clipboard` BEFORE the user clicks, then asserts (a) the button label changes to "Copied", (b) no uncaught console error, and (c) the synthesised clipboard write occurred. Both tests assert specific values, not response shape. | — |
| S04 | code-review-impl | Review S03: tests are falsifiable on main, semantic-correctness assertions only, no flaky timing. | — |
| S05 | code-review-final-impl | Global review across S01 + S03: helper + every migrated callsite + tests integrate end-to-end. Confirm no other consumers of clipboard regressed. | — |
| S06..S11 | qv-gate | lint, format-check, typecheck, arch-check, security-sast, unit-tests | — |
| S12 | qv-browser | Reproduce the original repro flow on the worktree's isolated stack and confirm the button now copies and shows "Copied" feedback. | — |
| S13 | self-assess-impl | Self-assessment via the iw-item-analyze skill | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None — this incident is dashboard frontend only.

### Code Changes

- **Files to create**:
  - `dashboard/static/clipboard.js` — the shared helper
  - `tests/dashboard/test_i00070_clipboard_fallback.py` — server-side fragment test
  - `tests/dashboard/browser/test_i00070_clipboard_fallback.py` — Playwright fallback test
- **Files to modify**:
  - `dashboard/templates/base.html` — load `clipboard.js`
  - `dashboard/templates/fragments/item_execution_report.html` — replace inline `onclick`
  - `dashboard/templates/fragments/oss_cli_block.html` — replace inline `onclick`
  - `dashboard/templates/fragments/oss_install_modal.html` — replace inline `onclick`
  - `dashboard/templates/pages/project/oss.html` — remove local `copyToClipboard`; rewire to shared helper
  - `dashboard/static/chat/actions.js` — switch to shared helper
  - `dashboard/static/chat/render.js` — switch to shared helper at both line 135 and 176
- **Nature of change**: Eliminate direct `navigator.clipboard.writeText(...)` calls in favour of the centralized fallback-aware helper, with mandatory UI feedback on success AND failure.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00070_Issue_Design.md` | Design | This document |
| `I-00070_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00070_S01_Frontend_prompt.md` | Prompt | Helper + callsite migration |
| `prompts/I-00070_S02_CodeReview_Frontend_prompt.md` | Prompt | Per-step review |
| `prompts/I-00070_S03_Tests_prompt.md` | Prompt | Reproduction + regression tests |
| `prompts/I-00070_S04_CodeReview_Tests_prompt.md` | Prompt | Per-step review |
| `prompts/I-00070_S05_CodeReview_Final_prompt.md` | Prompt | Global review |
| `prompts/I-00070_S12_BrowserVerification_prompt.md` | Prompt | qv-browser verification |
| `prompts/I-00070_S13_SelfAssess_prompt.md` | Prompt | Self-assessment via iw-item-analyze |

Reports are created during execution under `ai-dev/active/I-00070/reports/`.

## Test to Reproduce

```python
# tests/dashboard/test_i00070_clipboard_fallback.py
def test_i00070_self_assess_button_does_not_use_inline_clipboard_writetext(
    client, db_session, test_project, tmp_path,
):
    """RED: this test FAILS on the buggy template (inline navigator.clipboard call)
    and PASSES once the button is rewired through the new shared helper.
    """
    # Arrange: create a self_assess step with a finding so the button renders.
    item = _create_item_with_self_assess(
        db_session, test_project, tmp_path,
        findings_json='{"findings":[{"severity":"HIGH","class":"x","target":"iw-ai-core",'
                      '"title":"t","recommendation":"r","paste_prompt":"/iw-new-cr p","evidence":[]}]}',
    )

    # Act
    resp = client.get(f"/project/{test_project.id}/item/{item.id}/tab/execution-report")
    html = resp.text

    # Assert (semantic correctness, not shape):
    # The fragment must NOT contain a direct call to navigator.clipboard.writeText
    # in any inline onclick — that pattern is what fails outside secure contexts.
    assert "navigator.clipboard.writeText" not in html, (
        "Inline clipboard call still present — button will silently fail "
        "on http://iw-dev-01:9900 (non-secure context)"
    )
    # The button must be wired through the shared helper instead.
    assert "iwClipboard.copy" in html or "data-iw-copy" in html
    # The full prompt is still embedded (so the helper has something to copy).
    assert "/iw-new-cr p" in html
```

## Browser Verification Test

In `tests/dashboard/browser/test_i00070_clipboard_fallback.py`, after opening the dashboard via `localhost` (where the secure-context branch would normally be taken):

```python
# Pre-arrange: simulate the iw-dev-01 access mode in the same browser.
page.evaluate("Object.defineProperty(window, 'isSecureContext', { value: false });")
page.evaluate("delete navigator.clipboard;")

# Act
page.click('button:has-text("Copy paste prompt")')

# Assert (semantic correctness):
expect(page.locator('button:has-text("Copied")')).to_be_visible(timeout=2000)
# AND no uncaught console error captured.
assert not any("TypeError" in m for m in console_messages)
```

## Acceptance Criteria

### AC1: Button works on non-secure contexts

```
Given the dashboard is open at http://iw-dev-01:9900/project/iw-ai-core/item/I-00067
And the user navigates to the Execution Report tab and the Self-Assessment section
When the user clicks any "Copy paste prompt" button
Then the full /iw-new-cr ... text is written to the system clipboard
And the button briefly displays "Copied" then reverts to "Copy paste prompt"
And no TypeError is logged to the browser console
```

### AC2: Button works on secure contexts (no regression)

```
Given the dashboard is open at http://localhost:9900/project/iw-ai-core/item/I-00067
When the user clicks any "Copy paste prompt" button
Then the prompt is copied via navigator.clipboard.writeText (the modern path)
And the button briefly displays "Copied" then reverts
```

### AC3: All other clipboard buttons benefit from the same fix

```
Given any of the OSS CLI block, OSS install modal, OSS page actions, chat copy-message,
  chat copy-CSV, or chat copy-payload buttons is clicked
When the dashboard is being accessed over plain HTTP from a non-localhost hostname
Then the click result is identical to AC1 (clipboard updated, "Copied" feedback, no TypeError)
```

### AC4: Reproduction + regression tests exist

```
Given the test suite runs
When tests/dashboard/test_i00070_clipboard_fallback.py and the Playwright fallback test execute
Then both pass on the fixed code
And the server-side test FAILS on the pre-fix template (verified once before the fix lands)
```

## Regression Prevention

- The shared helper centralises the secure-context check and fallback in one place — future buttons can call `window.iwClipboard.copy(text, button)` and inherit the fix automatically.
- The shared helper rejects on failure (no `catch(_) { /* best-effort */ }`), so future regressions surface as visible "Copy failed" UI rather than silent no-ops.
- The server-side regression test (`test_i00070_clipboard_fallback.py`) asserts the rendered HTML contains no inline `navigator.clipboard.writeText` reference. If a future contributor adds a new direct call, that test fails with a clear message.
- Add a brief note in `dashboard/CLAUDE.md` (`## Clipboard buttons`) directing developers to the shared helper. Done as part of S01.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- `dashboard/static/clipboard.js`
- `dashboard/templates/base.html`
- `dashboard/templates/fragments/item_execution_report.html`
- `dashboard/templates/fragments/oss_cli_block.html`
- `dashboard/templates/fragments/oss_install_modal.html`
- `dashboard/templates/pages/project/oss.html`
- `dashboard/static/chat/actions.js`
- `dashboard/static/chat/render.js`
- `dashboard/CLAUDE.md`
- `tests/dashboard/test_i00070_clipboard_fallback.py`
- `tests/dashboard/browser/test_i00070_clipboard_fallback.py`
- `ai-dev/active/I-00070/**`
- `ai-dev/archive/I-00070/**`

## TDD Approach

- **Reproducing test**: `tests/dashboard/test_i00070_clipboard_fallback.py` (server-side fragment assertion that fails on the buggy template).
- **Unit tests**: a small inline JS unit test (or playwright eval-based assertion) that exercises both branches of the helper given a mocked `navigator.clipboard` and `window.isSecureContext`.
- **Integration tests**: the Playwright fallback test in `tests/dashboard/browser/test_i00070_clipboard_fallback.py` that simulates non-secure-context behaviour and asserts the button still copies and gives feedback.

## Notes

- The Clipboard API spec is here: <https://developer.mozilla.org/en-US/docs/Web/API/Clipboard>. The "Secure contexts" requirement is non-negotiable on the spec side; there is no flag or origin trial that exposes `navigator.clipboard` over plain HTTP on a non-localhost host.
- `document.execCommand('copy')` is officially deprecated but **every** evergreen browser still supports it for the no-API fallback case. It will remain supported until a replacement non-secure-context API exists, which it currently does not.
- Do NOT introduce a JS bundler or new dependency. The helper is ~30 lines of vanilla JS; one new `<script>` tag in `base.html` is the entire integration cost.
