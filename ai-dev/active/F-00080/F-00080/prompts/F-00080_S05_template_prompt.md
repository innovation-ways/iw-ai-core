# F-00080_S05_template-impl_prompt

**Work Item**: F-00080 — First-Time User Onboarding & Contextual Help (Dashboard OSS-readiness)
**Step**: S05
**Agent**: template-impl

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies. This step does NOT touch migrations or docker.

## Input Files

- `uv run iw item-status F-00080 --json`
- `ai-dev/active/F-00080/F-00080_Feature_Design.md`
- `ai-dev/work/F-00080/reports/F-00080_S03_frontend_report.md` — read the `notes` field for the list of `data-tour` selectors S03 used; you will add those `data-tour` attributes to the matching elements
- `dashboard/templates/macros/help_button.html` (already exists from S03)
- `dashboard/templates/macros/empty_state.html` (already exists from S03)
- All 22 fragment files under `dashboard/templates/_partials/help/`

## Output Files

- 22 page templates updated with `{% block page_help_slug %}<slug>{% endblock %}`
- 10 list templates refactored to use `{{ empty_state(...) }}` macro for the empty branch
- `data-tour="..."` attributes added to elements that S03's tour definitions reference
- `ai-dev/work/F-00080/reports/F-00080_S05_template_report.md`

## Context

S01 created the help router. S03 created the macros, fragments, JS, CSS, and the page-header `?` slot in `base.html`. This step is the wiring step: telling each in-scope page **which slug it is** by setting `{% block page_help_slug %}<slug>{% endblock %}`, refactoring empty-state branches to use the macro with concrete copy, and adding `data-tour` selectors so Driver.js can highlight the right elements.

Do NOT write any new backend code, JS, or CSS in this step. If you discover that S03 missed something, raise a blocker rather than patching frontend assets here.

## Requirements

### 1. Wire `page_help_slug` block on every in-scope page

For each page below, open the template, **add a single new line** somewhere near the existing `{% block title %}...{% endblock %}` line:

```jinja
{% block page_help_slug %}<slug>{% endblock %}
```

Page → slug mapping:

| Template path | slug |
|---|---|
| `dashboard/templates/pages/project_selector.html` | `projects` |
| `dashboard/templates/pages/project/queue.html` | `queue` |
| `dashboard/templates/pages/project/history.html` | `history` |
| `dashboard/templates/pages/project/batches.html` | `batches` |
| `dashboard/templates/pages/project/batch_detail.html` | `batch_detail` |
| `dashboard/templates/pages/project/item_detail.html` | `item_detail` |
| `dashboard/templates/pages/project/jobs.html` | `jobs` |
| `dashboard/templates/pages/project/job_detail.html` | `job_detail` |
| `dashboard/templates/pages/project/quality.html` | `quality` |
| `dashboard/templates/pages/project/tests.html` | `tests` |
| `dashboard/templates/pages/project/search.html` | `search` |
| `dashboard/templates/project_code.html` | `code` |
| `dashboard/templates/docs_library.html` | `docs` |
| `dashboard/templates/research_library.html` | `research` |
| `dashboard/templates/pages/system/status.html` | `status` |
| `dashboard/templates/pages/system/worktrees.html` | `worktrees` |
| `dashboard/templates/pages/system/containers.html` | `containers` |
| `dashboard/templates/pages/system/all_active.html` | `all_active` |
| `dashboard/templates/pages/system/config.html` | `config` |
| `dashboard/templates/pages/system/keep_alive.html` | `keep_alive` |
| `dashboard/templates/pages/system/coverage.html` | `coverage` |
| `dashboard/templates/pages/system/running.html` | `running` |

Pages NOT to touch (out of scope for this feature): `dashboard.html`, `oss.html`, `item_execution_report.html`, `docs_detail.html`, `docs_global.html`, `research_detail.html`, `containers.html.iw-collision`.

### 2. Refactor empty-state branches in 10 list views

For each of these templates, locate the existing `{% if items %} ... {% else %} ... {% endif %}` (or equivalent) and replace the `{% else %}` body with a call to the macro. Use plain English copy that fits the page semantics. Keep the wording short and concrete.

Targets:

