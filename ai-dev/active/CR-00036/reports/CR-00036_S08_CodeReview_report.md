# CR-00036 S08 Code Review — Frontend Implementation (S07)

## Work Item
CR-00036 — Batch-level `auto_merge` toggle with operator-approved manual merge

## Step Reviewed
S07 (frontend-impl)

## Reviewer
Code Review Agent

---

## Pre-Flight Gate

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format` | ✅ 637 files already formatted |
| `make test-unit` | ✅ 2689 passed |
| `make test-dashboard` | ✅ 523 passed, 13 skipped, 1 xfailed |
| Specific CR-00036 tests | ✅ 15 passed |

---

## Files Changed (by S07)

| File | Change |
|------|--------|
| `dashboard/templates/components/action_button.html` | Added `approve_merge_button` macro |
| `dashboard/templates/fragments/item_overview.html` | Added `awaiting_approval` branch + macro import |
| `dashboard/templates/components/status_badge.html` | Added `awaiting_approval` entry with `bg-info` |
| `dashboard/templates/pages/project/batch_detail.html` | Plan tab auto-merge toggle |
| `dashboard/templates/fragments/batch_detail_header.html` | `Auto-merge: yes/no` summary line |
| `dashboard/templates/pages/project/queue.html` | Create-batch form toggle pre-filled from `auto_merge_default` |
| `dashboard/routers/project_pages.py` | Passes `auto_merge_default` to queue template |
| `tests/dashboard/test_item_overview_awaiting_merge.py` | 6 new tests |
| `tests/dashboard/test_batch_detail_auto_merge_toggle.py` | 9 new tests |

---

## Review Checklist: Findings

### 1. Macro and Template Integration ✅
- `approve_merge_button(project_id, item_id)` is correctly defined in `action_button.html`
- Imported in `item_overview.html` via `with context` on line 3
- Branching order is correct: `awaiting_approval` is checked **before** `failed`/`merge_failed` (lines 91–94 vs 95–101) — prevents wrong button from rendering
- Macro accepts `(project_id, item_id)` in the same order as sibling macros (`restart_merge_button`, `abandon_merge_button`)

### 2. htmx Wiring ✅
- `approve_merge_button` POSTs to `/project/{project_id}/api/item/{item_id}/approve-merge`
  - The route is registered at `actions.py:1093` with `router.post("/item/{item_id}/approve-merge")`
  - The router has `prefix="/project/{project_id}/api"` → full path: `/project/{project_id}/api/item/{item_id}/approve-merge`
  - ✅ Matches S05 endpoint exactly
- Plan tab toggle POSTs to `/project/{current_project.id}/api/batch/{batch.id}/auto-merge`
  - Route at `actions.py:1698` (`router.post("/batch/{batch_id}/auto-merge")`)
  - ✅ Matches S05 endpoint
- SSE refresh: toggle has `hx-on::after-request="htmx.trigger('#batch-header-sse-trigger', 'batch-header-refresh')"` — re-renders header after toggle
- Toggle is `disabled` when `batch_status not in ('planning', 'approved', 'paused')` — mirrors max-parallel exactly

### 3. Tailwind / CSS ✅
- `bg-success` and `bg-info` classes confirmed present in prebuilt `styles.css`:
  - `.bg-success{background-color:var(--success)}`
  - `.bg-info{background-color:var(--info)}`
- No dynamic class construction in templates
- `make css` reports "Nothing to be done" — existing utility classes cover all new markup

### 4. Status Badge ✅
- `awaiting_approval` maps to `bg-info text-info-foreground` (same as `approved`)
- Label displays raw value `"awaiting_approval"` — human-readable with an underscore separator
- No title attribute on the badge itself; the step status tooltip comes from the `title` attribute on the MERGE action button (`title="Approve and trigger the squash-merge to main"`)

### 5. Create-Batch-from-Selection Form ✅
- Toggle in `queue.html` uses `{% if auto_merge_default %}checked{% endif %}`
- `auto_merge_default` is passed from `project_pages.py:project_queue()` (lines 230–250)
- The route loads `proj_cfg.auto_merge_default` from `projects.toml` via `load_projects_toml()`
- ✅ Pre-fills from project's `auto_merge_default` — not hardcoded

### 6. Tests ✅
- `test_item_overview_awaiting_merge.py` (6 tests):
  - `test_awaiting_approval_renders_merge_button` — verifies button + URL
  - `test_awaiting_approval_does_not_render_restart_merge`
  - `test_awaiting_approval_does_not_render_abandon_merge`
  - `test_failed_merge_still_shows_restart_and_abandon` — regression guard
  - `test_merge_failed_shows_restart_and_abandon`
  - `test_completed_merge_renders_no_action_buttons`
- `test_batch_detail_auto_merge_toggle.py` (9 tests):
  - Enabled + checked for `planning|approved|paused` with `auto_merge=True`
  - Enabled + unchecked for `planning|approved|paused` with `auto_merge=False`
  - Disabled for `executing|completed|completed_with_errors`
  - `_has_disabled_attr()` helper correctly distinguishes HTML `disabled` boolean attr from Tailwind `disabled:` class prefix using regex `\bdisabled\b(?=\s|/|>)`

### 7. Visual Sanity Check ⚠️ MEDIUM
- S07 report does not include a Playwright screenshot or manual browser verification
- The templates render correctly per tests, but a live browser check was not performed
- This is fixable at S17 (qv-browser step)

---

## Summary

**Verdict: PASS**

S07 correctly implements all frontend requirements for CR-00036:

| Requirement | Status |
|-------------|--------|
| `approve_merge_button` macro with correct URL | ✅ |
| Branching order (awaiting_approval before failed) | ✅ |
| Plan tab toggle with correct URL and disabled logic | ✅ |
| SSE refresh on toggle | ✅ |
| `auto_merge_default` pre-fills create-batch form | ✅ |
| `awaiting_approval` status badge | ✅ |
| `bg-success`/`bg-info` CSS classes present | ✅ |
| All tests passing | ✅ |
| No hardcoded defaults | ✅ |
| Visual sanity check | ⚠️ MEDIUM (deferred to S17) |

**Mandatory fixes: 0**

---

## Notes

1. **CSS classes verified**: `bg-success` and `bg-info` confirmed in `styles.css` — no Tailwind rebuild needed. The I-00067 workaround (appending plain CSS) is not required since the classes pre-exist.

2. **`_has_disabled_attr` regex**: The helper uses `\bdisabled\b(?=\s|/|>)` to match the HTML boolean attribute `disabled` while excluding Tailwind class fragments like `disabled:opacity-50`. This is a robust solution given the complexity of distinguishing the two in rendered HTML.

3. **Stall-checker exemption** (CR-00036 design note): The design specifies `awaiting_merge_approval` is exempt from the stall monitor. This is a backend/daemon concern, not a frontend issue — checked separately in S03/S04.

4. **URL discrepancy (non-issue)**: The design doc says `/actions/item/{item_id}/approve-merge` but the actual implementation uses `/project/{project_id}/api/item/{item_id}/approve-merge` (actions router with API prefix). Both resolve correctly; the design doc used a shorthand form.
