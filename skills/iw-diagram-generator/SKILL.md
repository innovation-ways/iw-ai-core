---
version: "1.0.0"
name: iw-diagram-generator
description: >
  Generates Mermaid-based technical diagrams with Innovation Ways brand styling.
  Best for quick, lightweight diagrams that render in GitHub markdown. Use for
  flowcharts, sequence diagrams, ER diagrams, state machines, Gantt charts, mind
  maps, class diagrams, and git graphs in Mermaid syntax. Triggers on "mermaid
  diagram", "mermaid flowchart", "mermaid sequence". For richer draw.io diagrams
  (editable in desktop app, multi-page, complex architecture), use iw-draw-io
  instead.
---

# Innovation Ways Diagram Generator

## Purpose

Generate technical diagrams in the appropriate diagram-as-code language, applying Innovation Ways brand styling, and render them to image files (SVG or PNG).

## Instructions

### 1. Select Diagram Language

Choose the language based on the diagram type:

| Diagram Type | Language | Rationale |
|-------------|----------|-----------|
| Flowcharts | **Mermaid** | Widest support, renders in GitHub |
| Sequence diagrams | **Mermaid** | Clean syntax, good auto-layout |
| Architecture overviews (inline markdown) | **Mermaid** (flowchart with subgraphs) | Renders natively in GitHub |
| C4 Context/Container | **Mermaid** (C4 diagram type) | Native C4 support since Mermaid v10 |
| ER diagrams | **Mermaid** (erDiagram) | Good relationship notation |
| State machines | **Mermaid** (stateDiagram-v2) | Clean state representation |
| Gantt charts | **Mermaid** (gantt) | Built-in timeline support |
| Mind maps | **Mermaid** (mindmap) | Simple hierarchy |
| Class diagrams | **Mermaid** (classDiagram) | UML-compliant |
| Git graphs | **Mermaid** (gitGraph) | Branch visualization |
| Architecture overviews (high aesthetics / docs) | **D2** | Superior auto-layout, ELK-native, modern look |
| Cloud architecture with icons | **Python Diagrams** (mingrammer) | Official cloud provider icons |
| Complex UML | **PlantUML** | Most comprehensive UML support |

**Default to Mermaid** unless there is a specific reason to use another language.

### 2. Apply Brand Theme

Every Mermaid diagram MUST begin with the ELK layout frontmatter — this is the single most impactful visual quality improvement:

```
---
config:
  layout: elk
---
```

Place this as the very first line of the `.mmd` file, then add the theme init string below it.

Every Mermaid diagram MUST include the IW theme initialization as the first line. Load it from `templates/brand/brand.json` field `diagrams.mermaidInit`:

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#D4E4F7', 'primaryTextColor': '#1A1A2E', 'primaryBorderColor': '#2E86AB', 'lineColor': '#6B7280', 'secondaryColor': '#E0F0F8', 'secondaryTextColor': '#1A1A2E', 'secondaryBorderColor': '#2E86AB', 'tertiaryColor': '#F5F7FA', 'tertiaryTextColor': '#1A1A2E', 'noteBkgColor': '#FFF7ED', 'noteTextColor': '#1A1A2E', 'noteBorderColor': '#F18F01', 'background': '#FFFFFF', 'mainBkg': '#D4E4F7', 'nodeBorder': '#2E86AB', 'clusterBkg': '#F0F4F8', 'clusterBorder': '#2E86AB', 'titleColor': '#1B2A4A', 'edgeLabelBackground': '#FFFFFF', 'fontFamily': 'Inter', 'fontSize': '14px'}}}%%
flowchart TD
    A[Start] --> B[End]
```

For D2 diagrams, apply brand colors through D2's style system.

### 3. Diagram Complexity Guidelines

- **Maximum 15 nodes** per diagram. If more are needed, split into multiple diagrams at different abstraction levels.
- **Maximum 3 levels** of nesting (subgraphs within subgraphs).
- **Label every edge** with a concise description of the relationship.
- **Use meaningful node IDs** — `API[FastAPI Backend]` not `A[FastAPI Backend]`.
- **Group related components** using subgraphs with descriptive labels.
- **Consistent direction**: Use `TD` (top-down) for hierarchical diagrams, `LR` (left-right) for flow/sequence-like diagrams.
- **"Why" paragraph required**: Every diagram in a document MUST be preceded by 1–2 sentences answering: "What question does this diagram answer? When should a developer refer to it?"

### 4. C4 Model Guidelines

When generating C4 architecture diagrams:

- **Level 1 — System Context**: Show the system as a single box, surrounded by users and external systems. Max 8-10 elements.
- **Level 2 — Container**: Show the major containers (applications, databases, message queues) within the system boundary. Max 10-12 elements.
- **Level 3 — Component**: Show components within a single container. Max 12-15 elements. Generate one diagram per container.
- **Level 4 — Code**: Rarely needed. Only generate if explicitly requested.

Use Mermaid's C4 diagram syntax:

```mermaid
C4Context
    title System Context diagram for PodForger
    Person(user, "Podcast Listener", "Consumes AI-generated podcasts")
    System(podforger, "PodForger", "AI podcast generation platform")
    System_Ext(ollama, "Ollama", "Self-hosted LLM inference")
    Rel(user, podforger, "Listens to podcasts")
    Rel(podforger, ollama, "Generates scripts", "HTTP/JSON")
```

### 5. Rendering

**Method 1 — mmdc with playwright Chromium** (preferred when available):

```bash
# Create puppeteer config once
cat > /tmp/puppeteer-config.json << 'EOF'
{"args": ["--no-sandbox", "--disable-setuid-sandbox"]}
EOF

PUPPETEER_EXECUTABLE_PATH="$HOME/.cache/ms-playwright/chromium-1217/chrome-linux64/chrome" \
  npx @mermaid-js/mermaid-cli \
  -i diagram.mmd -o diagram.svg -b white \
  --puppeteerConfigFile /tmp/puppeteer-config.json
```

**Method 2 — Kroki.io API** (fallback if mmdc fails):

```bash
curl -X POST https://kroki.io/mermaid/svg \
  -H "Content-Type: text/plain" \
  -d @diagram.mmd \
  -o diagram.svg
```

**Method 3 — MCP server**: If the Mermaid MCP server is configured, use it for rendering.

After rendering, verify the SVG is non-empty (>2KB):
```bash
ls -la diagram.svg
```
If under 2KB, the Mermaid syntax is likely invalid — review and fix.

### 6. Output Format Selection

| Use Case | Format | Rationale |
|----------|--------|-----------|
| Embedding in HTML/PDF | **SVG** | Vector, scales perfectly, smallest file |
| Embedding in PowerPoint | **PNG** (width: 1200px+) | PPTX requires raster images |
| Standalone sharing | **SVG** or **PNG** | SVG preferred for quality |
| Print documents | **SVG** | Vector ensures print quality |

### 7. File Naming Convention

Save diagram source and rendered output with descriptive names:

```
diagrams/
├── system-context.mmd          # Mermaid source
├── system-context.svg          # Rendered SVG
├── container-diagram.mmd
├── container-diagram.svg
├── episode-generation-sequence.mmd
├── episode-generation-sequence.svg
└── ...
```

Use kebab-case. Name should describe the diagram content, not a generic label.

## Output Format

- Mermaid source file (`.mmd`) — always saved for future editing
- Rendered image (`.svg` preferred, `.png` when needed)
- Both files in the same directory

## Files Referenced

- `templates/brand/brand.json` — For `diagrams.mermaidInit` theme configuration
