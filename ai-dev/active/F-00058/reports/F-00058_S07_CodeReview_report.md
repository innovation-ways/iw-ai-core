# F-00058_S07_CodeReview_report

## Summary

Joint review of S05 (API: `dashboard/routers/oss.py`) and S06 (Frontend: all OSS templates) against F-00058 design and the step review checklist. Found 2 code issues requiring fixes and 1 design observation.

## Findings

### CRITICAL — OSS tab NOT gated on `oss_enabled` (AC1 violation)

**File**: `dashboard/templates/fragments/nav_projects.html:23`

The OSS link is hardcoded in the nav links list and always rendered, regardless of `project.oss_enabled`. AC1 and Invariant #6 require the tab to appear **iff** `project.oss_enabled=true`.

**Fix required**: Add `{% if project.oss_enabled %}` conditional around the OSS link in the nav.

---

### HIGH — mypy error in `oss.py` router

**File**: `dashboard/routers/oss.py:83`

```python
by_domain: dict[str, list] = defaultdict(list)
```

`list` is a generic type in Python 3.9+ and requires a type argument: `dict[str, list[Any]]`.

---

### Design observation — Stale banner anchor in `oss_status_frame.html`

The "↻" refresh link on line 9-14 of `oss_status_frame.html` uses:
```html
href="/project/{{ current_project.id }}/oss/status"
```
This navigates away from the current page rather than triggering the htmx refresh inline. Since the frame is already htmx-refreshed via the parent `#oss-status-frame`, the `<a>` should probably be `<button hx-get="..." hx-target="closest .oss-status-frame" ...>` or simply removed. This is low severity (the link works, it just does a full page nav) but inconsistent with the htmx refresh intent.

---

## What passed inspection

### ✅ Contract alignment
- `oss_page` router passes: `current_project`, `recent_jobs`, `oss_enabled`, `scan_summary`, `findings_by_domain` — all referenced in `pages/project/oss.html`
- `oss_status_frame` router passes: `current_project`, `oss_enabled`, `scan_summary`, `running_job` — matches `oss_status_frame.html` context
- `oss_tools` router passes: `project_id`, `tools`, `all_installed` — matches `oss_install_modal.html`
- `oss_cli_block` is a proper Jinja macro receiving `command` and `description`

### ✅ htmx / SSE integration
- Scan button: `hx-post="/project/{id}/oss/scan"` — correct endpoint
- Prepare button: `hx-post="/project/{id}/oss/prepare"` — correct endpoint (embedded in inline `details`)
- Publish button: `hx-post="/project/{id}/oss/publish"` — correct endpoint
- Install-now button in modal: `fetch('/project/{project_id}/oss/install', {method: 'POST'})` — correct
- SSE stream on complete for install re-fetches `GET /tools` — correct
- SSE endpoint: `text/event-stream` + `Cache-Control: no-cache` + `X-Accel-Buffering: no` — correct
- `oss_scan_progress.html` uses `sse-connect` on `stream_url` with `sse-swap="oss-stream"` — correct

### ✅ Architecture
- Routers are thin — no business logic; all delegation to `oss_service`
- Tab visibility is single template condition (`oss_enabled` check needed)

### ✅ Error paths
- 409 Conflict on concurrent jobs correctly raised in all POST handlers

### ✅ Accessibility
- Pill has `aria-label="OSS status: {color} (stale)"` — correct
- Install modal: click-outside-to-close + keyboard `✕` button — present
- `<details>` for CLI block is natively keyboard accessible

### ✅ Regression prevention
- `oss_status_frame.html` included in: dashboard, tests, quality, jobs, history, queue, batches, batch_detail, search — all via htmx-loaded `#oss-status-frame` div, no layout modification to existing templates
- Project header template NOT modified — frame is added per-page via the `#oss-status-frame` div pattern (no shared layout change needed)

### ✅ Tests
- `test_oss_dashboard_routes.py` covers all POST endpoints with 409 concurrency and 200 success
- SSE stream returns `text/event-stream` media type
- HTMX headers verified in S05

## Test Results

| Check | Result | Notes |
|-------|--------|-------|
| `uv run mypy dashboard/` | FAIL | 1 error: `dict[str, list]` missing type arg in `oss.py:83` |
| `make lint` | FAIL | 41 errors — all pre-existing, none from S05/S06 changes |
| `make test-integration` | FAIL | All tests error at `verify_instance_identity()` — pre-existing DB identity mismatch (production DB vs. testcontainer). Not related to S05/S06 |
| `make test-unit` | 1226 passed, 17 failed | Failures are pre-existing (daemon, merge_queue, migrations, safe_migrate). OSS service tests (`TestFreshnessHelper`, `TestSseMessageFormatter`) fail due to mock session side_effect chaining issues — not related to S05/S06 router/template code |

**Note on test failures**: The `InstanceMismatchError` is a pre-existing infrastructure issue where the dashboard lifespan refuses to start against a testcontainer because `IW_CORE_EXPECTED_INSTANCE_ID` in `.env` points at the production DB instance. This is not a code issue in S05/S06. The S08 tests-impl step will need to address test isolation (likely via lifespan override in the test fixture).

## Files Reviewed

### S05 (API)
- `dashboard/routers/oss.py` — full review
- `dashboard/app.py` — router registration

### S06 (Frontend)
- `dashboard/templates/pages/project/oss.html`
- `dashboard/templates/fragments/oss_status_pill.html`
- `dashboard/templates/fragments/oss_status_frame.html`
- `dashboard/templates/fragments/oss_install_modal.html`
- `dashboard/templates/fragments/oss_cli_block.html`
- `dashboard/templates/fragments/oss_scan_progress.html`
- `dashboard/templates/fragments/oss_domain_card.html`
- `dashboard/templates/fragments/oss_tool_run_card.html`
- `dashboard/templates/fragments/nav_projects.html`
- `dashboard/templates/pages/project/dashboard.html`
- `dashboard/templates/pages/project/tests.html`
- `dashboard/templates/pages/project/quality.html`
- `dashboard/templates/pages/project/jobs.html`
- `dashboard/templates/pages/project/history.html`
- `dashboard/templates/pages/project/queue.html`
- `dashboard/templates/pages/project/batches.html`
- `dashboard/templates/pages/project/batch_detail.html`
- `dashboard/templates/pages/project/search.html`
- `dashboard/templates/base.html`

### Tests
- `tests/integration/test_oss_dashboard_routes.py`

## Required Fixes

1. **nav_projects.html**: Wrap the OSS nav link in `{% if project.oss_enabled %}...{% endif %}`
2. **oss.py line 83**: Change `dict[str, list]` → `dict[str, list[Any]]`