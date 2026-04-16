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
    lines = doc_content.split("\n")
    section_started = False
    section_lines: list[str] = []

    header_pattern = re.compile(
        r"^#{1,6}\s+.*?(component|architecture|module|structure)",
        re.IGNORECASE,
    )

    for line in lines:
        if header_pattern.search(line):
            section_started = True
            section_lines = []
        elif section_started:
            if line.startswith("#"):
                break
            section_lines.append(line)

    if not section_lines:
        return []

    modules: list[dict[str, str]] = []

    for line in section_lines:
        entry = _try_parse_line(line)
        if entry is not None:
            modules.append(entry)

    return modules


def _try_parse_line(line: str) -> dict[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

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
    return re.match(r"^- `([^`]+)`\s*--?\s*(.+)$", line)


def _match_bold_name_with_path(line: str) -> re.Match[str] | None:
    return re.match(r"^- \*\*([^*]+)\*\*\s*\(`([^)]+)`\):\s*(.+)$", line)


def _match_plain_format(line: str) -> re.Match[str] | None:
    return re.match(r"^- ([^ ]+/)\s*--?\s*(.+)$", line)


def _extract_name_from_description(description: str, path: str) -> str:
    if ":" in description:
        return description.split(":", 1)[0].strip()
    return path


def _make_slug(path: str) -> str:
    return path.strip("/").replace("/", "-").lower()
