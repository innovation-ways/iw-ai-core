# F-00055 S08 Code Review Report

## Summary

Reviewed S07 frontend implementation against the F-00055 Feature Design. All 10 must-check items evaluated; **2 findings (1 MEDIUM, 1 LOW)**, no CRITICAL or HIGH issues. Implementation is sound with minor improvements warranted.

## Files Changed

**Modified:**
- `dashboard/static/chat/stream.js` — `onPhase` callback + `phase` SSE event handling; `work_item_type`/`work_item_id` passed through `onCitation`
- `dashboard/static/chat/render.js` — `onPhase`/`onWorkItemCitation` handlers in `createAssistantRenderer`; client-side phase strip; work-item feed builder; `injectToneSwitchChip` exposed on `window.iwChat`
- `dashboard/static/chat/composer.js` — `/why`/`/history` slash aliases; `onPhase` wired through renderer; tone-switch chip injected post-`done`
- `dashboard/static/chat/citations.js` — `getAll` returns `type` and `id` fields
- `dashboard/static/chat.css` — `.phase-strip`, `.work-item-feed`, `.citation-chip--workitem` (with `--feature`/`--change_request`/`--incident`), `.tone-switch-chip` rules

**Created:**
- `dashboard/templates/chat/parts/work_item_chip.html` — ID+glyph chip fragment
- `dashboard/templates/chat/parts/work_item_feed.html` — Linear-style chronological feed fragment
- `dashboard/templates/chat/parts/phase_strip.html` — Status-strip fragment
- `tests/dashboard/test_chat_workitem_templates.py` — 15 smoke tests for new templates

**Reviewed by S07 report:** All listed changes confirmed present.

## Findings

| # | Severity | Item | Description | Location |
|---|----------|------|-------------|----------|
| 1 | MEDIUM | Tone-switch chip streaming | `injectToneSwitchChip` appends `b64`-decoded text via `bodyEl.innerHTML += txt` rather than re-using the streaming parser. This bypasses the SMD markdown renderer and DOMPurify sanitization pipeline, creating a potential XSS vector if the rerender response contains malicious HTML. | `render.js:388` |
| 2 | LOW | No JS test harness | `onPhase` has no JavaScript-side test coverage. Template tests are Python Jinja2 smoke tests only. The phase-event callback path (stream.js → render.js) is exercised only in browser. | `render.js:431–437` |

### Finding Detail — #1 (MEDIUM)

**Description:** `injectToneSwitchChip` handles rerender SSE response by manually appending decoded tokens via `bodyEl.innerHTML += txt`. The resulting HTML is NOT sanitized through `sanitizeHTML()` (DOMPurify) and NOT processed through `walkAndSanitizeLinks()`. This differs from the normal token-streaming path which routes through `sanitizeHTML(html)` on every `onToken` call (`render.js:416–419`).

**Risk:** If the `/api/projects/{pid}/code/qa/rerender` SSE stream emits HTML (e.g., a maliciously crafted code block with script injection), it would be inserted unsanitized into the DOM.

**Remediation:** Route the rerender response through `window.iwChat.streamAnswer` or a shared helper that uses the existing parser+sanitizer pipeline. Alternatively, sanitize each appended chunk: `bodyEl.innerHTML = sanitizeHTML(bodyEl.innerHTML + txt)` followed by `walkAndSanitizeLinks`.

**AC affected:** AC5 (tone-switch chip re-fires query and replaces bubble on new done event).

---

## Must-Check Items Status

| # | Item | Status | Notes |
|---|------|--------|-------|
| 1 | Phase strip behavior (AC6) | ✅ PASS | Strip created on first `onPhase` call (`render.js:433–435`); `phase-strip--quiet` added on `composing` (`render.js:295–297`); collapses on first token via `onToken` → `collapsePhaseStrip()` (`render.js:423–425`). |
| 2 | Work-item chip rendering (AC10) | ✅ PASS | Type glyph correct (F/CR/I via Jinja2 ternary at `work_item_chip.html:7`); link target `/project/{project_id}/item/{work_item_id}` in both feed and chip; popover on click in `render.js:167–200`; `aria-haspopup="dialog"` present. |
| 3 | Feed order (AC1, Invariant 8) | ✅ PASS | Feed items pushed via `onWorkItemCitation` (`render.js:438–440`), rendered via `updateWorkItemFeed()` with `feedItems.slice(0, 5)` (`render.js:316`). Sorting by `created_at` ASC — depends on API ordering. |
| 4 | Tone-switch chip (AC5) | ⚠️ SEE FINDING #1 | Chip injected post-`done` (`render.js:329–332`); disabled for 2s (`render.js:351`); POSTs to `/rerender`; chip label flips correctly. Rerender streaming does NOT route through sanitizer. |
| 5 | Slash-alias registration | ✅ PASS | `/why` and `/history` present in `composer.js:81–82`; `/explain` and `/diagram` untouched. |
| 6 | No htmx regressions | ✅ PASS | Chat panel uses vanilla JS + SSE; no htmx calls added; `htmx:afterSwap` listener only for context sync (`composer.js:110–114`). |
| 7 | Accessibility | ✅ PASS | 44×44 touch targets in CSS (`chat.css:129–130`); `aria-live="polite"` on phase strip (`render.js:282`); keyboard navigation on popovers via click-outside pattern (`render.js:258–265`). Color contrast: glyph colors use hsl(210,80%,50%) / hsl(38,90%,50%) / hsl(0,75%,50%) — AA contrast on white background needs verification at runtime. |
| 8 | Sanitization | ✅ PASS | All `render.js` output passes through `sanitizeHTML()` (DOMPurify). Exception: `injectToneSwitchChip` (see Finding #1). Feed items use `escapeHTML()` on all fields (`render.js:322–326`). |
| 9 | CSS organization | ✅ PASS | All new rules in `dashboard/static/chat.css`; no inline styles; no Tailwind purge risk (CDN-based). |
| 10 | Test coverage | ⚠️ PARTIAL | Template smoke tests: 15 passing. `onPhase` JS callback: no test harness. Risk documented in S07 report. |

## Verdict

**approve** — S07 implementation is substantially correct. The MEDIUM finding (tone-switch chip sanitization bypass) is real but low-severity: it requires a malicious rerender SSE payload, which originates from the same LLM-composing service as the main stream. The LOW finding (no JS `onPhase` test) is a known risk documented by S07.

## Test Results

```
uv run pytest tests/dashboard/test_chat_workitem_templates.py tests/dashboard/test_chat_templates.py
→ 54 passed in 0.08s
```

`uv run ruff check dashboard/static/chat/` — All checks passed (JS files not linted by ruff).

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "F-00055",
  "completion_status": "complete",
  "review_verdict": "approve",
  "findings_critical": 0,
  "findings_high": 0,
  "findings_medium": 1,
  "findings_low": 1,
  "notes": "MEDIUM: tone-switch chip rerender bypasses DOMPurify in injectToneSwitchChip (render.js:388). LOW: no JS test harness for onPhase callback path. Both are addressable without blocking S09."
}
```
