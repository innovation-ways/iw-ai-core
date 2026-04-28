# F-00066_S04_CodeReview_Frontend_prompt

**Work Item**: F-00066 — Proactive diagram rendering in QA chat
**Step Being Reviewed**: S03 (frontend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00066/F-00066_Feature_Design.md`
- `ai-dev/active/F-00066/reports/F-00066_S03_Frontend_report.md`
- `dashboard/static/chat/stream.js`
- `dashboard/static/chat/render.js`
- `dashboard/static/styles.css`

## Output Files

- `ai-dev/active/F-00066/reports/F-00066_S04_CodeReview_Frontend_report.md`

## Review Checklist

### `stream.js` changes
- [ ] `onImage` parameter added with no-op default (consistent with `onToken`, `onPhase` etc. pattern)
- [ ] `event: image` handled in the event loop; parses `svg_b64`, `alt`, `source_type`, `block_index`
- [ ] `onImage` called only when `svg_b64` is present (guard against malformed events)
- [ ] No other event types broken (existing token/citation/phase/error paths unchanged)

### `render.js` changes
- [ ] `onImage` implemented in `createAssistantRenderer` return object
- [ ] `onImage` passed to `streamAnswer` options
- [ ] `block_index` used to select the correct un-rendered `<pre>` — not the first one every time
- [ ] `data-iw-server-rendered` attribute set on the matched `<pre>` before inserting the figure
- [ ] Figure inserted after `<pre>`, not replacing it (the `<pre>` stays hidden, not deleted)
- [ ] Try/catch wraps the entire `onImage` body — no uncaught exceptions
- [ ] `onDone` hides server-rendered `<pre>` elements after `upgradeAllMermaidBlocks`

### Security
- [ ] SVG is embedded as a `data:` URI in `img.src` — browser sandboxes it, no XSS vector
- [ ] `download` link uses the same `data:` URI — not an external URL
- [ ] No `innerHTML` assignment with user-controlled content

### CSS
- [ ] `.chat-diagram-figure`, `.chat-diagram-img`, `.chat-diagram-caption` styles present in output CSS
- [ ] `pre[data-iw-server-rendered] { display: none; }` in CSS

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00066",
  "completion_status": "complete|partial|blocked",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "file": "...", "line": 0, "message": "..."}],
  "approved": true,
  "notes": ""
}
```
