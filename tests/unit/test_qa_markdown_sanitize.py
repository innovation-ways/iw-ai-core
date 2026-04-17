"""Smoke tests for DOMPurify wiring in the Q&A panel templates.

These are template-grep tests — they verify the presence of security-critical
markup patterns without requiring a browser.  Full XSS verification requires
playwright-cli in QV (S11).

Files checked:
  - dashboard/templates/base.html       — DOMPurify CDN script tag
  - dashboard/templates/fragments/code_qa_panel.html  — sanitization calls
"""

from __future__ import annotations

import re
from pathlib import Path

TEMPLATE_PATH = Path("dashboard/templates/fragments/code_qa_panel.html")
BASE_PATH = Path("dashboard/templates/base.html")


def test_dompurify_loaded_in_base() -> None:
    """DOMPurify must be loaded via CDN with a pinned version — no @latest or floating major."""
    content = BASE_PATH.read_text()
    assert "dompurify" in content.lower(), "DOMPurify CDN script not found in base.html"
    assert re.search(r"dompurify@\d+\.\d+\.\d+", content), (
        "DOMPurify must be pinned to a specific version "
        "(e.g. @3.1.7), not @latest or floating major"
    )


def test_qa_panel_uses_dompurify() -> None:
    """Q&A panel must call DOMPurify.sanitize and marked.parse on assistant output."""
    content = TEMPLATE_PATH.read_text()
    assert "DOMPurify.sanitize" in content, "qaRenderMarkdown must call DOMPurify.sanitize"
    assert "marked.parse" in content, "qaRenderMarkdown must call marked.parse"


def test_qa_panel_no_stale_textcontent_append() -> None:
    """The stale textContent append path must be gone from the Q&A panel."""
    content = TEMPLATE_PATH.read_text()
    assert "responseSpan.textContent +=" not in content, (
        "Stale textContent append path detected — "
        "assistant tokens must be rendered via innerHTML = qaRenderMarkdown(), "
        "not via responseSpan.textContent += token"
    )


def test_qa_panel_links_have_noopener_noreferrer() -> None:
    """Links rendered from markdown must enforce rel=noopener noreferrer on target=_blank."""
    content = TEMPLATE_PATH.read_text()
    assert "noopener noreferrer" in content, (
        "DOMPurify afterSanitizeAttributes hook must set rel='noopener noreferrer' "
        "on links with target=_blank"
    )


def test_qa_panel_user_bubble_uses_text_not_markdown() -> None:
    """User bubble must use textContent (no innerHTML) — user input is not markdown."""
    content = TEMPLATE_PATH.read_text()

    match = re.search(
        r"function qaAppendUserBubble.*?^  \}",
        content,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "qaAppendUserBubble function not found in template"
    body = match.group(0)

    assert "innerHTML" not in body, (
        "qaAppendUserBubble must not use innerHTML — user input is plain text, not markdown"
    )
    assert "textContent" in body, "qaAppendUserBubble should use textContent for user input"


def test_qa_render_markdown_returns_sanitized_html() -> None:
    """qaRenderMarkdown must return sanitized HTML via DOMPurify.sanitize."""
    content = TEMPLATE_PATH.read_text()

    match = re.search(
        r"function qaRenderMarkdown.*?^  \}",
        content,
        re.DOTALL | re.MULTILINE,
    )
    assert match is not None, "qaRenderMarkdown function not found in template"
    body = match.group(0)

    assert "DOMPurify.sanitize" in body, "qaRenderMarkdown must call DOMPurify.sanitize"
    assert "return" in body
    assert "clean" in body
