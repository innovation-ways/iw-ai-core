# Browser Verification Prompt: F-00080-S18-BrowserVerification

**Work Item**: F-00080 — First-Time User Onboarding & Contextual Help (Dashboard OSS-readiness)
**Step**: S18
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

You MUST NOT run `make dev`, `make e2e-up`, `docker compose up/down/restart/build`, `playwright install`, or `agent-browser`. The orchestrator already started an isolated E2E stack from THIS worktree. The stack is up. `docker compose exec app` is allowed only when re-running a fixture seed (none expected for this item).

## ⛔ Migrations: agents generate, daemon applies

Standard policy. No migrations are involved in this item.

## Environment

The IW orchestrator has **already** started an isolated E2E stack built from THIS worktree's source code.

**Base URL (read from env):** `$IW_BROWSER_BASE_URL`
**E2E credentials (read from env):** `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
**Work item / step identifiers (read from env):** `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports. Do NOT use `agent-browser` or direct `chromium.launch()` — `playwright-cli` exclusively.

## Input Files

- `ai-dev/active/F-00080/F-00080_Feature_Design.md`
- `dashboard/routers/help.py`
- `dashboard/templates/macros/help_button.html`
- `dashboard/templates/macros/empty_state.html`
- `dashboard/templates/_partials/help/queue.html` (and the other 21 fragments)
- `dashboard/templates/base.html`
- `dashboard/static/help/help.js`
- `dashboard/static/help/tours.js`
- `dashboard/static/vendor/driver/driver.js.iife.js`
- `dashboard/static/styles.css`
- All page templates touched in S05

## Output Files

