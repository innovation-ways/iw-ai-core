"""Unit tests for the batch dependency planner — pure logic, no DB required."""

import pytest

from orch.batch_planner import analyze_dependencies
from orch.cli.batch_commands import build_execution_groups

# ---------------------------------------------------------------------------
# No dependencies
# ---------------------------------------------------------------------------


def test_no_deps_all_in_group_0() -> None:
    item_deps = {"I-00001": [], "I-00002": [], "I-00003": []}
    groups = build_execution_groups(item_deps)
    assert groups == {"I-00001": 0, "I-00002": 0, "I-00003": 0}


def test_single_item_no_deps() -> None:
    groups = build_execution_groups({"I-00001": []})
    assert groups == {"I-00001": 0}


# ---------------------------------------------------------------------------
# Linear dependencies
# ---------------------------------------------------------------------------


def test_a_depends_on_b() -> None:
    # B must run before A → B in group 0, A in group 1
    item_deps = {"A": [], "B": ["A"]}
    groups = build_execution_groups(item_deps)
    assert groups["A"] == 0
    assert groups["B"] == 1


def test_chain_a_b_c() -> None:
    # C depends on B, B depends on A → groups 0, 1, 2
    item_deps = {"A": [], "B": ["A"], "C": ["B"]}
    groups = build_execution_groups(item_deps)
    assert groups["A"] == 0
    assert groups["B"] == 1
    assert groups["C"] == 2


# ---------------------------------------------------------------------------
# Diamond dependency
# ---------------------------------------------------------------------------


def test_diamond_dependency() -> None:
    # A has no deps; B and C both depend on A; D depends on B and C
    #   A (group 0) → B, C (group 1) → D (group 2)
    item_deps = {"A": [], "B": ["A"], "C": ["A"], "D": ["B", "C"]}
    groups = build_execution_groups(item_deps)
    assert groups["A"] == 0
    assert groups["B"] == groups["C"] == 1
    assert groups["D"] == 2


# ---------------------------------------------------------------------------
# External dependencies are ignored
# ---------------------------------------------------------------------------


def test_external_dependency_ignored() -> None:
    # I-00001 depends on EXTERNAL-999 which is not in the batch — should be in group 0
    item_deps = {"I-00001": ["EXTERNAL-999"], "I-00002": []}
    groups = build_execution_groups(item_deps)
    assert groups["I-00001"] == 0
    assert groups["I-00002"] == 0


# ---------------------------------------------------------------------------
# Circular dependency → ValueError
# ---------------------------------------------------------------------------


def test_circular_dependency_raises() -> None:
    item_deps = {"A": ["B"], "B": ["A"]}
    with pytest.raises(ValueError, match="Circular dependency"):
        build_execution_groups(item_deps)


def test_self_dependency_not_in_batch() -> None:
    # Self-references not in batch are filtered as external deps
    item_deps = {"A": ["A_external"], "B": []}
    groups = build_execution_groups(item_deps)
    assert groups["A"] == 0
    assert groups["B"] == 0


def test_three_way_cycle_raises() -> None:
    item_deps = {"A": ["C"], "B": ["A"], "C": ["B"]}
    with pytest.raises(ValueError, match="Circular dependency"):
        build_execution_groups(item_deps)


# ---------------------------------------------------------------------------
# analyze_dependencies — impacted_paths (F-00076)
# ---------------------------------------------------------------------------


def test_analyze_dependencies_reads_impacted_paths_column() -> None:
    """When impacted_paths is present, it is used instead of regex extraction."""
    items_data = [
        {
            "id": "F-00001",
            "title": "Test item",
            "type": "feature",
            "depends_on": [],
            "impacted_paths": ["orch/foo.py", "orch/bar.py"],
            "design_doc_content": None,
            "steps": [],
        },
    ]
    analysis = analyze_dependencies(items_data, active_items_data=None)
    assert analysis["F-00001"].affected_files == ["orch/foo.py", "orch/bar.py"]


def test_analyze_dependencies_falls_back_to_regex_when_impacted_paths_absent() -> None:
    """When impacted_paths is absent, regex extraction over design_doc_content is used."""
    items_data = [
        {
            "id": "F-00002",
            "title": "Test item",
            "type": "feature",
            "depends_on": [],
            "impacted_paths": None,
            "design_doc_content": (
                "## Description\n\nThis touches `orch/foo.py` and `dashboard/bar.ts`.\n"
            ),
            "steps": [],
        },
    ]
    analysis = analyze_dependencies(items_data, active_items_data=None)
    # extract_affected_files returns sorted unique paths, excluding test markers
    assert "orch/foo.py" in analysis["F-00002"].affected_files


def test_analyze_dependencies_impacted_paths_filters_test_files() -> None:
    """Test paths in impacted_paths are excluded from affected_files."""
    items_data = [
        {
            "id": "F-00003",
            "title": "Test item",
            "type": "feature",
            "depends_on": [],
            "impacted_paths": [
                "orch/foo.py",
                "orch/tests/bar.py",  # filtered: /tests/ marker
                "orch/__tests__/baz.py",  # filtered: /__tests__/ marker
                "conftest.py",  # filtered: conftest marker
                "foo.test.py",  # filtered: .test. marker
            ],
            "design_doc_content": None,
            "steps": [],
        },
    ]
    analysis = analyze_dependencies(items_data, active_items_data=None)
    affected = analysis["F-00003"].affected_files
    assert "orch/foo.py" in affected
    assert "orch/tests/bar.py" not in affected
    assert "orch/__tests__/baz.py" not in affected
    assert "conftest.py" not in affected
    assert "foo.test.py" not in affected


def test_analyze_dependencies_cross_batch_uses_impacted_paths() -> None:
    """Cross-batch overlap detection uses impacted_paths when available."""
    items_data = [
        {
            "id": "F-00004",
            "title": "New item",
            "type": "feature",
            "depends_on": [],
            "impacted_paths": ["orch/shared.py"],
            "design_doc_content": None,
            "steps": [],
        },
    ]
    active_items_data = [
        {
            "id": "F-00005",
            "batch_id": "B-00001",
            "impacted_paths": ["orch/shared.py", "orch/other.py"],
            "design_doc_content": None,
        },
    ]
    analysis = analyze_dependencies(items_data, active_items_data=active_items_data)
    assert ("B-00001", "F-00005", ["orch/shared.py"]) in analysis["F-00004"].cross_batch_conflicts
