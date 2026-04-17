# CR-00008 S07 — Frontend: Mermaid with ELK layout + brand theme + sandboxed iframe

**Work Item**: CR-00008
**Step**: S07
**Agent**: frontend-impl

---

## Input Files (read first)

- `CLAUDE.md`, `dashboard/CLAUDE.md`
- `ai-dev/active/CR-00008/CR-00008_CR_Design.md` — AC8, AC9, AC15
- `docs/research/R-00051-beautiful-diagram-tools.md` — F1 (ELK), F10 (skill pattern), F12 (integration), themeVariables notes
- `docs/research/R-00050-rich-content-chat-patterns.md` — F5 (Mermaid + parse validation + sandbox)
- `skills/iw-brand-config/` — brand palette source of truth
- `dashboard/static/chat/render.js` (S05) — the fence pass-through site
- `dashboard/static/theme.css` — existing CSS variables (`--primary`, `--accent`, `--muted`, `--border`, `--foreground`, `--background`)

## Output Files

- **New vendored assets**:
  - `dashboard/static/vendor/mermaid/` — Mermaid library (MIT) + LICENSE
  - `dashboard/static/vendor/mermaid-elk/` — ELK loader (EPL-2.0) + LICENSE (preserve notices)
  - Update `dashboard/static/vendor/LICENSES.md` with both entries
- **New**: `dashboard/templates/chat/parts/mermaid.html`
- **New**: `dashboard/static/chat/mermaid.js`
- **New report**: `ai-dev/active/CR-00008/reports/CR-00008_S07_Frontend_report.md`
- **Modify**: `dashboard/static/chat/render.js` — wire the mermaid upgrade hook to the `<pre data-lang="mermaid">` placeholder S05 leaves behind

## Scope

Upgrade every ` ```mermaid ` fenced block in assistant messages into a beautiful, sandboxed, parse-validated diagram. Nothing else.

## Tasks

### Task 1 — Vendor Mermaid + ELK loader

- Vendor the Mermaid UMD bundle (latest 11.x stable, MIT) and the ELK layout loader. Place under `dashboard/static/vendor/mermaid/` and `dashboard/static/vendor/mermaid-elk/`.
- Copy LICENSE files into each folder. **Preserve the EPL-2.0 notice for the ELK loader verbatim.**
- Update `dashboard/static/vendor/LICENSES.md`: add SPDX IDs (`MIT`, `EPL-2.0`), source URLs, versions.

### Task 2 — `dashboard/static/chat/mermaid.js`

Export one function:

```js
window.iwChat.upgradeMermaidBlock = function (preEl) { ... }
```

`preEl` is an existing `<pre data-lang="mermaid"><code>...</code></pre>` left by `render.js`. Behavior:

1. Extract the raw DSL from `preEl.textContent`.
2. Call `mermaid.parse(dsl, { suppressErrors: true })`. If it returns `false`: render the failure chip (Task 3) and return.
3. Assign a unique id `iw-mermaid-<counter>`.
4. Initialize Mermaid with a config that sets:
   - `securityLevel: 'sandbox'`
   - `layout: 'elk'`
   - `look: 'handDrawn'`
   - `themeVariables`: map from CSS custom properties on `document.documentElement` (read via `getComputedStyle(document.documentElement).getPropertyValue('--primary')` etc.) → `primaryColor`, `primaryBorderColor`, `primaryTextColor`, `lineColor`, `tertiaryColor`, `background`, `fontFamily`. Only hex / rgb values (Mermaid rejects named colors — verify).
5. Render via `mermaid.render(id, dsl)` and insert the resulting sandboxed iframe DOM in place of `preEl`. Wrap the iframe in a container div with a small caption ("Diagram — click to expand") and a button that opens the diagram full-screen in a modal.
6. Add a `try/catch` around render; on post-parse failure render the failure chip.

### Task 3 — `dashboard/templates/chat/parts/mermaid.html` and the failure chip

The template is the server-rendered fallback (used by the Sources panel preview etc.). The failure chip is emitted client-side when `mermaid.parse()` rejects or render throws:

```html
<div class="mermaid-error rounded-md border border-destructive/20 bg-destructive/5 p-3 text-xs">
  <div class="flex items-center justify-between gap-2">
    <span class="text-destructive">⚠ Diagram error</span>
    <button type="button" class="mermaid-retry min-h-[44px] min-w-[44px]" aria-label="Retry diagram render">↻ Retry</button>
  </div>
  <details class="mt-2">
    <summary class="cursor-pointer">Show source</summary>
    <pre class="mt-2 overflow-x-auto"><code></code></pre>
  </details>
</div>
```

Retry behavior: re-attempts `upgradeMermaidBlock` on the same DSL. No LLM round-trip (auto-repair is deferred).

### Task 4 — Brand-overlay CSS (if needed)

If Mermaid's `themeVariables` alone does not pick up the brand palette (e.g. sandbox iframe isolation), add a small CSS overlay applied to the iframe container (not inside — the sandbox blocks that). Prefer `themeVariables` as the primary mechanism; only fall back to overlay CSS if strictly necessary, and document the reason in the report.

### Task 5 — Wire into `render.js`

After the message stream completes (in `onDone`), scan the message body for `pre[data-lang="mermaid"]` and call `iwChat.upgradeMermaidBlock` on each. Do NOT attempt upgrade mid-stream — wait for the fence to close.

### Task 6 — Tests (RED → GREEN)

Under `tests/dashboard/`:

- `test_chat_mermaid_template.py`:
  - `parts/mermaid.html` renders with the Retry button, error label, and a details/summary showing source.
- `tests/dashboard/browser/test_chat_mermaid.py` (Playwright):
  - Load a page with a known-good flowchart of 8+ nodes embedded in a fake assistant response (use a test route or stub fixture).
  - Wait for upgrade.
  - Assert the mermaid iframe is present with `sandbox` attribute; assert `layout=elk` (via a `data-iw-layout="elk"` attribute we set on the wrapper container for test verification).
  - Load a response with invalid Mermaid (`flowchart TD\n  A -->`); assert the failure chip appears and clicking Retry re-runs (still fails, chip remains).
  - Assert no console errors.

If Playwright is not feasible, replace with a Mermaid unit test using `jsdom` (but prefer Playwright).

## Hard rules

- **NEVER** set `securityLevel: 'loose'` or `'antiscript'`. Always `'sandbox'`.
- **NEVER** accept named colors in `themeVariables` — hex / rgb only.
- **NEVER** call LLM auto-repair — deferred.
- **NEVER** inline-load the huge Mermaid bundle in `base.html`. Load it only on the code module page (add to `project_code.html`'s extra-scripts block or a dedicated include).
- Brand-theme values must come from CSS vars. No hard-coded palette duplication.
- ELK loader license notices preserved.
- Bundle size note: Mermaid 11.x is ~1.2MB minified; only load on the code page.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run ruff check dashboard/
uv run pytest tests/dashboard/ -k "chat_mermaid" -v
```

Zero failures. Playwright tests may be marked `pytest.mark.browser` and skipped automatically in CI if the runner is headless-unfriendly — but they MUST exist and pass locally before reporting done.

## Subagent Result Contract

```json
{
  "step": "S07",
  "agent": "frontend-impl",
  "work_item": "CR-00008",
  "completion_status": "complete|partial|blocked",
  "files_changed": [...],
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "State Mermaid version vendored and whether the brand-overlay CSS fallback was needed."
}
```
