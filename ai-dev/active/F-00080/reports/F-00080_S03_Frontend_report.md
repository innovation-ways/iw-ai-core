# F-00080 S03 — Frontend Report

## What was done

Implemented the entire frontend surface for the F-00080 help system:

### Vendor: Driver.js v1.4.0 (MIT)
- `dashboard/static/vendor/driver/driver.js.iife.js` — IIFE bundle fetched from unpkg.com; MIT header preserved at top
- `dashboard/static/vendor/driver/driver.css` — upstream stylesheet
- `dashboard/static/vendor/driver/LICENSE` — MIT license text verbatim from upstream
- Source: https://unpkg.com/driver.js@1.4.0/dist/ (IIFE + CSS)
- SHA256 of IIFE: `f0e0b0ae39fe7d1ccdef1a95e09e14f8ede9531fbe7ad4a903932c0c572817ca`

### Macros
- `dashboard/templates/macros/help_button.html` — `help_button(slug)` macro emitting the `?` button + empty popover mount
- `dashboard/templates/macros/empty_state.html` — `empty_state(...)` macro with all 7 parameters

### 22 Help Fragments
All created under `dashboard/templates/_partials/help/`:
`projects`, `queue`, `history`, `batches`, `batch_detail`, `item_detail`, `jobs`, `job_detail`, `code`, `docs`, `research`, `tests`, `quality`, `search`, `status`, `worktrees`, `containers`, `all_active`, `config`, `keep_alive`, `coverage`, `running`.

Each fragment follows the exact 4-section structure: "What is this page?", "What can I do here?", "Vocabulary", and footer with tour/docs links.

### `help.js` (popover + tour glue)
- Event delegation on `document` for `[data-help-slug]` (works before defer finishes)
- ESC closes popover; background click closes popover; focus returns to `?` button
- One popover at a time (clicking another `?` button closes the previous first)
- Lazy-loads `driver.js.iife.js` + `driver.css` on first `[data-tour-start]` click
- `window.driver.js` (IIFE factory) is called for Driver.js instance
- Options: `allowKeyboardControl: true`, `showProgress: true`, `showButtons: ["next","previous","close"]`
- `onDestroyStarted`/`onDestroyed` → marks tour seen in localStorage (`iw.tour.<slug>.completedAt`)
- `DOMContentLoaded` restores `data-tour-seen="true"` markers from localStorage
- If no tour defined for slug → `button.hidden = true`
- If driver.js fails to load → `aria-disabled="true"` + `disabled` + `title="Tour unavailable"`
- All localStorage operations wrapped in try/catch (private mode safe)
- Exposes `window.iwHelpRestoreSeen` for ajaxy page re-runs

### `tours.js`
`window.IW_TOURS` with tours for: `queue` (3 steps), `batches` (2 steps), `jobs` (2 steps), `item_detail` (3 steps), `code` (4 steps), `docs` (3 steps), `worktrees` (2 steps), `status` (3 steps).
Popover-only slugs: all others.

**data-tour selectors used** (for S05 template-impl checklist):
- `[data-tour='queue-table']`
- `[data-tour='queue-create']`
- `[data-tour='queue-drafts']`
- `[data-tour='batches-table']`
- `[data-tour='batch-create']`
- `[data-tour='jobs-table']`
- `[data-tour='job-cancel']`
- `[data-tour='item-header']`
- `[data-tour='item-tabs']`
- `[data-tour='item-fix-cycles']`
- `[data-tour='code-index']`
- `[data-tour='code-modules']`
- `[data-tour='code-qa']`
- `[data-tour='code-arch']`
- `[data-tour='docs-catalogue']`
- `[data-tour='docs-regen']`
- `[data-tour='docs-diff']`
- `[data-tour='worktrees-table']`
- `[data-tour='worktree-prune']`
- `[data-tour='status-daemon']`
- `[data-tour='status-db']`
- `[data-tour='status-identity']`

### `base.html` updates
- Added `{% block page_help_slug %}{% endblock %}` after the `<title>` line
- Added help-button mount after `#global-search-results` inside the header bar flex container:
  ```jinja
  {% set _help_slug = self.page_help_slug() %}
  {% if _help_slug %}
    {% from "macros/help_button.html" import help_button %}
    <div class="ml-auto flex-shrink-0">{{ help_button(_help_slug) }}</div>
  {% endif %}
  ```
- Added `<script src="/static/help/tours.js" defer></script>` and `<script src="/static/help/help.js" defer></script>` after the htmx json-enc tag
- **driver.js is NOT eagerly loaded** — lazy-loaded on first tour start

### CSS (plain, appended to `styles.css`)
Sections for: `.help-trigger`, `.help-trigger__mark`, `.help-trigger__seen` (✓-when-seen), `.help-popover` (fixed positioning), `.help-content__*`, `.empty-state__*`, focus-visible ring, reduced-motion support, Driver.js dark-mode overrides.

### THIRD_PARTY_LICENSES.md
Appended Driver.js v1.4.0 MIT entry with source URL, vendored path, and full MIT license text.

### Test file: `tests/dashboard/test_help_js_smoke.py`
8 file-system smoke tests (no DB needed):
1. `test_help_js_exists` — help.js exists with key functions
2. `test_tours_js_exists` — tours.js exists with IW_TOURS and queue tour
3. `test_driver_js_vendored` — all 3 driver vendor files present with MIT content
4. `test_driver_css_vendored` — driver.css present with .driver-popover
5. `test_macros_exist` — both macros present with expected attributes
6. `test_help_fragments_exist` — all 22 fragments present with 4-section structure
7. `test_base_html_has_help_slot` — base.html has page_help_slug block + script tags
8. `test_styles_css_has_help_rules` — styles.css contains help system CSS

## Files changed

```
dashboard/static/vendor/driver/driver.js.iife.js   (new, vendored IIFE)
dashboard/static/vendor/driver/driver.css          (new, vendored CSS)
dashboard/static/vendor/driver/LICENSE             (new, MIT license)
dashboard/static/help/help.js                      (new, popover + tour glue)
dashboard/static/help/tours.js                    (new, tour definitions)
dashboard/templates/macros/help_button.html      (new, macro)
dashboard/templates/macros/empty_state.html       (new, macro)
dashboard/templates/_partials/help/*.html        (×22, help fragments)
dashboard/templates/base.html                     (modified, added slot + scripts)
dashboard/static/styles.css                       (modified, appended CSS)
THIRD_PARTY_LICENSES.md                           (modified, appended entry)
tests/dashboard/test_help_js_smoke.py             (new, 8 smoke tests)
```

## Test results

```
uv run pytest tests/dashboard/test_help_js_smoke.py -v --no-cov
8 passed in 0.03s
```

`make typecheck` → Success (no issues in 230 source files)
`node --check dashboard/static/help/help.js dashboard/static/help/tours.js` → no output (clean)

## Issues / Observations

- `make css` is broken in worktrees (I-00067) — CSS was appended as plain rules to `styles.css` directly as specified in CLAUDE.md
- The `client` TestClient fixture is unavailable to unit tests due to `IW_CORE_AGENT_CONTEXT` being set at collection time; the smoke test uses file-system assertions instead of HTTP rendering tests (S07 integration tests cover the rendering path)
- Vocabulary terms are distributed across fragments (no single fragment defines all terms; each fragment defines the 2-3 most relevant terms for its page)

## Notes for S05 (template-impl)

S05 needs to add `{% block page_help_slug %}«slug»{% endblock %}` to each page template, and add `data-tour="..."` attributes to elements referenced in the tour step definitions listed above.
