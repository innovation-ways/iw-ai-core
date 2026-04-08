"""Unit tests for the batch dependency planner — pure logic, no DB required."""

import pytest

from orch.cli.batch_commands import build_execution_groups

# ---------------------------------------------------------------------------
# No dependencies
# ---------------------------------------------------------------------------


def test_no_deps_all_in_group_0() -> None:
    item_deps = {"I001": [], "I002": [], "I003": []}
    groups = build_execution_groups(item_deps)
    assert groups == {"I001": 0, "I002": 0, "I003": 0}


def test_single_item_no_deps() -> None:
    groups = build_execution_groups({"I001": []})
    assert groups == {"I001": 0}


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
    # I001 depends on EXTERNAL-999 which is not in the batch — should be in group 0
    item_deps = {"I001": ["EXTERNAL-999"], "I002": []}
    groups = build_execution_groups(item_deps)
    assert groups["I001"] == 0
    assert groups["I002"] == 0


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
