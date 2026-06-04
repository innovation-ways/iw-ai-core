"""Smoke tests for F-00080 help system — verifies static assets and template wiring are present."""

# Smoke test: verify help.js, tours.js, driver.js, and base.html contain
# the expected script tags and static assets are present on disk.
from pathlib import Path

# Project root — resolved relative to this file's location
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_help_js_exists() -> None:
    """help.js is present in static/ and implements popover + tour logic."""
    help_js = PROJECT_ROOT / "dashboard/static/help/help.js"
    assert help_js.exists(), f"help.js not found at {help_js}"
    content = help_js.read_text()
    # help.js lazy-loads driver.js on first tour start
    assert "loadDriverScript" in content
    assert "DOMContentLoaded" in content
    assert "data-tour-seen" in content or "markTourSeen" in content


def test_tours_js_exists() -> None:
    """tours.js defines IW_TOURS with at least one tour entry."""
    tours_js = PROJECT_ROOT / "dashboard/static/help/tours.js"
    assert tours_js.exists(), f"tours.js not found at {tours_js}"
    content = tours_js.read_text()
    assert "window.IW_TOURS" in content
    assert "queue" in content  # at least the queue tour should be present


def test_driver_js_vendored() -> None:
    """Driver.js IIFE, CSS, and LICENSE are all present."""
    vendor_dir = PROJECT_ROOT / "dashboard/static/vendor/driver"
    assert (vendor_dir / "driver.js.iife.js").exists()
    assert (vendor_dir / "driver.css").exists()
    assert (vendor_dir / "LICENSE").exists()
    iife = (vendor_dir / "driver.js.iife.js").read_text()
    assert "MIT" in iife or "license" in iife.lower()
    license_text = (vendor_dir / "LICENSE").read_text()
    assert "MIT" in license_text


def test_driver_css_vendored() -> None:
    """Driver.js CSS is vendored."""
    driver_css = PROJECT_ROOT / "dashboard/static/vendor/driver/driver.css"
    assert driver_css.exists()
    content = driver_css.read_text()
    assert ".driver-popover" in content


def test_macros_exist() -> None:
    """Jinja macros for help_button and empty_state are present."""
    macros_dir = PROJECT_ROOT / "dashboard/templates/macros"
    help_btn = macros_dir / "help_button.html"
    empty_state = macros_dir / "empty_state.html"
    assert help_btn.exists()
    assert empty_state.exists()
    # The button has class="help-trigger" and data-help-slug attribute
    btn_content = help_btn.read_text()
    assert "data-help-slug=" in btn_content
    assert "help-popover" in btn_content
    # empty_state macro takes slug, heading, body, primary_label, primary_href
    empty_content = empty_state.read_text()
    assert "primary_href" in empty_content or "empty-state" in empty_content


def test_help_fragments_exist() -> None:
    """All 22 help fragments are present."""
    fragments_dir = PROJECT_ROOT / "dashboard/templates/_partials/help"
    slugs = [
        "projects",
        "queue",
        "history",
        "batches",
        "batch_detail",
        "item_detail",
        "jobs",
        "job_detail",
        "code",
        "docs",
        "research",
        "tests",
        "quality",
        "search",
        "status",
        "worktrees",
        "containers",
        "all_active",
        "config",
        "keep_alive",
        "coverage",
        "running",
    ]
    for slug in slugs:
        fragment = fragments_dir / f"{slug}.html"
        assert fragment.exists(), f"Missing help fragment: {slug}.html"
        content = fragment.read_text()
        # Every fragment must have the 4-section structure
        assert "What is this page?" in content
        assert "What can I do here?" in content
        assert "Vocabulary" in content
        assert "data-help-close" in content or "help-content__close" in content


def test_base_html_has_help_slot() -> None:
    """base.html contains the page_help_slug block and help script tags."""
    base_html = PROJECT_ROOT / "dashboard/templates/base.html"
    content = base_html.read_text()
    assert "page_help_slug" in content
    assert 'src="/static/help/help.js"' in content
    assert 'src="/static/help/tours.js"' in content


def test_styles_css_has_help_rules() -> None:
    """styles.css contains F-00080 help system CSS."""
    styles = PROJECT_ROOT / "dashboard/static/styles.css"
    content = styles.read_text()
    assert "help-trigger" in content or "help_trigger" in content
    assert "help-popover" in content
    assert "help-content" in content
    assert "empty-state" in content
