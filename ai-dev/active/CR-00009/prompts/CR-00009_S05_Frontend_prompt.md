# CR-00009_S05_Frontend_prompt

**Work Item**: CR-00009 — Chat panel context awareness
**Step**: S05
**Agent**: frontend-impl

---

## Input Files

- `ai-dev/active/CR-00009/CR-00009_CR_Design.md`
- `ai-dev/active/CR-00009/reports/CR-00009_S03_Api_report.md` (router accepts `module_name` now)
- Files to modify:
  - `dashboard/templates/chat/panel.html`
  - `dashboard/templates/project_code.html`
  - `dashboard/templates/fragments/code_module_detail.html`
  - `dashboard/static/chat/panel.js`
  - `dashboard/static/chat/composer.js`

## Output Files

- `ai-dev/active/CR-00009/reports/CR-00009_S05_Frontend_report.md`

## Context

The chat panel currently shows a static `<h2>Chat</h2>` and the composer already reads `data-module-path` off `#code-content-root`. This step makes the header reflect the current context and ships `module_name` in the chat POST body. Read the design doc's **Desired Behavior** items 1 and 5 and AC1, AC2, AC6, AC7 before coding.

## Requirements

### 1. Surface `module_name` on `#code-content-root`

In `dashboard/templates/project_code.html` (around line 89-94), `#code-content-root` exposes `data-context-level`, `data-context-doc-id`, `data-module-path`, `data-project-id`. Add:

```html
data-module-name=""
```

Initial value is empty — set only when a module is selected.

### 2. Propagate `module_path` AND `module_name` onto `#code-content-root` on module-detail swap

**Important context (verified during design review):** today the codebase has a dead read path — `composer.js` reads `root.dataset.modulePath` to render a `module:<path>` chip, but nothing ever writes that attribute. `#code-content-root` declares `data-module-path=""` and stays empty; module navigation targets `#code-detail-panel`, not `#code-content-root`, so `composer.js`'s `htmx:afterSwap` listener never fires on module clicks. This CR fixes that as a required side-effect — you must implement the propagation for BOTH `data-module-path` and `data-module-name`, not just the new `data-module-name`.

**Mechanism (Option A — decided during design review):**

1. In `dashboard/templates/fragments/code_module_detail.html`, add two attrs on the root `#code-module-detail` element (alongside the existing `data-module-slug`):

   ```html
   data-module-path="{{ module.path }}"
   data-module-name="{{ module.name }}"
   ```

   Both rendered through Jinja's default autoescape — do NOT use `| safe`.

2. At the END of `code_module_detail.html` (after the closing `</div>` of `#code-module-detail`, still inside the fragment so it ships on every swap), add an inline `<script>` block:

   ```html
   <script>
     (function () {
       var detail = document.getElementById('code-module-detail');
       var root = document.getElementById('code-content-root');
       if (!detail || !root) return;
       root.dataset.modulePath = detail.dataset.modulePath || '';
       root.dataset.moduleName = detail.dataset.moduleName || '';
       // Notify listeners (chat header sync, composer chip sync) that
       // code-content-root's data-attrs just changed. htmx's own afterSwap
       // event only fires for #code-detail-panel here, not the root.
       document.body.dispatchEvent(new CustomEvent('iw:code-context-changed', {
         detail: { source: 'module-detail' }
       }));
     })();
   </script>
   ```

   The synthetic event is the coordination hook for items 4 (header sync) and for the composer chip (which must listen to the same event in addition to its existing `htmx:afterSwap` listener).

