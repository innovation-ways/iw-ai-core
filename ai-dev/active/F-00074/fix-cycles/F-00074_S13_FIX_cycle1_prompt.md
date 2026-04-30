# F-00074 S13 Browser Verification Fix Cycle 1/3

The end-to-end browser verification for step S13 of work item F-00074 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# F-00074 S13 Browser Verification Report

## Environment
- Base URL used: `http://localhost:9915`
- E2E user: `dev@example.local`

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Page loads + nav entry | **pass** | `evidences/post/F-00074_v1_page_load.png` | HTTP 200, title "Keep-Alive Scheduler", nav link present in System section |
| V2 | Add slot + timeline update | **pass** | `evidences/post/F-00074_v2_slot_added.png` | Slot "15:04" added via API, row appears with Active badge, timeline shows "10:02 + 5h" and "15:04 + 5h" |
| V3 | Toggle slot badge | **pass** | `evidences/post/F-00074_v3_slot_toggled.png` | "15:04" toggled Active→Disabled→Active via htmx PATCH, badge changes without full reload |
| V4 | Runs table visible | **pass** | `evidences/post/F-00074_v4_runs_table.png` | Seeded run row visible: "2026-04-30 10:02:00 / 10:02 / Success" |
| V5 | Config save | **fail** | `evidences/post/F-00074_v5_config_saved.png` | 422 Unprocessable Entity; form sends `window_duration_hours` as display string "4 hours" instead of integer `4` |
| V6 | No regressions | **pass** | `evidences/post/F-00074_v6a_system_status.png`, `v6b_system_coverage.png` | /system/status and /system/coverage render correctly; no console errors |

## Console / Network Errors
- V1–V4, V6: No console errors observed
- V5: `Failed to load resource: the server responded with a status of 422 (Unprocessable Entity) @ http://localhost:9915/api/keep-alive/config`

## Screenshots captured
- `ai-dev/active/F-00074/evidences/post/F-00074_v1_page_load.png`
- `ai-dev/active/F-00074/evidences/post/F-00074_v2_slot_added.png`
- `ai-dev/active/F-00074/evidences/post/F-00074_v3_slot_toggled.png`
- `ai-dev/active/F-00074/evidences/post/F-00074_v4_runs_table.png`
- `ai-dev/active/F-00074/evidences/post/F-00074_v5_config_saved.png`
- `ai-dev/active/F-00074/evidences/post/F-00074_v6a_system_status.png`
- `ai-dev/active/F-00074/evidences/post/F-00074_v6b_system_coverage.png`

## Root Cause (V5 failure)

**CODE DEFECT** — `dashboard/templates/fragments/keep_alive_config.html`

The form's duration `<select>` uses `{{ h }} hours` as both the display text AND the `value` attribute:
```html
<option value="{{ h }}">{{ h }} hours</option>
```

When htmx submits via `json-enc`, it sends `"window_duration_hours": "4 hours"` (a string),
but `ConfigPayload.window_duration_hours` is typed as `int` and Pydantic validates it as `4`.
Pydantic rejects `"4 hours"` → 422.

The model `select` also sends the full display name `"claude-sonnet-4-6"` which happens to
match the API enum, but the duration field is broken for all non-default values.

**Fix**: In `keep_alive_config.html`, change the duration option `value` to be just `{{ h }}`:
```html
<option value="{{ h }}">{{ h }} hours</option>
```
(The value and display text will now be `4` and `4 hours` respectively.)

## Subagent Result Contract

```json
{
  "step": "S13",
  "agent": "qv-browser",
  "work_item": "F-00074",
  "overall_status": "fail",
  "base_url_used": "http://localhost:9915",
  "verifications": [
    {"id": "V1", "name": "Page loads + nav entry", "status": "pass", "screenshot": "evidences/post/F-00074_v1_page_load.png", "notes": ""},
    {"id": "V2", "name": "Add slot + timeline update", "status": "pass", "screenshot": "evidences/post/F-00074_v2_slot_added.png", "notes": ""},
    {"id": "V3", "name": "Toggle slot badge", "status": "pass", "screenshot": "evidences/post/F-00074_v3_slot_toggled.png", "notes": ""},
    {"id": "V4", "name": "Runs table visible", "status": "pass", "screenshot": "evidences/post/F-00074_v4_runs_table.png", "notes": ""},
    {"id": "V5", "name": "Config save", "status": "fail", "screenshot": "evidences/post/F-00074_v5_config_saved.png", "notes": "422 - form sends window_duration_hours as '4 hours' string instead of integer 4"},
    {"id": "V6", "name": "No regressions", "status": "pass", "screenshot": "evidences/post/F-00074_v6a_system_status.png, v6b_system_coverage.png", "notes": ""}
  ],
  "console_errors_observed": [
    "422 Unprocessable Entity on POST /api/keep-alive/config (V5 attempt)"
  ],
  "screenshots": [
    "ai-dev/active/F-00074/evidences/post/F-00074_v1_page_load.png",
    "ai-dev/active/F-00074/evidences/post/F-00074_v2_slot_added.png",
    "ai-dev/active/F-00074/evidences/post/F-00074_v3_slot_toggled.png",
    "ai-dev/active/F-00074/evidences/post/F-00074_v4_runs_table.png",
    "ai-dev/active/F-00074/evidences/post/F-00074_v5_config_saved.png",
    "ai-dev/active/F-00074/evidences/post/F-00074_v6a_system_status.png",
    "ai-dev/active/F-00074/evidences/post/F-00074_v6b_system_coverage.png"
  ],
  "notes": "V5 fails due to form value mismatch: duration select sends display string '4 hours' instead of integer '4'. All other verifications pass."
}
```


## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/F-00074/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00074/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
