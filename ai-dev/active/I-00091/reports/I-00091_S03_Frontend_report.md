# I-00091 S03 Frontend — Step Report

**Work Item**: I-00091 — Auto-merge settings form stays "Use global default" after partial-axis override
**Step**: S03 (frontend-impl)
**Status**: complete

## What Was Done

Updated the auto-merge settings template, status chip template, and FastAPI route
to correctly consume the per-axis `phase_source` / `runtime_source` fields added
in S01, and to return a combined HTML fragment so htmx can swap both the settings
form and the chip in place after a save.

## Files Changed

### `dashboard/templates/fragments/auto_merge_settings.html`

- Replaced single `{% set _is_override = status.config.source == 'per_project_db' %}`
  with two independent booleans:
  - `{% set _phase_override = status.config.phase_source == 'per_project_db' %}`
  - `{% set _runtime_override = status.config.runtime_source == 'per_project_db' %}`
- Phase dropdown: `Use global default` is `selected` iff `_phase_override` is False;
  `0 — disabled` / `1 — dry-run` are `selected` iff `_phase_override` is True
  AND `status.config.phase` matches the option value.
- Runtime dropdown: same pattern using `_runtime_override` and
  `status.config.runtime_option_id`.
- Added `id="auto-merge-settings"` to the outer `<section>`.
- Changed form `hx-target` from `#auto-merge-status-chip` to `#auto-merge-settings`
  with `hx-swap="outerHTML"`.
- Added `hx-indicator="#auto-merge-saving"` to the form.
- Added `<span id="auto-merge-saving" class="auto-merge-save-indicator htmx-indicator">Saving…</span>`
  after the Save button.
- Added `{% if just_saved %}<span class="auto-merge-save-indicator auto-merge-save-indicator--saved">Saved</span>{% endif %}`
  for the transient "Saved" badge.
- Footer: renders `Last changed: … by dashboard` iff `_phase_override OR _runtime_override`,
  otherwise `Using global default`.

### `dashboard/templates/fragments/auto_merge_status_chip.html`

- Rich chip's `<section>` now carries `{% if oob %} hx-swap-oob="outerHTML:#auto-merge-status-chip"{% endif %}`
  on the same `id="auto-merge-status-chip"` element (Htmx finds OOB element by id).
- Source line changed from single `Source: {{ status.config.source }}` to per-axis:
  ```
  Phase source: {{ status.config.phase_source }}{% if status.config.phase_source == 'per_project_db' %} (Per-project override){% endif %}
  · Runtime source: {{ status.config.runtime_source }}{% if status.config.runtime_source == 'per_project_db' %} (Per-project override){% endif %}
  ```

### `dashboard/routers/auto_merge_ui.py`

- `auto_merge_set_config` non-JSON branch now renders both fragments:
  1. `auto_merge_settings.html` (primary response body — swaps `#auto-merge-settings`)
  2. `auto_merge_status_chip.html` with `oob: True` (OOB swap into `#auto-merge-status-chip`)
- Uses existing `_get_project_or_404`, `_load_status`, and `_render_fragment` helpers
  without duplicating logic.
- Added `# type: ignore[union-attr]` on the two `.body.decode()` calls to suppress
  mypy's `memoryview[int]` false positive on `Response.body`.

### `dashboard/static/styles.css`

- Appended CSS for saving/saved indicators:
  ```css
  .auto-merge-save-indicator{display:none;margin-left:.5rem;font-size:.75rem;color:var(--muted-foreground)}
  .auto-merge-save-indicator.htmx-request,.htmx-request .auto-merge-save-indicator{display:inline}
  .auto-merge-save-indicator--saved{display:inline;color:var(--primary);animation:auto-merge-fade 2s ease-out forwards}
  @keyframes auto-merge-fade{0%{opacity:1}80%{opacity:1}100%{opacity:0}}
  ```

## Preflight

| Check | Result |
|-------|--------|
| `make format` | ok (750 files already formatted) |
| `make typecheck` | ok (0 errors in 255 source files) |
| `make lint` | ok (all checks passed) |

## Test Results

```
tests/dashboard/test_auto_merge_routes.py: 25 passed, 0 failed
```

Coverage failure is pre-existing (total 19.89% vs required 50%) — not caused
by this step. All 25 tests pass.

## TDD RED Evidence

n/a — frontend/template + route response shape; behavioural tests written in S05.

## Notes

- Approach used: **Option A** — render two templates, concatenate into one
  `HTMLResponse`. The OOB element retains `id="auto-merge-status-chip"` so
  htmx finds it correctly.
- No new JavaScript modules introduced; `hx-indicator` + CSS animation pattern
  reused as specified.
- No existing dashboard tests needed updating — the `id="auto-merge-settings"`
  change doesn't affect any existing test assertion, and the chip source-line
  change matches what S05's new tests will assert.
- CSS appended directly to `styles.css` (plain CSS) per CLAUDE.md — `make css`
  is broken in worktrees (I-00067).