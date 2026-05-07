# F-00080: First-Time User Onboarding & Contextual Help (Dashboard OSS-readiness)

**Type**: Feature
**Priority**: Medium
**Created**: 2026-05-07
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This feature does NOT add, modify, or remove any migrations.**

## Description

Adds a first-time user onboarding & contextual help layer to the IW AI Core dashboard so that a visitor who has never seen the project can understand each page within seconds. Every project and system page gains a `?` help button that opens an htmx-loaded popover with 4 fixed sections (What is this page · What can I do · Vocabulary · Take the tour / Open docs); every list view gets an information-rich empty state via a reusable Jinja macro; and an opt-in 30-second guided tour powered by vendored Driver.js (MIT) is offered from the popover, never auto-launched. This is the OSS-readiness slice of the work derived from research [R-00067](../../docs/research/R-00067-first-time-user-onboarding-dashboard.md).

## Project Context

Read the project's `CLAUDE.md` (root + `dashboard/CLAUDE.md`) for architecture, conventions, and hard rules. Most important here:

- Stack is FastAPI + Jinja2 + htmx + prebuilt Tailwind CSS. **Plain CSS rules go directly into `dashboard/static/styles.css`** (per CLAUDE.md mitigation for the broken Tailwind toolchain in worktrees, see I-00067).
- Routers stay thin — orchestration logic lives in `orch/`. Help router is essentially a static Jinja-fragment loader, no `orch/` change required.
- Fragment templates under `templates/_partials/` and `templates/fragments/` MUST NOT extend `base.html`.
- All vendored JS lives under `dashboard/static/vendor/<lib>/` (htmx and json-enc already follow this pattern).

## Scope

### In Scope

- **Per-page `?` help popover** on 22 dashboard pages:
  - Landing: `/projects` (`templates/pages/project_selector.html`)
  - Project (13): queue, history, batches, batch_detail, item_detail, jobs, job_detail, code, docs, research, tests, quality, search
  - System (8): status, worktrees, containers, all_active, config, keep_alive, coverage, running
- **New router** `dashboard/routers/help.py` with `GET /_help/{slug}` returning the matching Jinja partial; unknown slugs → 404; allow-list driven by the set of fragment files present at startup.
- **22 Jinja help fragments** under `dashboard/templates/_partials/help/<slug>.html`, each strictly following a 4-section template (What is this page · What can I do here · Vocabulary used here · Take the 30-second tour → / Open full docs →).
- **Reusable macros** `dashboard/templates/macros/help_button.html` (renders the `?` button + invisible popover mount) and `dashboard/templates/macros/empty_state.html` (heading / body / primary CTA / secondary "Learn more" link).
- **Empty-state polish** on 10 list views using the macro: queue.html, batches.html, jobs.html, history.html, tests.html, quality.html, research_library.html, docs_library.html, worktrees.html, all_active.html.
- **Vendored Driver.js (MIT)** in `dashboard/static/vendor/driver/{driver.js.iife.js,driver.css,LICENSE}` with the upstream MIT header preserved; Driver.js entry added to `THIRD_PARTY_LICENSES`.
- **Tour definitions** in `dashboard/static/help/tours.js` keyed by page slug, 3–5 steps per tour, loaded as a static asset (no template rendering needed inside).
- **Help glue JS** in `dashboard/static/help/help.js`: handles the `?` button click → htmx GET → popover; ESC to close; focus-trap inside popover; return focus to the `?` button on close; "Take the tour" button mounts Driver.js with `allowKeyboardControl: true`, `showProgress: true`, `showButtons: ["next","previous","close"]`; on tour completion or close, set `localStorage` key `iw.tour.<slug>.completedAt`; on every page render, if the key is present, decorate the `?` button with a `data-tour-seen="true"` attribute that surfaces a subtle `✓` via CSS.
- **Page-header `?` slot** added to `templates/base.html` via a new `{% block page_help_slug %}{% endblock %}` and a `{% block page_help %}{% endblock %}` so each page declares its slug; the help button is rendered exactly once next to the page title.
- **Plain CSS** rules appended to `dashboard/static/styles.css` for the help button, popover, focus ring, and `✓ tour seen` indicator. No Tailwind recompile needed.

### Out of Scope

