# F-00068_S02_Frontend_prompt

**Work Item**: F-00068 — AI Chat Visual Improvements
**Step**: S02
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

---

## Input Files

- `ai-dev/active/F-00068/F-00068_Feature_Design.md` — Design doc (§Canonical Callout Spec, §Boundary Behavior, §Invariants)
- `dashboard/static/chat.css` — Chat layout styles (modify)
- `dashboard/static/chat/render.js` — Chat markdown renderer (modify)
- `dashboard/templates/chat/message.html` — Chat message template (read-only reference)

## Output Files

- `dashboard/static/chat.css` — Modified (prose + callout styles)
- `dashboard/static/chat/render.js` — Modified (callout parser + DOMPurify allowlist)
- `ai-dev/active/F-00068/reports/F-00068_S02_Frontend_report.md`

---

## Context

Chat responses render into `<div class="chat-message-body">` elements. Currently this div has no prose styles — all markdown-rendered headings, code, and blockquotes look the same. This step adds CSS prose hierarchy and callout rendering to make chat responses scannable.

**Key constraint**: The chat panel is ~400px wide — use smaller font sizes than the docs page (H2 → 1rem, H3 → 0.9rem, not the larger sizes used in `prose-doc`).

---

## Requirements

### 1. `chat-message-body` prose styles in `chat.css`

Append the following CSS to `dashboard/static/chat.css` (after existing rules):

```css
/* ── Chat message body prose ── */
.chat-message-body { font-size: 0.9rem; line-height: 1.7; color: var(--foreground); }
.chat-message-body h1,.chat-message-body h2,.chat-message-body h3,.chat-message-body h4 {
  font-weight: 600; margin-top: 1.2em; margin-bottom: 0.35em; line-height: 1.3;
}
.chat-message-body h1 { font-size: 1.05rem; border-bottom: 1px solid var(--border); padding-bottom: 0.2em; }
.chat-message-body h2 { font-size: 1rem; color: var(--foreground); }
.chat-message-body h3 { font-size: 0.9rem; color: var(--muted-foreground); }
.chat-message-body h4 { font-size: 0.875rem; color: var(--muted-foreground); }
.chat-message-body p  { margin-bottom: 0.6em; }
.chat-message-body ul,.chat-message-body ol { padding-left: 1.25em; margin-bottom: 0.6em; }
.chat-message-body li { margin-bottom: 0.2em; }
.chat-message-body blockquote {
  border-left: 3px solid var(--border);
  padding-left: 0.75em;
  color: var(--muted-foreground);
  margin: 0.75em 0;
  font-style: italic;
  font-size: 0.875rem;
}
.chat-message-body code {
  font-family: var(--font-mono, monospace);
  font-size: 0.8rem;
  background: var(--muted);
  color: var(--foreground);
  padding: 0.1em 0.3em;
  border-radius: 3px;
}
.chat-message-body pre {
  background: var(--muted);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 0.75em 1em;
  overflow-x: auto;
  margin-bottom: 0.75em;
}
.chat-message-body pre code { background: none; padding: 0; }
.chat-message-body table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-bottom: 0.75em; }
.chat-message-body th,.chat-message-body td { border: 1px solid var(--border); padding: 0.35em 0.6em; text-align: left; }
.chat-message-body th { background: var(--muted); font-weight: 600; }
.chat-message-body a { color: var(--primary); text-decoration: underline; }
.chat-message-body hr { border: none; border-top: 1px solid var(--border); margin: 1em 0; }

/* ── Chat callouts ── */
.chat-message-body .callout {
  border-left: 4px solid;
  border-radius: 0 var(--radius) var(--radius) 0;
  padding: 0.6em 0.85em;
  margin: 0.85em 0;
  font-size: 0.875rem;
  font-style: normal;
}
.chat-message-body .callout-header {
  display: flex;
  align-items: center;
  gap: 0.35em;
  font-weight: 600;
  margin-bottom: 0.3em;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
.chat-message-body .callout-note    { border-color: #3B82F6; background: #EFF6FF; }
.chat-message-body .callout-note    .callout-header { color: #1D4ED8; }
.chat-message-body .callout-tip     { border-color: #10B981; background: #ECFDF5; }
.chat-message-body .callout-tip     .callout-header { color: #065F46; }
.chat-message-body .callout-warning { border-color: #F59E0B; background: #FFFBEB; }
.chat-message-body .callout-warning .callout-header { color: #92400E; }
.chat-message-body .callout-danger  { border-color: #EF4444; background: #FEF2F2; }
.chat-message-body .callout-danger  .callout-header { color: #991B1B; }
.chat-message-body .callout-important { border-color: #8B5CF6; background: #F5F3FF; }
.chat-message-body .callout-important .callout-header { color: #4C1D95; }
```

