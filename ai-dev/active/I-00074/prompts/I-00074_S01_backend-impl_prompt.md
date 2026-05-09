# I-00074_S01_backend-impl_prompt

**Work Item**: I-00074 — PDF Export Missing Diagram Labels — WeasyPrint Does Not Support SVG foreignObject
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker container/volume/network management commands.
Testcontainer fixtures in pytest are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No migrations for this item. Do not run `alembic upgrade head` against the live DB.

## Input Files

- **Design**: `ai-dev/active/I-00074/I-00074_Issue_Design.md` — root cause, implementation notes, call-site details
- **Markdown helper**: `dashboard/utils/markdown.py` — add `render_pdf_chromium()` here
- **Docs router**: `dashboard/routers/docs.py` — replace 3 WeasyPrint call-sites
- **PDF template**: `dashboard/templates/pdf/doc_pdf.html` — read-only reference (no changes needed)

## Output Files

- `dashboard/utils/markdown.py` — modified: `render_pdf_chromium()` added
- `dashboard/routers/docs.py` — modified: 3 WeasyPrint call-sites replaced
- `ai-dev/work/I-00074/reports/I-00074_S01_backend-impl_report.md` — implementation report

## Context

Documentation pages contain Mermaid diagrams rendered as SVG by `mmdc`. Node labels are
encoded as HTML `<p>` / `<span>` elements inside SVG `<foreignObject>`. WeasyPrint does
not support `<foreignObject>` and silently discards the subtree — resulting in PDFs with
empty diagram boxes (no labels).

The fix replaces WeasyPrint with headless Chromium, which has full `<foreignObject>`
support. The Playwright-managed Chromium binary is already used by `mmdc` in the same
file (`_PLAYWRIGHT_CHROME` constant at line 34-36 of `dashboard/utils/markdown.py`).

## Requirements

### R1: Add `render_pdf_chromium()` to `dashboard/utils/markdown.py`

Add the following function after the `_PLAYWRIGHT_CHROME` constant (around line 37).
Place it before the `_sanitize_mermaid()` function so it stays in the "Chromium helpers"
section:

```python
def render_pdf_chromium(html_content: str, timeout: int = 30) -> bytes | None:
    """Render HTML to PDF using headless Chromium.

    WeasyPrint does not support SVG <foreignObject> (Mermaid node labels live there),
    so we use the Playwright-managed Chromium binary with --print-to-pdf instead.
    Returns None if the binary is missing or the subprocess fails.
    """
    if not _PLAYWRIGHT_CHROME.exists():
        logger.warning(
            "Chromium binary not found at %s — PDF generation unavailable", _PLAYWRIGHT_CHROME
        )
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

**Notes**:
- `subprocess.run` uses a list (not a shell string) — `# noqa: S603` is correct (S607 not needed since cmd is a list).
- `capture_output=True` suppresses Chromium startup noise from the console.
- `tempfile.TemporaryDirectory` ensures cleanup even on exception.
- `timeout=30` is conservative; Chromium is typically fast but large SVG docs may be slow.
- The `try/except (subprocess.TimeoutExpired, FileNotFoundError)` mirrors the existing
  pattern at `dashboard/utils/markdown.py:218` (mmdc helper). Without it, a Chromium hang
  would propagate as an unhandled exception and the route would return 500 instead of the
  intended 503. The `FileNotFoundError` branch protects against the binary disappearing
  between the `.exists()` check and the `subprocess.run` call.
- Return `None` on any failure so callers can surface a clean HTTP error instead of a traceback.

### R2: Replace the three WeasyPrint call-sites in `dashboard/routers/docs.py`

Add to the imports at the top of `docs.py`:
```python
from dashboard.utils.markdown import render_pdf_chromium
```

**Call-site 1: `docs_pdf_view` (around line 168)**

Replace:
```python
    try:
        from weasyprint import HTML

        pdf_bytes = HTML(string=html_content).write_pdf()
    except ImportError as exc:
        raise HTTPException(status_code=501, detail="WeasyPrint not installed") from exc
```

With:
```python
    pdf_bytes = render_pdf_chromium(html_content)
    if pdf_bytes is None:
        raise HTTPException(
            status_code=503,
            detail="PDF generation unavailable — Chromium binary not found",
        )
```

**Call-site 2: `docs_pdf` (around line 216)**

Replace:
```python
    try:
        from weasyprint import HTML

        def generate_pdf() -> bytes:
            return HTML(string=html_content).write_pdf()  # type: ignore[no-any-return]

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(generate_pdf)
            try:
                pdf_bytes = future.result(timeout=10)
            except concurrent.futures.TimeoutError:
                return JSONResponse(
                    {"error": "PDF generation timed out", "retry": True},
                    status_code=504,
                )
    except ImportError:
        return JSONResponse(
            {
                "error": "PDF generation not available",
                "detail": "WeasyPrint is not installed. Run: pip install weasyprint",
            },
            status_code=501,
        )
```

With:
```python
    pdf_bytes = render_pdf_chromium(html_content)
    if pdf_bytes is None:
        return JSONResponse(
            {
                "error": "PDF generation unavailable",
                "detail": "Chromium binary not found — check _PLAYWRIGHT_CHROME path",
            },
            status_code=503,
        )
```

**Call-site 3: `_make_render_pdf_fn()` (around line 914)**

Replace:
```python
def _make_render_pdf_fn() -> Any:
    def render_pdf(html_content: str) -> bytes | None:
        try:
            from weasyprint import HTML

            return HTML(string=html_content).write_pdf()  # type: ignore[no-any-return]
        except ImportError:
            return None

    return render_pdf
```

With:
```python
def _make_render_pdf_fn() -> Any:
    return render_pdf_chromium
```

### R3: Clean up unused imports in `docs.py`

After replacing the call-sites, check if `concurrent.futures` is still used elsewhere
in `docs.py`. If it was only used for the WeasyPrint thread pool in `docs_pdf`, remove:
```python
import concurrent.futures
```

### R4: No template changes

The `pdf/doc_pdf.html` template already has all CSS inline — it works correctly with
`file://` URLs passed to Chromium. Do not modify the template.

## TDD Requirement

This step implements the fix. The Tests agent (S03) will write the tests. Do NOT write
tests in this step — focus solely on the implementation.

Verify your implementation compiles and runs basic sanity checks:
```bash
uv run python -c "from dashboard.utils.markdown import render_pdf_chromium; print('OK')"
uv run mypy dashboard/utils/markdown.py dashboard/routers/docs.py
```

## Verification

After implementing:
1. Run `make lint` — must pass
2. Run `make type-check` — must pass (add `Any` to imports if needed)
3. Import check: `uv run python -c "from dashboard.utils.markdown import render_pdf_chromium; print(render_pdf_chromium)"`

Do NOT run the full test suite in this step — that is the qv-gate's job.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00074",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/utils/markdown.py",
    "dashboard/routers/docs.py"
  ],
  "preflight": {
    "format": "ok|skipped:no-code-changes",
    "typecheck": "ok|skipped:no-code-changes",
    "lint": "ok|skipped:no-code-changes"
  },
  "tests_passed": true,
  "test_summary": "no tests run in S01",
  "blockers": [],
  "notes": "render_pdf_chromium() added; 3 WeasyPrint call-sites replaced; concurrent.futures import removed if unused."
}
```
