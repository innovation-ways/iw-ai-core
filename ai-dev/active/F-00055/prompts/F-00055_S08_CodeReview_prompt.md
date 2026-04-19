# F-00055_S08_CodeReview_prompt

**Work Item**: F-00055 — Work-item-aware code chat
**Step**: S08
**Agent**: code-review-impl

---

## Input Files

- `ai-dev/active/F-00055/F-00055_Feature_Design.md` (AC1, AC5, AC6, AC10; Invariants 4, 6, 7, 8)
- `ai-dev/active/F-00055/reports/F-00055_S07_Frontend_report.md`
- All files changed in S07

## Output Files

- `ai-dev/active/F-00055/reports/F-00055_S08_CodeReview_report.md`

## Review Focus

Review S07 (frontend + templates). Findings with CRITICAL/HIGH/MEDIUM/LOW.

### Must-check items

1. **Phase strip behavior (AC6)** — strip appears before first token, updates on each phase, collapses on first token into a "based on N items" note.
2. **Work-item chip rendering (AC10)** — type glyph is correct (F/CR/I), link target is `/project/{pid}/item/{id}`, popover opens on click, keyboard-accessible.
3. **Feed order (AC1, Invariant 8)** — chronological ascending by `created_at`; cap at 5; overflow link exists if count > 5.
4. **Tone-switch chip (AC5)** — disabled during streaming; flips label; re-fires query with `tone:technical` or `tone:functional` chip; replaces bubble on new done event.
5. **Slash-alias registration** — `/why`, `/history`, `/findusages` appear in menu; `/explain`, `/diagram` untouched.
6. **No htmx regressions** — the chat panel still uses vanilla JS + SSE; no htmx calls were added.
7. **Accessibility** — 44×44 touch targets; aria-live="polite" on phase strip; keyboard navigation on popovers; color contrast for type glyphs meets WCAG AA.
8. **Sanitization** — all template-rendered data passes through `DOMPurify.sanitize` via `render.js`; no XSS vector in work-item title/summary.
9. **CSS organization** — new rules live in `dashboard/static/chat.css` (not inline in JS); no Tailwind purge break.
10. **Test coverage** — template-rendering tests exist; `onPhase` JS test harness or equivalent is present (or risk called out).

### Project conventions

- No build step — Tailwind CDN.
- Fragments don't extend `base.html`.
- `DOMPurify` is the sanitization layer; all dynamic HTML goes through it.

## Review Output Format

Same as S02: findings table + verdict + result contract.

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "F-00055",
  "completion_status": "complete",
  "review_verdict": "approve|approve-with-fixes|reject",
  "findings_critical": 0,
  "findings_high": 0,
  "findings_medium": 0,
  "findings_low": 0,
  "notes": ""
}
```
