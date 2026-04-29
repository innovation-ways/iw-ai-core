# Diagram Guidelines for Technical Documents

## Purpose

Diagram requirements, selection criteria, and quality standards for technical documentation. Referenced by the `iw-tech-doc-writer` skill.

---

## Canonical Color Palette

| Class   | Role                              | Fill    | Stroke  | Text    |
|---------|-----------------------------------|---------|---------|---------|
| api     | API / router / CLI entry points   | #DBEAFE | #3B82F6 | #1E3A5F |
| data    | Database / repository / storage   | #D1FAE5 | #10B981 | #065F46 |
| worker  | Background jobs / daemon          | #FEF3C7 | #F59E0B | #78350F |
| external| External APIs / third-party       | #F3F4F6 | #9CA3AF | #374151 |
| ui      | Dashboard / frontend              | #EDE9FE | #8B5CF6 | #3B0764 |
| core    | Core orchestration / services     | #FEE2E2 | #EF4444 | #7F1D1D |

Always add this block after the graph declaration:
```
classDef api fill:#DBEAFE,stroke:#3B82F6,color:#1E3A5F
classDef data fill:#D1FAE5,stroke:#10B981,color:#065F46
classDef worker fill:#FEF3C7,stroke:#F59E0B,color:#78350F
classDef external fill:#F3F4F6,stroke:#9CA3AF,color:#374151
classDef ui fill:#EDE9FE,stroke:#8B5CF6,color:#3B0764
classDef core fill:#FEE2E2,stroke:#EF4444,color:#7F1D1D
```

## Why Paragraph Rule

Every diagram MUST be preceded by a 1–2 sentence paragraph answering:
- What question does this diagram answer?
- When should a developer refer to it?

Example: _"This diagram shows the internal component structure of the `auth` module. Use it when adding a new authentication provider or tracing a login request through the system."_

---

## Diagram Selection by Document Type

### Architecture Documents

| Section | Diagram Type | Mermaid Syntax | Max Elements |
|---------|-------------|----------------|-------------|
| System Overview | C4 Context | `C4Context` or `flowchart TB` with subgraphs | 8-10 |
| Container View | C4 Container | `C4Container` or `flowchart TB` with subgraphs | 10-12 |
| Component Detail | Component | `flowchart` | 10-12 |
| Data Flows | Sequence | `sequenceDiagram` | 3-5 participants |
| Deployment | Topology | `flowchart TB` with nested subgraphs | 10-15 |
| Data Model | ER | `erDiagram` | 8-12 entities |
| State Machines | State | `stateDiagram-v2` | 5-8 states |

### Infrastructure Documents

| Section | Diagram Type | Mermaid Syntax | Max Elements |
|---------|-------------|----------------|-------------|
| Deployment Topology | Network/Topology | `flowchart TB` with subgraphs | 10-15 |
| Environment Comparison | Flowchart | `flowchart LR` | 6-10 |
| CI/CD Pipeline | Flowchart | `flowchart LR` | 8-12 |
| Networking | Topology | `flowchart TB` | 8-12 |
| Backup/DR Flow | Flowchart | `flowchart TD` | 6-8 |

### API Documents

| Section | Diagram Type | Mermaid Syntax | Max Elements |
|---------|-------------|----------------|-------------|
| Auth Flow | Sequence | `sequenceDiagram` | 3-4 participants |
| Request Lifecycle | Flowchart | `flowchart LR` | 6-8 |
| Error Handling | Flowchart | `flowchart TD` | 5-7 |
| Webhook Flow | Sequence | `sequenceDiagram` | 3-4 participants |

### User Guides

| Section | Diagram Type | Mermaid Syntax | Max Elements |
|---------|-------------|----------------|-------------|
| Workflow Overview | Flowchart | `flowchart TD` or `LR` | 6-10 |
| User Journey | Flowchart | `flowchart LR` | 5-8 |
| Setup Process | Flowchart | `flowchart TD` | 4-6 |

### Functional Documents

| Section | Diagram Type | Mermaid Syntax | Max Elements |
|---------|-------------|----------------|-------------|
| Business Process | Flowchart | `flowchart TD` | 8-12 |
| User Journey | Sequence | `sequenceDiagram` | 3-5 participants |
| Data Model | ER | `erDiagram` | 8-12 entities |
| State Transitions | State | `stateDiagram-v2` | 5-8 states |

---

## Complexity Rules

1. **Maximum 15 nodes per diagram.** Split into multiple diagrams if more are needed.
2. **Maximum 3 nesting levels** for subgraphs.
3. **Label every edge** — unlabeled arrows are ambiguous.
4. **Meaningful node IDs** — `API[FastAPI Backend]` not `A[Backend]`.
5. **Consistent direction**: `TD` for hierarchies, `LR` for flows and timelines.
6. **One concept per diagram** — don't combine deployment and data flow in one diagram.

## C4 Model Levels

Use these when the document calls for C4 diagrams:

| Level | What It Shows | When to Use | Max Elements |
|-------|---------------|-------------|-------------|
| 1 — Context | System + users + external systems | Every architecture doc | 5-8 |
| 2 — Container | Applications, databases, queues within system boundary | Every architecture doc | 8-12 |
| 3 — Component | Classes/modules within one container | Complex containers only | 10-15 |
| 4 — Code | Class diagrams | Rarely, only if requested | 10-15 |

Always start at Level 1 and drill down. Never jump to Level 3 without establishing Levels 1-2.

## Quality Standards

Every diagram in a document MUST:

- [ ] Include the IW brand theme init string from `brand.json`
- [ ] Have a caption: `Figure N: Description of what the diagram shows`
- [ ] Have a text explanation (1-3 sentences minimum) after the diagram
- [ ] Be readable at A4 print scale (test by checking SVG at 100%)
- [ ] Use dark text on light backgrounds (never light-on-light or dark-on-dark)
- [ ] Be saved as both `.mmd` (source) and `.svg` (rendered)

## Rendering

```bash
# Standard render
mmdc -i diagram.mmd -o diagram.svg -b white

# PNG for PowerPoint (wider)
mmdc -i diagram.mmd -o diagram.png -b white -w 1200
```

Verify each SVG is non-empty after rendering. If `mmdc` fails, check:
1. Mermaid syntax errors (missing brackets, unclosed quotes)
2. Special characters in labels (escape or use quotes)
3. Too many nodes causing timeout

## File Naming

```
poc/diagrams/{system}-{diagram-name}.mmd
poc/diagrams/{system}-{diagram-name}.svg
```

Examples:
- `podforger-system-context.mmd`
- `podforger-container-diagram.mmd`
- `podforger-episode-generation-sequence.mmd`
- `podforger-deployment-topology.mmd`
- `podforger-data-model.mmd`
