"""Unit tests for parse_modules_from_level1().

RED phase — tests are written BEFORE implementation and must FAIL initially.
"""

from __future__ import annotations

FIXTURE_LEVEL1_DOC = """
# Architecture Overview

## Components

- `engine/` -- C++ Sensor Engine: UDP listener and FFT pipeline
- `api/` -- Python FastAPI: REST backend and authentication
- `worker/` -- Celery: async background job processing
"""


def test_parse_returns_three_modules():
    """Verifies that parse returns three modules."""
    from orch.rag.parser import parse_modules_from_level1

    modules = parse_modules_from_level1(FIXTURE_LEVEL1_DOC)
    assert len(modules) == 3


def test_parse_module_fields():
    """Verifies that parse module fields."""
    from orch.rag.parser import parse_modules_from_level1

    modules = parse_modules_from_level1(FIXTURE_LEVEL1_DOC)
    engine = next(m for m in modules if m["path"] == "engine/")
    assert engine["name"] == "C++ Sensor Engine"
    assert engine["slug"] == "engine"
    assert "UDP" in engine["description"]


def test_parse_empty_doc_returns_empty_list():
    """Verifies that parse empty doc returns empty list."""
    from orch.rag.parser import parse_modules_from_level1

    assert parse_modules_from_level1("") == []


def test_parse_no_components_section_returns_empty_list():
    """Verifies that parse no components section returns empty list."""
    from orch.rag.parser import parse_modules_from_level1

    assert parse_modules_from_level1("# Title\n\nSome content with no components.") == []


def test_parse_slug_with_nested_path():
    """Verifies that parse slug with nested path."""
    from orch.rag.parser import parse_modules_from_level1

    doc = "## Components\n\n- `src/engine/core/` -- Core: processing\n"
    modules = parse_modules_from_level1(doc)
    assert modules[0]["slug"] == "src-engine-core"


def test_parse_never_raises():
    """Verifies that parse never raises."""
    from orch.rag.parser import parse_modules_from_level1

    result = parse_modules_from_level1("```\nnot valid markdown\n```\n\x00\xff")
    assert isinstance(result, list)


def test_parse_with_bold_name_format():
    """Verifies that parse with bold name format."""
    from orch.rag.parser import parse_modules_from_level1

    doc = "## Components\n\n- **My Module** (`engine/`): Does things\n"
    modules = parse_modules_from_level1(doc)
    assert len(modules) == 1
    assert modules[0]["name"] == "My Module"
    assert modules[0]["path"] == "engine/"
    assert modules[0]["slug"] == "engine"


def test_parse_plain_format():
    """Verifies that parse plain format."""
    from orch.rag.parser import parse_modules_from_level1

    doc = "## Components\n\n- engine/ -- Engine: main component\n"
    modules = parse_modules_from_level1(doc)
    assert len(modules) == 1
    assert modules[0]["name"] == "engine/"
    assert modules[0]["path"] == "engine/"
    assert modules[0]["slug"] == "engine"


def test_parse_star_bullet_backtick_format():
    """Verifies that parse star bullet backtick format."""
    from orch.rag.parser import parse_modules_from_level1

    doc = "## Components\n\n* `engine/` -- Engine: main component\n"
    modules = parse_modules_from_level1(doc)
    assert len(modules) == 1
    assert modules[0]["path"] == "engine/"
    assert modules[0]["slug"] == "engine"


def test_parse_bold_with_path_inside_parens():
    """LLM-emitted format: bullet **Name (`path`)**: description — bullet may be `*` or `-`."""
    from orch.rag.parser import parse_modules_from_level1

    doc = (
        "## Components\n\n"
        "* **Orchestration Daemon (`orch/daemon`)**: A long-running process.\n"
        "* **Web Dashboard (`dashboard`)**: A FastAPI app.\n"
    )
    modules = parse_modules_from_level1(doc)
    assert len(modules) == 2
    assert modules[0]["name"] == "Orchestration Daemon"
    assert modules[0]["path"] == "orch/daemon"
    assert modules[0]["slug"] == "orch-daemon"
    assert "long-running" in modules[0]["description"]
    assert modules[1]["name"] == "Web Dashboard"
    assert modules[1]["path"] == "dashboard"
    assert modules[1]["slug"] == "dashboard"


def test_parse_skips_top_level_matching_header_with_empty_body():
    """Top-level '# Architecture Map' matches the header keyword but the section body
    contains no parseable entries; parser must continue and use '## Components' below."""
    from orch.rag.parser import parse_modules_from_level1

    doc = (
        "# Architecture Map\n"
        "\n"
        "## Purpose\n"
        "Some prose about the project.\n"
        "\n"
        "## Components\n"
        "\n"
        "* **Engine (`engine/`)**: Sensor engine.\n"
    )
    modules = parse_modules_from_level1(doc)
    assert len(modules) == 1
    assert modules[0]["name"] == "Engine"
    assert modules[0]["path"] == "engine/"