### 2. Update DOMPurify allowlist in `render.js`

Locate the `sanitizeHTML()` function in `dashboard/static/chat/render.js` (around line 6). The `ALLOWED_TAGS` array currently includes `div` and `span`. Verify that `div` is in `ALLOWED_TAGS` (it is). Verify that the `ALLOWED_ATTR` array includes `class` (it already does via the existing allowlist).

No change needed IF `class` is already in `ALLOWED_ATTR`. If it is not, add it. Verify and note in the report.

Additionally, the `DOMPurify.sanitize()` call uses `ALLOW_DATA_ATTR: false`. This is fine — callout divs only use class attributes, not data attributes.

**Explicit test**: after your implementation, confirm that `sanitizeHTML('<div class="callout callout-warning"><div class="callout-header">⚠️ WARNING</div><div class="callout-body">text</div></div>')` returns a string containing `class="callout callout-warning"` (i.e., DOMPurify does not strip it). Document this verification in your report.

### 3. Add `iwProcessChatCallouts(container)` to `render.js`

Add the following function after `sanitizeHTML` and before `walkAndSanitizeLinks`:

```javascript
var CALLOUT_TYPES = {
  'note':      { icon: 'ℹ️', cls: 'callout-note' },
  'tip':       { icon: '💡', cls: 'callout-tip' },
  'warning':   { icon: '⚠️', cls: 'callout-warning' },
  'danger':    { icon: '🚨', cls: 'callout-danger' },
  'important': { icon: '📌', cls: 'callout-important' }
};

function iwProcessChatCallouts(container) {
  var blockquotes = container.querySelectorAll('blockquote');
  for (var i = 0; i < blockquotes.length; i++) {
    var bq = blockquotes[i];
    var firstP = bq.querySelector('p');
    if (!firstP) continue;
    var text = firstP.textContent || '';
    var match = text.match(/^\[!(NOTE|TIP|WARNING|DANGER|IMPORTANT)\]/i);
    if (!match) continue;
    var typeName = match[1].toLowerCase();
    var spec = CALLOUT_TYPES[typeName];
    if (!spec) continue;
    // Remove the [!TYPE] prefix from the first paragraph
    firstP.textContent = firstP.textContent.replace(/^\[!(NOTE|TIP|WARNING|DANGER|IMPORTANT)\]\s*/i, '');
    if (!firstP.textContent.trim()) firstP.remove();
    // Build callout div
    var div = document.createElement('div');
    div.className = 'callout ' + spec.cls;
    var header = document.createElement('div');
    header.className = 'callout-header';
    header.innerHTML = '<span class="callout-icon">' + spec.icon + '</span>'
      + '<span class="callout-label">' + typeName.toUpperCase() + '</span>';
    var body = document.createElement('div');
    body.className = 'callout-body';
    while (bq.firstChild) { body.appendChild(bq.firstChild); }
    div.appendChild(header);
    div.appendChild(body);
    bq.parentNode.replaceChild(div, bq);
  }
}
```

### 4. Call `iwProcessChatCallouts` after rendering

Find where the rendered HTML is injected into `.chat-message-body` in `render.js`. After the HTML injection and after `iwRenderMermaid()` is called (if present), add:

```javascript
iwProcessChatCallouts(bodyEl);
```

Also call it in the re-render path (the `rerenderBodyEl` flow around line 391).

---

## Project Conventions

- Dashboard frontend is vanilla JS — no modules, no build step for JS.
- CSS in `chat.css` is loaded globally for all pages that include the chat panel.
- Read `dashboard/CLAUDE.md` for dashboard-specific patterns.

## TDD Requirement

There is no JS test framework. Instead:
1. Add `tests/dashboard/test_chat_message.py` that renders a mock chat message and asserts the template structure (message.html uses `chat-message-body` class).
2. Manually verify the DOMPurify allowlist passes callout classes (document in report).

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`
4. `make test-unit`

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "frontend-impl",
  "work_item": "F-00068",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/static/chat.css",
    "dashboard/static/chat/render.js"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "DOMPurify class allowlist verification: ..."
}
```
