"""Unit tests for orch.batch_planner — dependency analysis, plan + diagram generation."""

from __future__ import annotations

from orch.batch_planner import (
    analyze_dependencies,
    extract_affected_files,
    generate_drawio,
    generate_execution_plan_md,
    generate_png,
    has_database_step,
)

# ---------------------------------------------------------------------------
# extract_affected_files
# ---------------------------------------------------------------------------


def test_extract_affected_files_finds_src_paths() -> None:
    doc = """
    | File | Change |
    | src/innoforge/api/routes.py | Add endpoint |
    | frontend/src/components/Foo.tsx | New component |
    """
    files = extract_affected_files(doc)
    assert "src/innoforge/api/routes.py" in files
    assert "frontend/src/components/Foo.tsx" in files


def test_extract_affected_files_excludes_tests() -> None:
    doc = "Modified src/innoforge/tests/test_foo.py and src/innoforge/core.py"
    files = extract_affected_files(doc)
    assert "src/innoforge/core.py" in files
    assert not any("tests/" in f for f in files)


def test_extract_affected_files_empty() -> None:
    assert extract_affected_files(None) == []
    assert extract_affected_files("") == []


# ---------------------------------------------------------------------------
# has_database_step
# ---------------------------------------------------------------------------


def test_has_database_step_true() -> None:
    steps = [{"agent_label": "Database", "step_type": "implementation"}]
    assert has_database_step(steps) is True


def test_has_database_step_false_wrong_type() -> None:
    steps = [{"agent_label": "Database", "step_type": "code_review"}]
    assert has_database_step(steps) is False


def test_has_database_step_false_no_db() -> None:
    steps = [{"agent_label": "Backend", "step_type": "implementation"}]
    assert has_database_step(steps) is False


def test_has_database_step_empty() -> None:
    assert has_database_step([]) is False


# ---------------------------------------------------------------------------
# analyze_dependencies
# ---------------------------------------------------------------------------


def _make_item(
    item_id: str,
    title: str = "Test item",
    item_type: str = "Feature",
    depends_on: list[str] | None = None,
    design_doc: str | None = None,
    steps: list[dict[str, str]] | None = None,
) -> dict:
    return {
        "id": item_id,
        "title": title,
        "type": item_type,
        "depends_on": depends_on or [],
        "design_doc_content": design_doc,
        "steps": steps or [],
    }


def test_analyze_no_deps_all_group_0() -> None:
    items = [_make_item("F001"), _make_item("F002"), _make_item("F003")]
    result = analyze_dependencies(items)
    assert all(info.group == 0 for info in result.values())


def test_analyze_respects_explicit_deps() -> None:
    items = [
        _make_item("F001"),
        _make_item("F002", depends_on=["F001"]),
    ]
    result = analyze_dependencies(items)
    assert result["F001"].group == 0
    assert result["F002"].group == 1


def test_analyze_db_step_sequencing() -> None:
    """Items with database steps should be sequenced."""
    db_steps = [{"agent_label": "Database", "step_type": "implementation"}]
    items = [
        _make_item("F001", steps=db_steps),
        _make_item("F002", steps=db_steps),
        _make_item("F003"),
    ]
    result = analyze_dependencies(items)
    # F001 and F002 both have DB steps — must be in different groups
    assert result["F001"].group != result["F002"].group
    # F003 has no DB step and no deps — group 0
    assert result["F003"].group == 0


def test_analyze_file_overlap_creates_dependency() -> None:
    doc_a = "Changes to src/innoforge/api/routes.py"
    doc_b = "Also changes src/innoforge/api/routes.py"
    items = [
        _make_item("F001", design_doc=doc_a),
        _make_item("F002", design_doc=doc_b),
    ]
    result = analyze_dependencies(items)
    # File overlap should create a dependency — different groups
    assert result["F001"].group != result["F002"].group
    assert "F002" in result["F001"].overlap_with or "F001" in result["F002"].overlap_with


def test_analyze_external_deps_ignored() -> None:
    items = [_make_item("F001", depends_on=["EXTERNAL-999"])]
    result = analyze_dependencies(items)
    assert result["F001"].group == 0
    assert result["F001"].depends_on == []


# ---------------------------------------------------------------------------
# generate_execution_plan_md
# ---------------------------------------------------------------------------


def test_generate_plan_md_contains_batch_id() -> None:
    items = [_make_item("F001"), _make_item("F002")]
    analysis = analyze_dependencies(items)
    md = generate_execution_plan_md("BATCH-00001", analysis, 4)
    assert "BATCH-00001" in md
    assert "F001" in md
    assert "F002" in md
    assert "## Dependency Analysis" in md
    assert "## Execution Order" in md
    assert "## Warnings" in md


# ---------------------------------------------------------------------------
# generate_drawio
# ---------------------------------------------------------------------------


def test_generate_drawio_valid_xml() -> None:
    items = [_make_item("F001"), _make_item("F002", depends_on=["F001"])]
    analysis = analyze_dependencies(items)
    xml = generate_drawio("BATCH-00001", analysis, 4)
    assert xml.startswith("<mxfile")
    assert "BATCH-00001" in xml
    assert 'id="node-F001"' in xml
    assert 'id="node-F002"' in xml
    assert 'id="edge-F001-F002"' in xml


# ---------------------------------------------------------------------------
# generate_png
# ---------------------------------------------------------------------------


def test_generate_png_returns_bytes() -> None:
    """PNG generation returns bytes (requires Pillow)."""
    items = [_make_item("F001"), _make_item("F002")]
    analysis = analyze_dependencies(items)
    result = generate_png("BATCH-00001", analysis, 4)
    if result is not None:
        # Pillow is available — check PNG magic bytes
        assert result[:4] == b"\x89PNG"
