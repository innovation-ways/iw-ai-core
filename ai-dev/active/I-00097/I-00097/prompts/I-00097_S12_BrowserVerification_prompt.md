# Browser Verification Prompt: I-00097-S12-BrowserVerification

**Work Item**: I-00097 — Auto-merge polish — token cost formatting & entity_id linkification
**Step**: S12
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

- `ai-dev/active/I-00097/I-00097_Issue_Design.md`
- The two modified fragment templates

## Output Files

- `ai-dev/active/I-00097/reports/I-00097_S12_BrowserVerification_Report.md`
- `ai-dev/active/I-00097/evidences/post/`

## Prerequisites

```bash
playwright-cli kill-all
playwright-cli open "$IW_BROWSER_BASE_URL"
```

Log in if needed.

## Verification Steps

### V0: Pre-flight page sanity (built-in)

Standard auto-prepended check.

### V1: Token cost zero renders as $0

1. Navigate to `$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge`.
2. Wait for the rollup card to load.
3. **Verify** via curl:

   ```bash
   curl -s "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge/rollup?window=7d" | grep -oE '\$[0-9.]+' | head -3
   ```

   Expect `$0` (not `$0.000000`) when the project has no token usage
   in the window.
4. **Screenshot:** `ai-dev/active/I-00097/evidences/post/I-00097_v1_zero_cost.png`.

### V2: entity_id link for work-item IDs

1. Find an event row whose entity_id matches `^(F|I|CR)-\d{5}$`. The
   seeded events almost certainly include some — e.g., `CR-00057` /
   `CR-00060` from recent batches.
2. Hover the entity_id cell — the cursor should be a hand pointer
   (real `<a href>` link).
3. Click the entity_id link.
4. **Verify** navigation to `$IW_BROWSER_BASE_URL/project/iw-ai-core/item/<entity_id>`
   (singular `item` — matches the FastAPI route in
   `dashboard/routers/items.py:1124`). The page should render the
   item detail.
5. **Screenshot:** `ai-dev/active/I-00097/evidences/post/I-00097_v2_link_click.png`.

If V2 cannot find a work-item entity_id in the seeded events, prefix
`--reason "ENV_DATA_MISSING: ..."` and document. If I-00096 has
landed and the default view filters out the relevant event types,
use `?all=1` or a `step_launched`-filter URL to find one.

### V3: entity_id plain text for non-work-item values

1. Navigate to `/auto-merge` (or filter to `config_updated` to surface
   a config-updated event whose entity_id is a project_id).
2. **Verify** via curl that "iw-ai-core" appears in the table but
   NOT inside an `<a href="/project/.../item/iw-ai-core">`:

   ```bash
   curl -s "$IW_BROWSER_BASE_URL/project/iw-ai-core/auto-merge/events?type=auto_merge_config_updated&page=0&page_size=10" \
     | grep -E 'href="/project/[^"]+/item/iw-ai-core"' \
     | wc -l
   # Must print 0
   ```

3. **Screenshot:** `ai-dev/active/I-00097/evidences/post/I-00097_v3_plain_text.png`.

### V4: entity_id dash for null

1. Filter to `health_probe` events (whose entity_id is null).
2. **Verify** the entity_id cells render `—`, not an empty link.
3. **Screenshot:** `ai-dev/active/I-00097/evidences/post/I-00097_v4_dash_null.png`.

### V5: No regressions

1. Other fragments still render correctly.
2. No console errors.
3. **Screenshot:** `ai-dev/active/I-00097/evidences/post/I-00097_v5_no_regressions.png`.

## Pass Criteria

All V1..V5 pass.

- CODE_DEFECT: `$0.000000` still rendering; entity_id not linkified or
  linkified for non-work-item values.
- ENV_DATA_MISSING: no work-item-ID entity_id in seed for V2 — use a
  fixture file.

## Report

Write
`ai-dev/active/I-00097/reports/I-00097_S12_BrowserVerification_Report.md`
with pass/fail table, base URL, screenshots, and "no regressions
observed" section. Call `iw step-done` / `iw step-fail` with `--report`.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "qv-browser",
  "work_item": "I-00097",
  "overall_status": "pass|fail",
  "overall_failure_class": "code_defect|env_data_missing|spec_mismatch|null",
  "base_url_used": "$IW_BROWSER_BASE_URL",
  "verifications": [
    {"id": "V0", "name": "Pre-flight page sanity", "status": "pass|fail", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V1", "name": "$0 zero formatting", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V2", "name": "entity_id link for work-item ID", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V3", "name": "entity_id plain text for non-work-item", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V4", "name": "entity_id dash for null", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""},
    {"id": "V5", "name": "No regressions", "status": "pass|fail|n/a", "failure_class": null, "screenshot": "", "notes": ""}
  ],
  "console_errors_observed": [],
  "screenshots": [],
  "notes": ""
}
```