| Template | Slug for empty_state | Heading | Body | Primary CTA |
|---|---|---|---|---|
| `pages/project/queue.html` | `queue` | "No work items yet" | "Items you design appear here. Create a feature, incident, or change request to get started." | "How to design an item →" / `docs/IW_AI_Core_CLI_Spec.md` |
| `pages/project/batches.html` | `batches` | "No batches yet" | "Approved items become batches that the daemon executes in worktrees." | "About batches →" / `docs/IW_AI_Core_Daemon_Design.md#batches` |
| `pages/project/jobs.html` | `jobs` | "No background jobs running" | "This page lists batches, code-index runs, doc-generation jobs, and research drafts as they happen." | "Daemon overview →" / `docs/IW_AI_Core_Daemon_Design.md` |
| `pages/project/history.html` | `history` | "No completed items yet" | "Once items merge to main, they show up here with a link to their final commit." | "How execution works →" / `docs/IW_AI_Core_Architecture.md` |
| `pages/project/tests.html` | `tests` | "No test runs yet" | "Launch a test run from this page; results stream in live and final reports stay browsable here." | "Test stack →" / `docs/IW_AI_Core_Tech_Stack.md` |
| `pages/project/quality.html` | `quality` | "No quality runs yet" | "Linting, formatting, type-checking, and security checks live here. Launch one to see the report." | "Quality gates →" / `docs/IW_AI_Core_Tech_Stack.md` |
| `research_library.html` | `research` | "No research yet" | "Filed research documents (those you create with /iw-research) appear here as drafts." | "Open the catalogue →" / `docs/implementation/00_INDEX.md` |
| `docs_library.html` | `docs` | "No project docs yet" | "Generated and human-authored docs for this project will be listed here once they're produced." | "Doc catalogue →" / `docs/implementation/00_INDEX.md` |
| `pages/system/worktrees.html` | `worktrees` | "No active worktrees" | "Each running batch gets its own git worktree; they appear here while the daemon is executing." | "Worktree isolation →" / `docs/IW_AI_Core_Worktree_Isolation.md` |
| `pages/system/all_active.html` | `all_active` | "Nothing is running" | "When any project has an active item, batch, or job, it appears here." | "Daemon overview →" / `docs/IW_AI_Core_Daemon_Design.md` |

Use the macro by adding `{% from "macros/empty_state.html" import empty_state %}` near the top of each template, then:

```jinja
{{ empty_state(
     slug="queue",
     heading="No work items yet",
     body="Items you design appear here. Create a feature, incident, or change request to get started.",
     primary_label="How to design an item →",
     primary_href="/docs/IW_AI_Core_CLI_Spec.md",
     secondary_label="",
     secondary_href=""
   ) }}
```

If a doc URL above is a markdown file path (`docs/...`), prefer the dashboard's `/docs/` route if there is one for that doc; otherwise just link to the markdown file path. Match whatever the dashboard already does for "external doc" links.

### 3. Add `data-tour` attributes for Driver.js

S03's report lists every selector its tour definitions reference (e.g. `[data-tour='queue-table']`). Walk through each entry and add the corresponding `data-tour="..."` attribute to the element it's meant to highlight. **Do not add `data-tour` to elements outside this list** — random additions inflate the surface area for regressions.

If S03's report does not list selectors, raise a blocker.

### 4. Verify base.html slot is auto-rendering correctly

After your changes, the `?` button is rendered automatically by `base.html` because S03's wiring reads `self.page_help_slug()`. You do not call the macro yourself anywhere. If a page renders without a `?` button after your edit, the `{% block page_help_slug %}` line is wrong (e.g. extra whitespace) — verify by inspecting the rendered HTML.

## Project Conventions

Read `dashboard/CLAUDE.md`. Most relevant:
- Templates use `{% extends "base.html" %}` already; do not change inheritance.
- Don't introduce new Tailwind classes (toolchain is broken). Use existing utility classes already on the page or rely on the empty-state macro's plain-CSS classes.
- Don't introduce JS in template files; help.js owns all behaviour.

## TDD Requirement

Tests for this step are in S07. Your sanity check: after editing each page, render it manually via the dashboard (or use `pytest tests/dashboard/test_help_js_smoke.py -q`) and confirm the `?` button shows up next to the page title.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting complete:

1. `make format`
2. `make typecheck` (no Python files touched, must still pass)
3. `make lint`

## Test Verification

`make test-unit` and `make test-frontend` must still pass.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "template-impl",
  "work_item": "F-00080",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/pages/project_selector.html",
    "dashboard/templates/pages/project/queue.html",
    "...etc 22 page templates total..."
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "Empty-state copy follows the macro contract; data-tour attributes added: [list]"
}
```
