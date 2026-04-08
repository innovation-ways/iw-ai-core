# Innovation Ways Brand Theme for Draw.io Diagrams

## Brand Colors

Source: `iw-development-fw/templates/brand/brand.json`

| Role | Hex | Use In Diagrams |
|------|-----|-----------------|
| Primary | `#1B2A4A` | Title text, primary headers |
| Secondary | `#2E86AB` | Shape borders, edge highlights |
| Accent | `#F18F01` | Callouts, notes, warnings, highlights |
| Background | `#FFFFFF` | Page background |
| Background Alt | `#F5F7FA` | Group/subgraph fills |
| Text | `#1A1A2E` | All body text, shape labels |
| Text Light | `#6B7280` | Edge labels, secondary text, legends |
| Success | `#10B981` | Status indicators, healthy state |
| Warning | `#F59E0B` | Caution indicators |
| Error | `#EF4444` | Error states, critical items |
| Border | `#E5E7EB` | Light borders, legend boxes |

## Font

- **Primary font**: Inter (all text)
- **Code font**: JetBrains Mono (code snippets if any)

In draw.io styles: `fontFamily=Inter;`

## Diagram Color Palette

Use these fill/stroke combinations for different component types:

### Component Categories

| Category | Fill Color | Stroke Color | Example Use |
|----------|-----------|--------------|-------------|
| Frontend | `#D4E4F7` | `#2E86AB` | React, UI components |
| Frontend inner | `#BBDEFB` | `#2E86AB` | Sub-components within frontend |
| API / Backend | `#C8E6C9` | `#82b366` | FastAPI, routers, services |
| API inner | `#A5D6A7` | `#82b366` | Sub-components within API |
| Workers / Queue | `#E1BEE7` | `#9673a6` | Celery, pipeline stages |
| Workers inner | `#CE93D8` | `#9673a6` | Sub-components within workers |
| Input / Adapters | `#FFF9C4` | `#d6b656` | File watcher, Oracle AQ |
| Databases | `#FFE0B2` | `#d6b656` | PostgreSQL, Redis |
| Storage | `#BBDEFB` | `#6c8ebf` | MinIO/S3, file storage |
| External Systems | `#F5F5F5` | `#666666` | OIDC, third-party APIs |
| Multi-tenancy | `#C8E6C9` | `#82b366` | Tenant/Brand/Client hierarchy |
| Template Layers | `#FFE0B2` → `#FFA726` | `#d6b656` | System → Tenant → Brand → Client |
| Priority High | `#f8cecc` | `#b85450` | Urgent queues, errors |
| Priority Normal | `#fff2cc` | `#d6b656` | Normal priority |
| Priority Low | `#d5e8d4` | `#82b366` | Low priority, healthy |
| Legend / Info | `#FFFFFF` | `#cccccc` | Legend boxes |

### Text Colors

| Element | Font Color | Font Size |
|---------|-----------|-----------|
| Diagram title | `#1B2A4A` | 16px, bold |
| Group/section labels | `#333333` | 12px, bold |
| Shape labels | `#333333` | 10px |
| Sub-labels | `#333333` | 9px |
| Edge labels | matched to edge strokeColor | 8px |
| Notes / fine print | `#666666` | 8px |
| Caption / footer | `#666666` | 10px |

### Edge / Arrow Colors

| Flow Type | Stroke Color | Width | Style |
|-----------|-------------|-------|-------|
| Primary data flow | matched to target category | 2px | solid |
| Secondary / read flow | matched to target category | 1px | dashed |
| Frontend ↔ API | `#82b366` | 2px | solid |
| API ↔ Database | `#d6b656` | 1-2px | solid or dashed |
| API ↔ Redis | `#b85450` | 1-2px | solid or dashed |
| Worker ↔ Storage | `#6c8ebf` | 2px | solid |
| Auth / SSO | `#a20025` | 1px | dashed |

## Style Template Snippets

### Group/container shape

```
rounded=1;whiteSpace=wrap;html=1;fillColor=#d5e8d4;strokeColor=#82b366;
verticalAlign=top;fontStyle=1;fontSize=12;fontColor=#333333;arcSize=6;
```

### Standard shape inside a group

```
rounded=1;whiteSpace=wrap;html=1;fillColor=#C8E6C9;strokeColor=#82b366;fontSize=10;
```

### Database cylinder

```
shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;size=10;
fillColor=#FFE0B2;strokeColor=#d6b656;fontSize=10;
```

### Text label (title, footer)

```
text;html=1;align=center;verticalAlign=middle;whiteSpace=wrap;fontSize=16;fontColor=#1B2A4A;
```

### Primary edge (solid arrow)

```
edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;
strokeColor=#82b366;strokeWidth=2;
```

### Secondary edge (dashed)

```
edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;
strokeColor=#333333;strokeWidth=1;dashed=1;
```

### Legend box

```
rounded=1;whiteSpace=wrap;html=1;fillColor=#ffffff;strokeColor=#cccccc;arcSize=8;
```
