"""Tests for static assets (E1/E3)."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestStaticAssets:
    @pytest.fixture
    def static_dir(self) -> Path:
        return Path(__file__).resolve().parent.parent.parent / "dashboard" / "static"

    def test_styles_css_exists_and_non_empty(self, static_dir: Path) -> None:
        styles_css = static_dir / "styles.css"
        assert styles_css.exists(), "dashboard/static/styles.css must exist"
        content = styles_css.read_text()
        assert len(content) > 1000, (
            "dashboard/static/styles.css must be non-empty (should be prebuilt Tailwind CSS)"
        )

    def test_inter_woff2_files_exist(self, static_dir: Path) -> None:
        fonts_dir = static_dir / "fonts" / "inter"
        assert fonts_dir.exists(), "dashboard/static/fonts/inter/ directory must exist"

        woff2_files = list(fonts_dir.glob("*.woff2"))
        assert len(woff2_files) >= 4, (
            f"Expected at least 4 Inter woff2 files (400, 500, 600, 700), "
            f"found {len(woff2_files)}: {woff2_files}"
        )

        expected_weights = {"400", "500", "600", "700"}
        found_weights = set()
        for f in woff2_files:
            for weight in expected_weights:
                if weight in f.name:
                    found_weights.add(weight)

        assert found_weights == expected_weights, (
            f"Expected Inter woff2 files for weights {expected_weights}, "
            f"found weights {found_weights}"
        )

    def test_theme_css_exists(self, static_dir: Path) -> None:
        theme_css = static_dir / "theme.css"
        assert theme_css.exists(), "dashboard/static/theme.css must exist"

    def test_vendor_htmx_exists(self, static_dir: Path) -> None:
        htmx_js = static_dir / "vendor" / "htmx" / "htmx.min.js"
        assert htmx_js.exists(), "dashboard/static/vendor/htmx/htmx.min.js must exist"


class TestStylesCssContent:
    def test_styles_css_contains_tailwind_directives(self) -> None:
        styles_css_path = (
            Path(__file__).resolve().parent.parent.parent / "dashboard" / "static" / "styles.css"
        )
        content = styles_css_path.read_text()
        assert "@tailwind" in content or "tailwind" in content.lower(), (
            "styles.css should contain Tailwind CSS content"
        )

    def test_theme_css_contains_font_face(self) -> None:
        theme_css_path = (
            Path(__file__).resolve().parent.parent.parent / "dashboard" / "static" / "theme.css"
        )
        content = theme_css_path.read_text()
        assert "@font-face" in content, (
            "theme.css should contain @font-face declarations for self-hosted Inter"
        )
        assert "Inter" in content, "theme.css should reference Inter font"
