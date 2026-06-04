"""Pure parsing helpers for design documents.

Provides:
- parse_dependencies(): extracts **Depends on:** and **Blocks:** from ## Dependencies
- strip_excluded_sections(): removes ## Out of Scope / ## Notes before file extraction

No I/O, no database calls, no logging beyond warnings.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Impacted Paths
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ImpactedPathsResult:
    """Result of parsing a design document's ## Impacted Paths section."""

    paths: list[str]  # validated, deduped, original order preserved
    found: bool  # True if the section existed (even if empty)


def parse_impacted_paths(content: str | None) -> ImpactedPathsResult:
    """Extract glob patterns from the '## Impacted Paths' section.

    Accepts BOTH markdown bullet lists (`- glob`, `* glob`) AND fenced code
    blocks. Validates each glob (raises ValueError on absolute paths, '..',
    whitespace inside the glob, or empty strings). Returns ImpactedPathsResult
    with `found=False` and `paths=[]` when the section is absent.
    """
    if not content:
        return ImpactedPathsResult(paths=[], found=False)

    # Find the ## Impacted Paths section
    section_ranges = _iter_section_ranges(content)
    impacted_paths_range: tuple[int, int] | None = None
    for start, end, title_lower in section_ranges:
        if title_lower == "impacted paths":
            impacted_paths_range = (start, end)
            break

    if impacted_paths_range is None:
        return ImpactedPathsResult(paths=[], found=False)

    section_start, section_end = impacted_paths_range
    lines = content.splitlines()
    # Skip the heading line itself; process from the line after
    section_lines = lines[section_start + 1 : section_end]

    # Collect globs from bullet lines and code blocks
    globs: list[str] = []
    seen: set[str] = set()
    in_code_block = False

    for raw_line in section_lines:
        stripped = raw_line.strip()

        # Fence detection: opening/closing ``` fence lines
        if stripped.startswith("```"):
            # Toggle in_code_block state
            in_code_block = not in_code_block
            continue

        if in_code_block:
            glob = _strip_code_span(stripped)
            _validate_glob(glob)  # raises ValueError on invalid
            if glob not in seen:
                seen.add(glob)
                globs.append(glob)
            continue

        # Bullet lines: preserve indentation when extracting glob.
        # raw_line e.g. "  - foo.py" or "- foo.py" or "   * bar.py"
        lstripped = raw_line.lstrip()
        if lstripped.startswith(("- ", "* ")):
            indent = len(raw_line) - len(lstripped)
            glob = _strip_code_span(
                raw_line[indent + 2 :].strip()
            )  # strip markdown code-span — I-00071
            _validate_glob(glob)  # raises ValueError on invalid
            if glob not in seen:
                seen.add(glob)
                globs.append(glob)

    return ImpactedPathsResult(paths=globs, found=True)


def _strip_code_span(s: str) -> str:
    """Remove surrounding markdown code-span backticks from `s`.

    Handles single-backtick fences: `` `foo/bar.py` `` → `` foo/bar.py ``.
    Also handles double-backtick fences (content with embedded backticks):
    `` `` `foo` `` `` → `` `foo` ``.
    Returns the original string if it has no matching fence.
    """
    stripped = s.strip()
    # Double-backtick outer fence: `` `...` ``
    if stripped.startswith("``") and stripped.endswith("``") and len(stripped) >= 4:
        inner = stripped[2:-2].strip()
        # Recurse to strip inner single-backtick fence if present
        return _strip_code_span(inner)
    # Single-backtick fence
    if stripped.startswith("`") and stripped.endswith("`") and len(stripped) >= 2:
        inner = stripped[1:-1]
        # Inner content must not contain whitespace or backticks
        if " " not in inner and "\t" not in inner and "`" not in inner:
            return inner
    return s


