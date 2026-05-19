# Browser Verification Prompt: I-00093-S12-BrowserVerification

**Work Item**: I-00093 — Auto-merge event detail modal hides the most useful fields
**Step**: S12
**Agent**: qv-browser

---

## ⛔ Docker is off-limits

Standard policy. No docker commands.

## ⛔ Migrations: agents generate, daemon applies

No alembic.

## Environment

Isolated E2E stack already up.

- `$IW_BROWSER_BASE_URL`
- `$IW_BROWSER_E2E_USER` / `$IW_BROWSER_E2E_PASSWORD`
- `$IW_ITEM_ID` / `$IW_STEP_ID`

Do NOT hardcode ports or run `make dev`/`docker compose …`/
`playwright install`/`agent-browser`/direct `chromium.launch()`.

## Input Files

- `ai-dev/active/I-00093/I-00093_Issue_Design.md`
- `dashboard/templates/fragments/auto_merge_event_detail.html`

## Output Files

- `ai-dev/active/I-00093/reports/I-00093_S12_BrowserVerification_Report.md`
- `ai-dev/active/I-00093/evidences/post/`

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Log in if needed.

## E2E DB seed data

Auto-merge daemon emits `auto_merge_health_probe` events every ~5 min
in the seeded stack, so at least one such event is reliably present.
`auto_merge_config_updated` events appear after any settings change
(if none exist in the seed, POST one via curl to create one — see V2).
`merge_auto_resolved` events are NOT guaranteed to exist in the seed;
if V3 needs one, add a fixture file:

```
ai-dev/active/I-00093/e2e_fixtures/001_resolved_event.py
```

## Verification Steps

### V0: Pre-flight page sanity (built-in)

Standard auto-prepended check.

### V1: Health probe modal shows message and metadata

1. Navigate via UI to `$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge`.
2. In the events table, click the `health_probe` filter chip (or scroll
   to find an `auto_merge_health_probe` row).
3. Click `(view)` on a health probe row.
4. **Verify**:
   - Modal opens.
   - Heading contains `auto_merge_health_probe` AND a timestamp string
     (not bare `Event #<id>`).
   - Modal body contains a `Message` section with text (or omits the
     section if message is null — verify with another event if needed).
   - Modal body contains a `Metadata` section with at least
     `runtime_reachable` visible as a JSON key.
5. **Screenshot:** `ai-dev/active/I-00093/evidences/post/I-00093_v1_health_probe.png`.

### V2: Config_updated modal shows old + new

1. Trigger a config_updated event:

   ```bash
   curl -s -X POST "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge/config" \
     -H "Content-Type: application/json" -H "Accept: application/json" \
     -d '{"phase": 1, "runtime_option_id": null}'
   curl -s -X POST "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge/config" \
     -H "Content-Type: application/json" -H "Accept: application/json" \
     -d '{"phase": null, "runtime_option_id": null}'
   ```

2. Reload the auto-merge page, filter to `config_updated`.
3. Click `(view)` on the latest config_updated row.
4. **Verify**:
   - Modal body shows JSON containing `old`, `new`, `updated_by`,
     `source` keys.
   - The `Copy as JSON` button is present.
5. **Screenshot:** `ai-dev/active/I-00093/evidences/post/I-00093_v2_config_updated.png`.

### V3: Resolved modal — verdict block + diff section preserved

If the seed has a `merge_auto_resolved` event, click `(view)` on it.
If not, prefix `--reason "ENV_DATA_MISSING: ..."` and add a fixture
file (see "E2E DB seed data" above).

1. Click `(view)`.
2. **Verify**:
   - Verdict block renders if a verdict exists.
   - The existing diffs section (one `<details>` per file) still
     renders.
   - The existing verdict-update form still renders below.
   - The new Message and Metadata sections also render.
3. **Screenshot:** `ai-dev/active/I-00093/evidences/post/I-00093_v3_resolved.png`.

### V4: Non-resolved modal — no verdict form

1. Click `(view)` on a `step_launched` row.
2. **Verify**:
   - Message and Metadata render.
   - NO verdict form appears (no `<input name="verdict">` element in the modal).
3. **Screenshot:** `ai-dev/active/I-00093/evidences/post/I-00093_v4_non_resolved.png`.

### V5: Copy as JSON

1. From V1's open modal, click `Copy as JSON`.
2. **Verify** the button feedback updates (the shared `iwClipboard.copy`
   helper sets the button text to `Copied` on success or `Copy failed`
   on failure). Snapshot the change.
3. **Screenshot:** `ai-dev/active/I-00093/evidences/post/I-00093_v5_copy.png`.

### V6: No regressions

1. Close all modals via Escape and ✕.
2. Verify the events table still renders behind the modal close and no
   console errors appeared.
3. Verify navigation to `/queue` and back to `/auto-merge` works.
4. **Screenshot:** `ai-dev/active/I-00093/evidences/post/I-00093_v6_no_regressions.png`.

## Pass Criteria

All V1..V6 must pass. ENV_DATA_MISSING for V3 (no resolved events in
seed) is acceptable with the appropriate fixture file added per the
"E2E DB seed data" section above.

## Report

Write `ai-dev/active/I-00093/reports/I-00093_S12_BrowserVerification_Report.md`
with the full V1..V6 table, base URL, screenshots, and no-regressions
section. Then call `iw step-done` or `iw step-fail` with `--report`.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "qv-browser",
  "work_item": "I-00093",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "Health probe modal — message+metadata", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "Config_updated modal — old+new", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "Resolved modal — verdict+diffs preserved", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "Non-resolved modal — no verdict form", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "Copy as JSON", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V6", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
