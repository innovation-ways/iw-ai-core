"""Property-based tests for doc-diff round-trip correctness.

Tests that `orch/doc_diff.py` and `orch/doc_sections.py` satisfy:
  1. split_by_sections is reversible: reassembling sections yields a doc
     that parses back to the same section names
  2. extract_sections and split_by_sections agree on section names and order

Using Hypothesis @given with composite strategies that build arbitrary documents
with unique section headings.
"""

from __future__ import annotations

from collections.abc import Callable

from hypothesis import given, settings
from hypothesis.strategies import (
    composite,
    integers,
    lists,
    text,
)

from orch.doc_diff import diff_document_versions
from orch.doc_sections import extract_sections, split_by_sections

# ----- Strategy helpers ---------------------------------------------------------------


@composite
def _unique_section(draw: Callable, used_names: set[str]) -> tuple[str, str]:
    """Build a section with a heading name unique within this document.

    Returns (heading_text, section_full_text).
    """
    attempt = 0
    while True:
        name = draw(text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz "))
        if name not in used_names:
            break
        attempt += 1
        if attempt > 100:
            name = f"{name} {len(used_names)}"
            break
    body_lines = draw(
        lists(
            text(min_size=0, max_size=100, alphabet="abcdefghijklmnopqrstuvwxyz .\n"),
            min_size=0,
            max_size=20,
        )
    )
    body = "\n".join(body_lines)
    # split_by_sections includes the heading line in the body
    section_text = f"## {name}\n\n{body}\n"
    return name, section_text


@composite
def markdown_document(draw: Callable, min_sections: int = 1, max_sections: int = 6) -> str:
    """Build a well-formed markdown document with unique H2 section headings.

    All section names are guaranteed unique so that extract_sections and
    split_by_sections identify the same sections in the same order.
    """
    n_sections = draw(integers(min_value=min_sections, max_value=max_sections))
    sections: list[str] = []
    used_names: set[str] = set()
    for _ in range(n_sections):
        name, section_text = draw(_unique_section(used_names))
        used_names.add(name)
        sections.append(section_text)
    return "\n".join(sections)


# ----- Property tests -----------------------------------------------------------------


@settings(max_examples=20)
@given(doc=markdown_document())
def test_reassembled_doc_parses_to_same_sections(doc: str) -> None:
    """Property: splitting and reassembling a doc produces sections that parse identically.

    When we split a doc, reassemble the sections, and split again, the second
    parse should yield the same section names in the same order.
    """
    # First parse
    sections = split_by_sections(doc)
    first_names = list(sections.keys())

    # Reassemble: join section bodies (each body includes the heading line)
    reassembled_parts = [sections[name] for name in first_names]
    reassembled = "\n".join(reassembled_parts)

    # Second parse
    second_sections = split_by_sections(reassembled)
    second_names = list(second_sections.keys())

    # Section names must be identical
    assert second_names == first_names


@settings(max_examples=20)
@given(doc=markdown_document())
def test_extract_and_split_agree_on_names(doc: str) -> None:
    """Property: extract_sections and split_by_sections return the same ordered name list."""
    names_from_extract = extract_sections(doc)
    names_from_split = list(split_by_sections(doc).keys())
    assert names_from_extract == names_from_split


@settings(max_examples=20)
@given(doc1=markdown_document(), doc2=markdown_document())
def test_diff_section_names_symmetric(doc1: str, doc2: str) -> None:
    """Property: diff_document_versions finds the same section names in both directions."""
    diff_ab = diff_document_versions(doc1, doc2, version_old=1, version_new=2)
    diff_ba = diff_document_versions(doc2, doc1, version_old=2, version_new=1)

    names_ab = {s.section_name for s in diff_ab.sections}
    names_ba = {s.section_name for s in diff_ba.sections}
    assert names_ab == names_ba


@settings(max_examples=20)
@given(doc=markdown_document(min_sections=1, max_sections=4))
def test_diff_preserves_version_metadata(doc: str) -> None:
    """Property: diff_document_versions records version numbers correctly."""
    diff = diff_document_versions(doc, doc, version_old=5, version_new=7)
    assert diff.version_old == 5
    assert diff.version_new == 7


@settings(max_examples=20)
@given(doc=markdown_document(min_sections=1))
def test_self_diff_marks_every_section_unchanged(doc: str) -> None:
    """Property: diffing a document against itself marks every section 'unchanged'.

    Stronger than checking status is *any* valid value — the only correct result
    when old and new are identical is that nothing changed, so we pin the exact
    expected status for every section.
    """
    diff = diff_document_versions(doc, doc, version_old=1, version_new=2)
    statuses = [s.status for s in diff.sections]
    assert statuses == ["unchanged"] * len(diff.sections), (
        f"Self-diff produced non-unchanged statuses: {statuses}"
    )


@settings(max_examples=20)
@given(doc=markdown_document())
def test_all_section_names_are_recoverable(doc: str) -> None:
    """Property: extract_sections and split_by_sections name the exact same sections.

    Tighter than `for name in names: assert name in sections`:
    - Set equality also catches the reverse failure (split returns names that
      extract didn't, or vice versa).
    - Ordering is also enforced — the two parsers must agree on the order in
      which the H2 headings appear.
    """
    names = extract_sections(doc)
    sections = split_by_sections(doc)
    split_names = list(sections.keys())
    assert names == split_names, (
        f"extract_sections and split_by_sections disagree: extract={names!r} split={split_names!r}"
    )
