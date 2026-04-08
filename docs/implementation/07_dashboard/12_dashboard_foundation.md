# Step 12: Dashboard Foundation

## Context

All backend logic is complete. Now build the dashboard — starting with the foundation: FastAPI app, theme, base template, reusable components, and the project selector page.

Read these documents:
- `IW_AI_Core_Dashboard_Design.md` — sections 2 (design system), 3 (layout), 4.1 (project selector), 6 (component library), 7 (dark mode)

## Task

### 1. FastAPI Application (`dashboard/app.py`)

- Factory function `create_app()` → FastAPI instance
- Mount static files: `dashboard/static/`
- Mount Jinja2 templates: `dashboard/templates/`
- Include all routers (import but register empty routers for pages not yet built)
- DB session dependency in `dashboard/dependencies.py`
- Read dashboard host/port from config

### 2. Theme CSS (`dashboard/static/theme.css`)

Copy the full CSS custom properties from Dashboard Design doc section 2.2:
- Light mode (`:root`)
- Dark mode (`.dark`)
- All colors: background, foreground, card, primary, secondary, muted, accent, destructive, border, input, ring, chart-1..5, sidebar-*, success, warning, info
- Layout: radius, spacing, fonts

### 3. Base Template (`dashboard/templates/base.html`)

The shell shared by ALL pages:
- HTML head: meta tags, Tailwind CDN with config (section 2.3), theme.css, htmx CDN, Inter font
- Sidebar (left 240px, collapsible): IW AI Core logo/text, project selector dropdown, navigation links, system section
- Main content area with breadcrumb slot and page content slot
- LLM quota footer bar (static placeholder for now — populated in Phase 2)
- Dark mode toggle button with localStorage persistence (section 7)
- Toast notification container (empty div for SSE toasts)
- `{% block content %}{% endblock %}` for page content
- `{% block title %}{% endblock %}` for page title

### 4. Jinja2 Component Macros (`dashboard/templates/components/`)

Create reusable macros (from Dashboard Design doc section 6):

#### `status_badge.html`
- `{% macro status_badge(status) %}` — colored pill for all status values

#### `step_pipeline.html`
- `{% macro step_pipeline(steps) %}` — visual dots + connectors (✓ ● ✗ ○)

#### `card.html`
- `{% macro card(title, value, subtitle=None) %}` — stat card

#### `action_button.html`
- Macros for kill, restart, skip buttons with correct htmx attributes
- Destructive buttons trigger confirmation dialog

#### `confirm_dialog.html`
- Confirmation modal template for destructive actions

#### `duration.html`
- `<span data-started-at="...">` with live JS counter

### 5. Live Duration Counter (`dashboard/static/duration.js`)

JavaScript that updates all `[data-started-at]` elements every second (from Dashboard Design doc section 8).

### 6. Theme Toggle (`dashboard/static/theme-toggle.js`)

Dark mode toggle with localStorage persistence (from Dashboard Design doc section 7).

### 7. Project Selector Page (`dashboard/routers/projects.py`)

Route: `GET /`

- Query all projects from DB with stats: item count, active batch count, running step count
- Render project cards (see wireframe in Dashboard Design 4.1)
- Each card shows: project name, stat badges (batches, running, queue, git status)
- Click → navigates to `/project/{id}/`
- Disabled projects shown as grayed out

### 8. Sidebar Navigation

The sidebar shows different links depending on context:
- If on root `/` or `/system/*`: show "All Projects" header + system nav links
- If on `/project/{id}/*`: show project name + project-scoped nav links
- Active link highlighted
- Running tasks count badge on the "Running" link (from DB query)

## Acceptance Criteria

- [ ] `make dashboard-start` serves on configured port
- [ ] Root page shows project selector with InnoForge card (if registered)
- [ ] Dark mode toggle works and persists across page loads
- [ ] Sidebar navigation changes based on URL context
- [ ] Component macros render correctly (status badges, step pipelines, cards)
- [ ] Duration counter updates live every second
- [ ] Page loads within 500ms
