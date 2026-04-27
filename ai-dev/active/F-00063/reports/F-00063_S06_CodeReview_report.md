# F-00063 S06 — Code Review: Frontend (S04)

**Work item**: F-00063 — Stale Process & Migration Detector
**Step reviewed**: S04 (frontend-impl)
**Reviewer step**: S06 (code-review-impl)
**Date**: 2026-04-27

---

## Summary

Three critical/high defects found and fixed. All three were runtime-only bugs invisible to the
template-rendering tests (which bypass the router and supply context directly). After fixes, all
three quality gates pass: `make test-unit` (1844 passed), `make lint` (clean), `make typecheck`
(clean).

---

## Findings

### FINDING-1 — CRITICAL: Router passes wrong context keys to panel template

**File**: `dashboard/routers/staleness.py`  
**Lines (before fix)**: 202-206

The `staleness_panel` endpoint passed `{"project_id": project_id, "result": result}` to
`staleness_panel.html`. The template uses `staleness` (not `result`) and `project.id` (attribute
access, not a plain string `project_id`). At runtime, every access to `staleness.*` in the
template would resolve to `undefined`/empty in Jinja2, silently rendering the wrong output.

**Fix**: Updated both TemplateResponse calls to pass `{"staleness": result, "project":
type("_Project", (), {"id": project_id})()}` — a minimal object that satisfies `project.id`.

---

### FINDING-2 — CRITICAL: Router passes wrong context to dot template

**File**: `dashboard/routers/staleness.py`  
**Lines (before fix)**: 231-235

`staleness_dot` passed `{"project_id": project_id, "is_stale": result.is_stale}`. The template
`staleness_dot.html` checks `staleness.services`, `staleness.alembic`, `staleness.is_stale`, and
uses `project.id`. The mismatched keys would cause the top-level `{% if staleness and ... %}`
guard to evaluate as falsy, rendering a completely empty dot for every project.

**Fix**: Same fix pattern as FINDING-1 — pass `{"staleness": result, "project": ...}`.

---

### FINDING-3 — CRITICAL: Missing confirm GET endpoints for action buttons

**File**: `dashboard/routers/staleness.py` (missing endpoints)  
**Template reference**: `dashboard/templates/fragments/staleness_panel.html` lines 122-145, 59

The panel template's action buttons (Restart, Stop, Start) all use `hx-get` on confirm-dialog
endpoints:

- `GET /projects/{id}/services/{name}/restart/confirm`
- `GET /projects/{id}/services/{name}/stop/confirm`
- `GET /projects/{id}/services/{name}/start/confirm`
- `GET /projects/{id}/alembic/upgrade/confirm`

None of these endpoints existed in the router. Every action button click would return 404 and
the confirm dialog would never open.

**Fix**: Added four GET endpoint handlers to `staleness.py` that render `staleness_confirm.html`
with the appropriate `action`, `service_name`, `command_text`, and `action_url` context.

---

### FINDING-4 — HIGH: Alembic "Upgrade head" button had both `hx-post` and `hx-get`

**File**: `dashboard/templates/fragments/staleness_panel.html`  
**Lines (before fix)**: 57-64

The button carried both `hx-post=".../alembic/upgrade"` and `hx-get=".../alembic/upgrade/confirm"`.
htmx processes only one HTTP verb per element (GET when both are present). This silently discarded
the POST, but more importantly the semantics were wrong: the button should first open the confirm
dialog (`hx-get`), not execute the action directly. The `hx-post` attribute was removed.

**Fix**: Removed `hx-post` from the Upgrade head button; kept only `hx-get` pointing at the
confirm endpoint.

---

### FINDING-5 — MEDIUM: Grey staleness dot missing `title` accessibility attribute

**File**: `dashboard/templates/fragments/staleness_dot.html`  
**Line (before fix)**: 9

The red dot carries `title="Outdated processes — click for details"`. The grey dot had no `title`,
making the dot colour-only signal for the grey/up-to-date state.

**Fix**: Added `title="All services up-to-date"` to the grey dot span.

---

### FINDING-6 — MEDIUM: CSS used hardcoded hex instead of CSS variables

**File**: `dashboard/static/tailwind.src.css`  
**Lines (before fix)**: 111-117

