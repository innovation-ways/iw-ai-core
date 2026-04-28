# F-00066_S03_Frontend_prompt

**Work Item**: F-00066 — Proactive diagram rendering in QA chat
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00066/F-00066_Feature_Design.md`
- `ai-dev/active/F-00066/reports/F-00066_S01_Backend_report.md`
- `dashboard/static/chat/stream.js`
- `dashboard/static/chat/render.js`
- `dashboard/static/chat/mermaid.js`

## Output Files

- `ai-dev/active/F-00066/reports/F-00066_S03_Frontend_report.md`
- `dashboard/static/chat/stream.js` (modified)
- `dashboard/static/chat/render.js` (modified)

## Context

Read `CLAUDE.md` and `dashboard/CLAUDE.md`.

The backend now emits `event: image` SSE events carrying a base64 SVG when a fenced diagram block is rendered server-side. The frontend must:
1. Accept the new `onImage` callback in `streamAnswer`
2. Handle `event: image` data in the SSE reader
3. In `render.js`, implement `onImage` to insert the SVG inline and mark the source `<pre>` as server-rendered

**JavaScript note**: `dashboard/static/chat/` files are vanilla JS (no bundler/transpiler). Write plain ES5/ES6 compatible code. Do NOT use TypeScript. Do NOT use `import`/`export` syntax.

## Requirements

### 1. `dashboard/static/chat/stream.js`

Add `onImage` to the `streamAnswer` function signature (defaults to no-op if not provided):

```js
var _h = _a.onImage, onImage = _h === void 0 ? function () {} : _h;
```

In the SSE event loop, after the existing `phase` event handler, add:

```js
} else if (eventType === 'image') {
  try {
    var imgData = JSON.parse(jsonStr);
    if (imgData.svg_b64 && onImage) {
      onImage({
        svg_b64: imgData.svg_b64,
        alt: imgData.alt || 'Diagram',
        source_type: imgData.source_type || 'mermaid',
        block_index: typeof imgData.block_index === 'number' ? imgData.block_index : 0,
      });
    }
  } catch (err) {}
}
```

Place this in the `try { var data = JSON.parse(jsonStr); ... }` block, after the `else if (data.name !== undefined && eventType === 'phase')` branch.

### 2. `dashboard/static/chat/render.js`

#### 2a. Implement `onImage` in `createAssistantRenderer`

Inside the object returned by `createAssistantRenderer`, add `onImage`:

```js
onImage: function (data) {
  try {
    var svgB64 = data.svg_b64;
    var sourceType = data.source_type || 'mermaid';
    var blockIndex = typeof data.block_index === 'number' ? data.block_index : 0;

    // Find the (blockIndex+1)-th un-rendered <pre data-lang="mermaid|d2"> in bodyEl
    var pres = bodyEl.querySelectorAll(
      'pre[data-lang="' + sourceType + '"]:not([data-iw-server-rendered])'
    );
    var targetPre = pres[blockIndex] || null;

    if (!targetPre) return;

    // Mark it so upgradeAllMermaidBlocks skips it in onDone
    targetPre.setAttribute('data-iw-server-rendered', '1');

    // Build the figure
    var figure = document.createElement('figure');
    figure.className = 'chat-diagram-figure';

    var img = document.createElement('img');
    img.src = 'data:image/svg+xml;base64,' + svgB64;
    img.alt = data.alt || 'Diagram';
    img.className = 'chat-diagram-img';
    figure.appendChild(img);

    var caption = document.createElement('figcaption');
    caption.className = 'chat-diagram-caption';
    var dlLink = document.createElement('a');
    dlLink.href = 'data:image/svg+xml;base64,' + svgB64;
    dlLink.download = sourceType + '-diagram.svg';
    dlLink.className = 'chat-diagram-download';
    dlLink.textContent = 'Download SVG';
    caption.appendChild(dlLink);
    figure.appendChild(caption);

    // Insert the figure after the <pre>
    if (targetPre.parentNode) {
      targetPre.parentNode.insertBefore(figure, targetPre.nextSibling);
    }
  } catch (err) {}
},
```

#### 2b. Pass `onImage` through `streamAnswer` call

In `render.js`, find where `window.iwChat.streamAnswer` is called and add `onImage` to the options object:

```js
window.iwChat.streamAnswer({
  // ... existing options ...
  onImage: renderer.onImage,
  // ...
});
```

#### 2c. In `onDone`, skip server-rendered blocks

The existing `upgradeAllMermaidBlocks(bodyEl)` call upgrades ALL `<pre data-lang="mermaid">` elements. Since `mermaid.js` is upstream code we should NOT modify, hide the server-rendered `<pre>` elements with a CSS attribute selector instead of modifying the upgrade function.

After the `upgradeAllMermaidBlocks(bodyEl)` call in `onDone`, add:

```js
// Hide <pre> blocks that were already rendered server-side as SVG images
bodyEl.querySelectorAll('pre[data-iw-server-rendered]').forEach(function (preEl) {
  preEl.style.display = 'none';
});
```

**Note**: `upgradeAllMermaidBlocks` will attempt to render the marked `<pre>` elements too, but hiding them after the call ensures they don't show duplicate content. If the Mermaid upgrade fails for a server-rendered block (already hidden), no visible error occurs.

### 3. CSS — add `.chat-diagram-figure` styles

Run `make css` after adding any new Tailwind classes to templates. Since these classes are added in JS (not templates), add them to `dashboard/static/styles.css` directly via `make css` or by adding a Tailwind config file entry. If the project uses a manual CSS file for non-Tailwind custom styles, add there:

Check if `dashboard/static/` has a `custom.css` or similar file. If not, add a small style block in the Tailwind input file (`dashboard/static/src/input.css` or equivalent — check `package.json` or `Makefile` for the CSS build command).

Minimal styles needed:
```css
.chat-diagram-figure { margin: 1rem 0; }
.chat-diagram-img { max-width: 100%; height: auto; display: block; }
.chat-diagram-caption { font-size: 0.75rem; color: var(--muted-foreground, #888); margin-top: 0.25rem; }
.chat-diagram-download { color: var(--primary, #3b82f6); text-decoration: underline; }
pre[data-iw-server-rendered] { display: none; }
```

Run `make css` after any changes to CSS source files.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format` — must pass
2. `make typecheck` — zero errors on touched files
3. `make lint` — zero errors (note: `make lint` includes node --check on `dashboard/static/**/*.js`)

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "F-00066",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/static/chat/stream.js",
    "dashboard/static/chat/render.js",
    "dashboard/static/styles.css"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
