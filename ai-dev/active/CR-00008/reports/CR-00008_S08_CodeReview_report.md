# CR-00008 S08 — Code Review of S07 (Mermaid ELK + brand + sandbox)

**Work Item**: CR-00008
**Step**: S08
**Agent**: code-review-impl
**Reviewed Step**: S07
**Completion**: complete

---

## Summary

S07 delivered a functional Mermaid rendering pipeline with sandboxed iframes and ELK layout. Three issues were found — one CRITICAL (missing `look: 'handDrawn'`), one HIGH (CDN Mermaid loaded globally in `base.html`). Both were verified in source. The remaining findings are MEDIUM/LOW.

---

## Security (CRITICAL layer)

| # | Finding | File | Line | Severity |
|---|---------|------|------|----------|
| S08-01 | `securityLevel: 'sandbox'` is correct — `'loose'` or `'antiscript'` not found | `dashboard/static/chat/mermaid.js` | 168 | PASS |
| S08-02 | Sandboxed `<iframe sandbox="allow-scripts allow-same-origin">` present in DOM | `dashboard/static/chat/mermaid.js` | 200 | PASS |
| S08-03 | `mermaid.parse()` called before `mermaid.render()` — invalid DSL rejected, no render on failure | `dashboard/static/chat/mermaid.js` | 152–161 | PASS |
| S08-04 | No path for raw model-emitted SVG to reach DOM outside the sandboxed iframe — `srcdoc` is used, not `src=` with unsanitized content | `dashboard/static/chat/mermaid.js` | 208–219 | PASS |

**Verdict**: CRITICAL security layer PASSES. No sandbox downgrade found.

---

## Correctness

| # | Finding | File | Line | Severity |
|---|---------|------|------|----------|
| S08-05 | `layout: 'elk'` applied — confirmed via `wrapper.setAttribute('data-iw-layout', 'elk')` and `elk: { layout: 'elk' }` in config | `mermaid.js` | 169, 182 | PASS |
| S08-06 | **`look: 'handDrawn'` is MISSING from the Mermaid config** | `mermaid.js` | 167–175 | **CRITICAL** |
| S08-07 | `themeVariables` sourced from CSS custom properties via `getComputedStyle()` → `toRgbHex()` — no hard-coded palette duplication | `mermaid.js` | 43–60 | PASS |
| S08-08 | Failure chip matches the template — Retry button, ⚠ label, collapsible source | `mermaid.js` | 62–97; `mermaid.html` | PASS |
| S08-09 | Retry re-attempts `upgradeMermaidBlock` on the same DSL — no LLM round-trip | `mermaid.js` | 80–92 | PASS |
| S08-10 | Upgrade only runs after stream completion — hooked in `onDone`, not mid-stream | `render.js` | 307–309 | PASS |

**Verdict**: S08-06 is a CRITICAL deviation from AC8. The `look: 'handDrawn'` style is absent from the config block. Without it, diagrams render in default (solid, non-sketchy) style instead of the hand-drawn look specified in the design.

```js
// Current config (line 167–175) — MISSING look:
var config = {
  securityLevel: 'sandbox',
  elk: { layout: 'elk', useGles: false },
  theme: 'base',
  themeVariables: themeVars,
  // ← look: 'handDrawn' is absent
};
```

---

## Vendoring + Licensing

| # | Finding | File | Severity |
|---|---------|------|----------|
| S08-11 | Mermaid LICENSE (MIT) present | `dashboard/static/vendor/mermaid/LICENSE` | PASS |
| S08-12 | ELK loader LICENSE (EPL-2.0) present with notices preserved verbatim | `dashboard/static/vendor/mermaid-elk/LICENSE` | PASS |
| S08-13 | `LICENSES.md` updated with SPDX IDs, source URLs, versions for both Mermaid and elkjs | `dashboard/static/vendor/LICENSES.md` | PASS |
| S08-14 | No GPL code found in vendored assets | — | PASS |
| S08-15 | **Mermaid bundle is loaded in `base.html` via CDN on ALL pages, not only on the code module page** | `dashboard/templates/base.html` | **HIGH** |

**S08-15 detail**: The hard rule states "NEVER inline-load the huge Mermaid bundle in `base.html`. Load it only on the code module page." The CDN `<script>` tag on line 112 of `base.html` loads Mermaid on every page. The S07 report (line 102) incorrectly claims the bundle is "only loaded on the code module page."

