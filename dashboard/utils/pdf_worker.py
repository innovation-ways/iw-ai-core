"""Isolated PDF render worker (Playwright + Paged.js).

Run as a subprocess by :func:`dashboard.utils.markdown.render_pdf_chromium` so each
render gets a fresh Playwright process — the sync Playwright API is not safe to
re-enter repeatedly inside the long-lived FastAPI server, so we isolate it here.

Usage:
    python -m dashboard.utils.pdf_worker <html_path> <pdf_path> <pagedjs_path> [<chrome_path>]

The optional ``chrome_path`` is the Chromium/Chrome executable resolved by
``dashboard.utils.markdown._resolve_chromium_binary``. When supplied it is passed
as Playwright's ``executable_path`` so the worker reuses the same system Chromium
the rest of the app relies on, instead of Playwright's separately-downloaded
browser (which may be absent — we never run ``playwright install``).

Exit codes: 0 ok · 2 bad args · 3 Paged.js layout error · 4 render failure.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    if len(argv) not in (3, 4):
        sys.stderr.write(
            "usage: pdf_worker <html_path> <pdf_path> <pagedjs_path> [<chrome_path>]\n"
        )
        return 2
    html_path, pdf_path, pagedjs_path = argv[:3]
    chrome_path = argv[3] if len(argv) == 4 else ""

    from playwright.sync_api import sync_playwright

    launch_kwargs: dict[str, object] = {
        "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-gpu"]
    }
    if chrome_path:
        launch_kwargs["executable_path"] = chrome_path

    html = Path(html_path).read_text(encoding="utf-8")
    with sync_playwright() as pw:
        browser = pw.chromium.launch(**launch_kwargs)  # type: ignore[arg-type]
        try:
            page = browser.new_page()
            page.set_content(html, wait_until="networkidle", timeout=60000)
            page.add_script_tag(path=pagedjs_path)
            # Kick off Paged.js pagination (buildLayout runs via PagedConfig.before)
            # and poll a done/error flag so an unbreakable element can't hang us.
            page.evaluate(
                "() => { window.PagedPolyfill.preview()"
                ".then(() => { window.__pagedReady = true; })"
                ".catch((e) => { window.__pagedErr = String((e && e.message) || e); }); }"
            )
            page.wait_for_function(
                "window.__pagedReady === true || window.__pagedErr", timeout=80000
            )
            err = page.evaluate("() => window.__pagedErr || null")
            if err:
                sys.stderr.write(f"paged_error: {err}\n")
                return 3
            pdf = page.pdf(
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                print_background=True,
                prefer_css_page_size=True,
            )
            Path(pdf_path).write_bytes(pdf)
            return 0
        finally:
            browser.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:  # noqa: BLE001 — surface any render failure to the parent via stderr/exit code
        sys.stderr.write(f"render_failure: {exc}\n")
        raise SystemExit(4) from exc
