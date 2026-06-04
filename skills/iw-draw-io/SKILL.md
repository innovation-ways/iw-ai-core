---
version: "1.0.0"
name: iw-draw-io
description: >
  Generates and exports draw.io diagrams programmatically using the CLI-Anything
  drawio harness for XML creation and the draw.io desktop CLI for PNG/SVG/PDF export.
  Use when asked to create draw.io diagrams, architecture diagrams in .drawio format,
  export diagrams to PNG/SVG/PDF, or when user says "draw.io", "drawio diagram",
  "create diagram", "export diagram", "/iw-draw-io". Prefer this over Mermaid for
  rich architecture diagrams, multi-page diagrams, and diagrams that need desktop
  editing later.
allowed-tools: Read, Grep, Glob, Edit, Write, Bash
argument-hint: <diagram description>
---

# Draw.io Diagram Generator

Generate professional draw.io diagrams with Innovation Ways brand styling, then export to PNG/SVG/PDF.

## Pre-flight Check

### 1. CLI-Anything drawio harness installation

Check if the drawio harness is installed:

```bash
cli-anything-drawio --help
```

If the command is not found, install it:

```bash
pip install -e ~/.claude/plugins/marketplaces/cli-anything/drawio/agent-harness/
```

Verify installation:

```bash
cli-anything-drawio --help
```

If installation fails (e.g., the harness directory does not exist), fall back to **Method B: Direct XML** — write `.drawio` XML directly using the reference in `references/drawio-xml-reference.md`. This always works regardless of harness installation.

### 2. Draw.io desktop (for export only)

The draw.io desktop app is installed on Windows at:

```
/mnt/c/Program Files/draw.io/draw.io.exe
```

This is required ONLY for PNG/SVG/PDF export. Diagram creation (`.drawio` files) works without it.

## Step 1: Determine Diagram Type and Content

Based on `$ARGUMENTS`, determine:

1. **What to diagram** — system architecture, data flow, sequence, ER, deployment, etc.
2. **Scope** — how many components, what level of detail
3. **Output formats** — `.drawio` (always) + PNG/SVG/PDF (if requested or default to PNG)

If `$ARGUMENTS` is insufficient, ask clarifying questions.

## Step 2: Load Brand Colors

Read `iw-development-fw/templates/brand/brand.json` to extract brand colors for the diagram. Apply the IW color palette to shapes, borders, and text. See `references/brand-theme.md` for the draw.io color mapping.

If `brand.json` is not available, use the fallback colors from `references/brand-theme.md` (they are hardcoded there as a fallback).

## Step 3: Create the Diagram

### Method A: CLI-Anything Harness (preferred)

Use `cli-anything-drawio` with `--json` flag for structured output:

```bash
# 1. Create project
cli-anything-drawio --json project new --preset letter -o docs/diagrams/<name>.drawio

# 2. Add shapes (capture IDs from JSON output for connections)
cli-anything-drawio --json --project docs/diagrams/<name>.drawio shape add rounded \
  --label "Component Name" --x 100 --y 100 --width 140 --height 70

# 3. Style shapes with brand colors
cli-anything-drawio --json --project docs/diagrams/<name>.drawio shape style <id> fillColor "#D4E4F7"
cli-anything-drawio --json --project docs/diagrams/<name>.drawio shape style <id> strokeColor "#2E86AB"
cli-anything-drawio --json --project docs/diagrams/<name>.drawio shape style <id> fontColor "#1A1A2E"

# 4. Connect shapes (use IDs from step 2)
cli-anything-drawio --json --project docs/diagrams/<name>.drawio connect add <source_id> <target_id> \
  --style orthogonal --label "data flow"

# 5. Save
cli-anything-drawio --json --project docs/diagrams/<name>.drawio project save
```

**Always use `--json`** — it returns cell IDs needed for `connect add` and `shape style`.

**Shape types available:** rectangle, rounded, ellipse, diamond, triangle, hexagon, cylinder, cloud, parallelogram, process, document, callout, note, actor, text

