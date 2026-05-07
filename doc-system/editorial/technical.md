# Technical Document Editorial Guidelines

Applies to: TECH-* documents (architecture, design, implementation)

## Audience

Software engineers, architects, and technical leads. Assume strong engineering
background. No hand-holding on basic concepts; focus on decisions, trade-offs,
and operational specifics.

## Structure for Technical Documents (TECH)

1. **Executive Summary** — One paragraph. What the system does, why it exists,
   and who operates it. Written for a reader who has 30 seconds.
2. **Architecture Overview** — Diagram first (component or sequence), then prose.
   Name every component. State every interface protocol.
3. **Key Design Decisions** — Table with two columns: Decision | Rationale.
   One row per non-obvious choice.
4. **Component Reference** — One subsection per major component.
   Purpose, inputs, outputs, configuration, failure modes.
5. **Data Flow** — Sequence diagram or numbered walkthrough. Show the happy path
   and at least one error path.
6. **Configuration Reference** — Table: variable | type | default | description.
   One row per configurable knob.
7. **Operations** — How to start, stop, monitor, and debug. Include actual commands.
8. **Known Limitations & Future Work** — Be honest about gaps. Readers trust
   documents that acknowledge limits.

## Do

- Name modules, files, and classes by their actual names in the codebase
- Include exact CLI commands, environment variables, and config keys
- Use Mermaid diagrams for flows; draw.io for component/architecture diagrams
- Prefer tables over prose for reference material (config, API, states)
- State performance characteristics only when measured, not estimated
- Document error cases alongside the happy path

## Do Not

- Do not describe implementation details that can change without affecting the
  documented behavior (internal variable names, SQL query internals)
- Do not repeat information already in CLAUDE.md — reference it
- Do not list every function — document systems and behaviors, not code
- Do not add a "Future Work" section that is just a wishlist
- Do not use "TBD" — if something is unknown, say "not yet determined" and why

## Length

Technical documents are typically 10–30 pages. Prefer conciseness: a 10-page
document that covers everything is better than a 30-page document that pads.
