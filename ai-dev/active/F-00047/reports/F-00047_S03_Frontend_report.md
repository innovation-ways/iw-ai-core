# F-00047 S03 — Frontend: Code Tab Templates + Job UI

## What was done

Implemented all Jinja2 templates for the Code Understanding tab, wired up htmx interactions, implemented the SSE EventSource client in vanilla JS, added Mermaid.js to the base template, and added the "Code" nav link to the sidebar.

## Files changed

1. **dashboard/templates/base.html** — Added Mermaid.js CDN script after `marked.js`, added `htmx:afterSwap` listener to re-initialize Mermaid diagrams injected by htmx swaps.

2. **dashboard/templates/fragments/nav_projects.html** — Added `('/project/' ~ project.id ~ '/code', 'Code')` to the sidebar nav links list.

3. **dashboard/templates/project_code.html** — New full-page template with:
   - Page header with meta bar (provider, models, last indexed, file/chunk counts)
   - Generate Code Map dropdown button (CSS-only, no framework)
   - Job status panel (live SSE updates)
   - Architecture panel (content or empty state)

4. **dashboard/templates/fragments/code_job_status.html** — SSE-enabled running job status fragment with vanilla JS EventSource, progress bar, elapsed timer, cancel button.

5. **dashboard/templates/fragments/code_empty_state.html** — Empty state with terminal/code SVG icon and Generate Code Map CTA button.

6. **dashboard/templates/fragments/code_architecture_view.html** — Architecture document viewer with `.prose-doc` styles and Mermaid diagram support.

7. **dashboard/templates/fragments/code_job_report.html** — Success panel showing last completed job stats (duration, files indexed, chunks, languages, model).

## Test results

- **ruff check**: 1 pre-existing issue in `tests/integration/conftest.py` (unrelated to these changes)
- **ruff format**: All 175 files already formatted
- **mypy**: Success — no issues found in 102 source files
- **pytest tests/unit/**: 732 passed, 2 warnings (pre-existing)

## Issues or observations

- The `intcomma` Jinja filter is used in `code_job_report.html` for chunk count formatting — this filter is already available in the existing codebase (used in `docs_library.html`).
- The `timeago` filter is used in `project_code.html` for the "Last indexed" timestamp — confirmed available via `dashboard/utils/timeago.py` which is registered in the Jinja environment.
- The SSE EventSource implementation uses vanilla JS (not htmx hx-ext="sse") as specified, connecting to `/project/{project_id}/api/code/index/stream`.
