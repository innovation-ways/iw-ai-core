"""Tests for batch planner overlap detection (AC1, AC3, AC4, AC5).

These tests verify that `analyze_dependencies` uses fnmatch/glob-intersection
semantics (via `scope_overlap.globs_intersect`) instead of plain string equality
set intersection, and that `generate_execution_plan_md` renders the max_parallel
value it is given without hardcoding.

RED evidence (pre-fix):
- test_glob_vs_concrete_file_overlap — pre-fix planner uses plain set & set
  on affected_files, so `skills/iw-ai-core-testing/**` ∩ `skills/iw-ai-core-testing/SKILL.md`
  is empty → analysis["A"].overlap_with == [] → `assert "B" in []` FAILS
- test_dir_glob_vs_dir_glob_overlap — same pre-fix bug, `a/**` ∩ `a/b/**` is empty
- test_cross_batch_overlap_uses_globs_intersect — pre-fix cross-batch loop uses
  set & set; active item with `dashboard/**` vs batch item with `dashboard/static/x.js`
  → cross_batch_conflicts empty → assertion fails
- test_execution_plan_md_renders_given_max_parallel — GREEN regression-lock only;
  the helper was always correct; the bug was the caller passing literal 4.
"""

from __future__ import annotations

from orch.batch_planner import (
    analyze_dependencies,
    generate_execution_plan_md,
)


def _item(
    item_id: str,
    title: str,
    item_type: str = "ChangeRequest",
    impacted_paths: list[str] | None = None,
    design_doc_content: str | None = None,
    steps: list[dict[str, object]] | None = None,
    depends_on: list[str] | None = None,
) -> dict[str, object]:
    return {
        "id": item_id,
        "title": title,
        "type": item_type,
        "impacted_paths": impacted_paths or [],
        "design_doc_content": design_doc_content,
        "steps": steps or [],
        "depends_on": depends_on or [],
    }


# ---------------------------------------------------------------------------
# AC1 — glob vs concrete file
# ---------------------------------------------------------------------------


def test_glob_vs_concrete_file_overlap() -> None:
    """A glob-style impacted_paths entry overlaps a concrete file under it.

    Pre-fix: `analysis["A"].overlap_with == []` (plain set & set on strings).
    Post-fix: `"B" in analysis["A"].overlap_with` and `"A" in analysis["B"].overlap_with`.
    """
    items = [
        _item(
            item_id="A",
            title="Skill update",
            impacted_paths=["skills/iw-ai-core-testing/**"],
        ),
        _item(
            item_id="B",
            title="Skill readme",
            impacted_paths=["skills/iw-ai-core-testing/SKILL.md"],
        ),
    ]

    analysis = analyze_dependencies(items, active_items_data=None)

    assert "B" in analysis["A"].overlap_with, (
        "glob ** pattern must overlap concrete file under it; "
        f"got overlap_with={analysis['A'].overlap_with!r}"
    )
    assert "A" in analysis["B"].overlap_with
    # The planner adds an implicit depends_on edge for overlapping pairs
    assert "A" in analysis["B"].depends_on or "B" in analysis["A"].depends_on


# ---------------------------------------------------------------------------
# AC1 variant — dir glob vs dir glob
# ---------------------------------------------------------------------------


def test_dir_glob_vs_dir_glob_overlap() -> None:
    """A broader directory glob overlaps a nested directory glob.

    `a/**` should intersect `a/b/**` because the latter is a subset.
    """
    items = [
        _item(item_id="A", title="Module a", impacted_paths=["a/**"]),
        _item(item_id="B", title="Module a/b", impacted_paths=["a/b/**"]),
    ]

    analysis = analyze_dependencies(items, active_items_data=None)

    # At least one item must see overlap (proves the fix is active — pre-fix: empty lists).
    total_overlaps = len(analysis["A"].overlap_with) + len(analysis["B"].overlap_with)
    assert total_overlaps >= 2, (
        f"at least 2 overlap entries expected (A→B and B→A); "
        f"got A={analysis['A'].overlap_with}, B={analysis['B'].overlap_with}"
    )
    assert "B" in analysis["A"].overlap_with, (
        f"dir glob a/** must overlap nested dir glob a/b/**; "
        f"got overlap_with={analysis['A'].overlap_with!r}"
    )
    assert "A" in analysis["B"].overlap_with


