# I-00074: PDF Export Missing Diagram Labels — WeasyPrint Does Not Support SVG foreignObject

**Type**: Issue
**Severity**: High
**Created**: 2026-05-09
**Reported By**: Sergio Gaspar (manual testing)
**Status**: Approved

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

No migrations. This item modifies only PDF rendering logic and tests.

## Description

Documentation pages that contain Mermaid diagrams export PDFs without any node labels —
only empty boxes are visible. WeasyPrint, the current PDF renderer, does not support
SVG `<foreignObject>`, which is how Mermaid CLI renders node labels (as embedded HTML
`<p>` / `<span>` elements). The fix replaces all three WeasyPrint call-sites in
`dashboard/routers/docs.py` with a headless Chromium subprocess (`--print-to-pdf`),
reusing the `_PLAYWRIGHT_CHROME` constant already defined in `dashboard/utils/markdown.py`.

## Project Context

Read `CLAUDE.md` and `dashboard/CLAUDE.md` for architecture, conventions, and hard rules.
The dashboard is FastAPI + Jinja2 + htmx (port 9900). PDF export uses a standalone
`pdf/doc_pdf.html` template (all CSS inline — works with `file://` URLs). The
Playwright-managed Chromium binary at `~/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome`
is already used by mmdc for SVG rendering and is confirmed to support `--print-to-pdf`.

## Browser Evidence

Pre-fix investigation was conducted in the previous session (2026-05-09).

- The dark-mode diagram label issue (white labels on light boxes) was fixed in CR-00039 by
  appending CSS to `dashboard/static/styles.css`.
- The PDF export issue is a separate, deeper problem: WeasyPrint silently discards all
  `<foreignObject>` subtrees from SVG, so labels are absent regardless of color. This was
  confirmed by code analysis of WeasyPrint's known SVG limitations.
- Browser capture of a PDF download is not directly screenshottable in Playwright. Root cause
  evidence is the code path at `dashboard/routers/docs.py:168-173` (WeasyPrint import +
  `HTML(string=...).write_pdf()`).

Evidence status: **Deferred — PDF binary output not capturable via Playwright screenshot;
root-cause confirmed via code analysis + WeasyPrint SVG limitation documentation.**

## Steps to Reproduce

1. Open the dashboard at `http://iw-dev-01:9900/project/iw-ai-core/docs/`
2. Navigate to a document that contains Mermaid diagram code blocks
   (e.g., `diagram-architecture`)
3. Click **Download PDF** or open the inline PDF view
4. Inspect the downloaded PDF

**Expected**: PDF contains Mermaid diagrams with node labels fully rendered

**Actual**: PDF contains only diagram shapes (rectangles, arrows) with empty boxes —
all node label text is absent

## Root Cause Analysis

Mermaid CLI (`mmdc`) renders diagrams as SVG with node labels encoded as HTML `<p>` and
`<span>` elements inside SVG `<foreignObject>` elements. `<foreignObject>` embeds
arbitrary HTML inside SVG.

WeasyPrint's SVG renderer is documented to **not support `<foreignObject>`** — it silently
discards the entire subtree on encounter. Since node labels live exclusively inside
`<foreignObject>`, the resulting PDF contains only the SVG geometry (rectangles, arrows,
edges) with no text.

Three WeasyPrint call-sites in `dashboard/routers/docs.py`:

| Line | Route / Function | Usage |
|------|-----------------|-------|
| 168–173 | `docs_pdf_view` (GET `.../pdf/view`) | Inline iframe PDF |
| 216–235 | `docs_pdf` (GET `.../pdf`) | Download + disk cache |
| 914–923 | `_make_render_pdf_fn()` | Export bundle factory |

All three use `from weasyprint import HTML; HTML(string=html_content).write_pdf()`.

The fix: add `render_pdf_chromium(html_content: str) -> bytes | None` to
`dashboard/utils/markdown.py`, which writes HTML to a temp file and calls:

```
chrome --headless --disable-gpu --no-sandbox --print-to-pdf=<outpath> file://<htmlpath>
```

Then replace all three WeasyPrint call-sites with `render_pdf_chromium()`.

The `_PLAYWRIGHT_CHROME` constant (already in `dashboard/utils/markdown.py:34-36`) points
to the same Chromium binary. Verified: Chromium supports `--print-to-pdf` and correctly
renders `<foreignObject>` HTML content.

## Affected Components

