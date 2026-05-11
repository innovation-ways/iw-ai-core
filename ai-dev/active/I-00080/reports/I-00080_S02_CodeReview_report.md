# I-00080 S02 — Code Review of S01 (backend-impl)

## What Was Reviewed

**Step agent**: `backend-impl`
**Step reviewed**: S01 — server-side Mermaid render theme/label-colour fix
**Files changed**: `dashboard/utils/markdown.py`, `tests/unit/test_markdown_mermaid_legibility.py`

## Files Examined

| File | Status |
|------|--------|
| `dashboard/utils/markdown.py` | Changed by S01 |
| `tests/unit/test_markdown_mermaid_legibility.py` | Added by S01 |

## Design Contract (from `I-00080_Issue_Design.md`)

S01's scope (Requirement 1) was:
- `_render_mermaid_mmdc`: pass explicit `-t default` and `-c <config>` to mmdc so Mermaid's `themeVariables.primaryTextColor` / `textColor` survives SVG serialisation — enforcing dark legible labels.
- `_render_mermaid_blocks`: wrap the rendered SVG in a `<div class="mermaid-diagram" style="…color:#1e293b…">` as a safety net.
- Keep the kroki fallback.
- Keep the raw-`<pre>` fallback.
- No in-process cache (that's S05's job).

## Review Findings

### 1. Dark-mode legibility (AC1 / Requirement 1) — PASS

`_render_mermaid_mmdc` (line 291–359) now:
- Writes a `mermaid.json` config with `theme: default` and explicit `themeVariables` (line 304–308): `primaryTextColor: "#1e293b"`, `textColor: "#1e293b"`, `lineColor: "#334155"`, `background: "#ffffff"`.
- Passes `-t default` (line 336) and `-c <mermaid.json>` (line 339–340) to mmdc.
- Also passes `-b #ffffff` (line 334) for the puppeteer background.

The wrapper in `_render_mermaid_blocks` (lines 413–416) adds:
```html
<div class="mermaid-diagram" style="overflow-x:auto;margin:1rem 0;
  background:#ffffff;color:#1e293b;border-radius:6px;padding:0.5rem;">{svg}</div>
```

`color:#1e293b` (slate-800) on the wrapper forces any `<foreignObject>` label `<div>` inside the SVG to inherit a dark colour and not compute to `rgb(255,255,255)` in dark mode. This is a proper two-layer defence.

### 2. Fallbacks intact — PASS

- `_render_mermaid_to_svg` (line 268): tries mmdc first, falls back to kroki (line 285).
- `_render_mermaid_blocks` `_replace` (line 401): when `svg is None`, returns `match.group(0)` — the raw `<pre><code class="language-mermaid">` block is preserved.
- Kroki SVG is also wrapped in the `.mermaid-diagram` div (lines 413–416) — the same legibility wrapper is applied regardless of which renderer succeeded.

### 3. No regressions to the markdown pipeline — PASS

- `render_markdown` (line 435): unchanged.
- `render_markdown_with_callouts` (line 450): signature unchanged (`render_mermaid: bool = True` preserved), only calls `_render_mermaid_blocks` when `"language-mermaid" in result`.
- Callout-blockquote conversion (`_convert_callout_blockquotes`, line 467): untouched.
- `_MERMAID_CODE_RE` (line 89): unchanged pattern.

### 4. No module-level dict cache added — PASS

No caching added to `markdown.py`. S05 (api-impl) owns version-keyed disk caching.

### 5. Test quality — PASS with one observation

`tests/unit/test_markdown_mermaid_legibility.py` (150 lines, 4 tests):

- `test_mermaid_render_contains_enforced_dark_colour_token`: asserts the specific token `"1e293b"` in result when mmdc produces an SVG. Skips cleanly when mmdc is unavailable (detected by raw `<pre>` presence). ✅
- `test_mermaid_render_does_not_produce_bare_white_labels`: belt-and-braces check that `mermaid-diagram` class is present (proxy for "wrapper was applied"). Skips cleanly when mmdc is unavailable. ✅
- `test_mermaid_render_kroki_fallback_also_has_wrapper`: verifies kroki SVG is also wrapped. Skips cleanly. ✅
- `test_render_mermaid_false_preserves_raw_block`: verifies `render_mermaid=False` returns raw `language-mermaid` block and no `<svg>`. ✅

All 4 tests PASSED.

**Observation**: `test_mermaid_render_does_not_produce_bare_white_labels` is a weak assertion — it only checks `"mermaid-diagram" in result`, not an actual colour value. This is by design (the companion `test_mermaid_render_contains_enforced_dark_colour_token` does the colour check; this test is labelled "belt-and-braces"). This is acceptable.

### 6. Conventions / security — PASS

- `make lint` → All checks passed.
- `make format-check` → All files already formatted.
- No new subprocess timeouts beyond the existing 30 s mmdc / 20 s kroki.
- No hardcoded paths; `_resolve_chromium_binary` follows the existing pattern.
- No secrets or credentials introduced.

## Pre-Review Lint & Format Gate — PASS

```
make lint    → All checks passed!
make format-check → 670 files already formatted
```

No new violations introduced by S01.

## Test Verification — PASS

```
uv run pytest tests/unit/ -k markdown -v
32 passed, 0 failed
```

All 4 S01 legibility tests passed:
- `test_mermaid_render_contains_enforced_dark_colour_token` — PASSED
- `test_mermaid_render_does_not_produce_bare_white_labels` — PASSED
- `test_mermaid_render_kroki_fallback_also_has_wrapper` — PASSED
- `test_render_mermaid_false_preserves_raw_block` — PASSED

## Verdict

**PASS** — S01 correctly implements the dark-mode legibility fix. No CRITICAL, HIGH, or MEDIUM_FIXABLE findings.

---

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00080",
  "step_reviewed": "S01",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "4/4 legibility tests passed; 32 total markdown-related tests passed",
  "notes": "S01 correctly: (1) adds explicit -t default + -c mermaid.json with themeVariables.primaryTextColor=#1e293b to mmdc; (2) wraps the SVG in a .mermaid-diagram div with style='color:#1e293b' — two-layer defence against white-on-white in dark mode; (3) applies the same wrapper to kroki SVG output; (4) keeps raw-<pre> fallback when both renderers fail; (5) adds comprehensive unit tests that assert the specific colour token and skip cleanly when mmdc is unavailable. No regressions to the markdown pipeline. No module-level cache added. Lint and format checks clean."
}
```