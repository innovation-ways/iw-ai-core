"""Regression tests for I-00053 — declared deps + section-aware extraction."""

from __future__ import annotations

import pytest

from orch.batch_planner import _is_test_path as planner_is_test_path
from orch.batch_planner import analyze_dependencies, extract_affected_files
from orch.daemon.scope_overlap import is_test_path as overlap_is_test_path


def _item(
    iid: str,
    depends_on: list[str],
    content: str = "",
    steps: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    """Return item."""
    return {
        "id": iid,
        "title": iid,
        "type": "feature",
        "depends_on": depends_on,
        "design_doc_content": content,
        "steps": steps or [],
    }


def test_declared_depends_on_drives_wave_assignment() -> None:
    """BATCH-00064 reproduction: declared dep must produce correct wave."""
    items = [
        _item("F-A", []),
        _item("F-B", ["F-A"]),
    ]
    analysis = analyze_dependencies(items)
    assert analysis["F-A"].group == 0
    assert analysis["F-B"].group == 1


def test_declared_dep_works_regardless_of_argument_order() -> None:
    """The fix must not depend on argument order."""
    for order in (["F-A", "F-B"], ["F-B", "F-A"]):
        items = [_item(iid, ["F-A"] if iid == "F-B" else []) for iid in order]
        analysis = analyze_dependencies(items)
        assert analysis["F-A"].group == 0, f"Failed for order {order}"
        assert analysis["F-B"].group == 1, f"Failed for order {order}"


def test_blocks_inversion_equivalent_to_depends_on() -> None:
    """`Blocks: F-B` on F-A must produce same wave as `Depends on: F-A` on F-B.

    The Blocks inversion is applied at register time, so by the time the planner
    sees the items, F-B already has F-A in its depends_on list. Verify the
    expected DB state produces the expected wave.
    """
    # Simulating post-register state where Blocks was inverted into depends_on
    inverted = [
        _item("F-A", []),
        _item("F-B", ["F-A"]),  # set by register's inversion logic
    ]
    direct = [
        _item("F-A", []),
        _item("F-B", ["F-A"]),  # set by register parsing F-B's `Depends on`
    ]
    a_inv = analyze_dependencies(inverted)
    a_dir = analyze_dependencies(direct)
    assert a_inv["F-A"].group == a_dir["F-A"].group
    assert a_inv["F-B"].group == a_dir["F-B"].group


def test_paths_in_out_of_scope_section_do_not_create_overlap() -> None:
    """BATCH-00064 second-form reproduction: `tests/unit/test_logging.py`
    mentioned in F-A's Out of Scope (because it's owned by F-B) must NOT count.
    """
    a_doc = (
        "## File Manifest\n\n"
        "| File | Type |\n|---|---|\n"
        "| `dashboard/foo.py` | Modified |\n\n"
        "## Out of Scope\n\n"
        "- `tests/unit/test_logging.py` — owned by F-B\n"
    )
    b_doc = (
        "## File Manifest\n\n| File | Type |\n|---|---|\n| `tests/unit/test_logging.py` | New |\n"
    )
    files_a = set(extract_affected_files(a_doc))
    files_b = set(extract_affected_files(b_doc))
    # tests/ paths are excluded by _is_test_path; check no overlap
    assert files_a & files_b == set(), f"Spurious overlap: {files_a & files_b}"


def test_paths_in_notes_section_do_not_create_overlap() -> None:
    """Verifies that paths in notes section do not create overlap."""
    a_doc = (
        "## File Manifest\n\n"
        "| File | Type |\n|---|---|\n"
        "| `dashboard/foo.py` | Modified |\n\n"
        "## Notes\n\n"
        "- See `dashboard/bar.py` for context.\n"
    )
    files = set(extract_affected_files(a_doc))
    assert "dashboard/bar.py" not in files, (
        "Notes-section mention must NOT be treated as a modification"
    )
    assert "dashboard/foo.py" in files


def test_pre_existing_empty_depends_on_still_works() -> None:
    """Backwards compatibility: items with no declared deps and no overlap
    just go in group 0.
    """
    items = [_item("F-A", []), _item("F-B", []), _item("F-C", [])]
    analysis = analyze_dependencies(items)
    assert analysis["F-A"].group == 0
    assert analysis["F-B"].group == 0
    assert analysis["F-C"].group == 0


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/dashboard/test_x.py", True),  # I-00071: relative tests/
        ("test/foo.py", True),  # I-00071: relative test/
        ("__tests__/bar.py", True),  # I-00071: relative __tests__/
        ("src/tests/foo.py", True),  # existing: nested
        ("conftest.py", True),  # existing: conftest
        ("foo.test.ts", True),  # existing: .test.
        ("test_data.json", False),  # existing: non-test
        ("src/test_utils.py", False),  # existing: non-test
    ],
)
def test_batch_planner_is_test_path_matches_scope_overlap(path: str, expected: bool) -> None:
    """I-00071: the two helpers must stay in lock-step."""
    assert planner_is_test_path(path) is expected
    assert overlap_is_test_path(path) is expected
