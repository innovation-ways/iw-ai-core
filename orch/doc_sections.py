"""Markdown section extraction utilities for the IW AI Core doc system.

Provides pure functions for parsing H2-level sections from document markdown content.
These functions have no side effects and do not interact with the database.
"""

import re


def extract_sections(content: str) -> list[str]:
    """Return the list of section names derived from H2 headings.

    Each ``## Heading`` line yields one section name. If no H2 headings are
    found the document is treated as a single section named "Document".

    Args:
        content: Full markdown content of the document.

    Returns:
        List of section name strings in document order.
    """
    names = re.findall(r"^## (.+)$", content, re.MULTILINE)
    names = [n.strip() for n in names]
    return names if names else ["Document"]


def split_by_sections(content: str) -> dict[str, str]:
    """Map each H2 section name to its body text.

    The body text runs from the H2 heading line up to (but not including) the
    next H2 heading or the end of the document.  The heading line itself is
    included in the body so that reassembly is lossless.

    If no H2 headings are found, the entire content is returned under the key
    "Document".

    Args:
        content: Full markdown content of the document.

    Returns:
        Ordered dict mapping section_name → body_text.
    """
    pattern = re.compile(r"^## .+$", re.MULTILINE)
    matches = list(pattern.finditer(content))

    if not matches:
        return {"Document": content}

    result: dict[str, str] = {}
    for i, m in enumerate(matches):
        name = m.group(0)[3:].strip()
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        result[name] = content[start:end].rstrip("\n")

    return result
