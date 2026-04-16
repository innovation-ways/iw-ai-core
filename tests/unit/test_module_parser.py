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
    from orch.rag.parser import parse_modules_from_level1

    modules = parse_modules_from_level1(FIXTURE_LEVEL1_DOC)
    assert len(modules) == 3


def test_parse_module_fields():
    from orch.rag.parser import parse_modules_from_level1

    modules = parse_modules_from_level1(FIXTURE_LEVEL1_DOC)
    engine = next(m for m in modules if m["path"] == "engine/")
    assert engine["name"] == "C++ Sensor Engine"
    assert engine["slug"] == "engine"
    assert "UDP" in engine["description"]


def test_parse_empty_doc_returns_empty_list():
    from orch.rag.parser import parse_modules_from_level1

    assert parse_modules_from_level1("") == []


def test_parse_no_components_section_returns_empty_list():
    from orch.rag.parser import parse_modules_from_level1

    assert parse_modules_from_level1("# Title\n\nSome content with no components.") == []


def test_parse_slug_with_nested_path():
    from orch.rag.parser import parse_modules_from_level1

    doc = "## Components\n\n- `src/engine/core/` -- Core: processing\n"
    modules = parse_modules_from_level1(doc)
    assert modules[0]["slug"] == "src-engine-core"


def test_parse_never_raises():
    from orch.rag.parser import parse_modules_from_level1

    result = parse_modules_from_level1("```\nnot valid markdown\n```\n\x00\xff")
    assert isinstance(result, list)


def test_parse_with_bold_name_format():
    from orch.rag.parser import parse_modules_from_level1

    doc = "## Components\n\n- **My Module** (`engine/`): Does things\n"
    modules = parse_modules_from_level1(doc)
    assert len(modules) == 1
    assert modules[0]["name"] == "My Module"
    assert modules[0]["path"] == "engine/"
    assert modules[0]["slug"] == "engine"


def test_parse_plain_format():
    from orch.rag.parser import parse_modules_from_level1

    doc = "## Components\n\n- engine/ -- Engine: main component\n"
    modules = parse_modules_from_level1(doc)
    assert len(modules) == 1
    assert modules[0]["name"] == "engine/"
    assert modules[0]["path"] == "engine/"
    assert modules[0]["slug"] == "engine"