| Component | File | Impact |
|-----------|------|--------|
| PDF inline view | `dashboard/routers/docs.py:168-173` | WeasyPrint strips labels |
| PDF download + cache | `dashboard/routers/docs.py:216-235` | WeasyPrint strips labels |
| Export bundle PDF factory | `dashboard/routers/docs.py:914-923` | WeasyPrint strips labels |
| Markdown rendering helper | `dashboard/utils/markdown.py` | New `render_pdf_chromium()` added here |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Add `render_pdf_chromium()` to `markdown.py`; replace 3 WeasyPrint call-sites in `docs.py` | — |
| S02 | code-review-impl | Review S01 output | — |
| S03 | tests-impl | Reproduction test + regression tests | — |
| S04 | code-review-impl | Review S03 tests | — |
| S05 | code-review-final-impl | Global review of all work | — |
| S06 | qv-gate | `make lint` | — |
| S07 | qv-gate | `make format-check` | — |
| S08 | qv-gate | `make type-check` | — |
| S09 | qv-gate | `make arch-check` | — |
| S10 | qv-gate | `make security-sast` | — |
| S11 | qv-gate | `make test-unit` | — |
| S12 | qv-gate | `make test-integration` | — |
| S13 | qv-browser | Browser verification | — |
| S14 | self-assess-impl | Self-assessment (required: self_assess=True) | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### Code Changes

- **Files to modify**:
  - `dashboard/utils/markdown.py` — add `render_pdf_chromium(html_content: str, timeout: int = 30) -> bytes | None`
  - `dashboard/routers/docs.py` — replace 3 WeasyPrint call-sites with `render_pdf_chromium()`
- **Files to create**:
  - `tests/dashboard/test_docs_pdf_chromium.py` — reproduction + regression tests

### Implementation Notes for S01

**New function** in `dashboard/utils/markdown.py` (after the `_PLAYWRIGHT_CHROME` constant):

```python
def render_pdf_chromium(html_content: str, timeout: int = 30) -> bytes | None:
    """Render HTML to PDF using headless Chromium.

    WeasyPrint does not support SVG <foreignObject> (Mermaid node labels live there),
    so we use the Playwright-managed Chromium binary with --print-to-pdf instead.
    Returns None if the binary is missing or the subprocess fails.
    """
    if not _PLAYWRIGHT_CHROME.exists():
        logger.warning("Chromium binary not found at %s — PDF not generated", _PLAYWRIGHT_CHROME)
        return None
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = Path(tmpdir) / "doc.html"
        pdf_path = Path(tmpdir) / "doc.pdf"
        html_path.write_text(html_content, encoding="utf-8")
        try:
            result = subprocess.run(  # noqa: S603
                [
                    str(_PLAYWRIGHT_CHROME),
                    "--headless",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    f"--print-to-pdf={pdf_path}",
                    f"file://{html_path}",
                ],
                timeout=timeout,
                capture_output=True,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.warning("Chromium PDF generation aborted: %s", exc)
            return None
        if result.returncode != 0:
            logger.warning(
                "Chromium PDF generation failed (rc=%d): %s",
                result.returncode,
                result.stderr.decode(errors="replace"),
            )
            return None
        if not pdf_path.exists():
            logger.warning("Chromium ran but no PDF was written to %s", pdf_path)
            return None
        return pdf_path.read_bytes()
```

**`docs_pdf_view` call-site** (replace lines 168–175):

```python
    from dashboard.utils.markdown import render_pdf_chromium
    pdf_bytes = render_pdf_chromium(html_content)
    if pdf_bytes is None:
        raise HTTPException(status_code=503, detail="PDF generation unavailable — Chromium not found")
```

**`docs_pdf` call-site** (replace lines 216–238):

```python
    from dashboard.utils.markdown import render_pdf_chromium
    pdf_bytes = render_pdf_chromium(html_content)
    if pdf_bytes is None:
        return JSONResponse(
            {"error": "PDF generation unavailable", "detail": "Chromium binary not found"},
            status_code=503,
        )
```

**`_make_render_pdf_fn()` factory** (replace lines 914–923):

