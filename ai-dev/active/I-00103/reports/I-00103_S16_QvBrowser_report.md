# I-00103 S16 QvBrowser Report

**Step**: S16 (Browser Verification)
**Agent**: qv-browser
**Status**: ✅ PASS

---

## What was done

- Opened the isolated E2E stack at `http://localhost:9926`
- Seeded 3 per-item fixtures into the E2E DB:
  - `001_seed_failed_event_with_per_file_errors.py` — `merge_auto_resolution_failed` event with `per_file_errors` key (already present from prior seed)
  - `001_historical_failed_event_no_per_file_errors.py` — historical `merge_auto_resolution_failed` event WITHOUT `per_file_errors` key (exercises AC4 backward-compat)
  - `002_historical_resolved_event.py` — `merge_auto_resolved` event for regression check
- Navigated to Auto-Merge page via UI
- Verified V1: modal for fixture event shows "Per-file errors" section with file path, runtime, and error substring
- Verified V2: modal for historical event (no `per_file_errors` key) opens cleanly with 200 response, no "Per-file errors" heading
- Verified V3: all filter chips present, resolved event modal correct, project home page loads without errors

## Files changed

- `ai-dev/active/I-00103/e2e_fixtures/001_historical_failed_event_no_per_file_errors.py` — new fixture
- `ai-dev/active/I-00103/e2e_fixtures/002_historical_resolved_event.py` — new fixture
- `ai-dev/active/I-00103/evidences/post/` — 4 screenshots captured

## Test results

All V0–V3: **PASS**  
No console errors observed. No regressions detected.