- `ai-dev/active/F-00080/reports/F-00080_S18_BrowserVerification_Report.md`
- `ai-dev/active/F-00080/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

If the dashboard requires authentication, log in using the env credentials following the standard flow:

```bash
playwright-cli snapshot
playwright-cli fill <user-field-ref> "$IW_BROWSER_E2E_USER"
playwright-cli fill <password-field-ref> "$IW_BROWSER_E2E_PASSWORD"
playwright-cli click <submit-button-ref>
```

If the dashboard is unauthenticated in the E2E stack, the navigation goes straight to the project list.

## E2E DB seed data

The stack's PostgreSQL is seeded from the production orchestration DB via `pg_dump`. No fixture file is required for this verification — empty queue/jobs/etc. is the *expected* state for several V(n) below.

## Verification Steps

### V1: `?` button is present on the queue page

1. Navigate to `$IW_BROWSER_BASE_URL` and select any project (or directly to `/project/<some-id>/queue` via the env-provided base URL — choose any project that exists in the seeded DB).
2. Run `playwright-cli snapshot` and verify that an element with `aria-label="Help for this page"` is present near the page title.
3. Verify in the snapshot that the queue page header contains a `?` button.
4. **Screenshot:** `ai-dev/active/F-00080/evidences/post/F-00080_v1_help_button_visible.png`.

### V2: Clicking `?` opens a popover with the four mandatory sections

1. Click the `?` button (use the snapshot ref from V1).
2. Run `playwright-cli snapshot` again.
3. **Verify:** the popover is visible (search for `data-help-popover` element no longer marked `hidden`) and contains the four section headings as plain text: "What is this page?", "What can I do here?", "Vocabulary", and a "Take the 30-second tour" button + "Open full docs" link.
4. Verify the popover has `role="dialog"` and `aria-modal="true"`.
5. **Screenshot:** `ai-dev/active/F-00080/evidences/post/F-00080_v2_popover_open.png`.

### V3: ESC closes the popover and returns focus to the `?` button

1. With the popover open from V2, press the Escape key (`playwright-cli press Escape` or the equivalent CLI command — consult `playwright-cli --help` if uncertain).
2. Run `playwright-cli snapshot`.
3. **Verify:** the popover is no longer visible (its element is `hidden` or removed); focus is back on the `?` button (the snapshot's focused element matches the original `?` button ref); no console errors.
4. **Screenshot:** `ai-dev/active/F-00080/evidences/post/F-00080_v3_esc_closed.png`.

### V4: "Take the 30-second tour" mounts Driver.js

1. Re-open the popover (click `?`).
2. Click the "Take the 30-second tour →" button.
3. Run `playwright-cli snapshot`.
4. **Verify:** a Driver.js overlay is mounted (look for the `driver.js` injected DOM — it typically uses a class like `driver-active-element` or `driver-popover`). The popover from V2 should have been closed before the tour mounts.
5. Press Escape to dismiss the tour. Verify the overlay is gone.
6. **Screenshot:** `ai-dev/active/F-00080/evidences/post/F-00080_v4_tour_mounted.png`.

### V5: `✓ tour seen` indicator appears after a completed/dismissed tour

1. Reload the queue page with `playwright-cli reload` (NOT `playwright-cli open`). `open` launches a fresh Chromium with an in-memory user-data-dir and wipes localStorage — `iw.tour.queue.completedAt` would silently disappear and the V would falsely fail. `reload` reuses the existing browser session.
2. Run `playwright-cli snapshot`.
3. **Verify:** the `?` button now carries `data-tour-seen="true"` (you can read element attributes from the snapshot output) and the `✓` glyph is visible next to or inside the button.
4. **Screenshot:** `ai-dev/active/F-00080/evidences/post/F-00080_v5_tour_seen_indicator.png`.

### V6: Empty list view shows the new empty-state markup

1. Navigate to `/project/iw-ai-core/jobs` — the `e2e_fixtures/001_emptiness.py` fixture empties this page in the E2E DB. (Use `playwright-cli goto`, NOT `playwright-cli open`, so the V5 localStorage flag is preserved for V9.) If the page is unexpectedly populated, fail with `ENV_DATA_MISSING:` — it means the fixture was added after the stack was provisioned and the daemon needs to re-provision.
2. Run `playwright-cli snapshot`.
3. **Verify:** the rendered HTML contains `data-empty-state="<slug>"`, an `<h3>` heading, a `<p>` body, and an `<a class="empty-state__cta-primary">` link.
4. **Screenshot:** `ai-dev/active/F-00080/evidences/post/F-00080_v6_empty_state.png`.

### V7: Path-traversal probe is rejected

1. Navigate to `$IW_BROWSER_BASE_URL/_help/../etc/passwd` (the orchestrator-provided base URL with the literal path appended).
2. **Verify:** HTTP status 404. The page does NOT contain content from `/etc/passwd`. The browser may show a 404 page or a JSON detail; either is acceptable.
3. **Screenshot:** `ai-dev/active/F-00080/evidences/post/F-00080_v7_traversal_404.png`.

### V8: No outbound network calls

1. Open browser dev-tools network panel via the playwright-cli (or capture all requests during the session).
2. **Verify:** during V1..V7, every request was to `$IW_BROWSER_BASE_URL` (same-origin). Specifically: no requests to `unpkg.com`, `cdn.jsdelivr.net`, `googletagmanager.com`, or any analytics/tour-SaaS host.
3. **Screenshot:** `ai-dev/active/F-00080/evidences/post/F-00080_v8_network_same_origin.png`.

### V9: No regressions on adjacent flows

1. Navigate to `/project/<id>/` (the project home, OUT of scope for this feature). NOTE: the project home is mounted at `/project/<id>/`, NOT `/project/<id>/dashboard` — the latter route does not exist and will 404. Use `playwright-cli goto`, not `playwright-cli open`, so the localStorage flag set in V5 is preserved. Verify the page still renders correctly with NO `?` button (out of scope confirms the slug-block mechanism is opt-in).
2. Click an existing primary action on the queue page (e.g. select an item, click a primary CTA). Verify it still works.
3. Verify no new console errors appear on any page visited during V1..V8.
4. **Screenshot:** `ai-dev/active/F-00080/evidences/post/F-00080_v9_no_regressions.png`.

## Pass Criteria

All V1..V9 must pass. Any failure — including a partial or ambiguous result — requires calling `iw step-fail`.

### Distinguishing code defects from environment gaps

- **CODE DEFECT** — the page returned an HTTP error, threw a console exception, rendered the wrong element, the popover did not open, the tour did not mount, the orphan check let through a missing fragment.
- **ENV_DATA_MISSING** — V6 cannot find any empty list. Fix path is to add a fixture file, not to retry. Use `--reason "ENV_DATA_MISSING: V6 needs an empty list view ..."`.

## Report

After verification, write `ai-dev/active/F-00080/reports/F-00080_S18_BrowserVerification_Report.md` with:

- A pass/fail table with one row per V1..V9
- The exact `$IW_BROWSER_BASE_URL` used
- Any issues with `file:line` references
- List of screenshots
- "No regressions observed" subsection

Then call:

```bash
# Pass
uv run iw step-done "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --report ai-dev/active/F-00080/reports/F-00080_S18_BrowserVerification_Report.md

# Fail
uv run iw step-fail "$IW_ITEM_ID" --step "$IW_STEP_ID" \
  --reason "<short, specific reason>" \
  --report ai-dev/active/F-00080/reports/F-00080_S18_BrowserVerification_Report.md
```

## Subagent Result Contract

```json
{
  "step": "S18",
  "agent": "qv-browser",
  "work_item": "F-00080",
  "overall_status": "pass|fail",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V1", "name": "help button visible", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V2", "name": "popover opens with 4 sections", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V3", "name": "ESC closes popover and restores focus", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V4", "name": "tour mounts Driver.js", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V5", "name": "tour seen indicator", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V6", "name": "empty state rendering", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V7", "name": "traversal 404", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V8", "name": "no outbound network", "status": "pass|fail", "screenshot": "...", "notes": ""},
    {"id": "V9", "name": "no regressions", "status": "pass|fail", "screenshot": "...", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
