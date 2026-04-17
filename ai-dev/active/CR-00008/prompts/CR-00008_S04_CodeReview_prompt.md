# CR-00008 S04 — Code Review of S03 (Layout / Scroll / Composer / Keyboard / Image paste)

**Work Item**: CR-00008
**Step**: S04
**Agent**: code-review-impl
**Reviews**: S03 (frontend-impl)

---

## Input Files

- `ai-dev/active/CR-00008/CR-00008_CR_Design.md`
- `ai-dev/active/CR-00008/prompts/CR-00008_S03_Frontend_prompt.md`
- `ai-dev/active/CR-00008/reports/CR-00008_S03_Frontend_report.md`
- `dashboard/templates/project_code.html`
- `dashboard/templates/chat/panel.html`
- `dashboard/templates/chat/composer.html`
- `dashboard/static/chat.css`
- `dashboard/static/chat/panel.js`
- `dashboard/static/chat/stream.js`
- `dashboard/static/chat/composer.js`
- New tests under `tests/dashboard/`

## Output Files

- `ai-dev/active/CR-00008/reports/CR-00008_S04_CodeReview_report.md`

## Review Checklist

### Layout and responsiveness

- [ ] `project_code.html` uses a 2-column grid with `var(--chat-width)` at ≥900px.
- [ ] Reading surface and chat panel have independent scroll containers (no linked scroll).
- [ ] Old `fragments/code_qa_panel.html` is deleted; no stale includes remain.
- [ ] Drawer fallback present for <900px; floating button opens/closes.

### Panel mechanics

- [ ] Width persists to `localStorage.iw_chat_width`, clamped 320..480.
- [ ] Drag handle resizes smoothly; cleans up listeners on `mouseup`.
- [ ] `Cmd+\` / `Ctrl+\` toggles collapse; keyboard listener is scoped / not duplicated on re-render.
- [ ] `role="region"` with `aria-label` on the panel container.
- [ ] `<div id="chat-messages" role="log" aria-live="polite" aria-relevant="additions">` present.
- [ ] All action buttons are real `<button>` with ≥44×44 min hit targets and visible focus rings.

### Composer

- [ ] Textarea: `Enter` = newline, `Cmd/Ctrl+Enter` = send.
- [ ] Slash menu: appears on `/`, keyboardable (↑/↓/Enter), closes on Esc or blur.
- [ ] Context chip auto-populated from `data-module-path` on load and on htmx `afterSwap`.
- [ ] Image input: paste + drag/drop + file picker all populate `#chat-image-chips`.
- [ ] MIME validation: JPEG/PNG/GIF/WEBP only; other types rejected with toast.
- [ ] On send with image chips → `multipart/form-data`; 501 response shows toast without clearing state.

### Scroll

- [ ] IntersectionObserver anchor releases stickiness on user scroll up.
- [ ] `#chat-scroll-to-bottom` appears only when released; clicking returns to bottom.
- [ ] First paint uses `behavior: 'instant'`.
- [ ] `min-height: 50dvh` applied to the last assistant message.

### SSE stream client

- [ ] `stream.js` parses both `event:` and `data:` lines (not just `data:`).
- [ ] Decodes `token.b64` via `atob` + `TextDecoder('utf-8')`. Round-trips correctly.
- [ ] Exposes `window.__iwChatCancel` that aborts the fetch.
- [ ] Does not render content itself — delegates via `onToken`/`onCitation`/`onDone`/`onError` callbacks with clear `TODO(S05)` markers at the placeholder renderer.
- [ ] No `eval`, no dynamic `script` injection, no `innerHTML` mutation.

### Accessibility

- [ ] Slash menu has `role="listbox"` + `aria-activedescendant`.
- [ ] Image chip "remove" buttons have descriptive `aria-label`.
- [ ] Focus management on collapse/expand: focus returns to the toggle button after collapse.
- [ ] Drawer: focus trapped while open; Esc closes and returns focus.

### Hygiene

- [ ] No CDN references added.
- [ ] No TypeScript / no npm / no build step introduced.
- [ ] Vanilla JS only; no IIFE leakage (uses `window.iwChat` namespace).
- [ ] `ruff check dashboard/` clean.
- [ ] Tests exist and pass for the five smoke cases listed in S03 Task 8.

## Severity definitions

- **CRITICAL** — blocks merge (security, broken contract, unusable panel, a11y blockers like missing `role="log"`).
- **HIGH** — correctness / contract issues (scroll fighting user, slash menu trap, image type bypass).
- **MEDIUM** — style / maintainability / focus management.
- **LOW** — polish.

## Report structure

Same as S02. End with a Verdict block.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00008",
  "completion_status": "complete",
  "reviewed_step": "S03",
  "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "blocking_next_step": false,
  "notes": ""
}
```
