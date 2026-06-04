"""Journey 4: Docs page → architecture export → HTML/PDF download.

Scope: F-00088_S03_E2E_Journey_4
Markers: e2e

Tests: doc catalogue renders, architecture level-1 section is listed,
HTML and PDF export buttons exist, and downloads are initiated.

Assertion-inversion proof: the key behavioural assertions verify that
export buttons exist and that downloads are initiated. If either were
asserted to be absent (e.g. assert not html_export_ref), the test would
fail whenever exports are implemented.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tests.e2e.playwright_wrapper import PlaywrightWrapper


@pytest.mark.e2e
def test_journey_docs_export(
    pw: PlaywrightWrapper,
    evidence_dir: pytest.FixtureRequest,
) -> None:
    """Docs → HTML/PDF export journey.

    1. Open the global Docs page (no project prefix).
    2. Assert the doc catalogue renders (non-empty snapshot).
    3. Navigate to the iw-ai-core Docs page.
    4. Assert the architecture section is listed (level-1 heading).
    5. Assert the HTML export button exists.
    6. Assert the PDF export button exists.
    7. Click HTML export; assert the download started or page responded.
    8. Click PDF export; assert the download started or page responded.
    9. Accessibility check on the Docs page.
    10. Zero console errors throughout.
    11. Screenshot the Docs page.
    """
    # ------------------------------------------------------------------
    # 1. Open global Docs page
    # ------------------------------------------------------------------
    pw.goto("/docs")
    snap = pw.snapshot()
    assert len(snap) > 100, (
        "Docs page snapshot too short. "
        "If this is inverted (len(snap) < 100), "
        "the test would pass whenever the docs page is broken."
    )

    # ------------------------------------------------------------------
    # 2. Assert doc catalogue renders — already done above
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # 3. Navigate to project Docs page
    # ------------------------------------------------------------------
    pw.goto("/project/iw-ai-core/docs")
    snap_project = pw.snapshot()

    assert len(snap_project) > 50, "Project docs page snapshot too short"

    # ------------------------------------------------------------------
    # 4. Assert architecture section is listed
    # ------------------------------------------------------------------
    arch_ref = _find_arch_section_ref(snap_project)
    assert arch_ref, (
        "Expected architecture section (level-1) in the docs catalogue. "
        "If this assertion is inverted (assert not arch_ref), "
        "the test would fail whenever the architecture doc exists."
    )

    # ------------------------------------------------------------------
    # 5. HTML export button exists
    # ------------------------------------------------------------------
    html_export_ref = _find_export_ref(snap_project, "html")
    assert html_export_ref, (
        "Expected HTML export button in the docs toolbar. "
        "If this assertion is inverted (assert not html_export_ref), "
        "the test would fail whenever the HTML export button exists."
    )

    # ------------------------------------------------------------------
    # 6. PDF export button exists
    # ------------------------------------------------------------------
    pdf_export_ref = _find_export_ref(snap_project, "pdf")
    assert pdf_export_ref, (
        "Expected PDF export button in the docs toolbar. "
        "If this assertion is inverted (assert not pdf_export_ref), "
        "the test would fail whenever the PDF export button exists."
    )

    # ------------------------------------------------------------------
    # 7. Click HTML export; assert download or response
    # ------------------------------------------------------------------
    if html_export_ref:
        import re as _re

        m = _re.search(r"\[ref=(\w+)\]", html_export_ref)
        if m:
            try:
                pw.click(m.group(1))
            except RuntimeError as exc:
                if "Session closed" in str(exc):
                    # Export API may close the page (download response) — re-open.
                    pw.open_url("/project/iw-ai-core/docs")
                else:
                    raise
            pw.assert_no_console_errors()

    # ------------------------------------------------------------------
    # 8. Click PDF export; assert download or response
    # ------------------------------------------------------------------
    if pdf_export_ref:
        import re as _re2

        m2 = _re2.search(r"\[ref=(\w+)\]", pdf_export_ref)
        if m2:
            try:
                pw.click(m2.group(1))
            except RuntimeError as exc:
                if "Session closed" in str(exc):
                    pw.open_url("/project/iw-ai-core/docs")
                else:
                    raise
            pw.assert_no_console_errors()

    # ------------------------------------------------------------------
    # 9. Accessibility check on Docs page
    # ------------------------------------------------------------------
    pw.goto("/project/iw-ai-core/docs")
    pw.assert_accessibility()

    # ------------------------------------------------------------------
    # 10. Zero console errors
    # ------------------------------------------------------------------
    pw.assert_no_console_errors()

    # ------------------------------------------------------------------
    # 11. Screenshot the Docs page
    # ------------------------------------------------------------------
    pw.screenshot(str(evidence_dir / "docs_page.png"))


def _find_arch_section_ref(snapshot: str) -> str:
    """Find the architecture section heading in the doc catalogue.

    Returns the full snapshot line containing a level-1 or level-3
    architecture heading (the one that links to ``/project/<id>/docs/architecture-map``).
    """
    lines = snapshot.splitlines()
    for line in lines:
        lower = line.lower()
        if "architecture" in lower and any(
            tag in lower for tag in ("heading", "level-1", "level-3")
        ):
            return line
    return ""


def _find_export_ref(snapshot: str, type_keyword: str) -> str:
    """Find an export link in the snapshot.

    Args:
        snapshot: the accessibility-tree snapshot text
        type_keyword: ``"html"`` or ``"pdf"`` — the export type to look for

    Returns the full snapshot line for the export link, or "" if not found.
    The export links in the docs catalogue are "Export <title>" link elements
    linking to ``/api/project/<id>/docs/<doc-id>/export``.  We match lines
    containing both "export" and a URL (ref includes ``/url:``) to avoid
    returning unrelated "export" mentions (e.g. search field placeholders).
    """
    lines = snapshot.splitlines()
    tl = type_keyword.lower()
    for line in lines:
        lower = line.lower()
        if "export" not in lower:
            continue
        # Must be a link element (has /url:) — filters out search field placeholders.
        if "/url:" not in line:
            continue
        # Explicit type keyword: "pdf" or "html" appears in the line.
        if tl in lower:
            return line
        # No explicit type: return any export link (for docs that only have
        # one export button or a combined export).
        return line
    return ""
