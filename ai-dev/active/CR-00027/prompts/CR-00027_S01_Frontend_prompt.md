# CR-00027 — S01: Frontend Implementation

## Context

You are implementing CR-00027: Dashboard Sidebar Nav — Collapsible Section Headers.

The IW AI Core dashboard (`dashboard/`) is a FastAPI + Jinja2 + htmx + Tailwind CSS application (port 9900). CSS is prebuilt via `make css` from `dashboard/templates/**/*.html` — always run `make css` after editing templates that add new Tailwind classes.

Architecture reference: `CLAUDE.md` and `dashboard/CLAUDE.md`.

## Objective

Modify `dashboard/templates/base.html` to:
1. Make the "Projects" and "System" section headers visually distinct from nav items
2. Make both sections collapsible using `<details>/<summary>`
3. Both start expanded by default
4. Persist open/closed state in `localStorage`

## Current State

In `base.html` the sidebar nav (lines ~85–133) has:

**Projects section (~lines 88–98):**
```html
<div class="px-2 py-1.5 mb-1">
  <p class="text-xs text-sidebar-foreground font-medium uppercase tracking-wide">Projects</p>
</div>
<!-- htmx-loaded project list -->
<div hx-get="/api/nav-projects?current={{ nav_current }}&path={{ request.url.path }}"
     hx-trigger="load"
     hx-swap="innerHTML"
     class="space-y-0.5">
</div>
```

**System section (~lines 103–133):**
```html
<div class="border-t border-sidebar-border my-2 pt-1">
  <p class="px-2 pb-1 text-xs text-sidebar-foreground font-medium uppercase tracking-wide">System</p>
</div>
{% set system_links = [...] %}
{% for href, label in system_links %}
  <a href="{{ href }}" ...>...</a>
{% endfor %}
```

The per-project entries in `nav_projects.html` already use `<details>/<summary>` with a rotating chevron — use the same visual pattern for consistency.

## Required Changes

### 1. Wrap Projects section in `<details>`

Replace the Projects header `<div>` and the htmx `<div>` with:

```html
<details id="sidebar-projects" open class="group/proj">
  <summary class="flex items-center justify-between px-2 py-1.5 mb-1 rounded cursor-pointer list-none select-none
                  text-sidebar-primary-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors">
    <span class="text-xs font-semibold uppercase tracking-wide">Projects</span>
    <svg class="w-3 h-3 flex-shrink-0 transition-transform duration-150 group-open/proj:rotate-90"
         fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
      <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
    </svg>
  </summary>
  {% set nav_current = current_project.id if current_project else '' %}
  <div hx-get="/api/nav-projects?current={{ nav_current }}&path={{ request.url.path }}"
       hx-trigger="load"
       hx-swap="innerHTML"
       class="space-y-0.5">
  </div>
</details>
```

Note: the `{% set nav_current = ... %}` line that precedes the htmx div in the original must move inside the `<details>` body (or remain just before it — keep it working).

### 2. Wrap System section in `<details>`

Replace the border-top wrapper + `<p>` header + `{% for %}` links block with:

```html
<details id="sidebar-system" open class="group/sys border-t border-sidebar-border mt-2 pt-1">
  <summary class="flex items-center justify-between px-2 py-1.5 rounded cursor-pointer list-none select-none
                  text-sidebar-primary-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground transition-colors">
    <span class="text-xs font-semibold uppercase tracking-wide">System</span>
    <svg class="w-3 h-3 flex-shrink-0 transition-transform duration-150 group-open/sys:rotate-90"
         fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
      <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
    </svg>
  </summary>
  {% set system_links = [
    ('/system/running', 'Running Tasks'),
    ('/system/worktrees', 'Worktree Health'),
    ('/system/containers', 'Container Health'),
    ('/system/status', 'System Status'),
    ('/system/coverage', 'Test Coverage'),
    ('/system/all-active', 'All Active Work'),
    ('/system/config', 'Configuration'),
  ] %}
  {% for href, label in system_links %}
    <a href="{{ href }}"
       class="flex items-center px-2 py-1.5 rounded text-sm transition-colors
              {% if request.url.path == href %}
                bg-sidebar-accent text-sidebar-accent-foreground font-medium
              {% else %}
                text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground
              {% endif %}">
      <span>{{ label }}</span>
      {% if href == '/system/running' and running_count|default(0) > 0 %}
        <span class="ml-auto text-xs bg-primary text-primary-foreground rounded-full px-1.5 py-0.5">{{ running_count }}</span>
      {% elif href == '/system/worktrees' %}
        <span hx-get="/system/nav/worktree-badge"
              hx-trigger="load, every 60s"
              hx-swap="outerHTML"
              class="ml-auto"></span>
      {% endif %}
    </a>
  {% endfor %}
</details>
```

### 3. Add localStorage persistence

Add the following script to the existing inline `<script>` block at the bottom of `base.html` (before `</body>`, alongside the existing `toggleSidebar` function):

```js
// Persist sidebar section open/closed state across page loads
(function () {
  ['sidebar-projects', 'sidebar-system'].forEach(function (id) {
    var el = document.getElementById(id);
    if (!el) return;
    var saved = localStorage.getItem(id + '-open');
    if (saved === 'false') el.removeAttribute('open');
    el.addEventListener('toggle', function () {
      localStorage.setItem(id + '-open', el.open ? 'true' : 'false');
    });
  });
})();
```

This runs synchronously on page load (not deferred) so the state is applied before first paint, avoiding flicker.

### 4. Rebuild CSS

After editing the template, run:
```bash
make css
```

Verify it exits 0.

## Tailwind Note

Tailwind's JIT scanner reads template files to know which classes are used. The `group-open/proj:rotate-90` and `group-open/sys:rotate-90` variant classes must appear literally in the template. Do not construct them dynamically in JS.

## Verification (local sanity check)

```bash
make lint
```

Should pass with no errors. The full QV browser check runs in S07.

## Output

Modify only `dashboard/templates/base.html`. Do not modify any other files except regenerating `dashboard/static/styles.css` via `make css`.
