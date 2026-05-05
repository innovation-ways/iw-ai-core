# I-00070_S01_Frontend_prompt

**Work Item**: I-00070 -- Copy paste prompt button silently fails over plain HTTP from a non-localhost hostname
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy. No container operations are required for this step. See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does NOT touch Alembic migrations.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00070 --json` for the current step list.
- `ai-dev/active/I-00070/I-00070_Issue_Design.md` — Design document (READ FIRST)
- `ai-dev/active/I-00070/I-00070_Functional.md` — Functional design (read for user-facing intent)
- `ai-dev/active/I-00070/evidences/pre/I-00070-console-typeerror.log` — captured browser console showing the live `TypeError`
- `ai-dev/active/I-00070/evidences/pre/I-00070-button-on-iw-dev-01.png` — pre-fix screenshot of the broken state
- `dashboard/templates/fragments/item_execution_report.html` — contains the reported bug at line 354
- `dashboard/templates/fragments/oss_cli_block.html` — duplicate bug at line 15
- `dashboard/templates/fragments/oss_install_modal.html` — duplicate bug at line 37
- `dashboard/templates/pages/project/oss.html` — duplicate bug at lines 520-521 (already partially guarded with `isSecureContext` but swallows errors)
- `dashboard/static/chat/actions.js` — duplicate bug at line 40
- `dashboard/static/chat/render.js` — duplicate bug at lines 135 and 176
- `dashboard/templates/base.html` — where the new helper script tag is loaded
- `dashboard/CLAUDE.md` — dashboard conventions (Jinja2 + htmx + prebuilt Tailwind, vanilla JS only)
- `CLAUDE.md` — project conventions

## Output Files

- `ai-dev/active/I-00070/reports/I-00070_S01_Frontend_report.md` — Step report

## Context

You are implementing the only fix step for **I-00070 — Copy paste prompt button silently fails over plain HTTP from a non-localhost hostname**.

The reported bug: clicking "Copy paste prompt" on a Self-Assessment finding card does nothing on `http://iw-dev-01:9900` (and any other non-localhost hostname over plain HTTP). Browser console captures the live error: `TypeError: Cannot read properties of undefined (reading 'writeText')`. Root cause: `navigator.clipboard` is `undefined` outside secure contexts (per W3C spec — HTTPS, `file://`, and `localhost`/`127.0.0.1`/`::1` only). Six other dashboard buttons share the identical anti-pattern.

Read `I-00070_Issue_Design.md` end-to-end first, especially the Acceptance Criteria, Affected Components, and the Root Cause Analysis table listing the 7 callsites.

## Requirements

### 1. Create the shared clipboard helper

Create a new file `dashboard/static/clipboard.js` with this contract:

```js
// dashboard/static/clipboard.js
(function () {
  function copyViaTextarea(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    ta.style.top = '0';
    document.body.appendChild(ta);
    ta.select();
    try {
      var ok = document.execCommand('copy');
      return ok;
    } finally {
      document.body.removeChild(ta);
    }
  }

  function applyButtonFeedback(button, label, durationMs) {
    if (!button || typeof button.textContent !== 'string') return;
    var original = button.dataset.iwClipboardOriginal;
    if (typeof original !== 'string') {
      original = button.textContent;
      button.dataset.iwClipboardOriginal = original;
    }
    button.textContent = label;
    setTimeout(function () {
      // Only restore if no other call has changed the label since
      if (button.textContent === label) {
        button.textContent = original;
      }
    }, durationMs || 1500);
  }

  function copy(text, button) {
    var hasModern = typeof navigator !== 'undefined' &&
                    !!navigator.clipboard &&
                    typeof navigator.clipboard.writeText === 'function' &&
                    typeof window !== 'undefined' &&
                    window.isSecureContext === true;
    var p;
    if (hasModern) {
      p = navigator.clipboard.writeText(text);
    } else {
      p = new Promise(function (resolve, reject) {
        try {
          var ok = copyViaTextarea(text);
          if (ok) resolve(); else reject(new Error('execCommand("copy") returned false'));
        } catch (err) {
          reject(err);
        }
      });
    }
    return p.then(
      function () { applyButtonFeedback(button, 'Copied'); },
      function (err) { applyButtonFeedback(button, 'Copy failed'); throw err; }
    );
  }

  window.iwClipboard = { copy: copy };
})();
```