**Edge styles available:** straight, orthogonal, curved, entity-relation

### Method B: Direct XML (fallback)

If the harness is not installed or for complex diagrams that benefit from full XML control, write `.drawio` XML directly. See `references/drawio-xml-reference.md` for the complete format specification.

This approach allows:
- Subgraph grouping (shapes inside container shapes)
- HTML-formatted labels (`<b>`, `<br>`, `<font>`)
- Custom mxGraph shapes (`shape=mxgraph.aws4.*`, etc.)
- Fine-grained edge routing with waypoints
- Multi-page diagrams

## Step 4: Export to Image

Export the `.drawio` file to PNG (default) using the draw.io desktop CLI:

```bash
"/mnt/c/Program Files/draw.io/draw.io.exe" --export docs/diagrams/<name>.drawio \
  --output docs/diagrams/<name>.png --format png
```

For other formats:

```bash
# SVG (vector, best for web)
"/mnt/c/Program Files/draw.io/draw.io.exe" --export docs/diagrams/<name>.drawio \
  --output docs/diagrams/<name>.svg --format svg

# PDF (best for print)
"/mnt/c/Program Files/draw.io/draw.io.exe" --export docs/diagrams/<name>.drawio \
  --output docs/diagrams/<name>.pdf --format pdf
```

Additional export options:
- `--scale 2` — 2x resolution for high-DPI
- `--crop` — crop to content (no whitespace border)
- `--transparent` — transparent background (PNG only)
- `--page-index N` — export specific page from multi-page diagram

If draw.io desktop is not available, inform the user:
> "The `.drawio` file has been created. To export to PNG, open it in draw.io desktop or at https://app.diagrams.net and use File > Export."

## Step 5: Verify and Report

1. Verify the `.drawio` file was created
2. Verify the exported image exists and has reasonable file size (> 1KB)
3. Report the created files to the user

## File Naming Convention

All diagrams go in `docs/diagrams/` with kebab-case names describing the content:

```
docs/diagrams/
  <name>.drawio          # Source file (always saved, editable in draw.io)
  <name>.png             # Exported PNG (default)
  <name>.svg             # Exported SVG (if requested)
  <name>.pdf             # Exported PDF (if requested)
```

Name examples:
- `system-context.drawio` — C4 Level 1
- `container-diagram.drawio` — C4 Level 2
- `data-flow-pipeline.drawio` — data flow
- `er-diagram-templates.drawio` — ER diagram for templates subsystem
- `deployment-k8s.drawio` — deployment architecture
- `sequence-job-submission.drawio` — sequence diagram

**Do NOT use generic names** like `diagram.drawio` or `architecture.drawio` (unless it truly is THE architecture overview).

## Diagram Complexity Guidelines

- **Maximum 15 nodes** per diagram. Split into multiple diagrams (or pages) at different abstraction levels if more are needed.
- **Maximum 3 levels** of nesting (subgraphs within subgraphs).
- **Label every edge** with a concise description.
- **Use meaningful node IDs** — `api-server`, `postgres-db`, not `v_1`, `v_2`.
- **Group related components** using container shapes with descriptive labels.
- **Consistent direction**: Top-down for hierarchical, left-right for flow/sequence.

## Constraints

- **NEVER** use Mermaid — this skill is exclusively for draw.io diagrams. Use `/iw-diagram-generator` for Mermaid.
- **ALWAYS** save the `.drawio` source file — it is the editable source of truth.
- **ALWAYS** apply IW brand colors from `references/brand-theme.md`.
- **ALWAYS** use the hardcoded draw.io path: `"/mnt/c/Program Files/draw.io/draw.io.exe"`.
- **NEVER** attempt to install draw.io desktop — it is already installed on the Windows host.

## Files Referenced

- `iw-development-fw/templates/brand/brand.json` — Brand colors and fonts
- [references/drawio-xml-reference.md](references/drawio-xml-reference.md) — Complete draw.io XML format, shapes, styles
- [references/brand-theme.md](references/brand-theme.md) — IW brand color mapping for draw.io diagrams
