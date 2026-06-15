"""Lightweight, deterministic repair of common LLM-authored Mermaid mistakes.

Shared by the dashboard render path (``dashboard.utils.markdown``) and the
authoring-time validator (``orch.diagram.validate``) so both agree on what the
platform will actually render. Pure string transformation — no I/O, never raises.
"""

from __future__ import annotations

import re


def sanitize_mermaid(source: str) -> str:
    """Apply lightweight fixes for common Mermaid syntax problems.

    Rules applied:

    1. **Sequence diagram semicolons** — arrow-label text containing `;` confuses
       the parser (``CLI->>DB: BEGIN; SELECT FOR UPDATE``).  Replace `;` in labels
       with `,`.

    2. **Bracket/paren inside unquoted node label** — ``{pid}``, ``[pid]``, or
       ``(pid)`` inside a ``NodeID[...]`` label triggers shape parsing.  Convert
       the whole unquoted ``[label]`` to ``["label"]`` (double-quoted labels allow
       arbitrary text including brackets).  Quoted labels like ``NodeID["..."]``
       and subgraph headers like ``subgraph X["..."]`` are left untouched.

    3. **state-v2 → stateDiagram-v2** — LLMs sometimes write the shorthand;
       Mermaid only recognises ``stateDiagram-v2``.

    4. **ELK layout removed for non-flowchart diagrams** — the ELK renderer is
       only valid for ``flowchart``/``graph`` diagrams.  Applying it to
       ``sequenceDiagram``, ``erDiagram``, ``stateDiagram-v2``, etc. breaks
       rendering.  Strip the ``---\\nconfig:\\n  layout: elk\\n---`` frontmatter
       when the diagram type is not a flowchart or graph.

    Args:
        source: Raw Mermaid diagram source (the fenced block body).

    Returns:
        The sanitised Mermaid source.
    """
    # Rule 3: state-v2 → stateDiagram-v2
    source = re.sub(r"\bstate-v2\b", "stateDiagram-v2", source)

    # Rule 5: strip '?' from node IDs (invalid in Mermaid)
    # Matches bareword node IDs ending in '?' before whitespace, '[', '{', '(', or '>'
    # e.g. "has_batches?" → "has_batches", "all_proj_done?" → "all_proj_done"
    source = re.sub(r"(\b\w[\w-]*)\?(?=[\s\[\{>\(|]|$)", r"\1", source)

    # Rule 6: replace [*] in flowchart context (stateDiagram-only syntax)
    if re.search(r"^\s*(flowchart|graph)\b", source, re.MULTILINE | re.IGNORECASE):
        source = source.replace("--> [*]", '--> end_node["End"]')
        source = source.replace("[*] -->", 'start_node["Start"] -->')

    # Rule 8: join multi-line flowchart arrows — LLMs sometimes write
    #   nodeId
    #   -->|label| target
    # which is invalid; join so the arrow is on the same line as the source.
    # Only applies inside flowchart/graph blocks (not sequence/stateDiagram).
    if re.search(r"^\s*(flowchart|graph)\b", source, re.MULTILINE | re.IGNORECASE):
        _multiline_arrow = re.compile(
            r"^(\s*)(\w[\w-]*)\s*\n\s*\n?\s*(-->|-.->|==>)(.*)$",
            re.MULTILINE,
        )
        # Iterate to handle multiple consecutive splits; limit iterations to avoid loops
        for _ in range(10):
            new_source = _multiline_arrow.sub(r"\1\2 \3\4", source)
            if new_source == source:
                break
            source = new_source

    lines = source.splitlines()

    # Detect the diagram type (first non-frontmatter line that looks like a type)
    _elk_frontmatter_re = re.compile(
        r"^---\s*\nconfig:\s*\n\s+layout:\s*elk\s*\n---\s*\n", re.MULTILINE
    )
    _flowchart_types = re.compile(r"^\s*(flowchart|graph)\b", re.IGNORECASE)
    # Strip ELK layout for diagram types that don't support it (Rule 4)
    if _elk_frontmatter_re.search(source):
        non_front = _elk_frontmatter_re.sub("", source, count=1).lstrip()
        first_content_line = non_front.splitlines()[0] if non_front else ""
        if not _flowchart_types.match(first_content_line):
            source = _elk_frontmatter_re.sub("", source, count=1)
            lines = source.splitlines()

    in_sequence = any(line.strip().lower() == "sequencediagram" for line in lines)

    # Arrow pattern for sequence diagrams (labels after ':')
    _arrow_re = re.compile(r"^(\s*\S+\s*(?:->>|-->|->>|->)\s*\S+\s*:)(.*)")

    # Node definition: NodeId[label...]
    # We only rewrite unquoted labels — those that DON'T already start with "
    # Pattern: word chars, then '[' not immediately followed by '"'
    _unquoted_node = re.compile(r"^(\s*\w[\w-]*)\[(?!\")")

    # Pattern to detect brackets/parens that need quoting inside node labels
    bracket_chars = re.compile(r"[{}\[\]()]")

    fixed: list[str] = []
    for line in lines:
        # Rule 1: sequence diagram arrow semicolons
        if in_sequence:
            m = _arrow_re.match(line)
            if m:
                label = m.group(2).replace(";", ",")
                line = m.group(1) + label

        # Skip %%{init:...}%% frontmatter
        if line.strip().startswith("%%"):
            fixed.append(line)
            continue

        # Rule 2: convert NodeId[label] → NodeId["label"] if label has brackets
        m2 = _unquoted_node.match(line)
        if m2:
            rest_after_bracket = line[m2.end() :]  # everything after the opening '['
            # Find the matching closing ']' at the top level
            depth = 1
            end_idx = None
            for ci, ch in enumerate(rest_after_bracket):
                if ch == "[":
                    depth += 1
                elif ch == "]":
                    depth -= 1
                    if depth == 0:
                        end_idx = ci
                        break
            if end_idx is not None:
                label_content = rest_after_bracket[:end_idx]
                suffix = rest_after_bracket[end_idx + 1 :]  # after the closing ']'
                if bracket_chars.search(label_content):
                    # Wrap in double quotes; escape any existing double quotes
                    quoted_label = label_content.replace('"', "&quot;")
                    line = m2.group(1) + '["' + quoted_label + '"]' + suffix

        fixed.append(line)
    return "\n".join(fixed)
