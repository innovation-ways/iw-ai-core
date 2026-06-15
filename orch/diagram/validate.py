"""Authoring-time validation of Mermaid and D2 diagrams in markdown content.

Extracts every fenced ``mermaid`` / ``d2`` block from a document and checks that
each actually renders through the platform's renderers (after the shared Mermaid
sanitiser). Lets agents and operators catch broken diagrams BEFORE a document is
published, rather than discovering a raw code block in the rendered output.

Reliability contract: a block is only marked invalid when its renderer toolchain
is present AND the render fails. When the renderer binary is unavailable the
block is *skipped* (counted, never reported as an error) so a missing toolchain
never produces false positives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from orch.diagram.render import d2_available, mermaid_available, render_d2, render_mermaid
from orch.diagram.sanitize import sanitize_mermaid

# Fenced ```mermaid / ```d2 blocks. Group 1 = kind, group 2 = source body.
_DIAGRAM_BLOCK_RE = re.compile(r"```(mermaid|d2)[^\n]*\n(.*?)```", re.DOTALL)


@dataclass
class DiagramIssue:
    """A single diagram that failed to render.

    Attributes:
        index: 1-based ordinal of the diagram block within the document.
        kind: Diagram language — ``"mermaid"`` or ``"d2"``.
        message: Human-readable failure description.
    """

    index: int
    kind: str
    message: str


@dataclass
class DiagramValidationResult:
    """Outcome of validating all diagrams in a document.

    Attributes:
        total: Number of diagram blocks found.
        validated: Number actually rendered (toolchain present).
        skipped: Number skipped because the renderer binary was unavailable.
        issues: One :class:`DiagramIssue` per block that failed to render.
    """

    total: int = 0
    validated: int = 0
    skipped: int = 0
    issues: list[DiagramIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True when no validated diagram failed."""
        return not self.issues


def extract_diagram_blocks(markdown: str) -> list[tuple[str, str]]:
    """Return ``(kind, source)`` pairs for every fenced mermaid/d2 block.

    Args:
        markdown: Document markdown content.

    Returns:
        A list of ``(kind, source)`` tuples in document order.
    """
    return [(m.group(1), m.group(2)) for m in _DIAGRAM_BLOCK_RE.finditer(markdown)]


def validate_markdown_diagrams(markdown: str) -> DiagramValidationResult:
    """Validate every Mermaid/D2 diagram in a markdown document by rendering it.

    Mermaid blocks are sanitised (the same shared sanitiser the dashboard renders
    with) before validation so a diagram the platform would auto-fix is not
    flagged. Blocks whose renderer binary is unavailable are skipped, not failed.

    Args:
        markdown: Document markdown content.

    Returns:
        A :class:`DiagramValidationResult` summarising totals and any issues.
    """
    result = DiagramValidationResult()
    if not markdown:
        return result

    mmd_ok = mermaid_available()
    d2_ok = d2_available()

    for ordinal, (kind, source) in enumerate(extract_diagram_blocks(markdown), start=1):
        result.total += 1
        if kind == "mermaid":
            if not mmd_ok:
                result.skipped += 1
                continue
            svg = render_mermaid(sanitize_mermaid(source))
        else:  # d2
            if not d2_ok:
                result.skipped += 1
                continue
            svg = render_d2(source)

        result.validated += 1
        if svg is None or "<svg" not in svg:
            result.issues.append(
                DiagramIssue(
                    index=ordinal,
                    kind=kind,
                    message=f"{kind} diagram #{ordinal} failed to render (syntax error?)",
                )
            )

    return result
