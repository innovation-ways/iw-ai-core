"""Unit tests for authoring-time diagram validation (orch.diagram.validate).

Extraction and the validated/skipped/failed accounting are tested deterministically
by stubbing the renderers, so the suite does not depend on the mmdc/d2 toolchain.
"""

from __future__ import annotations

import orch.diagram.validate as v


def test_extract_diagram_blocks_returns_kind_and_source() -> None:
    """Verifies fenced mermaid/d2 blocks are extracted in document order."""
    md = "intro\n```mermaid\nflowchart TD\n A-->B\n```\nmid\n```d2\nx -> y\n```\nend\n"
    blocks = v.extract_diagram_blocks(md)
    assert len(blocks) == 2
    assert blocks[0][0] == "mermaid"
    assert blocks[0][1].find("flowchart TD") != -1
    assert blocks[1][0] == "d2"
    assert blocks[1][1].find("x -> y") != -1


def test_non_diagram_fences_are_ignored() -> None:
    """Verifies a python code fence is not treated as a diagram."""
    blocks = v.extract_diagram_blocks("```python\nprint(1)\n```\n")
    assert blocks == []


def test_all_valid_when_renderers_return_svg(monkeypatch) -> None:
    """Verifies diagrams that render to SVG are counted validated with no issues."""
    monkeypatch.setattr(v, "mermaid_available", lambda: True)
    monkeypatch.setattr(v, "d2_available", lambda: True)
    monkeypatch.setattr(v, "render_mermaid", lambda _s: "<svg>ok</svg>")
    monkeypatch.setattr(v, "render_d2", lambda _s: "<svg>ok</svg>")

    res = v.validate_markdown_diagrams("```mermaid\nA\n```\n```d2\nx -> y\n```\n")

    assert res.total == 2
    assert res.validated == 2
    assert res.skipped == 0
    assert res.ok is True


def test_failed_render_is_flagged(monkeypatch) -> None:
    """Verifies a diagram whose render returns None is reported as an issue."""
    monkeypatch.setattr(v, "mermaid_available", lambda: True)
    monkeypatch.setattr(v, "render_mermaid", lambda _s: None)

    res = v.validate_markdown_diagrams("```mermaid\nbroken\n```\n")

    assert res.ok is False
    assert len(res.issues) == 1
    assert res.issues[0].kind == "mermaid"
    assert res.issues[0].index == 1


def test_non_svg_output_is_flagged(monkeypatch) -> None:
    """Verifies output lacking an <svg> tag is treated as a failure."""
    monkeypatch.setattr(v, "d2_available", lambda: True)
    monkeypatch.setattr(v, "render_d2", lambda _s: "error: bad d2")

    res = v.validate_markdown_diagrams("```d2\n!!!\n```\n")

    assert res.ok is False
    assert res.issues[0].kind == "d2"


def test_blocks_skipped_when_renderer_unavailable(monkeypatch) -> None:
    """Verifies missing toolchain skips blocks (no false-positive failures)."""
    monkeypatch.setattr(v, "mermaid_available", lambda: False)
    monkeypatch.setattr(v, "d2_available", lambda: False)

    res = v.validate_markdown_diagrams("```mermaid\nA\n```\n```d2\nx -> y\n```\n")

    assert res.total == 2
    assert res.skipped == 2
    assert res.validated == 0
    assert res.ok is True  # skipped != failed


def test_empty_content_yields_empty_result() -> None:
    """Verifies empty/None content returns a clean zero result."""
    res = v.validate_markdown_diagrams("")
    assert res.total == 0
    assert res.ok is True