def _validate_glob(glob: str) -> bool:
    """Validate a single glob. Raises ValueError on invalid input."""
    stripped = glob.strip()
    if not stripped:
        raise ValueError("empty glob")

    if " " in stripped or "\t" in stripped:
        raise ValueError("whitespace inside glob is not allowed")

    if stripped.startswith("/"):
        raise ValueError("absolute paths are not allowed")

    parts = PurePosixPath(stripped).parts
    if ".." in parts:
        raise ValueError("'..' path segments are not allowed")

    return True


# ---------------------------------------------------------------------------
# ID pattern
# ---------------------------------------------------------------------------

_ID_PATTERN = re.compile(r"\b(?:F|I|CR)-\d{3,5}\b")

# ---------------------------------------------------------------------------
# Section stripping
# ---------------------------------------------------------------------------

_SECTION_HEADING_RE = re.compile(r"^#{1,6}\s+(?P<title>[^\n]+?)\s*$", re.MULTILINE | re.IGNORECASE)

# Sections we consider "excluded" for file-extraction purposes
_EXCLUDED_SECTION_TITLES = frozenset(["out of scope", "notes"])

# Code-fence markers to avoid stripping inside code blocks
_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```|`[^`\n]*`")


def _iter_section_ranges(content: str) -> list[tuple[int, int, str]]:
    """Yield (start_offset, end_offset, section_title_lower) for each section.

    A section runs from its heading line to the next top-level `## ` heading
    (or end of file).  Only `## ` (exactly two hashes) headings are considered
    top-level for the purpose of determining section boundaries.
    """
    positions: list[tuple[int, int, str]] = []
    lines = content.splitlines()
    in_section = False
    section_start = 0
    section_title_lower = ""

    for i, line in enumerate(lines):
        m = _SECTION_HEADING_RE.match(line)
        if not m:
            continue
        heading_text = m.group("title").strip()
        heading_level = len(line) - len(line.lstrip("#"))
        title_lower = heading_text.lower()

        if heading_level == 2:  # top-level ## heading
            if in_section:
                # close previous section
                positions.append((section_start, i, section_title_lower))
            in_section = True
            section_start = i
            section_title_lower = title_lower

    if in_section:
        positions.append((section_start, len(lines), section_title_lower))

    return positions


def strip_excluded_sections(content: str | None) -> str:
    """Return the doc content with ``## Out of Scope`` and ``## Notes`` sections
    removed.

    A section runs from its ``## Heading`` line to the next top-level ``## ``
    heading (exclusive) or end of file.  Content inside code fences is left
    untouched and is NOT stripped — code fences do not contain prose that
    should influence file extraction.
    """
    if not content:
        return ""

    # Record code-fence ranges so we can skip them
    fence_ranges: list[tuple[int, int]] = []
    for m in _CODE_FENCE_RE.finditer(content):
        fence_ranges.append((m.start(), m.end()))

    def _in_fence(offset: int) -> bool:
        return any(start <= offset < end for start, end in fence_ranges)

    result_lines: list[str] = []
    lines = content.splitlines()
    section_ranges = _iter_section_ranges(content)

    # No headings at all — return the full document unchanged
    if not section_ranges:
        return content

    for start, end, title_lower in section_ranges:
        if title_lower in _EXCLUDED_SECTION_TITLES:
            # Skip all lines of this section, but protect lines inside fences
            for i in range(start, end):
                if _in_fence(_get_offset_for_line(content, i)):
                    result_lines.append(lines[i])
            continue
        for i in range(start, end):
            result_lines.append(lines[i])

    return "\n".join(result_lines)


def _get_offset_for_line(content: str, line_index: int) -> int:
    """Return the byte offset in content where line `line_index` starts."""
    lines_before = content.splitlines()[:line_index]
    return sum(len(line) + 1 for line in lines_before)


# ---------------------------------------------------------------------------
# Dependency parsing
# ---------------------------------------------------------------------------


def _strip_parenthetical(text: str) -> str:
    """Remove parenthetical commentary from a string.

    ``F-00069 (provides make test-parallel)`` → ``F-00069``
    ``F-00069 - reason`` → ``F-00069``
    """
    text = re.sub(r"\s*\([^)]*\)", "", text)
    text = re.sub(r"\s*-\s+.*", "", text)
    return text.strip()


def _extract_ids_from_line(line: str) -> list[str]:
    """Extract all F-/I-/CR- IDs from a line, strip commentary, dedupe, preserve order."""
    found = _ID_PATTERN.findall(line)
    cleaned = [_strip_parenthetical(id_) for id_ in found]
    seen: list[str] = []
    for c in cleaned:
        if c and c not in seen:
            seen.append(c)
    return seen


def _parse_depends_line(line: str, field_name: str) -> list[str]:
    """Parse a single `**Depends on**:` or `**Blocks**:` line.

    Handles:
    - ``**Depends on**: None`` / ``**Blocks**: None``
    - ``**Depends on**: —``
    - ``**Depends on**:`` (empty value)
    - ``**Depends on**: F-00069, I-00042, CR-99025``
    - ``**Depends on**: F-00069 (provides ...)``
    - ``**Depends on**: F-00069 - reason``
    """
    # Build a pattern that matches the field at the start of the meaningful content.
    # Handles optional leading bullet (- ), sub-list (  ), or nothing.
    # Captures everything AFTER the `**: ` delimiter.
    field_re = re.compile(
        r"^\s*(?:-\s+|\d+\.\s+)?\*\*" + re.escape(field_name) + r"\*\*\s*:\s*(?P<value>.*)",
        re.IGNORECASE,
    )
    m = field_re.match(line.strip())
    if not m:
        return []

    value = m.group("value").strip()

    if not value or value.lower() in ("none", "—"):
        return []

    return _extract_ids_from_line(value)


def _find_field_line(lines: list[str], field_name: str) -> str | None:
    """Find the first line matching `**FieldName**:` (case-insensitive prefix)."""
    pattern = re.compile(r"^\s*\*\*" + re.escape(field_name) + r"\*\*\s*:", re.IGNORECASE)
    for line in lines:
        if pattern.match(line):
            return line
    return None


@dataclass(frozen=True)
class Dependencies:
    """Result of parsing a design document's dependency section."""

    depends_on: list[str]
    blocks: list[str]


def parse_dependencies(content: str | None) -> Dependencies:
    """Parse ``**Depends on**:`` and ``**Blocks**:`` lines from a design doc.

    Tolerates: missing section, "None", "—", empty, comma-separated lists,
    parenthetical commentary after IDs, dash-separated reasons.  Never raises.
    Logs a WARNING for malformed lines but returns sensible defaults.
    """
    if not content:
        return Dependencies(depends_on=[], blocks=[])

    # Find the ## Dependencies section (case-insensitive)
    in_deps_section = False
    deps_lines: list[str] = []
    for line in content.splitlines():
        stripped = line.strip()
        if re.match(r"^#{1,6}\s+dependencies\s*$", stripped, re.IGNORECASE):
            in_deps_section = True
            continue
        if in_deps_section:
            # Stop at the next top-level ## heading
            if re.match(r"^##\s+", stripped):
                break
            deps_lines.append(line)

    if not deps_lines:
        return Dependencies(depends_on=[], blocks=[])

    depends_on_ids: list[str] = []
    blocks_ids: list[str] = []

    for raw_line in deps_lines:
        line = raw_line.strip()
        if not line:
            continue

        # Try to match "**Depends on**:" first
        dep_line = _parse_depends_line(line, "Depends on")
        if dep_line:
            depends_on_ids.extend(dep_line)
            continue

        # Try to match "**Blocks**:" next
        block_line = _parse_depends_line(line, "Blocks")
        if block_line:
            blocks_ids.extend(block_line)
            continue

        # Malformed line — log and skip
        if _ID_PATTERN.search(line):
            logger.warning("Malformed dependency line — skipping: %r", line)

    return Dependencies(depends_on=depends_on_ids, blocks=blocks_ids)
