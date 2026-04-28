# F-00066_S07_CodeReview_Final_prompt

**Work Item**: F-00066 — Proactive diagram rendering in QA chat
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01, S03, S05

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

All S01–S06 reports and all changed files. Refer to the File Manifest in the design doc.

## Output Files

- `ai-dev/active/F-00066/reports/F-00066_S07_CodeReview_Final_report.md`

## Final Review Checklist

### Invariants from design doc
- [ ] `_find_new_diagram_blocks` never raises (try/except wraps body)
- [ ] Render call uses `loop.run_in_executor` — does not block the async generator
- [ ] `image` SSE event only emitted when render returns a non-None SVG string
- [ ] `<pre data-iw-server-rendered>` elements are hidden (CSS or `display: none` in `onDone`)
- [ ] `upgradeAllMermaidBlocks` still called for un-rendered blocks (graceful fallback preserved)

### Integration consistency
- [ ] `onImage` is passed from `render.js` to `stream.js` `streamAnswer` call
- [ ] `block_index` is **per-type** (backend uses `emit_counts[lang]`; frontend queries `pre[data-lang="${sourceType}"]` without `:not()` filter and uses `pres[block_index]`)
- [ ] `_DIAGRAM_RENDER_AVAILABLE` flag correctly gates block detection when F-00064 is absent
- [ ] D2 blocks handled alongside Mermaid blocks (not silently dropped)

### Security
- [ ] SVG embedded as data URI in `img.src` — no direct HTML injection
- [ ] No inline SVG via `innerHTML` (data URI is safe, inline SVG could embed scripts)
- [ ] `download` attribute on the anchor — file saved locally, not served from an external URL

### Open issues (CRITICAL/HIGH only)
State: "No CRITICAL or HIGH findings" if none.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "F-00066",
  "completion_status": "complete|partial|blocked",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO", "file": "...", "line": 0, "message": "..."}],
  "approved": true,
  "notes": ""
}
```