Key points (NON-NEGOTIABLE):

- The helper MUST reject (not swallow) on failure, so callers / tests can react.
- The fallback uses `document.execCommand('copy')` with a fixed-position off-screen `<textarea>`. This is the only universally supported non-secure-context copy mechanism today.
- The helper MUST set the button label to "Copied" on success and "Copy failed" on failure for ~1.5s, then restore the original label.
- The original label is cached in `button.dataset.iwClipboardOriginal` so repeated rapid clicks restore consistently.
- Vanilla JS only — no module syntax, no framework imports. Wrap in an IIFE so nothing leaks to the global scope except `window.iwClipboard`.

### 2. Load the helper from `base.html`

In `dashboard/templates/base.html`, add a `<script src="/static/clipboard.js"></script>` tag in the same neighborhood as `theme-toggle.js` and `duration.js` (around line 212-213). It MUST load synchronously (no `defer`) before any inline `<script>` blocks that call `iwClipboard.copy(...)` execute on click. Place it before any inline scripts that use it but after htmx (which is already deferred) — putting it next to the other static helpers is correct.

### 3. Migrate every callsite (all 7)

Replace each direct `navigator.clipboard.writeText(...)` call with `window.iwClipboard.copy(text, button)`. After your changes, `grep -rn "navigator.clipboard.writeText" dashboard/` MUST return matches ONLY inside `dashboard/static/clipboard.js`. Verify this with grep before reporting `complete`.

#### 3a. `dashboard/templates/fragments/item_execution_report.html` (line ~354)

The current handler is:
```html
onclick="navigator.clipboard.writeText(this.dataset.pastePrompt).then(() => { this.textContent = 'Copied'; setTimeout(() => this.textContent = 'Copy paste prompt', 1500); })"
```

Replace with:
```html
onclick="window.iwClipboard.copy(this.dataset.pastePrompt, this).catch(function(){})"
```

The helper handles all UI feedback. The trailing `.catch(function(){})` exists only to prevent the dev console "Uncaught (in promise)" warning — the failure label is already shown by the helper. The button's original text "Copy paste prompt" is auto-cached by the helper on first click.

#### 3b. `dashboard/templates/fragments/oss_cli_block.html` (line ~15)

```html
onclick="navigator.clipboard.writeText(this.closest('.relative').querySelector('code').textContent)"
```
becomes:
```html
onclick="window.iwClipboard.copy(this.closest('.relative').querySelector('code').textContent, this).catch(function(){})"
```

#### 3c. `dashboard/templates/fragments/oss_install_modal.html` (line ~37)

```html
onclick="navigator.clipboard.writeText('{{ info.install_cmd }}')"
```
becomes:
```html
onclick="window.iwClipboard.copy('{{ info.install_cmd }}', this).catch(function(){})"
```

