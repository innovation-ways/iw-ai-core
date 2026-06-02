"""Tests for base.html template (E1/E2/E3)."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestBaseHtmlRenders:
    """Tests for BaseHtmlRenders scenarios."""

    @pytest.fixture
    def base_html_content(self) -> str:
        """Provide base html content for tests."""
        base_html_path = (
            Path(__file__).resolve().parent.parent.parent / "dashboard" / "templates" / "base.html"
        )
        return base_html_path.read_text()

    def test_no_tailwind_cdn(self, base_html_content: str) -> None:
        """Verifies that no tailwind cdn."""
        assert "cdn.tailwindcss.com" not in base_html_content, (
            "base.html must not contain cdn.tailwindcss.com"
        )

    def test_prebuilt_css_link_present(self, base_html_content: str) -> None:
        """Verifies that prebuilt css link present."""
        assert 'href="/static/styles.css"' in base_html_content, (
            "base.html must include a link to /static/styles.css"
        )

    def test_no_google_fonts(self, base_html_content: str) -> None:
        """Verifies that no google fonts."""
        assert "fonts.googleapis.com" not in base_html_content, (
            "base.html must not contain fonts.googleapis.com"
        )
        assert "fonts.gstatic.com" not in base_html_content, (
            "base.html must not contain fonts.gstatic.com"
        )

    def test_no_mermaid_script_by_default(self, base_html_content: str) -> None:
        """Verifies that no mermaid script by default."""
        assert '<script src="/static/vendor/mermaid' not in base_html_content, (
            "base.html must not eagerly load mermaid script"
        )

    def test_no_hljs_script_by_default(self, base_html_content: str) -> None:
        """Verifies that no hljs script by default."""
        assert '<script src="/static/vendor/highlight.js' not in base_html_content, (
            "base.html must not eagerly load highlight.js script"
        )

    def test_no_dompurify_script_by_default(self, base_html_content: str) -> None:
        """Verifies that no dompurify script by default."""
        assert '<script src="/static/vendor/dompurify' not in base_html_content, (
            "base.html must not eagerly load DOMPurify script"
        )

    def test_no_smd_script_by_default(self, base_html_content: str) -> None:
        """Verifies that no smd script by default."""
        assert '<script src="/static/vendor/streaming-markdown' not in base_html_content, (
            "base.html must not eagerly load streaming-markdown script"
        )

    def test_lazy_libs_comment_present(self, base_html_content: str) -> None:
        """Verifies that lazy libs comment present."""
        assert "loaded lazily per-page" in base_html_content, (
            "base.html should have a comment about lazy loading"
        )

    def test_block_head_present(self, base_html_content: str) -> None:
        """Verifies that block head present."""
        assert "{% block head %}" in base_html_content, (
            "base.html must have {% block head %} for per-page includes"
        )
