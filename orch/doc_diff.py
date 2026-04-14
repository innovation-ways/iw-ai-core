"""Section-aware document diff module for iw-ai-core.

Computes structured diffs between two document version strings by splitting
each version into H2-bounded sections and diffing each section pair individually.
This module has no database dependencies — it operates on strings only.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from typing import Literal

from orch.doc_sections import split_by_sections


@dataclass
class SectionDiff:
    """Diff result for a single document section."""

    section_name: str
    """H2 heading text, or 'Document' for docs with no H2 headings."""

    status: Literal["added", "removed", "changed", "unchanged"]
    """Change classification for this section between versions."""

    unified_diff: list[str] = field(default_factory=list)
    """Unified diff lines for this section (empty when status is 'unchanged')."""


@dataclass
class DocDiff:
    """Structured diff between two document versions."""

    version_old: int
    version_new: int
    sections: list[SectionDiff] = field(default_factory=list)


def diff_document_versions(
    old_content: str,
    new_content: str,
    version_old: int,
    version_new: int,
) -> DocDiff:
    """Compute a section-aware diff between two document version strings.

    Splits both versions into H2-bounded sections using extract_sections/
    split_by_sections, then diffs each section pair. Sections present only
    in the old version are classified as 'removed'; sections only in the new
    version are classified as 'added'.

    Documents with no H2 headings are treated as a single section named
    "Document".

    Args:
        old_content: Markdown content of the older version.
        new_content: Markdown content of the newer version.
        version_old: Version number of the old content.
        version_new: Version number of the new content.

    Returns:
        DocDiff with one SectionDiff per section found in either version.
    """
    old_sections = split_by_sections(old_content)
    new_sections = split_by_sections(new_content)

    all_section_names = list(dict.fromkeys(list(old_sections.keys()) + list(new_sections.keys())))

    section_diffs: list[SectionDiff] = []
    for name in all_section_names:
        old_body = old_sections.get(name)
        new_body = new_sections.get(name)

        if old_body is None:
            if new_body is None:
                raise ValueError(f"Section {name!r} not found in either version")
            section_diffs.append(
                SectionDiff(
                    section_name=name,
                    status="added",
                    unified_diff=list(
                        difflib.unified_diff(
                            [],
                            new_body.splitlines(keepends=True),
                            fromfile=f"v{version_old}/{name}",
                            tofile=f"v{version_new}/{name}",
                            n=3,
                        )
                    ),
                )
            )
        elif new_body is None:
            section_diffs.append(
                SectionDiff(
                    section_name=name,
                    status="removed",
                    unified_diff=list(
                        difflib.unified_diff(
                            old_body.splitlines(keepends=True),
                            [],
                            fromfile=f"v{version_old}/{name}",
                            tofile=f"v{version_new}/{name}",
                            n=3,
                        )
                    ),
                )
            )
        elif old_body == new_body:
            section_diffs.append(SectionDiff(section_name=name, status="unchanged"))
        else:
            section_diffs.append(
                SectionDiff(
                    section_name=name,
                    status="changed",
                    unified_diff=list(
                        difflib.unified_diff(
                            old_body.splitlines(keepends=True),
                            new_body.splitlines(keepends=True),
                            fromfile=f"v{version_old}/{name}",
                            tofile=f"v{version_new}/{name}",
                            n=3,
                        )
                    ),
                )
            )

    return DocDiff(version_old=version_old, version_new=version_new, sections=section_diffs)
