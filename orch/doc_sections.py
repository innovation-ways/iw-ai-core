"""Section extraction utilities for document guide management."""

from __future__ import annotations

import re


def extract_sections(content: str) -> list[str]:
    """Extract H2 section names from markdown content.

    Returns section names in order of appearance. If no H2 headings are found,
    returns ["Document"] to represent the whole-document guide.

    Args:
        content: Raw markdown content string.

    Returns:
        List of section names (H2 heading text, without the "## " prefix).
    """
    if not content:
        return ["Document"]

    pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    matches = pattern.findall(content)

    if not matches:
        return ["Document"]

    return matches