```python
def _make_render_pdf_fn() -> Any:
    from dashboard.utils.markdown import render_pdf_chromium
    return render_pdf_chromium
```

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00074_Issue_Design.md` | Design | This document |
| `I-00074_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00074_S01_backend-impl_prompt.md` | Prompt | S01: implement fix |
| `prompts/I-00074_S02_CodeReview_prompt.md` | Prompt | S02: review S01 |
| `prompts/I-00074_S03_tests-impl_prompt.md` | Prompt | S03: write tests |
| `prompts/I-00074_S04_CodeReview_prompt.md` | Prompt | S04: review S03 |
| `prompts/I-00074_S05_CodeReview_Final_prompt.md` | Prompt | S05: global review |
| `prompts/I-00074_S13_BrowserVerification_prompt.md` | Prompt | S13: browser verification |
| `prompts/I-00074_S14_SelfAssess_prompt.md` | Prompt | S14: self-assessment |

Reports go to `ai-dev/work/I-00074/reports/` during execution.

## Test to Reproduce

Tests that drive a FastAPI route must be placed under `tests/dashboard/` (the `client`
fixture is only registered in `tests/dashboard/conftest.py`).

```python
# tests/dashboard/test_docs_pdf_chromium.py
from unittest.mock import patch, MagicMock
from pathlib import Path


def test_i00074_render_pdf_chromium_exists():
    """render_pdf_chromium must exist — this fails before the fix."""
    from dashboard.utils.markdown import render_pdf_chromium
    assert callable(render_pdf_chromium)


def test_i00074_pdf_view_does_not_call_weasyprint(client, ...):
    """docs_pdf_view must not import or call WeasyPrint (I-00074)."""
    # The full test is written by S03 tests-impl
    ...
```

## Acceptance Criteria

### AC1: Bug is fixed

```
Given a document with Mermaid diagram content
When the user downloads or views the PDF via the dashboard
Then the PDF contains node labels rendered by Chromium (not blank boxes)
```

### AC2: WeasyPrint is not called for any PDF route

```
Given any of the three PDF endpoints is called
When PDF bytes are generated
Then WeasyPrint is NOT imported or called — Chromium is used instead
```

### AC3: Regression test exists

```
Given the fix is applied
When the test suite runs
Then tests/dashboard/test_docs_pdf_chromium.py passes with semantic assertions
```

### AC4: Chromium unavailable returns a clean error

```
Given the Chromium binary is absent (test environment)
When a PDF endpoint is called
Then a 503 response is returned (not a 500 traceback)
```

## Regression Prevention

- The `render_pdf_chromium()` function is the single place PDF generation is implemented.
  Future changes must go through it — no new WeasyPrint call-sites.
- Tests assert WeasyPrint is NOT called via `patch("weasyprint", create=True)` combined
  with `assert_not_called()`, catching any future re-introduction.
- The `arch-check` gate (`make arch-check`) should be extended if needed to flag
  WeasyPrint imports in routers.

## Dependencies

- **Depends on**: CR-00039 (dark-mode CSS fix already merged — `styles.css` has correct colors)
- **Blocks**: None

## Impacted Paths

- `dashboard/utils/markdown.py`
- `dashboard/routers/docs.py`
- `tests/dashboard/test_docs_pdf_chromium.py`

## TDD Approach

- **Reproducing test**: `test_i00074_render_pdf_chromium_exists` — fails before fix (function
  doesn't exist), passes after
- **Unit tests**: `render_pdf_chromium()` with mocked `subprocess.run` + `_PLAYWRIGHT_CHROME`
  path — covers success path, binary missing path, non-zero returncode path, **subprocess
  timeout path** (must return `None`, not propagate `subprocess.TimeoutExpired`)
- **Integration tests (dashboard)**: Route-level tests using `client` fixture — mock
  `render_pdf_chromium` to return fake bytes; assert WeasyPrint is not imported

## Notes

- The `pdf/doc_pdf.html` template already has all CSS inline (no external stylesheets),
  so it works correctly with `file://` URLs passed to Chromium. No template changes needed.
- The `--print-to-pdf` flag writes to a path, not stdout. The helper writes HTML to a temp
  file, runs Chromium, then reads the output PDF — all inside a `TemporaryDirectory`.
- Timeout is 30s (configurable via parameter). WeasyPrint's ThreadPoolExecutor had 10s;
  Chromium is typically faster but the HTML may include large SVGs.
- `weasyprint` can remain in `pyproject.toml` for now (other potential callers) but all
  dashboard routes must route through `render_pdf_chromium`.
- The iw-doc-system skill also generates PDFs via Playwright directly (it already uses
  Chromium natively). That path is unaffected by this fix.
