"""Tests for I-00066: OSS finding modal width and footer button styling.

Verifies:
1. `.oss-modal-inner` uses `max-width: 80vw` (not `36rem`) in source and compiled CSS.
2. The footer Close button carries the new `.modal-footer-close` class.
3. The `.modal-footer-close` class defines real border + padding declarations.

All four tests MUST fail on pre-fix `main` and pass on the fix branch.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = REPO_ROOT / "dashboard/templates/fragments/oss_finding_modal.html"
SOURCE_CSS = REPO_ROOT / "dashboard/static/tailwind.src.css"
COMPILED_CSS = REPO_ROOT / "dashboard/static/styles.css"


def _block(css: str, selector: str) -> str:
    """Return the contents of the FIRST CSS block whose selector exactly matches."""
    pattern = re.compile(
        r"(?:^|\s|,)" + re.escape(selector) + r"\s*\{([^}]*)\}",
        re.MULTILINE,
    )
    m = pattern.search(css)
    assert m, f"selector not found: {selector}"
    return m.group(1)


def test_i00066_modal_inner_widened_in_source_css():
    """.oss-modal-inner must use 80vw, not 36rem (semantic value check)."""
    body = _block(SOURCE_CSS.read_text(), ".oss-modal-inner")
    assert "max-width: 80vw" in body, body
    assert "36rem" not in body, body


def test_i00066_modal_inner_widened_in_compiled_css():
    """Compiled stylesheet must reflect the source change."""
    css = COMPILED_CSS.read_text()
    assert ".oss-modal-inner" in css
    # The compiled file is minified; just check the selector and the new value
    # appear together (no 36rem in the same rule).
    inner_match = re.search(r"\.oss-modal-inner\{([^}]*)\}", css)
    assert inner_match, "oss-modal-inner not found in compiled CSS"
    body = inner_match.group(1)
    assert "max-width:80vw" in body or "max-width: 80vw" in body, body
    assert "36rem" not in body, body


def test_i00066_footer_close_uses_peer_button_class():
    """The footer Close button must carry the new peer-button class so it
    renders like Re-run check / Mark accepted, not like the header × close."""
    html = TEMPLATE.read_text()
    # The header × close button is OK to keep `.modal-close` only.
    # The FOOTER close button (the one with text 'Close') must also have
    # the new `.modal-footer-close` class.
    footer_close = re.search(
        r'<button[^>]*class="[^"]*modal-footer-close[^"]*"[^>]*>\s*Close\s*</button>',
        html,
    )
    assert footer_close, html


def test_i00066_footer_button_class_styled_in_source_css():
    """The new `.modal-footer-close` class must have border + padding so
    it renders as a button, not a plain × close icon."""
    body = _block(SOURCE_CSS.read_text(), ".modal-footer-close")
    # Semantic checks: must have a real border, real padding, and font-weight
    # consistent with the other footer buttons.
    assert "border:" in body, body
    assert "padding:" in body, body
