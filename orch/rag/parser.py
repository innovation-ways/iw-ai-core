"""Parser for extracting module entries from Level 1 architecture documents."""

from __future__ import annotations

import re


def parse_modules_from_level1(doc_content: str) -> list[dict[str, str]]:
    """
    Extract component entries from Level 1 architecture doc.

    Returns list of dicts with keys:
      - name: str       — human-readable module name (e.g. "C++ Sensor Engine")
      - path: str       — filesystem path (e.g. "engine/")
      - description: str — short description
      - slug: str       — URL-safe identifier (e.g. "engine")

    Returns empty list if no components section is found.
    Never raises — all parsing errors result in empty list or partial list.
    """
    if not doc_content or not isinstance(doc_content, str):
        return []

    try:
        return list(_parse_modules_safe(doc_content))
    except Exception:
        return []


def _parse_modules_safe(doc_content: str) -> list[dict[str, str]]:
    """Scan doc_content for component/architecture/module/structure H# sections and parse entries.

    Splits the document into candidate sections by header keywords, then applies
    _try_parse_line to each line and returns the first section that yields at least
    one entry. Returns an empty list when no section matches.
    """
    lines = doc_content.split("\n")

    matching_header = re.compile(
        r"^#{1,6}\s+.*?(component|architecture|module|structure)",
        re.IGNORECASE,
    )
    any_header = re.compile(r"^#{1,6}\s+")

    sections: list[list[str]] = []
    current: list[str] | None = None

    for line in lines:
        if matching_header.search(line):
            if current is not None:
                sections.append(current)
            current = []
        elif any_header.match(line):
            if current is not None:
                sections.append(current)
                current = None
        elif current is not None:
            current.append(line)

    if current is not None:
        sections.append(current)

    for section_lines in sections:
        modules: list[dict[str, str]] = []
        for line in section_lines:
            entry = _try_parse_line(line)
            if entry is not None:
                modules.append(entry)
        if modules:
            return modules

    return []


def _try_parse_line(line: str) -> dict[str, str] | None:
    """Attempt to parse a single markdown list line as a module entry using multiple format
    patterns.

    Tries four patterns in priority order:
    1. Bold with path inside: ``**Name (`path/`)**:``
    2. Backtick with dash separator: ``- `path/` -- description``
    3. Bold name with parenthesised path: ``**Name** (`path/`):``
    4. Plain path with dash separator: ``- path/ -- description``

    Returns None for blank lines, comment-like lines, or lines that match none of the patterns.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    m = _match_bold_with_path_inside(stripped)
    if m:
        name = m.group(1).strip()
        path = m.group(2)
        description = m.group(3)
        slug = _make_slug(path)
        return {"name": name, "path": path, "description": description, "slug": slug}

    m = _match_backtick_with_description(stripped)
    if m:
        path = m.group(1)
        description = m.group(2)
        name = _extract_name_from_description(description, path)
        slug = _make_slug(path)
        return {"name": name, "path": path, "description": description, "slug": slug}

    m = _match_bold_name_with_path(stripped)
    if m:
        name = m.group(1)
        path = m.group(2)
        description = m.group(3)
        slug = _make_slug(path)
        return {"name": name, "path": path, "description": description, "slug": slug}

    m = _match_plain_format(stripped)
    if m:
        path = m.group(1)
        description = m.group(2)
        name = path
        slug = _make_slug(path)
        return {"name": name, "path": path, "description": description, "slug": slug}

    return None


def _match_backtick_with_description(line: str) -> re.Match[str] | None:
    return re.match(r"^[-*]\s+`([^`]+)`\s*--?\s*(.+)$", line)


def _match_bold_name_with_path(line: str) -> re.Match[str] | None:
    return re.match(r"^[-*]\s+\*\*([^*]+)\*\*\s*\(`([^)]+)`\):\s*(.+)$", line)


def _match_bold_with_path_inside(line: str) -> re.Match[str] | None:
    return re.match(
        r"^[-*]\s+\*\*([^*(]+?)\s*\(`([^`]+)`\)\*\*\s*:\s*(.+)$",
        line,
    )


def _match_plain_format(line: str) -> re.Match[str] | None:
    return re.match(r"^[-*]\s+([^ ]+/)\s*--?\s*(.+)$", line)


def _extract_name_from_description(description: str, path: str) -> str:
    if ":" in description:
        return description.split(":", 1)[0].strip()
    return path


def _make_slug(path: str) -> str:
    return path.strip("/").replace("/", "-").lower()
