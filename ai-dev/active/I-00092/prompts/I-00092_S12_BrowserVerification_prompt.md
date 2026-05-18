# Browser Verification Prompt: I-00092-S12-BrowserVerification

**Work Item**: I-00092 — Auto-merge filter chip never highlights the active filter
**Step**: S12
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Standard policy. No docker commands. `docker compose exec app <cmd>`
is the only exception and not needed here.

## ⛔ Migrations: agents generate, daemon applies

No alembic commands.

## Environment

Isolated E2E stack is already up. Use these env vars:

- `$IW_BROWSER_BASE_URL`
- `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
- `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports or run `make dev` / `make e2e-up` /
`docker compose …` / `playwright install` / `agent-browser` / direct
`chromium.launch()`.

## Input Files

- `ai-dev/active/I-00092/I-00092_Issue_Design.md`
- `dashboard/templates/fragments/auto_merge_events_table.html`

## Output Files

- `ai-dev/active/I-00092/reports/I-00092_S12_BrowserVerification_Report.md`
- `ai-dev/active/I-00092/evidences/post/` — screenshots

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Log in if needed (snapshot → fill → click).

## E2E DB seed data

Auto-merge events come from production-seeded data. No fixture needed.

## Verification Steps

### V0: Pre-flight page sanity (built-in, do NOT modify)

Standard auto-prepended check (fragment ID consistency + console
error scan).

### V1: Default (no filter) → "all" chip is highlighted

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge`
   via the project nav.
2. Wait for the events table fragment to load (the `Loading events…`
   placeholder disappears).
3. `playwright-cli snapshot`.
4. **Verify** the snapshot shows the `all` chip with a visually
   distinct active style (the snapshot text may not include the class,
   but the screenshot will).
5. **Screenshot:** `ai-dev/active/I-00092/evidences/post/I-00092_v1_all_active.png`.

### V2: Click "resolved" → only the "resolved" chip is highlighted

1. From V1, click the `resolved` chip.
2. Wait for the swap, snapshot.
3. **Verify** via the rendered DOM: `resolved` is now visually active
   and `all` is not. (Inspecting `class` strings on each chip via the
   snapshot is fine; alternatively `curl "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge/events?type=merge_auto_resolved" | grep -oE 'class="[^"]*bg-primary[^"]*"' | wc -l` should equal 1.)
4. **Screenshot:** `ai-dev/active/I-00092/evidences/post/I-00092_v2_resolved_active.png`.

### V3: Click "all" → returns to all-events view, "all" chip active again

1. Click the `all` chip.
2. Verify the events table re-renders without a `type` filter (table
   should now contain mixed event types).
3. Verify `all` chip is active; `resolved` is not.
4. **Screenshot:** `ai-dev/active/I-00092/evidences/post/I-00092_v3_back_to_all.png`.

### V4: Hover tooltip shows the underlying event_type

1. Hover the `resolved` chip with `playwright-cli hover <ref>` (or
   inspect the rendered HTML for `title="merge_auto_resolved"`).
2. **Verify** the `title` attribute is present on the chip. The
   snapshot will include it under `[title="…"]` annotation; if it
   doesn't, fall back to `curl` and grep the `<a>` for the chip.
3. **Screenshot:** `ai-dev/active/I-00092/evidences/post/I-00092_v4_tooltip.png`.

### V5: No regressions

1. The events table itself still renders rows when no filter is
   applied; pagination still works (click Next / Prev if more than one
   page).
2. The verdict rollup card and token cost rollup card still render
   correctly.
3. Visit `/project/iw-ai-core/queue` to confirm no console errors
   propagated.
4. **Screenshot:** `ai-dev/active/I-00092/evidences/post/I-00092_v5_no_regressions.png`.

## Pass Criteria

All V1..V5 pass. Any failure requires `iw step-fail` with a reason
classified as:

- **CODE_DEFECT** — chip not highlighting, wrong chip highlighted, etc.
- **ENV_DATA_MISSING** — no auto-merge events in the seed (unlikely but
  possible on a fresh worktree). Prefix `--reason "ENV_DATA_MISSING:
  …"` and consider adding a fixture file.
- **SPEC_MISMATCH** — design doc disagrees with the V step.

## Report

Write `ai-dev/active/I-00092/reports/I-00092_S12_BrowserVerification_Report.md`
with pass/fail table, base URL, screenshots, and "no regressions
observed" section. Then call `iw step-done` or `iw step-fail` with
`--report`.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "qv-browser",
  "work_item": "I-00092",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Default 'all' chip active", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Click 'resolved' activates only that chip", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Click 'all' returns to default view", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Tooltip shows event_type", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