- Demo-data seed script ("Load example project") — separate Feature later (layer 4 of R-00067).
- Command palette (Cmd+K) help search — separate Feature later (layer 5 of R-00067).
- i18n / localisation — strings stay in Jinja so a future translation pass is a template-only change.
- README screenshots & GIF — handled under the OSS publish track (skill `iw-oss-publish`).
- Help fragments for `dashboard.html` (project home), `oss.html`, `item_execution_report.html` — follow-up.
- Auto-launching tour on first visit — explicitly forbidden (see Hard Rules).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | api-impl | New `dashboard/routers/help.py`; register router in `dashboard/app.py`; allow-list of slugs derived from fragments-on-disk | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | frontend-impl | Vendor Driver.js into `static/vendor/driver/`, update `THIRD_PARTY_LICENSES`; create `static/help/help.js`, `static/help/tours.js`; create macros `help_button.html` and `empty_state.html`; create all 22 help fragments under `_partials/help/`; append plain CSS to `static/styles.css`; add page-header `?` slot to `base.html` | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | template-impl | Set `{% block page_help_slug %}` on all 22 pages so the `?` button renders with the correct slug; refactor empty-state branches in 10 list views to use the `empty_state` macro with concrete copy per page | after S03 |
| S06 | code-review-impl | Review S05 | — |
| S07 | tests-impl | Unit tests for `help.py` (every known slug → 200; unknown → 404); orphan-slug strict integration test (every page declaring a slug must have a matching fragment file); `test_empty_states.py` asserts each list view renders the macro markers on empty input; lightweight Playwright smoke test for the queue page (click `?`, popover renders, ESC closes, "Take the tour" mounts Driver.js) | after S05 |
| S08 | code-review-impl | Review S07 | — |
| S09 | code-review-final-impl | Global cross-agent review (consistency of slug naming, fragment shape, accessibility, integration points) | — |
| S10 | qv-gate | `make lint` | — |
| S11 | qv-gate | `make format-check` | — |
| S12 | qv-gate | `make type-check` | — |
| S13 | qv-gate | `make arch-check` | — |
| S14 | qv-gate | `make security-sast` | — |
| S15 | qv-gate | `make test-unit` | — |
| S16 | qv-gate | `make test-integration` (timeout 900) | — |
| S17 | qv-gate | `make test-frontend` | — |
| S18 | qv-browser | Browser verification end-to-end (no-regression checks) | — |
| S19 | self-assess-impl | Self-assessment via the `iw-item-analyze` skill | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: None

### API Changes

- **New endpoints**:
  - `GET /_help/{slug}` — returns a Jinja help fragment (HTML). 200 on known slug; 404 on unknown.
- **Modified endpoints**: None

### Frontend Changes

- **New macros**: `templates/macros/help_button.html`, `templates/macros/empty_state.html`
- **New fragments**: 22 files under `templates/_partials/help/`
- **New static assets**: `static/help/help.js`, `static/help/tours.js`, `static/vendor/driver/{driver.js.iife.js,driver.css,LICENSE}`
- **Modified pages**: 22 page templates (one new line each: `{% block page_help_slug %}<slug>{% endblock %}`); 10 list views (refactor empty branch to `{{ empty_state(...) }}`)
- **Modified base**: `templates/base.html` adds a `{% block page_help_slug %}` and renders the `?` button **server-side** at the right end of the existing global header bar (same `<div>` that holds the hamburger + search input) via the `help_button` macro — no JS-driven repositioning. Loads `help.js` and `tours.js` deferred. `driver.js`/`driver.css` are NOT loaded eagerly; help.js lazy-injects them on first tour mount.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `F-00080_Feature_Design.md` | Design | This document |
| `F-00080_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/F-00080_S01_api_prompt.md` | Prompt | help router |
| `prompts/F-00080_S02_CodeReview_prompt.md` | Prompt | review S01 |
| `prompts/F-00080_S03_frontend_prompt.md` | Prompt | vendor Driver.js, macros, fragments, JS, CSS |
| `prompts/F-00080_S04_CodeReview_prompt.md` | Prompt | review S03 |
| `prompts/F-00080_S05_template_prompt.md` | Prompt | wire `?` slot + empty_state macro into pages |
| `prompts/F-00080_S06_CodeReview_prompt.md` | Prompt | review S05 |
| `prompts/F-00080_S07_tests_prompt.md` | Prompt | unit + orphan-check + smoke tests |
| `prompts/F-00080_S08_CodeReview_prompt.md` | Prompt | review S07 |
| `prompts/F-00080_S09_CodeReview_Final_prompt.md` | Prompt | global review |
| `prompts/F-00080_S18_BrowserVerification_prompt.md` | Prompt | qv-browser |
| `prompts/F-00080_S19_SelfAssess_prompt.md` | Prompt | self-assess |

