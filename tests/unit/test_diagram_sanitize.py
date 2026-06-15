"""Unit tests for the shared Mermaid sanitiser (orch.diagram.sanitize).

The sanitiser is shared by the dashboard renderer and the authoring validator, so
these lock in the deterministic repairs it applies to common LLM mistakes.
"""

from __future__ import annotations

import orch.diagram.sanitize as s


def test_state_v2_shorthand_is_normalised() -> None:
    """Verifies 'state-v2' is rewritten to the valid 'stateDiagram-v2'."""
    out = s.sanitize_mermaid("state-v2\n[*] --> A")
    assert out.find("stateDiagram-v2") != -1


def test_unquoted_bracket_label_is_quoted() -> None:
    """Verifies a node label containing parens is wrapped in double quotes."""
    out = s.sanitize_mermaid("flowchart TD\n    A[do (x)] --> B")
    assert out.find('A["do (x)"]') != -1


def test_question_mark_stripped_from_node_id() -> None:
    """Verifies a trailing '?' is removed from bareword node IDs."""
    out = s.sanitize_mermaid("flowchart TD\n    has_batches? --> done")
    assert out.find("has_batches?") == -1
    assert out.find("has_batches") != -1


def test_sequence_label_semicolons_become_commas() -> None:
    """Verifies semicolons inside sequence arrow labels are replaced with commas."""
    out = s.sanitize_mermaid("sequenceDiagram\n    CLI->>DB: BEGIN; SELECT")
    assert out.find("BEGIN, SELECT") != -1


def test_valid_diagram_is_unchanged() -> None:
    """Verifies a clean diagram passes through without modification."""
    src = "flowchart LR\n    A --> B\n    B --> C"
    assert s.sanitize_mermaid(src) == src
