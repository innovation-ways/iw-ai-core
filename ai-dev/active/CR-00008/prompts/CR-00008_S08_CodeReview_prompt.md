# CR-00008 S08 — Code Review of S07 (Mermaid ELK + brand + sandbox)

**Work Item**: CR-00008
**Step**: S08
**Agent**: code-review-impl
**Reviews**: S07

---

## Input Files

- `ai-dev/active/CR-00008/CR-00008_CR_Design.md`
- `ai-dev/active/CR-00008/prompts/CR-00008_S07_Frontend_prompt.md`
- `ai-dev/active/CR-00008/reports/CR-00008_S07_Frontend_report.md`
- `dashboard/static/vendor/mermaid/` and `mermaid-elk/` (source + LICENSE)
- `dashboard/static/vendor/LICENSES.md`
- `dashboard/static/chat/mermaid.js`
- `dashboard/templates/chat/parts/mermaid.html`
- `dashboard/static/chat/render.js` (upgraded)
- Tests under `tests/dashboard/`

## Output Files

- `ai-dev/active/CR-00008/reports/CR-00008_S08_CodeReview_report.md`

## Review Checklist

### Security (CRITICAL layer)

- [ ] `securityLevel: 'sandbox'` — exact literal. Never `'loose'` or `'antiscript'`.
- [ ] Sandboxed iframe is present in the rendered DOM with a `sandbox` attribute. Verify via test.
- [ ] `mermaid.parse()` is called **before** `mermaid.render()`. No render on invalid DSL.
- [ ] No path allows raw model-emitted SVG to reach the DOM outside the sandboxed iframe.

### Correctness

- [ ] `layout: 'elk'` applied (asserted in test via `data-iw-layout` wrapper).
- [ ] `look: 'handDrawn'` applied.
- [ ] `themeVariables` sourced from CSS custom properties — no hard-coded palette duplication. Named colors NOT used.
- [ ] Failure chip matches the template and includes a working Retry button.
- [ ] Retry re-attempts upgrade without calling the LLM.
- [ ] Upgrade only runs after stream completion (hooked in `onDone`), not mid-stream.

### Vendoring + licensing

- [ ] Mermaid LICENSE (MIT) present under `dashboard/static/vendor/mermaid/`.
- [ ] ELK loader LICENSE (EPL-2.0) present with notices preserved verbatim.
- [ ] `LICENSES.md` updated with SPDX IDs, source URLs, versions.
- [ ] No GPL code anywhere.
- [ ] Mermaid bundle is loaded **only on the code module page** (not in `base.html`).

### Accessibility

- [ ] Failure chip's Retry button has a non-empty `aria-label`.
- [ ] The expand/modal-open button on successful diagrams has a non-empty `aria-label`.
- [ ] The iframe container exposes a focusable descendant or the caption is keyboard-focusable; the diagram is not a focus trap.

### Hygiene

- [ ] `mermaid.js` module is under 400 lines.
- [ ] No console errors when rendering a valid diagram.
- [ ] `ruff check` clean.

### Tests

- [ ] Playwright tests (or jsdom fallback) exist for: good-diagram upgrade, invalid-diagram failure chip, Retry click, no-console-errors.
- [ ] Test assertions actually verify ELK usage (via the wrapper `data-iw-layout`).

## Severity definitions

Same as previous CodeReview steps. Any sandbox-level downgrade is **CRITICAL**.

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "CR-00008",
  "completion_status": "complete",
  "reviewed_step": "S07",
  "findings": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "blocking_next_step": false,
  "notes": ""
}
```