3. **Architecture-view reset.** When the user navigates back (breadcrumb "Architecture" link → `hx-get="/api/projects/.../code/modules"` which swaps `#code-components-section`, OR a module back-button → swap into `#code-detail-panel` that does NOT include `#code-module-detail`), `#code-content-root`'s `data-module-path` / `data-module-name` must be reset to `""`. Implement this in `panel.js` (or the same header sync block — see item 4) as a single `htmx:afterSwap` listener:

   ```js
   document.body.addEventListener('htmx:afterSwap', function (e) {
     var target = e.detail && e.detail.target;
     if (!target) return;
     // Back-to-architecture paths: either the components-section re-rendered,
     // or the detail panel was swapped with content that does NOT contain
     // #code-module-detail.
     var isComponentsSwap = target.id === 'code-components-section';
     var isDetailPanelSwap = target.id === 'code-detail-panel';
     if (isComponentsSwap || (isDetailPanelSwap && !target.querySelector('#code-module-detail'))) {
       var root = document.getElementById('code-content-root');
       if (root) {
         root.dataset.modulePath = '';
         root.dataset.moduleName = '';
         document.body.dispatchEvent(new CustomEvent('iw:code-context-changed', {
           detail: { source: 'architecture-reset' }
         }));
       }
     }
   });
   ```

   Note: on the module-detail swap path, the inline script in step 2 fires AFTER htmx inserts the fragment, so this listener (which runs during htmx's own afterSwap dispatch on `#code-detail-panel`) will NOT see `#code-module-detail` in the old content, but WILL see it in the new content — the `!target.querySelector('#code-module-detail')` guard prevents false resets on module-to-module navigation.

### 3. Make the chat header label a live-updating element

In `dashboard/templates/chat/panel.html` line 11, replace:

```html
<h2 class="text-sm font-medium">Chat</h2>
```

with:

```html
<h2 id="chat-context-label" class="text-sm font-medium truncate" title="Chat — Architecture">Chat — Architecture</h2>
```

- `id="chat-context-label"` is the hook JS will target.
- `truncate` prevents overflow when module paths are long.
- `title` gives a native tooltip for the full text when truncated.
- Default text is `Chat — Architecture` for first paint (before JS runs).

### 4. Implement the header-label sync

Add the sync logic to `dashboard/static/chat/panel.js` (preferred — keeps the panel's lifecycle code co-located). If you decide to ship a new `dashboard/static/chat/header.js` instead, update `dashboard/templates/project_code.html` to include it after `panel.js`.

The sync:

```js
function syncChatHeader() {
  var root = document.getElementById('code-content-root');
  var label = document.getElementById('chat-context-label');
  if (!root || !label) return;
  var path = (root.dataset.modulePath || '').trim();
  var name = (root.dataset.moduleName || '').trim();
  var text;
  if (path) {
    text = name ? 'Chat — ' + path + ' (' + name + ')' : 'Chat — ' + path;
  } else {
    text = 'Chat — Architecture';
  }
  label.textContent = text;
  label.setAttribute('title', text);
}

syncChatHeader();
// The inline <script> in code_module_detail.html dispatches this after the
// fragment mirrors its data-attrs onto #code-content-root. The architecture-
// reset listener (item 2 step 3) also dispatches it. Both keep the header
// in sync regardless of which swap path fired.
document.body.addEventListener('iw:code-context-changed', syncChatHeader);
// Also re-run on any raw htmx swap that targets #code-content-root, in case
// a future swap path writes the attrs directly.
document.body.addEventListener('htmx:afterSwap', function (e) {
  if (e.detail && e.detail.target && e.detail.target.id === 'code-content-root') {
    syncChatHeader();
  }
});
```

Notes:
- `textContent` (not `innerHTML`) — user-controlled module names must not be interpreted as HTML. This is the primary XSS guard.
- Run on initial load, on every `iw:code-context-changed` event (dispatched by the mirror script and the architecture-reset listener in item 2), AND on any `htmx:afterSwap` that directly targets `#code-content-root`.
- If `panel.js` already wraps its code in an IIFE, add the sync inside that IIFE to avoid leaking `syncChatHeader` onto `window`.
- **Composer chip regression guard:** `composer.js::syncContextChip` must also listen to `iw:code-context-changed` in addition to its existing `htmx:afterSwap` listener, otherwise the chip will keep never appearing (the existing bug). Add a single new `document.body.addEventListener('iw:code-context-changed', syncContextChip);` line inside the composer IIFE — do NOT modify `syncContextChip` itself (see item 6).

### 5. Send `module_name` in the chat POST body

In `dashboard/static/chat/composer.js`, the send handler reads from `#code-content-root` (around lines 260-264) and constructs the body (around lines 285-292). Add:

```js
var moduleName = (root && root.dataset.moduleName) || null;
// ...
var body = {
  question: question,
  context_level: contextLevel,
  context_doc_id: contextDocId,
  module_path: modulePath,
  module_name: moduleName,
  conversation_history: conversationHistory,
  context_chips: contextChips_data,
};
```

### 6. Preserve existing composer chip rendering; wire it to the new event

Do NOT change the internals of `composer.js::syncContextChip` (lines 85-105) — the chip markup, chip dataset, and remove-button behavior stay as-is. The header label is separate and additive. If you want to make the chip show the name too, do it in a follow-up CR — out of scope here.

The ONE change required inside the composer IIFE: add `document.body.addEventListener('iw:code-context-changed', syncContextChip);` alongside the existing `htmx:afterSwap` listener (lines 108-112). This is what actually makes the chip start appearing on module navigation — today it never fires because swaps go to `#code-detail-panel`, not `#code-content-root`. Leaving the existing `htmx:afterSwap` listener in place is intentional (defensive — if a future swap path writes the attrs directly to `#code-content-root`, the chip still syncs).

## Project Conventions

- Read `CLAUDE.md` (root) and `dashboard/CLAUDE.md`. Jinja2 + htmx + Tailwind CDN. No build step, no bundler — ES5-compatible vanilla JS, same style as the existing `composer.js` and `panel.js`.
- No new dependencies. No JSX. No template literals with embedded expressions if the surrounding file doesn't already use them (keep the style consistent).
- Tailwind classes must be static strings (no dynamic class construction) because the CDN has no purge step.
- Autoescape is on for Jinja attribute values — `{{ module.name }}` is safe. Do NOT use `| safe`.

## TDD Requirement

Frontend TDD here is light:

1. **RED**: If you can add a quick DOM-level unit test (e.g., a script that mounts a detached `#code-content-root` + `#chat-context-label` and asserts `syncChatHeader` updates the label text), do so in a small test file alongside S07's work. Otherwise, the qv-browser step (S16) is the source of truth for header behavior — note this in your report.
2. **GREEN**: Implement the changes above.
3. **REFACTOR**: Keep the JS style consistent with the existing IIFE pattern.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `uv run ruff check dashboard/` (covers any Python template helpers)
3. Start the dashboard locally if practical (`make dashboard-start`), open a project's code page, open the browser dev console, and manually confirm:
   - On architecture view: header reads `Chat — Architecture`, no console errors.
   - After clicking a module in the sidebar: header reads `Chat — <path> (<name>)`, no console errors.
   - The `composer.js` module chip still works.
4. If you can't start the dashboard in your environment, note it in the report; S16 will cover it end-to-end.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "frontend-impl",
  "work_item": "CR-00009",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/chat/panel.html",
    "dashboard/templates/project_code.html",
    "dashboard/templates/fragments/code_module_detail.html",
    "dashboard/static/chat/panel.js",
    "dashboard/static/chat/composer.js"
  ],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