Confirm `info.install_cmd` is properly escaped by Jinja2 autoescape (it is — that's the default).

#### 3d. `dashboard/templates/pages/project/oss.html` (lines 518-534, 547)

Delete the local `async function copyToClipboard(text) { ... }` block at lines 518-534 entirely. At line ~547, replace:
```js
copyToClipboard(copyBtn.dataset.ossCopy).then(function () { ... })
```
with:
```js
window.iwClipboard.copy(copyBtn.dataset.ossCopy, copyBtn).catch(function(){})
```

The OSS page's own button text-update logic (lines 548-550 set `'✓'` for 1200ms) currently OVERRIDES the helper's `'Copied'` text. Decide explicitly:
- **Preferred**: keep the helper's `'Copied'` label and remove the OSS page's local checkmark/restore logic. Consistent UI across the dashboard.
- If you can't remove it cleanly without other breakage, leave the OSS-page logic in place — but only after the helper's promise resolves successfully (use `.then(function(){ copyBtn.textContent = '✓'; ... })`). Do NOT do both.

#### 3e. `dashboard/static/chat/actions.js` (line 40)

```js
navigator.clipboard.writeText(source).then(function () { ... });
```
becomes (preserving the existing success/failure handlers wrapped around the helper call):
```js
window.iwClipboard.copy(source, /* button if available, otherwise null */).then(function () { /* existing success */ }).catch(function (err) { /* existing failure handling */ });
```

If the surrounding code already has UI feedback you want to keep, pass `null` for the button arg (so the helper does NOT also touch the button) and keep the existing handlers. If the surrounding code only had the bare `.then(...)`, pass the button so the helper provides feedback.

#### 3f. `dashboard/static/chat/render.js` (lines 135 and 176)

Same migration as 3e — replace `navigator.clipboard.writeText(...)` with `window.iwClipboard.copy(text, button|null)`. Read each call's context to decide whether to keep or remove the existing UI-update code.

### 4. Update `dashboard/CLAUDE.md`

Add a short subsection under the existing rules:

```markdown
## Clipboard buttons

Use the shared `window.iwClipboard.copy(text, button)` helper from
`dashboard/static/clipboard.js` for every "copy to clipboard" button.
NEVER call `navigator.clipboard.writeText(...)` directly from a template or
static JS file — `navigator.clipboard` is undefined outside secure contexts
(plain HTTP on a non-localhost hostname like `iw-dev-01`), and direct calls
silently throw a `TypeError`. The helper falls back to a textarea +
`document.execCommand('copy')` and surfaces success / failure via the button
label ("Copied" / "Copy failed").
```

### 5. Pre-flight quality gates

Before reporting `completion_status: complete`:

1. `make format` — auto-fixes formatting drift.
2. `make typecheck` — must report zero errors involving the files you touched.
3. `make lint` — must report zero errors. `make lint` runs `node --check` on the dashboard JS — your `clipboard.js` MUST pass.
4. `grep -rn "navigator.clipboard.writeText" dashboard/` — output MUST contain ONLY `dashboard/static/clipboard.js` matches.

Record each command in the `preflight` block of your result contract.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md` for:

- Vanilla JS only — no bundler, no module syntax in template-embedded scripts.
- Static assets live under `dashboard/static/` and are served at `/static/...`.
- Tailwind CSS is prebuilt — your changes do NOT add Tailwind classes, so `make css` is NOT required.

## TDD Requirement

Follow Red-Green-Refactor:

1. **RED**: Write the failing server-side test FIRST in `tests/dashboard/test_i00070_clipboard_fallback.py` (S03 will own the comprehensive suite, but your S01 work MUST be motivated by at least one failing assertion — typically the assertion that `navigator.clipboard.writeText` is no longer present in the rendered fragment).
2. **GREEN**: Implement the helper, load it from `base.html`, migrate the 7 callsites.
3. **REFACTOR**: Clean up.

Do not skip the RED phase.

## Test Verification

After implementation:

1. Run `make test-unit` — all unit tests must pass.
2. Run `make lint`, `make format-check`, `make typecheck`. Zero errors involving touched files.
3. Do NOT report `tests_passed: true` unless all gates pass.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00070",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/static/clipboard.js",
    "dashboard/templates/base.html",
    "dashboard/templates/fragments/item_execution_report.html",
    "dashboard/templates/fragments/oss_cli_block.html",
    "dashboard/templates/fragments/oss_install_modal.html",
    "dashboard/templates/pages/project/oss.html",
    "dashboard/static/chat/actions.js",
    "dashboard/static/chat/render.js",
    "dashboard/CLAUDE.md"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Includes confirmation that grep -rn navigator.clipboard.writeText dashboard/ matches ONLY clipboard.js."
}
```
