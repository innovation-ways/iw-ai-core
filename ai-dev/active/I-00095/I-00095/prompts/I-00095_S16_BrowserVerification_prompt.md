# Browser Verification Prompt: I-00095-S16-BrowserVerification

**Work Item**: I-00095 — Auto-merge events table columns are not sortable
**Step**: S16
**Agent**: qv-browser

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Environment

Isolated E2E stack already up.

- `$IW_BROWSER_BASE_URL`
- `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
- `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports or run `make dev` / `docker compose …` /
`playwright install` / `agent-browser` / direct `chromium.launch()`.

## Input Files

- `ai-dev/active/I-00095/I-00095_Issue_Design.md`
- `dashboard/templates/fragments/auto_merge_events_table.html`
- `dashboard/routers/auto_merge_ui.py`
- `orch/auto_merge_aggregator.py`

## Output Files

- `ai-dev/active/I-00095/reports/I-00095_S16_BrowserVerification_Report.md`
- `ai-dev/active/I-00095/evidences/post/`

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Log in if needed.

## Verification Steps

### V0: Pre-flight page sanity (built-in, do NOT modify)

Standard auto-prepended check.

### V1: Sortable headers appear as buttons

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge`.
2. `playwright-cli snapshot`.
3. **Verify** in the snapshot: `timestamp`, `event_type`,
   `entity_id`, and `verdict` headers appear as `button` refs.
   `message` and `actions` remain plain cell text.
4. **Screenshot:** `ai-dev/active/I-00095/evidences/post/I-00095_v1_headers.png`.

### V2: Clicking timestamp sorts by created_at

1. Click the `timestamp` header button.
2. **Verify** the URL fragment in the htmx request is
   `…?sort=created_at&dir=…` (use page snapshot or DOM inspection of
   the htmx-triggered request). The displayed events should now be in
   the toggled direction.
3. Click again to toggle direction (descending → ascending or vice
   versa).
4. **Screenshot:** `ai-dev/active/I-00095/evidences/post/I-00095_v2_timestamp_sort.png`.

### V3: Chevron + aria-sort on active column

1. Click `event_type` header.
2. **Verify** via curl on the same URL:

   ```bash
   curl -s "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge/events?page=0&page_size=50&sort=event_type&dir=desc" | grep -E 'aria-sort|↓|↑'
   ```

   - Exactly one `aria-sort=` occurrence, on the `event_type` `<th>`.
   - A `↓` or `↑` glyph next to "event_type".
3. **Screenshot:** `ai-dev/active/I-00095/evidences/post/I-00095_v3_chevron.png`.

### V4: Switching column resets to descending

1. With `event_type asc` active, click `entity_id`.
2. **Verify** the URL becomes `…?sort=entity_id&dir=desc` (NOT asc).
3. **Screenshot:** `ai-dev/active/I-00095/evidences/post/I-00095_v4_switch_col.png`.

### V5: Filter + sort compose

1. Click the `health_probe` filter chip (from I-00092 or pre-fix
   behaviour), then click `timestamp` to sort asc.
2. **Verify** the rendered table has only `auto_merge_health_probe`
   rows AND is sorted oldest-first.
3. **Verify** Next/Prev pagination link URLs (via curl on
   `?type=auto_merge_health_probe&sort=created_at&dir=asc&page=0`)
   contain all three params.
4. **Screenshot:** `ai-dev/active/I-00095/evidences/post/I-00095_v5_compose.png`.

### V6: Invalid sort returns 400

1. `curl -s -o /dev/null -w "%{http_code}\n" "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge/events?sort=message&page=0&page_size=10"`
2. **Verify** the HTTP code is `400`.
3. **Screenshot:** `ai-dev/active/I-00095/evidences/post/I-00095_v6_400.png`
   (capture the response body in the report).

### V7: No regressions

1. Adjacent flows: filter chip clicks still re-render; the verdict
   buttons in row 1 still work; the modal still opens on `(view)`.
2. No console errors on any page visited.
3. **Screenshot:** `ai-dev/active/I-00095/evidences/post/I-00095_v7_no_regressions.png`.

## Pass Criteria

All V1..V7 pass.

- CODE_DEFECT: chevron missing on active column; URL doesn't include
  expected params; invalid sort doesn't 400.
- ENV_DATA_MISSING: not enough events of multiple types to demonstrate
  sort visually. If so, prefix `--reason "ENV_DATA_MISSING: …"`.

## Report

Write
`ai-dev/active/I-00095/reports/I-00095_S16_BrowserVerification_Report.md`
with pass/fail table, base URL, screenshots, and "no regressions
observed" section. Then `iw step-done` / `iw step-fail` with `--report`.

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "I-00095",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Sortable headers are buttons", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Timestamp sort toggles", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Chevron + aria-sort on active column", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Switching column resets to desc", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Filter + sort + pagination compose", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V6", "name": "Invalid sort returns 400", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V7", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