The local vendored `mermaid.min.js` under `dashboard/static/vendor/mermaid/` is separate from the CDN script in `base.html`. The CDN script on line 112 serves the architecture diagrams (non-chat, server-side rendered Mermaid) via `mermaid.init()` — this is a distinct use case from the chat panel's `upgradeMermaidBlock` which uses the vendored local bundle. However, the prompt hard rule is unambiguous: Mermaid must NOT be in `base.html`.

---

## Accessibility

| # | Finding | File | Line | Severity |
|---|---------|------|------|----------|
| S08-16 | Retry button has `aria-label="Retry diagram render"` — non-empty | `mermaid.html` | 5–6 | PASS |
| S08-17 | Expand button has `aria-label="Expand diagram full-screen"` — non-empty | `mermaid.js` | 191 | PASS |
| S08-18 | iframe container has no keyboard-focusable wrapper; the caption `<p>` and button are focusable but the diagram itself is not reachable via keyboard | `mermaid.js` | 184–192 | MEDIUM |

**S08-18 detail**: The `<p>` caption and expand `<button>` are keyboard-focusable, but the diagram iframe itself has no focusable descendant. The wrapper `div.mermaid-wrapper` is not tabbable. This is not a focus trap (no `tabindex=-1` traps), but the iframe content is only reachable via the expand button — not ideal for AT users who might want to interact with the diagram content.

---

## Hygiene

| # | Finding | Severity |
|---|---------|----------|
| S08-19 | `mermaid.js` is 249 lines — under 400 line limit | PASS |
| S08-20 | `ruff check` on `.js` files reports syntax errors (ruff does not lint modern JS); these are false positives from ruff treating JS as Python | LOW (tool limitation) |
| S08-21 | `render.js` is 345 lines | PASS |

---

## Tests

| Test | Status | Notes |
|------|--------|-------|
| `test_chat_templates.py::TestMermaidTemplate` | 4/4 PASS | Template smoke tests — retry button, error label, details/source |
| `test_chat_mermaid.py::TestMermaidRendering` | Written, Playwright not available | Browser tests structurally complete; fixture works when Playwright installed |

**Coverage gap**: No test asserts `look: 'handDrawn'` is in the generated config — S08-06 would have been caught by `test_good_mermaid_renders_iframe` if it inspected the Mermaid config object.

---

## Findings Summary

| Severity | Count | Items |
|----------|-------|-------|
| CRITICAL | 1 | S08-06 — `look: 'handDrawn'` missing from config |
| HIGH | 1 | S08-15 — CDN Mermaid in `base.html` |
| MEDIUM | 1 | S08-18 — iframe not keyboard-reachable |
| LOW | 1 | S08-20 — ruff JS false positives (tool limitation) |
| **TOTAL** | **4** | |

---

## Required Fixes (Blocking Next Step)

1. **S08-06 (CRITICAL)**: Add `look: 'handDrawn'` to the `config` object in `mermaid.js` (around line 167–175):
   ```js
   var config = {
     securityLevel: 'sandbox',
     elk: { layout: 'elk', useGles: false },
     theme: 'base',
     themeVariables: themeVars,
     look: 'handDrawn',
   };
   ```
2. **S08-15 (HIGH)**: Remove the CDN Mermaid `<script>` from `base.html` (line 111–119) or scope it so it only loads on the code module page (`project_code.html`). If the architecture diagrams need the CDN mermaid, move it to `project_code.html`'s `{% block head %}`.

---

## Files Reviewed

| File | Lines | Status |
|------|-------|--------|
| `dashboard/static/chat/mermaid.js` | 249 | 1 CRITICAL issue |
| `dashboard/templates/chat/parts/mermaid.html` | 12 | Clean |
| `dashboard/static/chat/render.js` | 345 | Clean |
| `dashboard/static/vendor/mermaid/LICENSE` | 13 | Clean |
| `dashboard/static/vendor/mermaid-elk/LICENSE` | 12 | Clean |
| `dashboard/static/vendor/LICENSES.md` | 87 | Clean |
| `dashboard/templates/base.html` | 305 | 1 HIGH issue |
| `tests/dashboard/browser/test_chat_mermaid.py` | 163 | Tests written |
| `tests/dashboard/test_chat_templates.py` (TestMermaidTemplate) | 36 | 4/4 pass |

---

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "code-review-impl",
  "work_item": "CR-00008",
  "completion_status": "complete",
  "reviewed_step": "S07",
  "findings": {"critical": 1, "high": 1, "medium": 1, "low": 1},
  "blocking_next_step": true,
  "notes": "S07 must fix S08-06 (add look:'handDrawn') and S08-15 (remove CDN mermaid from base.html) before S09 can proceed."
}
```