## Acceptance Criteria

### AC1: Help popover renders for every page

```
Given the dashboard is running
And I open any of the 22 in-scope pages
When I click the `?` button next to the page title
Then a popover opens within 200ms
And the popover contains 4 sections: "What is this page?", "What can I do here?", "Vocabulary", and a "Take the 30-second tour" button + "Open full docs" link
And the popover content was fetched via htmx GET /_help/<slug>
```

### AC2: Popover is keyboard-accessible and dismissible

```
Given a help popover is open
When I press ESC
Then the popover closes
And keyboard focus returns to the `?` button that opened it
And no page scroll occurred when the popover opened/closed
```

### AC3: Tour is opt-in only and persists "seen" state

```
Given I am on the Queue page for the first time
When I load the page
Then no tour auto-launches
And no full-screen modal appears
When I open the help popover and click "Take the 30-second tour"
Then a Driver.js tour mounts with progress indicator and 3–5 steps
And ESC dismisses the tour
When I complete or dismiss the tour
Then localStorage["iw.tour.queue.completedAt"] is set
And on the next page load the `?` button shows a subtle ✓ indicator
```

### AC4: Empty list views are informative

```
Given the Queue list is empty
When I load /project/<id>/queue
Then I see a heading explaining the empty state ("No work items yet")
And one sentence body text explaining what populates it
And a primary CTA button to the most likely next action
And a secondary "Learn more" link to the relevant doc
```

### AC5: Unknown help slug returns 404

```
Given the dashboard is running
When I GET /_help/this-slug-does-not-exist
Then the response status is 404
And the response body is a plain JSON {"detail": "..."} or short HTML 404 (matching FastAPI default)
```

### AC6: No orphan `?` buttons

```
Given the test suite runs
When the orphan-slug integration test executes
Then for every page template declaring `{% block page_help_slug %}<slug>{% endblock %}`,
     a matching `templates/_partials/help/<slug>.html` file exists
And the test fails if any orphan slug is found
```

### AC7: Apache 2.0 OSS license compatibility