# ---------------------------------------------------------------------------
# AC4 — no overlap on disjoint paths
# ---------------------------------------------------------------------------


def test_strictly_disjoint_paths_no_overlap() -> None:
    """Strictly disjoint impacted_paths yield empty overlap_with on both sides."""
    items = [
        _item(
            item_id="A",
            title="Foo bar",
            impacted_paths=["foo/bar.py"],
        ),
        _item(
            item_id="B",
            title="Baz qux",
            impacted_paths=["baz/qux.py"],
        ),
    ]

    analysis = analyze_dependencies(items, active_items_data=None)

    assert analysis["A"].overlap_with == []
    assert analysis["B"].overlap_with == []
    # Both end up in group 0 (parallel) since nothing forces serialisation
    assert analysis["A"].group == 0
    assert analysis["B"].group == 0


# ---------------------------------------------------------------------------
# AC1 — cross-batch overlap via globs_intersect
# ---------------------------------------------------------------------------


def test_cross_batch_overlap_uses_globs_intersect() -> None:
    """A batch item overlaps an actively-executing item from another batch.

    Pre-fix: cross-batch loop uses plain set & set on strings;
    `dashboard/**` ∩ `dashboard/static/x.js` → empty → assertion fails.
    Post-fix: `cross_batch_conflicts` contains the active item's batch+id+overlap globs.
    """
    batch_items = [
        _item(
            item_id="NEW-1",
            title="New UI item",
            impacted_paths=["dashboard/static/x.js"],
        ),
    ]
    active_items = [
        {
            "id": "ACTIVE-1",
            "batch_id": "BATCH-ACTIVE",
            "impacted_paths": ["dashboard/**"],
            "design_doc_content": None,
        },
    ]

    analysis = analyze_dependencies(batch_items, active_items_data=active_items)

    entry = analysis["NEW-1"].cross_batch_conflicts
    assert len(entry) == 1, f"expected 1 cross-batch conflict; got {entry}"
    batch_id, active_id, overlap_globs = entry[0]
    assert batch_id == "BATCH-ACTIVE"
    assert active_id == "ACTIVE-1"
    # globs_intersect returns items from the first list that match the second
    # list's glob patterns — the batch item's concrete path matches the active
    # item's `dashboard/**` glob
    assert "dashboard/static/x.js" in overlap_globs


# ---------------------------------------------------------------------------
# AC3 — generate_execution_plan_md renders the max_parallel argument
# ---------------------------------------------------------------------------


def test_execution_plan_md_renders_given_max_parallel() -> None:
    """The rendered markdown must include the exact max_parallel value passed.

    This is a GREEN regression-lock: the helper was always correct; the bug
    was the caller (dashboard/routers/actions.py:_build_plan) passing a literal 4.
    Verifying value variation proves the rendered value tracks the argument.
    """
    items = [
        _item(item_id="A", title="Alpha", impacted_paths=["foo/a.py"]),
        _item(item_id="B", title="Beta", impacted_paths=["bar/b.py"]),
    ]
    analysis = analyze_dependencies(items, active_items_data=None)

    for n in (3, 7):
        md = generate_execution_plan_md("BATCH-TEST", analysis, max_parallel=n)
        assert f"**Max Parallel**: {n}" in md, (
            f"expected **Max Parallel**: {n} in markdown; got the rendered value "
            f"from the markdown header"
        )
        # Defend against a future regression that re-hardcodes any value
        assert f"**Max Parallel**: {n - 1}" not in md