`.iw-staleness-dot--red` used `background-color: #dc2626` and `.iw-staleness-dot--grey` used
`background-color: #9ca3af`, while the rest of the codebase uses `var(--destructive)` and
`var(--muted-foreground)` where available. This would break theming / dark-mode.

**Fix**: Changed to `var(--destructive, #dc2626)` and `var(--muted-foreground, #9ca3af)` (with
hex as fallback for safety). `make css` was re-run to regenerate `styles.css`.

---

## Checklist Results

| Check | Result |
|-------|--------|
| Migrations section rendered BEFORE Services section (Invariant 7) | PASS — comment + ordering verified in template |
| Migrations section omitted when no alembic block | PASS — `status != "no_config"` guard |
| Empty staleness renders literally nothing (Invariant 2) | PASS — top-level `{% if staleness and (...) %}` guard |
| Status badges use text labels (not colour-only) | PASS — text in every badge span |
| "Apply migrations first" hint only when both stale | PASS — `has_stale_alembic and has_stale_service` guard |
| Panel outer `<section>` has `hx-trigger="every 15s"` + `hx-swap="outerHTML"` | PASS |
| Project home page wrapper has `hx-trigger="load, every 15s"` | PASS |
| Red dot has `hx-trigger="every 15s"` | PASS |
| Action buttons gate on `svc.actions` | PASS — `{% if "restart" in svc.actions %}` etc. |
| Confirm dialog matches existing modal style | PASS — same button layout, same `.bg-card` wrapper |
| Router context matches template variable names | FIXED (FINDING-1 + FINDING-2) |
| Confirm endpoints exist in router | FIXED (FINDING-3) |
| Upgrade head button uses single htmx verb | FIXED (FINDING-4) |
| Grey dot has accessibility title | FIXED (FINDING-5) |
| CSS uses CSS variables for dot colours | FIXED (FINDING-6) |

## Test Verification

| Gate | Command | Result |
|------|---------|--------|
| Unit tests | `make test-unit` | 1844 passed, 2 skipped |
| Lint | `make lint` | All checks passed |
| Typecheck | `make typecheck` | No issues in 190 source files |

---

## Subagent Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00063",
  "step_reviewed": "S04",
  "verdict": "NEEDS_FIX",
  "findings": [
    {
      "id": "FINDING-1",
      "severity": "CRITICAL",
      "file": "dashboard/routers/staleness.py",
      "description": "staleness_panel endpoint passed wrong context keys (result/project_id) — template expects staleness/project.id",
      "fixed": true
    },
    {
      "id": "FINDING-2",
      "severity": "CRITICAL",
      "file": "dashboard/routers/staleness.py",
      "description": "staleness_dot endpoint passed wrong context keys (is_stale/project_id) — template expects staleness/project.id",
      "fixed": true
    },
    {
      "id": "FINDING-3",
      "severity": "CRITICAL",
      "file": "dashboard/routers/staleness.py",
      "description": "Missing GET confirm endpoints for restart/start/stop/alembic-upgrade — all action buttons returned 404",
      "fixed": true
    },
    {
      "id": "FINDING-4",
      "severity": "HIGH",
      "file": "dashboard/templates/fragments/staleness_panel.html",
      "description": "Upgrade head button had both hx-post and hx-get — removed erroneous hx-post",
      "fixed": true
    },
    {
      "id": "FINDING-5",
      "severity": "MEDIUM",
      "file": "dashboard/templates/fragments/staleness_dot.html",
      "description": "Grey staleness dot missing title attribute — colour-only accessibility signal",
      "fixed": true
    },
    {
      "id": "FINDING-6",
      "severity": "MEDIUM",
      "file": "dashboard/static/tailwind.src.css",
      "description": "CSS used hardcoded hex instead of var(--destructive) / var(--muted-foreground)",
      "fixed": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "1844 passed, 2 skipped (unit); lint clean; typecheck clean (190 files).",
  "notes": "All 6 findings have been fixed. The tests passed before fixes because the template tests bypass the router and supply context directly. Runtime bugs were only detectable via code review. After fixes: make test-unit, make lint, make typecheck all pass."
}
```
