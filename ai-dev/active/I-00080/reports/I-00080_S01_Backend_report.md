# I-00080 S01 Backend-impl Report

## What was done

Fixed the server-side Mermaid rendering in `dashboard/utils/markdown.py` so that
diagrams are self-contained and legible regardless of embedding context (dark
dashboard page, standalone HTML file, PDF export).

### Root cause

`mmdc` was called with only `-b white` and no theme/config, so Mermaid's default
`htmlLabels: true` produced `<foreignObject>` label `<div>` elements with no
enforced colour. When the SVG was embedded in a dark-mode dashboard page, those
labels inherited `color: rgb(255,255,255)` — invisible on the white diagram box.

### Changes

**`dashboard/utils/markdown.py`**

1. `_render_mermaid_mmdc` now:
   - Passes `-t default` to mmdc (Mermaid's `default` theme uses a light
     background with dark `#333`-ish text, and is fully deterministic).
   - Writes a `mermaid_config` JSON file with `themeVariables` setting
     `primaryTextColor`, `textColor`, `lineColor`, and `background` explicitly,
     and passes it to mmdc via `-c`/`--configFile`. This survives SVG
     serialisation even when `htmlLabels: true` puts text in `<foreignObject>`.
   - Changed `-b white` to the more precise `-b #ffffff`.

2. `_render_mermaid_blocks` now wraps the SVG in:
   ```html
   <div class="mermaid-diagram" style="overflow-x:auto;margin:1rem 0;background:#ffffff;color:#1e293b;border-radius:6px;padding:0.5rem;">
   ```
   The `color:#1e293b` on the wrapper div is a belt-and-braces cascade
   override: any `<foreignObject>` label `<div>` inside the SVG will inherit
   this colour and never render white-on-white, regardless of the host page's
   CSS. The Kroki fallback SVG gets the same wrapper treatment.

**`tests/unit/test_markdown_mermaid_legibility.py`** (new file)

4 tests covering:
- `test_mermaid_render_contains_enforced_dark_colour_token` — asserts `1e293b`
  appears in the rendered output when mmdc succeeds (RED before fix, GREEN after).
- `test_mermaid_render_does_not_produce_bare_white_labels` — asserts the
  wrapper div is present.
- `test_mermaid_render_kroki_fallback_also_has_wrapper` — Kroki SVG also gets
  the wrapper (same safety net applies).
- `test_render_mermaid_false_preserves_raw_block` — `render_mermaid=False`
  leaves the `language-mermaid` block intact for client-side rendering.

## Files changed

- `dashboard/utils/markdown.py` — mmdc now uses `-t default -c <config>` and
  wrapper div has explicit `color:#1e293b`.
- `tests/unit/test_markdown_mermaid_legibility.py` — new test file.

## Test results

```
tests/unit/test_markdown_mermaid_legibility.py::TestMermaidLegibility::test_mermaid_render_contains_enforced_dark_colour_token PASSED
tests/unit/test_markdown_mermaid_legibility.py::TestMermaidLegibility::test_mermaid_render_does_not_produce_bare_white_labels PASSED
tests/unit/test_markdown_mermaid_legibility.py::TestMermaidLegibility::test_mermaid_render_kroki_fallback_also_has_wrapper PASSED
tests/unit/test_markdown_mermaid_legibility.py::TestMermaidLegibility::test_render_mermaid_false_preserves_raw_block PASSED
```

4 passed, 0 failed. mmdc was available in this worktree so all 4 tests
exercised the actual render path (no skips).

## Preflight

| Check | Result |
|-------|--------|
| `make format` | ok (670 files already formatted after auto-fix) |
| `make typecheck` | ok (no issues in 240 source files) |
| `make lint` | ok (All checks passed) |

## Notes

- The approach uses `-t default` + `themeVariables.primaryTextColor: "#1e293b"`
  (slate-800, the same shade used by the client-side mermaid loader's `base`
  theme) + the wrapper `color:#1e293b` as a two-layer defence. The mmdc config
  file is the primary mechanism; the wrapper inline style is the safety net.
- The Kroki fallback SVG also receives the wrapper div, so it inherits the
  `color:#1e293b` from the host page context and is legible too.
- Caching is intentionally not added here — it belongs in the router layer
  (S05), keyed to `ProjectDoc.version`.
- `render_markdown_with_callouts` public signature is unchanged.
- The `make lint` check for Jinja2 `format`-filter calls was not triggered
  (no template changes in this step).