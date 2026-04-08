# Draw.io XML Reference

## File Format: mxGraph XML (.drawio)

Draw.io uses an XML-based format built on the mxGraph library. Files are plain-text XML — fully parseable and writable.

### Document Structure

```xml
<mxfile host="Claude Code" agent="iw-draw-io/1.0.0" version="24.0.0" type="device">
  <diagram id="unique-id" name="Page Name">
    <mxGraphModel dx="1800" dy="1200" grid="1" gridSize="10" guides="1"
                  tooltips="1" connect="1" arrows="1" fold="1"
                  page="1" pageScale="1" pageWidth="1600" pageHeight="1100"
                  math="0" shadow="0">
      <root>
        <mxCell id="0" />                    <!-- Root container (always present) -->
        <mxCell id="1" parent="0" />         <!-- Default layer (always present) -->

        <!-- Shapes and edges go here -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

**Rules:**
- `id="0"` (root) and `id="1"` (default layer) are ALWAYS present as the first two cells.
- Multiple pages = multiple `<diagram>` elements under `<mxfile>`.
- `pageWidth` and `pageHeight` set the page dimensions.

### Page Presets

| Preset | Width | Height | Use For |
|--------|-------|--------|---------|
| letter | 1100 | 850 | Default, US Letter landscape |
| a4 | 1169 | 827 | A4 landscape |
| a3 | 1654 | 1169 | A3 landscape (large diagrams) |
| 16:9 | 1600 | 900 | Presentations |
| square | 1000 | 1000 | Social media, thumbnails |

## Shapes (Vertices)

A shape is an `<mxCell>` with `vertex="1"`:

```xml
<mxCell id="my-shape" value="Label Text"
        style="rounded=1;whiteSpace=wrap;html=1;fillColor=#D4E4F7;strokeColor=#2E86AB;"
        vertex="1" parent="1">
  <mxGeometry x="100" y="100" width="120" height="60" as="geometry" />
</mxCell>
```

- `id` — unique identifier (use descriptive kebab-case: `api-server`, `pg-database`)
- `value` — label text (supports HTML: `<b>`, `<br>`, `<font>`)
- `style` — semicolon-delimited key=value pairs
- `parent` — always `"1"` for top-level shapes, or a container shape's ID for grouped shapes
- `<mxGeometry>` — position (`x`, `y`) and size (`width`, `height`)

### Shape Style Presets

| Shape | Style Base |
|-------|-----------|
| rectangle | `rounded=0;whiteSpace=wrap;html=1` |
| rounded | `rounded=1;whiteSpace=wrap;html=1` |
| ellipse | `ellipse;whiteSpace=wrap;html=1` |
| diamond | `rhombus;whiteSpace=wrap;html=1` |
| triangle | `triangle;whiteSpace=wrap;html=1` |
| hexagon | `shape=hexagon;perimeter=hexagonPerimeter2;whiteSpace=wrap;html=1` |
| cylinder | `shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=10` |
| cloud | `ellipse;shape=cloud;whiteSpace=wrap;html=1` |
| parallelogram | `shape=parallelogram;whiteSpace=wrap;html=1` |
| process | `shape=process;whiteSpace=wrap;html=1` |
| document | `shape=document;whiteSpace=wrap;html=1` |
| callout | `shape=callout;whiteSpace=wrap;html=1` |
| note | `shape=note;whiteSpace=wrap;html=1` |
| actor | `shape=mxgraph.basic.person;whiteSpace=wrap;html=1` |
| text | `text;html=1;align=center;verticalAlign=middle;whiteSpace=wrap` |

### Container / Group Shapes

To group shapes, create a container shape and set child shapes' `parent` to the container's ID:

```xml
<!-- Container (group boundary) -->
<mxCell id="grp-api" value="&lt;b&gt;API Layer&lt;/b&gt;"
        style="rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;
               verticalAlign=top;fontStyle=1;fontSize=12;arcSize=6;"
        vertex="1" parent="1">
  <mxGeometry x="100" y="100" width="400" height="200" as="geometry" />
</mxCell>

<!-- Child shape (parent = container ID) -->
<mxCell id="api-router" value="Router"
        style="rounded=1;whiteSpace=wrap;html=1;fillColor=#C8E6C9;strokeColor=#82b366;"
        vertex="1" parent="grp-api">
  <mxGeometry x="20" y="40" width="100" height="50" as="geometry" />
