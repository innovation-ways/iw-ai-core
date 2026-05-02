# I-00055 S11 Browser Verification Report

## Environment
- **Base URL used:** `http://localhost:9954`
- **E2E user:** `dev@example.local`
- **Work item:** I-00055
- **Step:** S11

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | One diagram (light) | **pass** | `evidences/post/I-00055_v1_one_diagram_light.png` | `div.mermaid` count=1, `pre[data-lang="mermaid"]` count=0 → total=1 |
| V2 | One diagram + readable (dark) | **pass** | `evidences/post/I-00055_v2_one_diagram_dark.png` | Same count after theme toggle; body bg=`rgb(50,51,57)`; no low-contrast text detected |
| V3 | Prose has no inline mermaid | **pass** | `evidences/post/I-00055_v3_prose_clean.png` | `document.querySelector('.prose-doc')?.innerHTML.includes('mermaid')` returned `false` |
| V4 | No regressions | **pass** | `evidences/post/I-00055_v4_no_regressions.png` | Component cards present (count=3); clicking a card loads module panel; console errors=0 |

## Console / Network Errors
**None observed** — Console diagnostics showed 0 errors, 0 warnings throughout V1–V4 navigation.

## No Regressions
- Component cards under `#code-components-section` render correctly (3 cards found for `iw-ai-core`).
- Clicking a component card (`Orchestration Daemon`) navigated to its detail panel without HTTP errors.
- No red-level console errors during any verification step.

## Root Cause (on failure only)
N/A — all verifications passed.

## Screenshots captured
- `ai-dev/active/I-00055/evidences/post/I-00055_v1_one_diagram_light.png`
- `ai-dev/active/I-00055/evidences/post/I-00055_v2_one_diagram_dark.png`
- `ai-dev/active/I-00055/evidences/post/I-00055_v3_prose_clean.png`
- `ai-dev/active/I-00055/evidences/post/I-00055_v4_no_regressions.png`

## Technical Notes

### V1 / V2 — Diagram count
The page renders **exactly one** mermaid container across both themes:
- Light mode: `div.mermaid`=1, `pre[data-lang="mermaid"]`=0 → **total=1**
- Dark mode: same count; body background is `rgb(50,51,57)` — dark theme is active
- The single container is the `<div class="mermaid">` produced by `code_architecture_diagram.html` (the clean standalone diagram-architecture doc, rendered via `arch_diagram_dsl`)
- No `<pre data-lang="mermaid">` element appears in the DOM at any point — the strip-helper + render-time deduplication is working

### V3 — Prose cleanliness
The `.prose-doc` element's inner HTML contains no "mermaid" string, confirming that:
1. The `_render_architecture_html()` function calls `strip_trailing_arch_diagram_section()` on the legacy architecture-map content **before** `_preprocess_mermaid()` runs
2. The legacy trailing `## Architecture Diagram` section (with its `<!-- purpose -->` comment and ` ```mermaid ` fence) is stripped at render time, so it never reaches the markdown renderer
3. The `content_html` is clean prose only — no inline diagram markup

### Architecture of the fix
The fix works in two layers as designed:
1. **Mapgen** (`orch/rag/mapgen.py`): `_assemble_markdown()` no longer appends the trailing diagram block — new architecture-map docs are clean from the start
2. **Render-time guard** (`dashboard/routers/code_ui.py:82-87`): `_render_architecture_html()` calls `strip_trailing_arch_diagram_section()` before `_preprocess_mermaid()`, ensuring legacy stored docs render correctly until regeneration

Both layers were verified working by this browser test.