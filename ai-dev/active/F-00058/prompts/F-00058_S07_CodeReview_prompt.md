# F-00058_S07_CodeReview_prompt

**Work Item**: F-00058
**Step Being Reviewed**: S05 (API) + S06 (Frontend) — joint review
**Review Step**: S07

---

## Input Files

- `ai-dev/active/F-00058/F-00058_Feature_Design.md`
- `ai-dev/active/F-00058/reports/F-00058_S05_API_report.md`
- `ai-dev/active/F-00058/reports/F-00058_S06_Frontend_report.md`
- All files listed in both reports

## Output Files

- `ai-dev/active/F-00058/reports/F-00058_S07_CodeReview_report.md`

## Context

Joint review of API + Frontend because the HTML contract between them must match exactly.

## Review Checklist

### 1. Contract alignment
- Every `render_template(...)` call in a router passes exactly the context variables the template references.
- Missing template variables do NOT default to `None` silently (use `StrictUndefined` or verify via tests).
- `oss_cli_block.html` receives a `command` and `description` from each action row.
- `oss_install_modal.html` receives the output of `probe_tier1()` unchanged.
- `oss_status_frame.html` is included in the shared project header with the required context (pill_color, summary_text, stale, url, oss_enabled).

### 2. htmx / SSE integration
- HTMX attributes on the Scan/Prepare/Publish/Install buttons match the router endpoints (`/scan`, `/prepare`, `/publish`, `/install` respectively).
- The Install-now button in `oss_install_modal.html` POSTs to `/install` (not to a placeholder or missing endpoint — AC2 traceability).
- On SSE `complete` for an install job, the modal re-fetches `GET /tools` — verify the htmx trigger wiring.
- SSE endpoint sets correct `Content-Type: text/event-stream`, `Cache-Control: no-cache`.
- `hx-sse` on progress row subscribes to the right job stream URL.
- Heartbeat messages don't break the swap logic.

### 3. Architecture
- Routers remain thin — no template-rendering logic leaks into services and no business logic leaks into routers.
- Tab visibility is a single template condition (`{% if project.oss_enabled %}`), not duplicated.

### 4. Error paths
- 409 Conflict on concurrent scan renders a toast (not a hard failure page).
- Network/SSE disconnection triggers reconnect logic, not a blank result.

### 5. Accessibility
- Pill has `aria-label` describing state.
- Install modal is keyboard-trappable; `Esc` closes it.
- CLI block `<details>` toggle is keyboard accessible.

### 6. Regression prevention
- Project header template change does NOT affect layout of existing pages (Code, Tests, Quality, Documentation).
- Tab partial change preserves existing tab order; OSS is added, nothing moved.

### 7. Testing
- S05 tests assert endpoint status codes + HTMX headers.
- S06 tests assert template renders for all 4 pill states + 3 enablement states (disabled / enabled-no-scan / enabled-with-scan).
- Stale banner tested.

## Test Verification (NON-NEGOTIABLE)

`make test-integration` + `make lint` + `uv run mypy dashboard/` pass.

## Review Result Contract

Standard JSON.
