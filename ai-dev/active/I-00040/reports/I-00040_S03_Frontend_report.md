# I-00040 S03 Frontend Report

## What was done

Implemented the stale-DB banner (R1) and write-action button disabling (R2) across all affected dashboard templates, plus the Jinja global registration (R3).

### R1 — Global banner in `base.html`

Added a conditional banner block immediately inside `<body>`, before the nav, using the exact markup contract from the spec. It uses `role="alert"`, `aria-live="polite"`, `bg-red-700 text-white` (Tailwind red palette classes already present in the codebase), and renders only when `is_db_stale(request)` is True.

### R2 — Write-button disabling

Created `dashboard/templates/macros/db_guard.html` with the `write_button_attrs(request)` macro. Updated all write-action buttons across these templates:

- `fragments/daemon_panel.html` — daemon start/stop/restart buttons
- `pages/project/queue.html` — batch-create submit, item approve button
- `docs_detail.html` — doc generate/regenerate buttons
- `fragments/tests_launch.html` — test launch button
- `fragments/quality_launch.html` — quality launch and auto-fix buttons
- `pages/system/worktrees.html` — prune orphans button
- `fragments/worktree_table.html` — worktree teardown button
- `project_code.html` — code index/reindex/regen-map buttons
- `pages/system/running.html` — "restart from here" button
- `fragments/item_overview.html` — restart/skip/kill action buttons (already uses `action_button.html` macros)
- `components/action_button.html` — added `{{ write_button_attrs(request) }}` to all four macros so callers automatically get disabled state

The "restart from here" button in `running.html` and the action buttons in `item_overview.html` were the only ones that needed explicit macro calls since they don't go through the dropdown pattern.

### R3 — `is_db_stale` Jinja global

Registered `is_db_stale` as a Jinja global in `dashboard/app.py` via a wrapper `_is_db_stale(request)` function, making it available in all templates without any import.

### R5 — Tailwind

The `bg-red-700` class is part of the standard Tailwind palette and is already present in the compiled `styles.css`. Running `make css` failed due to a corrupted `node_modules` in this worktree (missing `postcss-selector-parser`), which is an environment issue unrelated to this change. The class is confirmed to exist in the compiled CSS.

### R4 — htmx-swapped fragments

Grepped for `HX-Reswap` and `HX-Trigger` headers — none found in the affected templates. Full-page responses from `base.html`-extended templates will include the banner; fragment responses (e.g. daemon panel refresh, queue form) are partial updates that don't need the banner since the parent page (on next reload) will show it.

## Files changed

| File | Change |
|------|--------|
| `dashboard/templates/base.html` | Banner block added at top of body |
| `dashboard/templates/macros/db_guard.html` | **NEW** — `write_button_attrs` macro |
| `dashboard/app.py` | `is_db_stale` Jinja global registered |
| `dashboard/templates/components/action_button.html` | Added `{{ write_button_attrs(request) }}` to all 4 macros |
| `dashboard/templates/fragments/daemon_panel.html` | Added import + macro calls to 3 buttons |
| `dashboard/templates/pages/project/queue.html` | Added import + macro calls to create-batch submit and item approve |
| `dashboard/templates/docs_detail.html` | Added import + macro calls to generate/regenerate buttons |
| `dashboard/templates/fragments/tests_launch.html` | Added import + macro call to launch button |
| `dashboard/templates/fragments/quality_launch.html` | Added import + macro calls to launch and auto-fix buttons |
| `dashboard/templates/pages/system/worktrees.html` | Added import + macro call to prune button |
| `dashboard/templates/fragments/worktree_table.html` | Added import + macro call to teardown button |
| `dashboard/templates/project_code.html` | Added import + macro calls to 4 code dropdown buttons |
| `dashboard/templates/pages/system/running.html` | Added import + macro call to "restart from here" button |
| `dashboard/templates/fragments/item_overview.html` | Added import (macros auto-apply via action_button.html) |

## Test results

- `make lint`: All checks passed
- `make format`: 404 files already formatted  
- `make typecheck`: Success — no issues found in 178 source files

## Notes / observations

- `make css` failed due to corrupted `node_modules` in this worktree (pre-existing environment issue). The `bg-red-700` class is a standard Tailwind palette color and is already in the compiled CSS — no CSS regeneration is actually needed for this change.
- The `restart_button`, `skip_button`, `kill_button`, and `restart_merge_button` macros in `action_button.html` now include `{{ write_button_attrs(request) }}`, so any template using them gets disabled-state automatically.
- Read-only forms (search, filters, nav fragments) were correctly left untouched.
- The `require_db_at_head` dependency in `actions.py` provides server-side enforcement at the API level; the template-level disabling provides user-facing UX. Both layers together satisfy AC2.