</mxCell>
```

**Note:** Child coordinates are relative to the container's top-left corner.

### HTML Labels

Labels support HTML for rich formatting:

```xml
value="&lt;b&gt;Bold Title&lt;/b&gt;&lt;br&gt;&lt;font style=&quot;font-size:9px&quot;&gt;Subtitle text&lt;/font&gt;"
```

Common patterns:
- Bold: `&lt;b&gt;text&lt;/b&gt;`
- Line break: `&lt;br&gt;`
- Font size: `&lt;font style=&quot;font-size:9px&quot;&gt;text&lt;/font&gt;`
- Font color: `&lt;font color=&quot;#666666&quot;&gt;text&lt;/font&gt;`

## Edges (Connectors)

An edge is an `<mxCell>` with `edge="1"`:

```xml
<mxCell id="edge-1" value="queries"
        style="edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor=#6B7280;strokeWidth=2;"
        edge="1" source="api-server" target="pg-database" parent="1">
  <mxGeometry relative="1" as="geometry" />
</mxCell>
```

- `source` and `target` reference shape IDs
- `value` — edge label (optional)
- Always include `<mxGeometry relative="1" as="geometry" />`

### Edge Style Presets

| Style | Style String | Description |
|-------|-------------|-------------|
| straight | `edgeStyle=none` | Straight line |
| orthogonal | `edgeStyle=orthogonalEdgeStyle;rounded=0` | Right-angle routing |
| curved | `edgeStyle=orthogonalEdgeStyle;curved=1;rounded=1` | Curved routing |
| entity-relation | `edgeStyle=entityRelationEdgeStyle` | ER diagram style |

### Edge Connection Points

Control where edges attach to shapes:

```xml
<!-- Connect from right side of source to left side of target -->
edge="1" source="shape-a" target="shape-b"
<!-- Add exit/entry points in style: -->
style="...;exitX=1;exitY=0.5;entryX=0;entryY=0.5;"
```

Exit/entry values (0-1 range): `0,0`=top-left, `1,0`=top-right, `0.5,1`=bottom-center, etc.

### Edge Waypoints

For custom routing, add intermediate points:

```xml
<mxCell id="edge-1" style="..." edge="1" source="a" target="b" parent="1">
  <mxGeometry relative="1" as="geometry">
    <Array as="points">
      <mxPoint x="300" y="200" />
      <mxPoint x="300" y="400" />
    </Array>
  </mxGeometry>
</mxCell>
```

## Style Properties

Common style keys applicable to shapes and edges:

| Key | Values | Description |
|-----|--------|-------------|
| fillColor | `#rrggbb` | Shape fill color |
| strokeColor | `#rrggbb` | Border/line color |
| fontColor | `#rrggbb` | Text color |
| fontSize | integer | Font size in points |
| fontStyle | 0/1/2/4 | 0=normal, 1=bold, 2=italic, 4=underline (additive) |
| fontFamily | string | Font name (e.g., `Inter`) |
| opacity | 0-100 | Opacity percentage |
| rounded | 0/1 | Rounded corners |
| shadow | 0/1 | Drop shadow |
| dashed | 0/1 | Dashed border/line |
| strokeWidth | number | Border/line width |
| endArrow | classic/block/open/none | Arrow head style |
| startArrow | classic/block/open/none | Arrow tail style |
| verticalAlign | top/middle/bottom | Vertical text alignment |
| align | left/center/right | Horizontal text alignment |
| whiteSpace | wrap | Enable text wrapping |
| html | 1 | Enable HTML in labels |
| arcSize | 0-50 | Rounded corner radius |

## Multi-Page Diagrams

Add multiple `<diagram>` elements under `<mxfile>`:

```xml
<mxfile>
  <diagram id="page-1" name="System Context">
    <mxGraphModel>...</mxGraphModel>
  </diagram>
  <diagram id="page-2" name="Container Diagram">
    <mxGraphModel>...</mxGraphModel>
  </diagram>
</mxfile>
```

Export specific pages: `--page-index 0` (zero-based).

## Special Shape Libraries

draw.io includes extensive shape libraries accessible via the `shape=` style property:

```
shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.sqs     # AWS SQS
shape=mxgraph.cisco.users.standing_man_and_woman               # Cisco user icon
shape=mxgraph.signs.tech.key_digital                           # Key/security icon
shape=mxgraph.basic.person                                     # Person/actor
```

These render correctly in draw.io desktop but may not display in all contexts. Use standard shapes (rectangle, cylinder, etc.) for maximum compatibility.
