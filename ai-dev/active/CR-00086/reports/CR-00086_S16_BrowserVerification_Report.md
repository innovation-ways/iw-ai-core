# CR-00086 S16 Browser Verification Report

**Work Item**: CR-00086 — Self-dashboarding of test health
**Step**: S16 (qv-browser)
**Verified**: 2026-05-28
**Base URL**: http://localhost:9919
**E2E Stack**: `iw-ai-core-e2e-cr00086` (isolated per-worktree compose)

---

## Verification Results

| ID | Name | Status | Failure Class | Screenshot |
|----|------|--------|---------------|------------|
| V0 | Pre-flight page sanity | **PASS** | — | — |
| V1 | Test Health panel on Tests page | **PASS** | — | `evidences/post/CR-00086_v1_tests_panel.png` |
| V2 | Test Health panel on Quality page | **PASS** | — | `evidences/post/CR-00086_v2_quality_panel.png` |
| V3 | Empty-state placeholder (innoforge) | **PASS** | — | `evidences/post/CR-00086_v3_empty_state.png` |
| V4 | Capture appears in Jobs view | **PASS** | — | `evidences/post/CR-00086_v4_jobs_view.png` |
| V5 | No regressions | **PASS** | — | `evidences/post/CR-00086_v5_no_regressions.png` |

---

## Detail

### V0: Pre-flight page sanity
- Visited `/project/iw-ai-core/tests` and `/project/iw-ai-core/quality` via htmx navigation
- No unhandled exception pages; no 5xx errors
- All fragment endpoints (`/project/iw-ai-core/test-health`, launch/runs/results fragments) returned HTTP 200
- Console logs: none

### V1: Test Health panel on Tests page ✅
- Navigated: Projects → IW AI Core (E2E) → Tests
- Panel loaded via htmx (`hx-get="/project/iw-ai-core/test-health"`)
- **Four metric cards visible**: Mutation Score (85.4%), Coverage (79.0%), Flaky Tests (1), Assertion Baseline (558)
- Each card shows numeric value + delta (up/down/dash arrow + number)
- Each card shows an inline `<svg>` (sparkline) with `path d="M..."` data
- Tab navigation (Launch / Runs / Results) and test category cards still render below the panel
- No console errors

### V2: Test Health panel on Quality page ✅
- Navigated: IW AI Core → Quality
- Panel identical to V1 (same four metric cards, same sparklines, same data values)
- Quality gate cards render below the panel (Lint / Auto-fix)
- No console errors

### V3: Empty-state placeholder (innoforge, no snapshots) ✅
- Navigated: Projects → Innoforge (E2E) → Tests
- Panel shows: `"Test health data will appear after the first capture runs"` (combined empty state, per AC5)
- No `<svg>` with empty path; no `NaN` text; no crash
- InnoForge project has `test_config.categories` configured but **zero** `TestHealthSnapshot` rows — correct empty-state behaviour

### V4: Capture appears in Jobs view ✅
- Ran `docker compose -p iw-ai-core-e2e-cr00086 exec e2e-dashboard uv run iw test-health-capture --project iw-ai-core` (inside container, allowed per env exception)
- Command exited 0; captured 2 metrics (coverage_pct, assertion_baseline_size); mutation/flaky skipped (source artefacts absent in E2E stack — expected)
- Navigated to `/project/iw-ai-core/jobs`
- Row visible at top: ID=`thc-iw-ai-core-20260528T1341`, Type=`test-health-capture`, Status=`completed`, Duration=`1m00s`
- 33 total items in table; historical fixture rows (one per hour, 13:00–01:00) also visible from the fixture seed
- Row timestamp (May 28 13:42) matches the capture just triggered

### V5: No regressions ✅
- Tests page: test category cards (Unit Tests, Integration Tests) still render below the panel
- Quality page: quality gate cards (Lint/Ruff) still render
- Queue page: 2 approved items visible, table renders correctly — unrelated page unaffected
- No console errors on any page visited during V1–V4

---

## Console Errors Observed

None. No JavaScript errors, no HTMX errors, no 5xx responses.

---

## Screenshot Inventory

| Filename | Description |
|----------|-------------|
| `CR-00086_v1_tests_panel.png` | V1: Tests page with 4 metric cards + sparklines |
| `CR-00086_v2_quality_panel.png` | V2: Quality page with 4 metric cards + sparklines |
| `CR-00086_v3_empty_state.png` | V3: InnoForge Tests page with combined empty-state message |
| `CR-00086_v4_jobs_view.png` | V4: Jobs page showing `test-health-capture` row at top |
| `CR-00086_v5_no_regressions.png` | V5: Queue page (unaffected, no regressions) |

---

## Fixture Notes

The following fixture was created to seed the E2E DB before verification:
- `ai-dev/active/CR-00086/e2e_fixtures/001_test_health_snapshots.py`
  - Inserts 30 `TestHealthSnapshot` rows per metric (mutation_score, coverage_pct, flaky_test_count, assertion_baseline_size) for `iw-ai-core` with realistic trend values
  - Also seeds `test_config` and `quality_config` on `iw-ai-core` so the Tests/Quality pages render (the pages require `categories` to be non-empty to show the panel section — this is a pre-existing guard in the page templates, not a CR-00086 issue)
  - Leaves `innoforge` with `test_config.categories` but zero snapshots (V3 target)
  - Fixture runs via `scripts/e2e_seed.py` on stack start; idempotent (checked via `db.scalar(select(...).limit(1))` before insert)

---

## Root Cause of V3 "No Test Configuration" (Transient, Resolved)

The initial Tests page for `iw-ai-core` showed "No Test Configuration" instead of the panel because the project lacked `test_config.categories`. The direct `/project/iw-ai-core/test-health` fragment endpoint worked immediately (confirmed before any fixture work). Resolved by including `test_config` seeding in the fixture file and re-running `scripts/e2e_seed.py`.

This does **not** indicate a code defect — the page correctly guards against missing config. The fix (seed the config in the fixture) ensures future browser verifications start from a fully-configured state.

---

## Overall Status: ✅ PASS

All V0–V5 verifications passed. The Test Health panel, sparklines, empty state, Jobs integration, and no-regression checks are all functioning correctly.
