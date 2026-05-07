"""Orphan-slug strict integration test (AC6).

Walks every Jinja page template and:
1. Asserts every declared `{% block page_help_slug %}<slug>{% endblock %}` has a
   matching `dashboard/templates/_partials/help/<slug>.html` fragment file.
2. Asserts every fragment file is referenced by at least one page template
   (catches dead fragments with no owning page).

Both directions are checked in a single test so the full violation list is
available in one assertion failure.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Project root — resolved relative to this file's location
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

TEMPLATES_DIR = PROJECT_ROOT / "dashboard" / "templates"
PAGES_DIR = TEMPLATES_DIR / "pages"
PARTIALS_HELP_DIR = TEMPLATES_DIR / "_partials" / "help"

# Regex to extract `{% block page_help_slug %}<slug>{% endblock %}`.
_SLUG_BLOCK_RE = re.compile(
    r"{%\s*block\s+page_help_slug\s*%}\s*([a-z][a-z0-9_-]*)\s*{%\s*endblock\s*%}",
    re.IGNORECASE,
)


def _extract_slug_blocks_from_file(file_path: Path) -> list[str]:
    """Return all page_help_slug block values found in a template file."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        return []
    return _SLUG_BLOCK_RE.findall(content)


class TestHelpFragmentsPresent:
    """AC6: Every declared slug must have a fragment; every fragment must have a page."""

    def test_no_orphan_page_slugs(self) -> None:
        """Every page template with a page_help_slug block has a matching fragment file."""
        # Collect all page templates under pages/ and root templates/
        page_files: list[Path] = []
        if PAGES_DIR.is_dir():
            page_files.extend(PAGES_DIR.rglob("*.html"))
        # Root-level page templates (e.g. project_selector.html)
        for pattern in ("*.html",):
            page_files.extend(TEMPLATES_DIR.glob(pattern))

        orphan_pages: list[str] = []
        for page_file in page_files:
            slugs = _extract_slug_blocks_from_file(page_file)
            for slug in slugs:
                fragment_path = PARTIALS_HELP_DIR / f"{slug}.html"
                if not fragment_path.exists():
                    orphan_pages.append(
                        f"page={page_file.relative_to(PROJECT_ROOT)} "
                        f"declares slug={slug!r} but "
                        f"fragment {fragment_path.relative_to(PROJECT_ROOT)} does not exist"
                    )

        assert not orphan_pages, "Orphan page slugs (no matching fragment file):\n" + "\n".join(
            f"  • {msg}" for msg in orphan_pages
        )

    def test_no_dead_fragments(self) -> None:
        """Every fragment file is referenced by at least one page template."""
        if not PARTIALS_HELP_DIR.is_dir():
            pytest.fail(f"Fragments directory does not exist: {PARTIALS_HELP_DIR}")

        # Build the set of slugs declared by all page templates
        page_files: list[Path] = []
        if PAGES_DIR.is_dir():
            page_files.extend(PAGES_DIR.rglob("*.html"))
        for pattern in ("*.html",):
            page_files.extend(TEMPLATES_DIR.glob(pattern))

        declared_slugs: set[str] = set()
        for page_file in page_files:
            declared_slugs.update(_extract_slug_blocks_from_file(page_file))

        # Check each fragment file
        dead_fragments: list[str] = []
        for fragment_file in sorted(PARTIALS_HELP_DIR.glob("*.html")):
            slug = fragment_file.stem
            if slug not in declared_slugs:
                dead_fragments.append(
                    f"fragment={fragment_file.relative_to(PROJECT_ROOT)} "
                    f"has no owning page (slug={slug!r} not in any page_help_slug block)"
                )

        assert not dead_fragments, "Dead fragments (not referenced by any page):\n" + "\n".join(
            f"  • {msg}" for msg in dead_fragments
        )