```
Given the feature ships
When a reviewer inspects THIRD_PARTY_LICENSES
Then there is an entry for Driver.js identifying it as MIT-licensed
And the upstream MIT license header is preserved at the top of static/vendor/driver/driver.js.iife.js
And the file static/vendor/driver/LICENSE contains the upstream MIT text
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| User opens a page with no `page_help_slug` block (out-of-scope page) | e.g. `dashboard.html` (project home) | No `?` button rendered. Page works as before. |
| User opens a page whose slug has no fragment file | Misconfiguration | Server-side: orphan-check integration test fails CI. Runtime: GET `/_help/<slug>` returns 404; popover JS displays a tiny graceful "Help not available for this page" message and reports a console.warn. |
| User clicks `?` twice rapidly | Double-click | Second click toggles the popover closed (idempotent). No duplicate htmx fetch. |
| User clicks `?` while another popover is already open | Two popovers | Old popover closes before new one opens (only one popover may be open at a time). |
| User has cached an old version of `tours.js` after an upgrade | Stale tour definitions | Each tour is namespaced by page slug; missing tour for current slug → "Take the tour" button is hidden, `?` popover still works. |
| User has localStorage disabled | Privacy mode | Tour completion is not persisted; `✓ tour seen` indicator never shows. Tour still runs on demand. |
| User triggers tour but the highlighted element is missing from the DOM | E.g. an empty list with no rows | Driver.js's default behaviour: skip the missing step and continue (configured via `popover.allowOnInvisible: true`). The tour never crashes the page. |
| Page renders before `help.js` finishes loading | Slow connection | `?` button is a real `<button>` and is keyboard-focusable from the moment it renders; click handler attaches via event delegation on `document` so a click before JS load is handled when JS attaches. |
| Driver.js fails to load (vendor file missing) | 404 on `static/vendor/driver/driver.js.iife.js` | "Take the tour" button is disabled with `aria-disabled="true"` and tooltip "Tour unavailable"; popover continues to function. |
| User on a screen-reader navigates to the `?` button | a11y test | The button has `aria-label="Help for this page"`. On open, focus moves to the popover container which has `role="dialog" aria-modal="true" aria-label="Page help"`. ESC closes; focus returns to `?`. |

## Invariants

1. The `?` button is **never** auto-clicked. No page may auto-launch a tour or popover on first load.
2. Every page declaring `{% block page_help_slug %}<s>{% endblock %}` has a matching `_partials/help/<s>.html` file (enforced by integration test).
3. The `_help/<slug>` endpoint never returns content from outside `_partials/help/` — slugs are validated against the on-disk allow-list and `..` / `/` are rejected.
4. Plain CSS for help components lives in `dashboard/static/styles.css` (no Tailwind compile required); no JS file inlines CSS strings.
5. Tour completion uses a `localStorage` key prefixed `iw.tour.` — no cookies, no server roundtrip, no telemetry.
6. Driver.js is loaded with `allowKeyboardControl: true`; the tour is dismissible by ESC, button, or backdrop click.
7. The vendored Driver.js retains its upstream MIT license header; the project's `THIRD_PARTY_LICENSES` lists Driver.js.
8. No Shepherd.js, Intro.js, or any other AGPL-licensed onboarding library is added.
9. No third-party SaaS onboarding script (Pendo / Appcues / Chameleon) is loaded; the help system makes zero outbound network requests.
10. The help router is read-only: it never writes to the database and never accepts query parameters that influence rendered content other than the slug path parameter.

## Dependencies

- **Depends on**: None (standalone dashboard feature)
- **Blocks**: None
- **Source research**: R-00067 (`docs/research/R-00067-first-time-user-onboarding-dashboard.md`)

## Impacted Paths

- `dashboard/routers/help.py`
- `dashboard/app.py`
- `dashboard/templates/base.html`
- `dashboard/templates/macros/help_button.html`
- `dashboard/templates/macros/empty_state.html`
- `dashboard/templates/_partials/help/**`
- `dashboard/templates/pages/project/**`
- `dashboard/templates/pages/system/**`
- `dashboard/templates/pages/project_selector.html`
- `dashboard/templates/project_code.html`
- `dashboard/templates/docs_library.html`
- `dashboard/templates/research_library.html`
- `dashboard/static/help/**`
- `dashboard/static/vendor/driver/**`
- `dashboard/static/styles.css`
- `THIRD_PARTY_LICENSES`
- `tests/dashboard/test_help_router.py`
- `tests/dashboard/test_help_fragments_present.py`
- `tests/dashboard/test_empty_states.py`
- `tests/dashboard/test_help_js_smoke.py`
- `tests/dashboard/test_help_license.py`
- `tests/integration/test_help_smoke.py`
- `ai-dev/active/F-00080/**`

## TDD Approach

- **Unit tests** (`tests/dashboard/test_help_router.py`)
  - Each known slug → 200 + HTML body containing the four section headings ("What is this page?", "What can I do here?", "Vocabulary", "Take the 30-second tour").
  - Unknown slug → 404.
  - Path traversal attempt (`/_help/../etc/passwd`) → 404 (not 500, not file disclosure).
- **Integration tests**
  - `tests/dashboard/test_help_fragments_present.py` — for every page template under `templates/pages/**` and `templates/*.html`, parse the `{% block page_help_slug %}` body and assert a matching fragment file exists. Fail loudly with the orphan list.
  - `tests/dashboard/test_empty_states.py` — render each list page with empty queries (queue, batches, jobs, history, tests, quality, research_library, docs_library, worktrees, all_active) and assert the rendered HTML contains markers `data-empty-state="<page>"` and a primary CTA link.
- **Smoke test** (`tests/integration/test_help_smoke.py`)
  - Lightweight: launch the dashboard via the existing TestClient pattern in `tests/dashboard/conftest.py`; GET `/_help/queue`; assert 200 + the four headings; assert tours.js declares a `queue` tour.
- **Edge cases**
  - All boundary-behavior table rows above are mandatory test cases.

## Notes

- Driver.js MIT license vs. Shepherd.js AGPL-3.0 was the decisive licensing factor — see R-00067 §5.
- The help fragments live as one file per slug so they can be reviewed in PRs and won't drift; this is the explicit reason we did not stuff them all into a single dict in Python.
- The `✓ tour seen` indicator is intentionally subtle (faint colour + small unicode `✓`) — it must not draw the eye away from primary actions.
- Future i18n is a translation pass on Jinja files only; help.js never inlines user-visible strings except the disabled-tour fallback ("Tour unavailable") which lives in a `data-` attribute on the button so it is also translatable from the macro.
- WCAG 2.2 SC 1.4.13 is the binding accessibility criterion for popovers: dismissible (ESC), hoverable (don't disappear when the pointer enters them), persistent (only dismiss on user action).
- This feature touches **no** Python orchestration code; the only `orch/` adjacency is none — this is purely a dashboard-layer change. That is why the only "backend" agent involved is `api-impl` for the help router.
