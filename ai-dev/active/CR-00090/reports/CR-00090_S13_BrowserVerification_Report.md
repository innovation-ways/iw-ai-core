# CR-00090 S13 Browser Verification Report

**Work Item**: CR-00090 — Fix E2E Polling Suppression — Replace UA Sniffing with IW_CORE_E2E_MODE Env Var
**Step**: S13
**Agent**: qv-browser
**Base URL Used**: `http://localhost:9958`
**E2E Credentials**: `dev@example.local / DevPass2026!`

---

## Verification Results

| ID | Name | Status | Failure Class | Screenshot | Notes |
|----|------|--------|---------------|------------|-------|
| V0 | Pre-flight page sanity | **PASS** | — | — | All pages returned HTTP 200, no 500 errors |
| V1 | Polling suppressed — worktree-badge | **PASS** | — | `evidences/post/CR-00090_v1_polling_suppressed.png` | `hx-trigger="never"`, no `hx-get` on badge |
| V2 | Polling suppressed — staleness-dot | **PASS** | — | `evidences/post/CR-00090_v2_staleness_dot_suppressed.png` | `hx-trigger="never"`, no `hx-get` on staleness-dot |
| V3 | Navigation works with polling suppressed | **PASS** | — | `evidences/post/CR-00090_v3_nav_no_regressions.png` | All pages (selector, history, batches) render correctly with HTTP 200 |
| V4 | No console errors | **PASS** | — | `evidences/post/CR-00090_v4_no_console_errors.png` | Zero `ERR_CONNECTION_REFUSED` or `htmx:sendError` entries |

**Overall Status**: ✅ PASS

---

## Evidence

### V1: worktree-badge polling suppressed

```bash
$ curl -s http://localhost:9958/system/nav/worktree-badge
<span       hx-trigger="never"
      hx-swap="outerHTML"
      class="ml-auto"></span>
```

The worktree-badge span has `hx-trigger="never"` and no `hx-get` attribute — confirmed by both curl and the rendered HTML on the project selector page.

### V2: staleness-dot polling suppressed

```bash
$ curl -s http://localhost:9958/projects/iw-ai-core/staleness-dot
<span class="iw-staleness-dot iw-staleness-dot--grey"
      title="All services up-to-date"
      hx-trigger="never"
      hx-swap="outerHTML"></span>
```

The staleness-dot span has `hx-trigger="never"` and no `hx-get` attribute — confirmed by both curl and the rendered HTML on the project selector and project detail pages.

### V3: Navigation — no regressions

All tested pages return HTTP 200, contain expected UI elements, and exhibit no `UndefinedError` for `_e2e_mode`:

| URL | HTTP Status | Content |
|-----|-------------|---------|
| `/` (project selector) | 200 | Project list with stats |
| `/project/iw-ai-core/` | 200 | Project dashboard with worktree health |
| `/project/iw-ai-core/history` | 200 | History table |
| `/project/iw-ai-core/batches` | 200 | Batches table |

### V4: Console logs clean

After ~40s of browser session time (with polling suppressed), no console entries matched `ERR_CONNECTION`, `htmx:sendError`, or `HTMX` error patterns. The only remaining console entries were benign navigation/API requests that returned 200.

---

## Screenshots Captured

| File | Description |
|------|-------------|
| `evidences/post/CR-00090_v1_polling_suppressed.png` | Project selector with no polling errors (worktree-badge suppressed) |
| `evidences/post/CR-00090_v2_staleness_dot_suppressed.png` | Project dashboard (staleness-dot suppressed) |
| `evidences/post/CR-00090_v3_nav_no_regressions.png` | Batches page with no regressions |
| `evidences/post/CR-00090_v4_no_console_errors.png` | Final state with clean console logs |

---

## Implementation Details Verified

- **`orch/config.py`**: `get_e2e_mode()` reads `IW_CORE_E2E_MODE` from environment (`true`/`1` → `True`, else `False`)
- **`dashboard/routers/staleness.py`**: Module-level `templates.env.globals["_e2e_mode"] = get_e2e_mode()` sets the global for the staleness router's template instance
- **`dashboard/templates/base.html`**: `{% set _headless = _e2e_mode or ... %}` — env var drives polling suppression
- **`dashboard/templates/fragments/staleness_dot.html`**: `{% set _headless = _e2e_mode %}` — no UA fallback on staleness-dot (already handled in base.html nav)
- **`dashboard/templates/pages/project_selector.html`**: `{% set _headless = _e2e_mode %}` — no UA fallback on project-level staleness dots
- **`ai-dev/iw-config/worktree-compose.template.yml`**: `IW_CORE_E2E_MODE: "true"` is injected into the app container environment

---

## No Regressions Observed

- ✅ All dashboard pages load with HTTP 200
- ✅ No Jinja2 `UndefinedError` for `_e2e_mode` (the global is set at startup)
- ✅ Normal navigation (project selector → project dashboard → history → batches) works correctly
- ✅ No `ERR_CONNECTION_REFUSED` or `htmx:sendError` entries in console logs
- ✅ HTMX's `hx-get` on nav-projects and API search endpoints still function normally (they are not gated on `_headless`)

---

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "CR-00090",
  "overall_status": "pass",
  "overall_failure_class": null,
  "base_url_used": "http://localhost:9958",
  "verifications": [
    {
      "id": "V0",
      "name": "Pre-flight page sanity",
      "status": "pass",
      "failure_class": null,
      "screenshot": "",
      "notes": "All pages HTTP 200, no 500 errors"
    },
    {
      "id": "V1",
      "name": "Polling suppressed — worktree-badge",
      "status": "pass",
      "failure_class": null,
      "screenshot": "evidences/post/CR-00090_v1_polling_suppressed.png",
      "notes": "hx-trigger=never, no hx-get. Confirmed via curl and browser render."
    },
    {
      "id": "V2",
      "name": "Polling suppressed — staleness-dot",
      "status": "pass",
      "failure_class": null,
      "screenshot": "evidences/post/CR-00090_v2_staleness_dot_suppressed.png",
      "notes": "hx-trigger=never, no hx-get. Confirmed via curl and browser render."
    },
    {
      "id": "V3",
      "name": "Navigation works with polling suppressed",
      "status": "pass",
      "failure_class": null,
      "screenshot": "evidences/post/CR-00090_v3_nav_no_regressions.png",
      "notes": "All pages (selector, history, batches) return HTTP 200. No UndefinedError for _e2e_mode."
    },
    {
      "id": "V4",
      "name": "No console errors",
      "status": "pass",
      "failure_class": null,
      "screenshot": "evidences/post/CR-00090_v4_no_console_errors.png",
      "notes": "Zero ERR_CONNECTION_REFUSED or htmx:sendError entries across 40s session."
    }
  ],
  "console_errors_observed": [],
  "screenshots": [
    "evidences/post/CR-00090_v1_polling_suppressed.png",
    "evidences/post/CR-00090_v2_staleness_dot_suppressed.png",
    "evidences/post/CR-00090_v3_nav_no_regressions.png",
    "evidences/post/CR-00090_v4_no_console_errors.png"
  ],
  "notes": "All ACs verified. IW_CORE_E2E_MODE=true correctly suppresses HTMX polling on worktree-badge and staleness-dot. No regressions in navigation. Console is clean."
}
```
