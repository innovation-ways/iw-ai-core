# I-00034 S11 Browser Verification Report

## Step: S11 — Browser Verification (qv-browser)
## Work Item: I-00034 — "Item view step Duration is incorrect when a step goes through retries or fix cycles"

---

## Environment

| Variable | Value |
|----------|-------|
| `IW_BROWSER_BASE_URL` | `http://localhost:9953` |
| `IW_BROWSER_E2E_USER` | `dev@example.local` |
| `IW_ITEM_ID` | `I-00034` |
| `IW_STEP_ID` | `S11` |
| Default E2E Project | `iw-ai-core` |

---

## Verifications

| ID | Name | Status | Notes |
|----|------|--------|-------|
| V1 | Retry-prone step aggregated duration | **PASS** | Duration: `10m30s`, Started: `12:00:00`, Total Time: `10m30s` |
| V2 | Happy-path unchanged | **PASS** | Duration: `0m45s`, Started: `14:00:00`, Total Time: `0m45s` |
| V3 | No regressions (project home, batches, running) | **PASS** | All pages render without errors |

---

## V1 Detail — Retry-prone Step Duration

**Item:** `I-00034-RETRY-DEMO`
**URL:** `http://localhost:9953/project/iw-ai-core/item/I-00034-RETRY-DEMO`

**Expected:**
- Duration: `10m30s` (full span from 12:00:00 to 12:10:30)
- Started: `12:00:00` (aggregated earliest, not last-iteration start)
- Total Time card: `10m30s`

**Observed:**
- S01 Duration cell: `10m30s` ✅
- S01 Started column: `12:00:00` ✅
- Total Time card: `10m30s` ✅
- Fix Cycles badge: `1` ✅
- Runs: `2` with `1↻` indicator ✅

**Seed data summary:**
| Row type | started_at | completed_at | Notes |
|----------|-----------|--------------|-------|
| StepRun #1 (failed) | 12:00:00 | 12:02:00 | First attempt |
| FixCycle #1 (completed) | 12:03:00 | 12:09:00 | Fix agent ran |
| StepRun #2 (completed) | 12:10:00 | 12:10:30 | Final success |
| **Aggregated span** | **12:00:00** | **12:10:30** | **10m30s** |

Screenshots:
- `ai-dev/active/I-00034/evidences/post/I-00034_v1_retry_demo_duration.png`

---

## V2 Detail — Happy-path Unchanged (No Regression)

**Item:** `I-00034-HAPPY-DEMO`
**URL:** `http://localhost:9953/project/iw-ai-core/item/I-00034-HAPPY-DEMO`

**Expected:**
- Duration: `0m45s` (single run, 45 seconds)
- Started: `14:00:00`
- Total Time: `0m45s` (within 0m45s to 2m expected range)

**Observed:**
- S01 Duration cell: `0m45s` ✅
- S01 Started column: `14:00:00` ✅
- Total Time card: `0m45s` ✅
- Fix Cycles badge: `0` ✅
- Runs: `1` ✅

**Seed data summary:**
| Row type | started_at | completed_at | Notes |
|----------|-----------|--------------|-------|
| StepRun #1 (completed) | 14:00:00 | 14:00:45 | Single run, no retries |

Screenshots:
- `ai-dev/active/I-00034/evidences/post/I-00034_v2_happy_path_unchanged.png`

---

## V3 Detail — No Regressions

### Adjacent flows tested

| Page | URL | Status | Notes |
|------|-----|--------|-------|
| Project home | `http://localhost:9953/project/iw-ai-core/` | ✅ Rendered | Shows active batches, recent activity |
| Batches | `http://localhost:9953/project/iw-ai-core/batches` | ✅ Rendered | Batch list with status filters |
| Running Tasks | `http://localhost:9953/system/running` | ✅ Rendered | System-wide running view |

### Console errors

Errors observed: **2 (pre-existing, unrelated to I-00034 fix)**

```
[WARNING] cdn.tailwindcss.com should not be used in production
[ReferenceError] module is not defined at http://localhost:9953/static/vendor/highlight.js/core.js:2595:1
```

These are pre-existing JS errors in the highlight.js vendor bundle and the Tailwind CDN warning — unrelated to the duration aggregation fix. The fix only changes the Python router's SQL aggregation; no client-side JS was modified.

Screenshots:
- No separate screenshot for V3 (pages rendered cleanly without new errors)

---

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "I-00034",
  "overall_status": "pass",
  "base_url_used": "http://localhost:9953",
  "verifications": [
    {
      "id": "V1",
      "name": "Retry-prone step aggregated duration",
      "status": "pass",
      "screenshot": "ai-dev/active/I-00034/evidences/post/I-00034_v1_retry_demo_duration.png",
      "notes": "Duration: 10m30s (aggregated from step_runs+fix_cycles span 12:00:00→12:10:30). Started: 12:00:00 (earliest). Total Time: 10m30s. All expected."
    },
    {
      "id": "V2",
      "name": "Happy-path unchanged",
      "status": "pass",
      "screenshot": "ai-dev/active/I-00034/evidences/post/I-00034_v2_happy_path_unchanged.png",
      "notes": "Duration: 0m45s (single run, unchanged from pre-fix). Started: 14:00:00. Total Time: 0m45s. No regression."
    },
    {
      "id": "V3",
      "name": "No regressions",
      "status": "pass",
      "screenshot": null,
      "notes": "Project home, batches, and running tasks pages all render cleanly. Pre-existing highlight.js and Tailwind CDN console errors are unrelated to I-00034 fix. No new errors introduced by the duration aggregation change."
    }
  ],
  "console_errors_observed": [
    "cdn.tailwindcss.com should not be used in production (WARNING — pre-existing)",
    "ReferenceError: module is not defined at highlight.js/core.js (pre-existing, unrelated)"
  ],
  "screenshots": [
    "ai-dev/active/I-00034/evidences/post/I-00034_v1_retry_demo_duration.png",
    "ai-dev/active/I-00034/evidences/post/I-00034_v2_happy_path_unchanged.png"
  ],
  "notes": "All three verifications passed. V1 confirms the core fix: retry-prone step shows 10m30s (aggregated from 3 rows across step_runs+fix_cycles) instead of 30s. V2 confirms no regression on happy-path. V3 confirms adjacent flows are unaffected. Pre-existing JS errors are unrelated to this fix."
}
```

---

## Conclusion

**All verifications PASSED.** The I-00034 duration aggregation fix is working correctly on the E2E stack:

- **V1 (core fix):** A step with 2 `step_runs` + 1 `fix_cycle` correctly shows `10m30s` (12:00:00→12:10:30) instead of the pre-fix value of `30s`.
- **V2 (no regression):** A step with a single run shows `0m45s` — identical to what it would have shown before the fix.
- **V3 (adjacent flows):** Project home, batches, and running tasks pages all render without new errors.

The fix in `dashboard/routers/items.py` (`_aggregate_step_spans` bulk query + use of `step_spans` in `_get_steps`) correctly surfaces the full wall-clock span from `step_runs` ∪ `fix_cycles` without modifying any daemon behavior or schema.