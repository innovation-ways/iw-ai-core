# CR001 S01 — Frontend: Create Favicon and Wire into Base Template

## Context

The IW AI Core dashboard (FastAPI + Jinja2 + htmx + Tailwind CDN, port 9900) has no favicon. This step adds one.

- Dashboard static files are served from `dashboard/static/` mounted at `/static`
- Base template: `dashboard/templates/base.html`
- Primary brand color: `#5865f2` (indigo) — see `dashboard/static/theme.css`

## Tasks

### 1. Create `dashboard/static/favicon.svg`

Create an SVG favicon with these requirements:

- **Viewbox**: `0 0 32 32`
- **Motif**: A stylized brain/circuit hybrid — an abstract brain silhouette formed by circuit-board traces and nodes (small circles at junctions connected by straight/angled lines)
- **Primary color**: `#5865f2` for strokes and nodes
- **Style**: Clean, geometric, modern. No gradients or complex effects — must render crisply at 16x16
- **Self-contained**: No external references, fonts, or images
- **Dark-mode friendly**: The indigo color (`#5865f2`) is visible against both light and dark browser chrome

The icon should feel like "AI orchestration" — think neural network meets circuit board.

### 2. Add favicon link to `dashboard/templates/base.html`

In the `<head>` section, add this line after the `<meta>` tags and before the font `<link>` tags:

```html
<link rel="icon" type="image/svg+xml" href="/static/favicon.svg" />
```

## Files to Change

| File | Action |
|------|--------|
| `dashboard/static/favicon.svg` | **Create** |
| `dashboard/templates/base.html` | **Edit** — add `<link rel="icon">` in `<head>` |

## Acceptance Criteria

- [ ] `favicon.svg` exists and is valid SVG
- [ ] The icon is visually recognizable at 16x16 and 32x32
- [ ] `base.html` references the favicon
- [ ] No other files are modified
- [ ] `ruff check` and `ruff format --check` pass (no Python changes expected, but verify)
