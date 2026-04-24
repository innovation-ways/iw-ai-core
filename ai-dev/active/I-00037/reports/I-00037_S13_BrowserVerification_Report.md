# I-00037 S13 Browser Verification Report

## Verification Results

| ID | Name | Status | Notes |
|----|------|--------|-------|
| V1 | Dashboard home shows 30% step-based progress | **PASS** | Active Batches card shows "30% complete" for BATCH-TEST37 |
| V2 | Batches view shows 30% step-based progress | **PASS** | Progress column shows "30%" for BATCH-TEST37 |
| V3 | Parity — both views agree on same batch | **PASS** | V1=30%, V2=30% — identical, within ±1% tolerance |
| V4 | No regressions (detail / queue / history / console) | **PASS** | Batch detail, queue, history all render without errors |

## Base URL Tested

```
http://localhost:9947
```

## Environment

- E2E credentials: `dev@example.local` / `***` (12 chars)
- Project: `iw-ai-core`
- Fixture: `ai-dev/active/I-00037/e2e_fixtures/001_partial_progress_batch.py`
- Seeded batch: `BATCH-TEST37` (executing, 3/10 steps completed → 30%)
- Seeded work item: `I-TEST-37` (10 steps: S01–S03 completed, S04–S10 pending)

## V1 — Dashboard Home (30%)

**URL:** `http://localhost:9947/project/iw-ai-core/`

**Snapshot excerpt:**
- Line 74: `link "BATCH-TEST37"` → `/project/iw-ai-core/batch/BATCH-TEST37`
- Line 68: `generic [ref=e68]: executing`
- Line 69: `generic [ref=e69]: 0/1 items`
- **Line 82: `paragraph [ref=e75]: 30% complete`** ✓

The Active Batches card shows "30% complete" for BATCH-TEST37 — matching the step-based calculation (3 completed / 10 total = 30%). This is **not** the pre-fix 0% value driven by item-level counts.

**Screenshot:** `evidences/post/I-00037_v1_home_30pct.png`

## V2 — Batches View (30%)

**URL:** `http://localhost:9947/project/iw-ai-core/batches`

**Snapshot excerpt:**
- Row 122: `row "BATCH-TEST37 executing 0/1 30% Apr 24 21:42 —" [ref=e105]`
- Cell 127: `cell "30%" [ref=e110]` → `generic [ref=e114]: 30%`
- Items column: `cell "0/1" [ref=e109]`

**Screenshot:** `evidences/post/I-00037_v2_batches_30pct.png`

## V3 — Parity Check

| View | Page | BATCH-TEST37 Progress |
|------|------|-----------------------|
| V1 | Dashboard home (`/project/iw-ai-core/`) | **30%** |
| V2 | Batches view (`/project/iw-ai-core/batches`) | **30%** |

**Difference:** 0% — identical within ±1% tolerance.

This confirms the fix eliminated the drift. Pre-fix, the home page showed **0%** (item-level: no BatchItems completed) while the batches view showed **94%** (step-based). Post-fix, both show **30%** for the same seeded batch. The inconsistency is gone.

## V4 — No Regressions

### Batch Detail Page

**URL:** `http://localhost:9947/project/iw-ai-core/batch/BATCH-TEST37`

- Page rendered with HTTP 200 ✓
- Batch header: "BATCH-TEST37", "executing", "1 item" ✓
- Items table shows I-TEST-37 with step indicators ✓
- No template errors, no 500 ✓

**Screenshot:** `evidences/post/I-00037_v4_no_regressions.png`

### Queue Page

**URL:** `http://localhost:9947/project/iw-ai-core/queue`

- Page rendered with HTTP 200 ✓
- No errors ✓

### History Page

**URL:** `http://localhost:9947/project/iw-ai-core/history`

- Page rendered with HTTP 200 ✓
- No errors ✓

### Console Errors

No JS console errors observed on any visited page.

## Screenshots Captured

```
ai-dev/active/I-00037/evidences/post/I-00037_v1_home_30pct.png       — Dashboard home, 30%
ai-dev/active/I-00037/evidences/post/I-00037_v2_batches_30pct.png   — Batches view, 30%
ai-dev/active/I-00037/evidences/post/I-00037_v4_no_regressions.png   — Batch detail page
```

## Comparison Against Pre-fix Evidence

| Evidence | Page | Pre-fix Value | Post-fix Value |
|----------|------|---------------|----------------|
| `evidences/pre/I-00037-dashboard-home-shows-0pct.png` | Dashboard home | 0% (item-level bug) | 30% (step-based, correct) |
| `evidences/pre/I-00037-batches-view-shows-correct-pct.png` | Batches view | 94% (step-based, correct) | 30% (step-based, same formula) |

**Pre-fix divergence:** Dashboard home showed 0% while Batches view showed 94% for the same batch (different formula sources).

**Post-fix parity:** Both pages show 30% for the seeded test batch. The values are identical (V1 = V2 = 30%), confirming the fix consolidated to a single source of truth (`dashboard/utils/batch_progress.py`).

Note: The pre-fix evidence used live batches (BATCH-00044 at 94%, BATCH-00043 at 42%) because the E2E fixture did not yet exist. The post-fix verification uses the seeded `BATCH-TEST37` which is structurally equivalent (partial step completion, zero items completed).

## Overall Status

**PASS** — All verifications V1–V4 passed. The bug is fixed, parity is confirmed, and no regressions observed.