# CR-00008 S06 — Code Review of S05 (rich-content rendering)

**Work Item**: CR-00008
**Step**: S06
**Agent**: code-review-impl
**Reviews**: S05

---

## Input Files

- `ai-dev/active/CR-00008/CR-00008_CR_Design.md`
- `ai-dev/active/CR-00008/prompts/CR-00008_S05_Frontend_prompt.md`
- `ai-dev/active/CR-00008/reports/CR-00008_S05_Frontend_report.md`
- `dashboard/templates/chat/message.html` and `parts/*.html`
- `dashboard/static/chat/render.js`, `citations.js`, `actions.js`
- `dashboard/static/vendor/` (all vendored libs + LICENSE files)
- `dashboard/static/vendor/LICENSES.md`
- `dashboard/templates/base.html` (verify CDN removal)
- New tests under `tests/dashboard/`

## Output Files

- `ai-dev/active/CR-00008/reports/CR-00008_S06_CodeReview_report.md`

## Review Checklist

### Sanitization (CRITICAL layer)

- [ ] **No `innerHTML =`** anywhere on the accumulating message element. Grep `dashboard/static/chat/` for `innerHTML` and verify every hit is read-only (e.g. reading existing text) or explicitly benign.
- [ ] **No per-chunk sanitization.** DOMPurify is invoked on the accumulated buffer, not per delta.
- [ ] DOMPurify configured with `FORBID_TAGS` including `script`, `iframe`, `object`, `embed`, `svg`; `FORBID_ATTR` including `onclick`, `onload`, `onerror`, and any `on*` handler.
- [ ] Link scheme allowlist enforced (`http`, `https`, `mailto`); `javascript:` and `data:` links are neutralised (rendered as text or stripped).
- [ ] All `<a target="_blank">` have `rel="noopener noreferrer"`.
- [ ] The XSS test (`test_chat_security.py`) exists and asserts both script-tag and `on*` attribute removal.

### Streaming correctness

- [ ] Code-block streaming uses the two-phase pattern (plain `<pre>` → highlighted on close). No flicker of literal `` ``` ``.
- [ ] Table cells do not render with trailing `|` artefacts during streaming.
- [ ] Citation chip `[N]` rehydrates as `onCitation` events arrive after some text has already rendered.

### Code blocks

- [ ] Copy button present on every code block. `aria-label="Copy code"` (or equivalent) non-empty. `min-h-[44px] min-w-[44px]`.
- [ ] Copy payload is the **raw source**, not the highlighted DOM text.
- [ ] Language label present when a language is declared; absent or generic otherwise.

### Tables

- [ ] Zebra striping via CSS (not per-row classes).
- [ ] Copy-CSV button exists, escapes quotes / commas / newlines correctly.

### Citations + Sources

- [ ] Each `[N]` is a real `<button>` with `aria-haspopup`. Popover contains label + snippet + source link.
- [ ] `Sources (N)` block collapsed by default; uses `<details>` or an accessible equivalent.
- [ ] Citations with no citations yielded: Sources block absent or clearly hidden (no "Sources (0)" line).

### Per-message actions

- [ ] Copy / Regenerate / 👍 / 👎 all real `<button>`. 44×44 targets. Visible focus.
- [ ] Copy copies the **source markdown**, not rendered HTML.
- [ ] Regenerate only on the last assistant message. Disabled during stream.
- [ ] 👎 form has four categorized checkboxes + optional text (max 280 chars). Esc collapses.

### Vendoring + licenses

- [ ] Every vendored library has a LICENSE file in its folder.
- [ ] `dashboard/static/vendor/LICENSES.md` lists every library with SPDX identifier + source URL.
- [ ] No GPL-licensed code. ELK loader (if present here — otherwise in S07) is EPL-2.0 with notices preserved.
- [ ] No CDN references remain in `base.html`. Grep: `cdn.jsdelivr.net`, `cdnjs`, `unpkg`, `marked`.
- [ ] `dashboard/templates/fragments/item_artifacts.html` no longer references `marked.parse` / `window.marked`. The inline script uses `iwChat.renderMarkdownStatic(text)` and inserts a sanitized fragment via `replaceChildren` (or equivalent) — NOT `innerHTML = marked.parse(...)`. Grep the file to confirm.

### Bundle size decision

- [ ] Report explicitly records the measured gzipped bundle size and the Streamdown vs. a-la-carte choice per Task 1 criterion.

### Accessibility

- [ ] Every `<button>` has a non-empty accessible name (text or `aria-label`).
- [ ] No `onclick` on `<div>` / `<span>`.
- [ ] Focus rings visible on all interactive elements.

### Hygiene

- [ ] Each module under 400 lines.
- [ ] `ruff check dashboard/` clean.
- [ ] No new test regressions outside S05's scope.

## Severity definitions

Same as S02. Any sanitization or CDN-residue finding is **CRITICAL** by default.

## Report

Markdown with findings + Verdict block.

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "CR-00008",
  "completion_status": "complete",
  "reviewed_step": "S05",
  "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "blocking_next_step": false,
  "notes": ""
}
```
