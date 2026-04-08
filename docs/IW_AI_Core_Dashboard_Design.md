# IW AI Core — Dashboard Design

**Project**: IW AI Core (Innovation Ways AI Orchestration Platform)
**Author**: Sergio G. + Claude
**Date**: 2026-04-07
**Version**: 1.0.0
**Status**: Draft

---

## 1. Overview

The dashboard is the primary management interface for IW AI Core. It provides real-time visibility into all running agents, batch status, work item history, and system health across all projects.

**Design principles:**
- **Server-rendered**: FastAPI + Jinja2 + htmx. No SPA, no build pipeline.
- **Real-time**: SSE for live updates (running durations, notifications). No page refresh needed.
- **Theme**: Adapted from shadcn/ui Discord theme — flat, modern, light/dark mode.
- **Zero JS framework**: htmx handles all interactivity. Vanilla JS only for timers and charts.

---

## 2. Visual Design System

### 2.1. Theme Source

Based on the [tweakcn Discord theme](https://tweakcn.com/themes/cmn4wp9hz000104lbgtucaj5m) — a shadcn/ui-compatible design system with flat aesthetics, indigo primary, and excellent light/dark mode support.

We take the CSS custom properties directly and apply them to our server-rendered HTML. The variable names follow the shadcn convention, which gives us a well-structured design token system even without React.

### 2.2. CSS Custom Properties

```css
/* dashboard/static/theme.css */

:root {
  /* --- Core palette (light mode) --- */
  --background: #fbfbfb;
  --foreground: #28282d;
  --card: #ffffff;
  --card-foreground: #28282d;
  --popover: #ffffff;
  --popover-foreground: #28282d;
  --primary: #5865f2;
  --primary-foreground: #ffffff;
  --secondary: #f2f2f3;
  --secondary-foreground: #28282d;
  --muted: #f6f6f6;
  --muted-foreground: #6c6d76;
  --accent: #eeeef0;
  --accent-foreground: #28282d;
  --destructive: #b92733;
  --destructive-foreground: #ffffff;
  --border: #dfdfe1;
  --input: #f2f2f3;
  --ring: #5865f2;

  /* --- Chart colors --- */
  --chart-1: #f5a3d1;
  --chart-2: #f5d18a;
  --chart-3: #a3f5d1;
  --chart-4: #a3d1f5;
  --chart-5: #d1a3f5;

  /* --- Sidebar --- */
  --sidebar: #f3f3f4;
  --sidebar-foreground: #666770;
  --sidebar-primary: #dddde0;
  --sidebar-primary-foreground: #28282d;
  --sidebar-accent: #e7e7e9;
  --sidebar-accent-foreground: #28282d;
  --sidebar-border: #d9d9dc;
  --sidebar-ring: #00b0f4;

  /* --- Semantic status (IW additions) --- */
  --success: #22c55e;
  --success-foreground: #ffffff;
  --warning: #f59e0b;
  --warning-foreground: #ffffff;
  --info: #00b0f4;
  --info-foreground: #ffffff;

  /* --- Layout --- */
  --radius: 0.625rem;
  --spacing: 0.25rem;
  --shadow-opacity: 0;
  --letter-spacing: 0em;

  /* --- Fonts --- */
  --font-sans: 'Inter', 'Noto Sans JP', ui-sans-serif, system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', 'SFMono-Regular', Menlo, monospace;
}

.dark {
  --background: #323339;
  --foreground: #ffffff;
  --card: #393a41;
  --card-foreground: #ffffff;
  --popover: #393a41;
  --popover-foreground: #ffffff;
  --primary: #5865f2;
  --primary-foreground: #ffffff;
  --secondary: #414148;
  --secondary-foreground: #ffffff;
  --muted: #2e2f35;
  --muted-foreground: #a4a5ab;
  --accent: #484951;
  --accent-foreground: #ffffff;
  --destructive: #ffa09b;
  --destructive-foreground: #ffffff;
  --border: #3e3f45;
  --input: #2e2f35;
  --ring: #5865f2;
  --chart-1: #f5a3d1;
  --chart-2: #f5d18a;
  --chart-3: #a3f5d1;
  --chart-4: #a3d1f5;
  --chart-5: #d1a3f5;
  --sidebar: #2c2d32;
  --sidebar-foreground: #999aa1;
  --sidebar-primary: #414248;
  --sidebar-primary-foreground: #ffffff;
  --sidebar-accent: #35353a;
  --sidebar-accent-foreground: #ffffff;
  --sidebar-border: #393a3f;
  --sidebar-ring: #00b0f4;

  --success: #4ade80;
  --warning: #fbbf24;
  --info: #38bdf8;
}
```

### 2.3. Tailwind Integration

Tailwind CSS (via CDN for dev, standalone CLI for production) is configured to use the CSS custom properties:

```html
<!-- In base.html -->
<script src="https://cdn.tailwindcss.com"></script>
<script>
  tailwind.config = {
    darkMode: 'class',
    theme: {
      extend: {
        colors: {
          background: 'var(--background)',
          foreground: 'var(--foreground)',
          card: { DEFAULT: 'var(--card)', foreground: 'var(--card-foreground)' },
          primary: { DEFAULT: 'var(--primary)', foreground: 'var(--primary-foreground)' },
          secondary: { DEFAULT: 'var(--secondary)', foreground: 'var(--secondary-foreground)' },
          muted: { DEFAULT: 'var(--muted)', foreground: 'var(--muted-foreground)' },
          accent: { DEFAULT: 'var(--accent)', foreground: 'var(--accent-foreground)' },
          destructive: { DEFAULT: 'var(--destructive)', foreground: 'var(--destructive-foreground)' },
          border: 'var(--border)',
          input: 'var(--input)',
          ring: 'var(--ring)',
          success: { DEFAULT: 'var(--success)', foreground: 'var(--success-foreground)' },
          warning: { DEFAULT: 'var(--warning)', foreground: 'var(--warning-foreground)' },
          info: { DEFAULT: 'var(--info)', foreground: 'var(--info-foreground)' },
          sidebar: {
            DEFAULT: 'var(--sidebar)',
            foreground: 'var(--sidebar-foreground)',
            primary: 'var(--sidebar-primary)',
            accent: 'var(--sidebar-accent)',
            border: 'var(--sidebar-border)',
          },
        },
        borderRadius: {
          lg: 'calc(var(--radius) + 2px)',
          md: 'var(--radius)',
          sm: 'calc(var(--radius) - 2px)',
        },
        fontFamily: {
          sans: ['var(--font-sans)'],
          mono: ['var(--font-mono)'],
        },
      },
    },
  }
</script>
```

This means we can use Tailwind classes like `bg-primary`, `text-muted-foreground`, `border-border`, `bg-sidebar` — and they map to our theme variables. Dark mode just works via the `.dark` class toggle.

---

## 3. Layout Structure

### 3.1. Shell Layout

Every page shares the same shell:

```
+--[ Sidebar (240px, collapsible) ]--+--[ Main Content ]------------------+
|                                     |                                    |
|  [IW AI Core logo/text]            |  [ Breadcrumb / Page Title ]       |
|                                     |  [ Search bar (global) ]          |
|  [ Project Selector dropdown ]      |                                    |
|  ─────────────────────────         |  +------------------------------+  |
|  [ Navigation links ]              |  |                              |  |
|    > Running Tasks (3)             |  |   Page-specific content      |  |
|    > Batches                       |  |                              |  |
|    > Queue & Backlog               |  |                              |  |
|    > History                       |  |                              |  |
|    > Analytics                     |  |                              |  |
|  ─────────────────────────         |  +------------------------------+  |
|  [ System section ]                |                                    |
|    > System Status                 |  +------------------------------+  |
|    > All Active Work               |  | [ LLM Quota footer bar ]     |  |
|    > Configuration                 |  +------------------------------+  |
|                                     |                                    |
+-------------------------------------+------------------------------------+
```

### 3.2. Jinja2 Template Hierarchy

```
templates/
├── base.html                    # Shell: sidebar + main area + footer + SSE + dark mode toggle
├── components/
│   ├── sidebar.html             # Sidebar with project selector and nav
│   ├── breadcrumb.html          # Breadcrumb trail
│   ├── search.html              # Global search bar
│   ├── status_badge.html        # Colored status pill (running, failed, etc.)
│   ├── action_button.html       # Button with htmx confirmation dialog
│   ├── step_pipeline.html       # Visual step pipeline (dots + connectors)
│   ├── duration.html            # Live duration counter (JS)
│   ├── toast.html               # SSE-powered notification toast
│   ├── confirm_dialog.html      # Confirmation modal for destructive actions
│   └── pagination.html          # Page controls
├── pages/
│   ├── project_selector.html    # Root page: all projects
│   ├── running.html             # Running tasks (cross-project)
│   ├── project/
│   │   ├── dashboard.html       # Project overview
│   │   ├── batches.html         # Batch list
│   │   ├── batch_detail.html    # Single batch: items, timeline, logs
│   │   ├── item_detail.html     # Work item: design doc, steps, reports
│   │   ├── queue.html           # Pending items + designs
│   │   ├── history.html         # Completed items
│   │   └── analytics.html       # Charts and metrics
│   └── system/
│       ├── status.html          # Daemon health, quota
│       └── config.html          # projects.toml viewer
└── fragments/                   # htmx partial responses (no base layout)
    ├── running_table.html       # Just the table rows (for SSE refresh)
    ├── step_row.html            # Single step row update
    ├── batch_items.html         # Batch items table
    └── toast_message.html       # Single toast notification
```

### 3.3. htmx Interaction Patterns

All interactivity is htmx — no custom JS framework.

**Pattern 1: Action buttons with confirmation**
```html
<!-- Kill button triggers a confirmation dialog -->
<button
  hx-get="/project/innoforge/api/confirm/kill-step/I001/S01"
  hx-target="#confirm-dialog"
  hx-swap="innerHTML"
  class="px-3 py-1 bg-destructive text-destructive-foreground rounded-md text-sm">
  Kill
</button>

<!-- Dialog returned by the GET endpoint -->
<div class="fixed inset-0 bg-black/50 flex items-center justify-center">
  <div class="bg-card p-6 rounded-lg shadow-lg max-w-sm">
    <h3 class="text-lg font-semibold">Kill step S01?</h3>
    <p class="text-muted-foreground mt-2">This will send SIGTERM to PID 45231.</p>
    <div class="flex gap-3 mt-4">
      <button hx-post="/project/innoforge/api/item/I001/kill-step/S01"
              hx-swap="none"
              class="px-4 py-2 bg-destructive text-destructive-foreground rounded-md">
        Confirm Kill
      </button>
      <button onclick="document.getElementById('confirm-dialog').innerHTML=''"
              class="px-4 py-2 bg-secondary text-secondary-foreground rounded-md">
        Cancel
      </button>
    </div>
  </div>
</div>
```

**Pattern 2: Live table updates via SSE**
```html
<!-- Running tasks table with SSE updates -->
<div hx-ext="sse" sse-connect="/api/stream/running" sse-swap="running-update">
  <table class="w-full">
    <thead>...</thead>
    <tbody id="running-rows">
      {% include 'fragments/running_table.html' %}
    </tbody>
  </table>
</div>
```

**Pattern 3: Tab navigation without page reload**
```html
<!-- Work item detail tabs -->
<div class="flex border-b border-border">
  <button hx-get="/project/innoforge/item/I001/tab/overview"
          hx-target="#tab-content"
          class="px-4 py-2 border-b-2 border-primary text-primary font-medium">
    Overview
  </button>
  <button hx-get="/project/innoforge/item/I001/tab/design-doc"
          hx-target="#tab-content"
          class="px-4 py-2 text-muted-foreground hover:text-foreground">
    Design Document
  </button>
  <button hx-get="/project/innoforge/item/I001/tab/reports"
          hx-target="#tab-content"
          class="px-4 py-2 text-muted-foreground hover:text-foreground">
    Reports
  </button>
  <button hx-get="/project/innoforge/item/I001/tab/artifacts"
          hx-target="#tab-content"
          class="px-4 py-2 text-muted-foreground hover:text-foreground">
    Full Artifacts
  </button>
</div>
<div id="tab-content" class="mt-4">
  {% include 'fragments/item_overview.html' %}
</div>
```

**Pattern 4: Search with live results**
```html
<input type="search"
       hx-get="/api/search"
       hx-trigger="keyup changed delay:300ms"
       hx-target="#search-results"
       hx-include="[name='project']"
       name="q"
       placeholder="Search work items..."
       class="w-full px-4 py-2 bg-input border border-border rounded-md text-foreground placeholder-muted-foreground" />
<div id="search-results"></div>
```

---

## 4. Page Wireframes

### 4.1. Project Selector (Root Page `/`)

The landing page when opening the dashboard.

```
+===========================================================================+
|  IW AI Core                                              [dark mode ☾]   |
+===========================================================================+
|                                                                           |
|  Your Projects                                                            |
|                                                                           |
|  +-------------------------------------------------------------------+   |
|  | ● InnoForge Document Platform                                     |   |
|  |   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           |   |
|  |   │ Batches  │ │ Running  │ │ Queue    │ │ Git      │           |   |
|  |   │    2     │ │    3     │ │    5     │ │ 3 ahead  │           |   |
|  |   └──────────┘ └──────────┘ └──────────┘ └──────────┘           |   |
|  +-------------------------------------------------------------------+   |
|                                                                           |
|  +-------------------------------------------------------------------+   |
|  | ● Project B                                                       |   |
|  |   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           |   |
|  |   │ Batches  │ │ Running  │ │ Queue    │ │ Git      │           |   |
|  |   │    0     │ │    0     │ │    2     │ │ clean    │           |   |
|  |   └──────────┘ └──────────┘ └──────────┘ └──────────┘           |   |
|  +-------------------------------------------------------------------+   |
|                                                                           |
|  +-------------------------------------------------------------------+   |
|  | ○ Project C  (disabled)                                           |   |
|  +-------------------------------------------------------------------+   |
|                                                                           |
|  System Status: Daemon running (4h 23m) | 3 steps active | Quota: 37%   |
+===========================================================================+
```

Each project card is clickable → navigates to `/project/{id}/`.

### 4.2. Running Tasks (`/system/running`)

The most important operational page — shows everything executing across all projects.

```
+==[ Sidebar ]=====+==[ Running Tasks ]=====================================+
|                   |                                                        |
| [IW AI Core]     |  Running Now                              3 active     |
|                   |  ──────────────────────────────────────────────────── |
| All Projects  ▾  |                                                        |
| ─────────────── |  Project    Item  Step           Agent     Dur    Act   |
| > Running (3)   |  ───────── ────── ─────────── ───────── ────── ─────  |
| > Batches       |  InnoForge  I003  S01 Backend   back-impl 12m34s [Kill] |
| > Queue         |  InnoForge  I004  S03 CR Final  cr-final   4m12s [Kill] |
| > History       |  Project B  F002  S02 API       api-impl   1m05s [Kill] |
| > Analytics     |                                                        |
| ─────────────── |  Failed / Needs Attention                  2 items     |
| System          |  ──────────────────────────────────────────────────── |
| > Status        |                                                        |
| > Config        |  Project    Item  Step           Error          Actions |
|                   |  ───────── ────── ─────────── ─────────────── ─────  |
|                   |  InnoForge  I001  S02 CR Back  Timeout (30m)  [↻][⏭] |
|                   |  Project B  F001  S05 QV Test  3 tests fail   [↻][⏭] |
|                   |                                                        |
|                   |  Recently Completed (last hour)              8 steps  |
|                   |  ──────────────────────────────────────────────────── |
|                   |  InnoForge  I002  S04 QV Lint     0m45s   ✓          |
|                   |  InnoForge  I002  S05 QV Types    1m22s   ✓          |
|                   |  Project B  F002  S01 Database   18m22s   ✓          |
|                   |  ···                                                  |
+-------------------+--------------------------------------------------------+
| Claude: ████████░░ 63% (5h) │ ██░░░░░░░░ 26% (7d) resets Apr 10         |
+===========================================================================+
```

- Duration columns update in real-time via SSE (no page refresh)
- `[Kill]` triggers confirmation dialog, then `POST /api/item/{id}/kill-step/{n}`
- `[↻]` = Restart, `[⏭]` = Skip
- Status badges are color-coded: running=blue, failed=red, completed=green

### 4.3. Project Dashboard (`/project/{id}/`)

Overview page for a single project.

```
+==[ Sidebar ]=====+==[ InnoForge — Dashboard ]=============================+
|                   |                                                        |
| InnoForge     ▾  |  ┌────────────┐ ┌────────────┐ ┌────────────┐        |
| ─────────────── |  │ Active     │ │ Running    │ │ Completed  │        |
| > Dashboard  ●  |  │ Batches: 2 │ │ Steps: 3   │ │ This week: │        |
| > Batches       |  │            │ │            │ │ 15 items   │        |
| > Queue (5)     |  └────────────┘ └────────────┘ └────────────┘        |
| > History       |                                                        |
| > Analytics     |  Active Batches                                        |
| ─────────────── |  ──────────────────────────────────────────────────── |
|                   |  BATCH-003 [executing] 4 items: 2 merged, 1 running  |
|                   |    ■■■■■■■■■■░░░░░░░░░░ 50%  [Pause] [View]        |
|                   |                                                        |
|                   |  BATCH-004 [approved] 3 items: waiting for daemon     |
|                   |    ░░░░░░░░░░░░░░░░░░░░  0%  [View]                  |
|                   |                                                        |
|                   |  Recent Activity                                      |
|                   |  ──────────────────────────────────────────────────── |
|                   |  14:52  I003/S01 Backend launched (PID 45231)         |
|                   |  14:48  I002 merged to main ✓                         |
|                   |  14:45  I001/S02 timed out — needs restart            |
|                   |  14:30  BATCH-003 started (4 items)                   |
|                   |                                                        |
|                   |  Git Status                                           |
|                   |  ──────────────────────────────────────────────────── |
|                   |  Branch: main | 3 unpushed commits | 2 worktrees     |
+-------------------+--------------------------------------------------------+
```

### 4.4. Batch Detail (`/project/{id}/batch/{batch_id}`)

```
+==[ Sidebar ]=====+==[ BATCH-003 ]=========================================+
|                   |                                                        |
|                   |  BATCH-003                          [Pause] [Archive] |
|                   |  Status: executing | Items: 4 | Max parallel: 4      |
|                   |  Created: 2026-04-07 22:00 | Running: 1h 23m         |
|                   |                                                        |
|                   |  [ Items ]  [ Timeline ]  [ Logs ]                    |
|                   |  ──────────────────────────────────────────────────── |
|                   |                                                        |
|                   |  Grp  Item  Title                Status   Dur   Act   |
|                   |  ──── ───── ─────────────────── ──────── ───── ───── |
|                   |   0   I001  Fix template timeout merged   45m   —     |
|                   |   0   I002  Add zone caching     merged   38m   —     |
|                   |   0   I003  Fix PDF export       running  12m  [View] |
|                   |   1   I004  Add config key       pending  —    —      |
|                   |                                                        |
|                   |  ──────────────────────────────────────────────────── |
|                   |  Step pipeline for I003:                              |
|                   |  [✓S01]──[✓S02]──[●S03]──[○S04]──[○S05]──[○S06]    |
|                   |  Backend  CR:BE   CR:Final QV:Lint QV:Test QV:Types  |
+-------------------+--------------------------------------------------------+
```

- Timeline tab shows a Gantt-style view (Chart.js or SVG)
- Logs tab shows dispatcher log with auto-scroll
- Step pipeline is a visual component: ✓=completed, ●=running, ○=pending, ✗=failed

### 4.5. Work Item Detail (`/project/{id}/item/{item_id}`)

```
+==[ Sidebar ]=====+==[ I001 — Fix template rendering timeout ]=============+
|                   |                                                        |
|                   |  I001: Fix template rendering timeout                 |
|                   |  Issue | completed | Batch: BATCH-003                 |
|                   |                                                        |
|                   |  [ Overview ]  [ Design Doc ]  [ Reports ]  [ Artifacts ] |
|                   |  ──────────────────────────────────────────────────── |
|                   |                                                        |
|                   |  Step Pipeline                                        |
|                   |  [✓S01]──[✓S02]──[✓S03]──[✓S04]──[✓S05]──[✓S06]   |
|                   |  Backend  CR:BE   CR:Fin  QV:Lint QV:Test QV:Type    |
|                   |  18m22s  12m05s  8m44s   0m45s   3m10s   1m22s      |
|                   |                                                        |
|                   |  Summary                                              |
|                   |  WeasyPrint timeout on templates with >50 zones.      |
|                   |  Root cause: synchronous zone rendering loop.          |
|                   |  Fix: async batch rendering with 30s per-zone limit.  |
|                   |                                                        |
|                   |  Metrics                                              |
|                   |  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ |
|                   |  │ Total time   │ │ Fix cycles   │ │ Steps        │ |
|                   |  │ 44m 28s      │ │ 1 (S02)      │ │ 6/6 passed   │ |
|                   |  └──────────────┘ └──────────────┘ └──────────────┘ |
+-------------------+--------------------------------------------------------+
```

**Design Doc tab**: Renders `work_items.design_doc_content` as HTML (markdown → HTML via server-side rendering). Always instant — no file access.

**Reports tab**: Each step's report rendered from `workflow_steps.report_content`. Collapsible sections per step.

**Artifacts tab**: "Load Artifacts" button → extracts archive to tmp → shows file tree browser.

### 4.6. Queue & Backlog (`/project/{id}/queue`)

```
+==[ Sidebar ]=====+==[ Queue & Backlog ]===================================+
|                   |                                                        |
|                   |  Ready for Execution (approved)            3 items     |
|                   |  ──────────────────────────────────────────────────── |
|                   |  [ ] I005  Fix login redirect       Issue    approved  |
|                   |  [ ] I006  Add audit logging        Issue    approved  |
|                   |  [ ] F015  Template versioning      Feature  approved  |
|                   |                                                        |
|                   |  [ Create Batch from Selected ]                       |
|                   |                                                        |
|                   |  Drafts (awaiting review)              5 items        |
|                   |  ──────────────────────────────────────────────────── |
|                   |  I007  Fix memory leak in worker    Issue    draft     |
|                   |  CR005 Update config schema          CR      draft     |
|                   |  F016  Add bulk import               Feature  draft    |
|                   |  ···                                                  |
|                   |                                                        |
|                   |  Each item row is clickable → item detail page        |
+-------------------+--------------------------------------------------------+
```

Checkboxes allow selecting multiple approved items → "Create Batch" button.

### 4.7. History (`/project/{id}/history`)

```
+==[ Sidebar ]=====+==[ History ]============================================+
|                   |                                                        |
|                   |  [Search: ________________] [Type: All ▾] [Date: ▾]  |
|                   |                                                        |
|                   |  ID    Type     Title                    Date    Dur   |
|                   |  ───── ──────── ──────────────────────── ──────  ───── |
|                   |  I004  Issue    Fix batch merge order    Apr 07  22m   |
|                   |  I003  Issue    Fix PDF export encoding  Apr 07  45m   |
|                   |  CR04  CR       Update timeout config    Apr 06  18m   |
|                   |  F014  Feature  Add template layers      Apr 05  1h2m  |
|                   |  I002  Issue    Fix zone caching bug     Apr 05  38m   |
|                   |  ···                                                  |
|                   |                                                        |
|                   |  [ 1 ] [ 2 ] [ 3 ] ... [ 12 ]   Showing 1-20 of 234 |
+-------------------+--------------------------------------------------------+
```

Each row clickable → item detail. Filters persist via URL query params. Full-text search integrated.

### 4.8. System Status (`/system/status`)

```
+==[ Sidebar ]=====+==[ System Status ]=====================================+
|                   |                                                        |
|                   |  Daemon                                               |
|                   |  ┌────────────────────────────────────────────────┐  |
|                   |  │ Status: ● running     PID: 45231              │  |
|                   |  │ Uptime: 4h 23m        Last poll: 12s ago      │  |
|                   |  │ Poll count: 254       Projects: 3 enabled     │  |
|                   |  │                        [Stop] [Restart]       │  |
|                   |  └────────────────────────────────────────────────┘  |
|                   |                                                        |
|                   |  Projects                                             |
|                   |  ┌────────────────────────────────────────────────┐  |
|                   |  │ InnoForge  ● enabled  371 items  2 batches    │  |
|                   |  │ Project B  ● enabled   12 items  0 batches    │  |
|                   |  │ Project C  ○ disabled   0 items               │  |
|                   |  └────────────────────────────────────────────────┘  |
|                   |                                                        |
|                   |  LLM Quota                                            |
|                   |  ┌────────────────────────────────────────────────┐  |
|                   |  │ Claude Code                                    │  |
|                   |  │ 5h:  ████████░░ 63%     resets in 2h 15m     │  |
|                   |  │ 7d:  ██░░░░░░░░ 26%     resets Apr 10        │  |
|                   |  │                                                │  |
|                   |  │ MiniMax                                        │  |
|                   |  │ 1245/1500 prompts ████████░░ 83%  3h 17m     │  |
|                   |  └────────────────────────────────────────────────┘  |
|                   |                                                        |
|                   |  Git Status (per project)                             |
|                   |  ┌────────────────────────────────────────────────┐  |
|                   |  │ InnoForge: main | 3 unpushed | 2 worktrees   │  |
|                   |  │ Project B: main | clean | 0 worktrees        │  |
|                   |  └────────────────────────────────────────────────┘  |
+-------------------+--------------------------------------------------------+
```

---

## 5. SSE (Server-Sent Events)

### 5.1. Architecture

```
Dashboard (FastAPI)
  |
  GET /api/stream/events  ← Browser connects via EventSource
  |
  Daemon writes to daemon_events table
  |
  SSE endpoint polls daemon_events (last 60s) every 5 seconds
  |
  Pushes new events to connected browsers
```

### 5.2. Event Types and UI Responses

| Event | SSE Message | UI Action |
|-------|------------|-----------|
| `step_launched` | `running-update` | Add row to running table |
| `step_completed` | `running-update` | Move row from running to completed |
| `step_failed` | `toast` | Show error toast + update running table |
| `step_timeout` | `toast` | Show warning toast + update running table |
| `step_killed` | `running-update` | Remove from running, add to failed |
| `batch_completed` | `toast` | Show success toast |
| `batch_completed_with_errors` | `toast` | Show warning toast |
| `item_merged` | `toast` | Show info toast |
| `quota_warning` | `quota-update` | Update quota bars in footer |

### 5.3. SSE Endpoint

```python
# dashboard/routers/sse.py

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.get("/api/stream/events")
async def event_stream(request: Request):
    """SSE stream for real-time dashboard updates."""
    async def generate():
        last_check = datetime.utcnow()
        while True:
            await asyncio.sleep(5)

            # Check for new events since last check
            events = db.query(DaemonEvent).filter(
                DaemonEvent.created_at > last_check
            ).order_by(DaemonEvent.created_at).all()

            for event in events:
                if event.event_type in ('step_launched', 'step_completed', 'step_killed'):
                    yield f"event: running-update\ndata: {json.dumps(event.metadata)}\n\n"
                elif event.event_type in ('step_failed', 'step_timeout', 'batch_completed'):
                    yield f"event: toast\ndata: {json.dumps({'type': event.event_type, 'message': event.message})}\n\n"
                elif event.event_type == 'quota_warning':
                    yield f"event: quota-update\ndata: {json.dumps(event.metadata)}\n\n"

            last_check = datetime.utcnow()

    return StreamingResponse(generate(), media_type="text/event-stream")
```

---

## 6. Component Library (Jinja2 Macros)

Reusable UI components as Jinja2 macros, styled with Tailwind + theme variables:

### 6.1. Status Badge

```html
{% macro status_badge(status) %}
  {% set colors = {
    'running': 'bg-primary text-primary-foreground',
    'completed': 'bg-success text-success-foreground',
    'merged': 'bg-success text-success-foreground',
    'failed': 'bg-destructive text-destructive-foreground',
    'timeout': 'bg-warning text-warning-foreground',
    'stalled': 'bg-warning text-warning-foreground',
    'pending': 'bg-muted text-muted-foreground',
    'draft': 'bg-secondary text-secondary-foreground',
    'approved': 'bg-info text-info-foreground',
    'killed': 'bg-destructive text-destructive-foreground',
    'skipped': 'bg-muted text-muted-foreground',
  } %}
  <span class="inline-flex items-center px-2 py-0.5 rounded-sm text-xs font-medium {{ colors.get(status, 'bg-muted text-muted-foreground') }}">
    {{ status }}
  </span>
{% endmacro %}
```

### 6.2. Step Pipeline

```html
{% macro step_pipeline(steps) %}
  <div class="flex items-center gap-1">
    {% for step in steps %}
      {% if step.status == 'completed' %}
        <div class="w-8 h-8 rounded-full bg-success flex items-center justify-center text-success-foreground text-xs font-bold" title="{{ step.step_id }} {{ step.agent_label }}: {{ step.duration }}">✓</div>
      {% elif step.status == 'in_progress' %}
        <div class="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-xs font-bold animate-pulse" title="{{ step.step_id }} {{ step.agent_label }}: running">●</div>
      {% elif step.status == 'failed' %}
        <div class="w-8 h-8 rounded-full bg-destructive flex items-center justify-center text-destructive-foreground text-xs font-bold" title="{{ step.step_id }} {{ step.agent_label }}: failed">✗</div>
      {% elif step.status == 'skipped' %}
        <div class="w-8 h-8 rounded-full bg-muted flex items-center justify-center text-muted-foreground text-xs font-bold" title="{{ step.step_id }}: skipped">⏭</div>
      {% else %}
        <div class="w-8 h-8 rounded-full bg-secondary flex items-center justify-center text-secondary-foreground text-xs" title="{{ step.step_id }} {{ step.agent_label }}: pending">○</div>
      {% endif %}
      {% if not loop.last %}
        <div class="w-4 h-0.5 bg-border"></div>
      {% endif %}
    {% endfor %}
  </div>
{% endmacro %}
```

### 6.3. Card

```html
{% macro card(title, value, subtitle=None, color='card') %}
  <div class="bg-{{ color }} border border-border rounded-lg p-4">
    <p class="text-sm text-muted-foreground">{{ title }}</p>
    <p class="text-2xl font-semibold text-card-foreground mt-1">{{ value }}</p>
    {% if subtitle %}
      <p class="text-xs text-muted-foreground mt-1">{{ subtitle }}</p>
    {% endif %}
  </div>
{% endmacro %}
```

---

## 7. Dark Mode

Dark mode is toggled via a button in the header that adds/removes the `.dark` class on `<html>`. Preference is persisted in `localStorage`:

```javascript
// dashboard/static/theme-toggle.js
function toggleDarkMode() {
  const html = document.documentElement;
  html.classList.toggle('dark');
  localStorage.setItem('theme', html.classList.contains('dark') ? 'dark' : 'light');
}

// On page load: restore preference
(function() {
  const saved = localStorage.getItem('theme');
  if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    document.documentElement.classList.add('dark');
  }
})();
```

---

## 8. Live Duration Counters

Running steps show live-updating duration counters without page refresh:

```javascript
// dashboard/static/duration.js
// Updates all elements with data-started-at to show live elapsed time
setInterval(() => {
  document.querySelectorAll('[data-started-at]').forEach(el => {
    const started = new Date(el.dataset.startedAt);
    const elapsed = Math.floor((Date.now() - started) / 1000);
    const min = Math.floor(elapsed / 60);
    const sec = elapsed % 60;
    el.textContent = `${min}m${sec.toString().padStart(2, '0')}s`;
  });
}, 1000);
```

```html
<!-- In template -->
<td data-started-at="{{ run.started_at.isoformat() }}">{{ run.duration_display }}</td>
```

---

## 9. API Routes (Dashboard Backend)

### 9.1. Page Routes (return full HTML)

```
GET  /                                        Project selector
GET  /system/running                          Running tasks (cross-project)
GET  /system/status                           Daemon health, quota
GET  /project/{id}/                           Project dashboard
GET  /project/{id}/batches                    Batch list
GET  /project/{id}/batch/{bid}                Batch detail
GET  /project/{id}/item/{iid}                 Work item detail
GET  /project/{id}/queue                      Queue & backlog
GET  /project/{id}/history                    History
GET  /project/{id}/analytics                  Analytics (Phase 2)
```

### 9.2. Fragment Routes (return partial HTML for htmx)

```
GET  /project/{id}/item/{iid}/tab/overview    Tab content
GET  /project/{id}/item/{iid}/tab/design-doc  Design doc rendered
GET  /project/{id}/item/{iid}/tab/reports     Step reports
GET  /project/{id}/item/{iid}/tab/artifacts   Artifact browser
GET  /api/search?q=...&project=...            Search results fragment
GET  /api/confirm/kill-step/{iid}/{step}      Confirmation dialog HTML
```

### 9.3. Action Routes (mutate state, return redirect or fragment)

```
POST /project/{id}/api/item/{iid}/kill-step/{n}      Kill a running step
POST /project/{id}/api/item/{iid}/restart-step/{n}    Restart a failed step
POST /project/{id}/api/item/{iid}/skip-step/{n}       Skip a failed step
POST /project/{id}/api/item/{iid}/restart-from/{n}    Restart from step N
POST /project/{id}/api/batch/{bid}/approve             Approve batch
POST /project/{id}/api/batch/{bid}/pause               Pause batch
POST /project/{id}/api/batch/{bid}/resume              Resume batch
POST /project/{id}/api/batch/{bid}/archive             Archive batch
```

### 9.4. SSE Routes

```
GET  /api/stream/events                       Global event stream
GET  /api/stream/running                      Running tasks updates
```
