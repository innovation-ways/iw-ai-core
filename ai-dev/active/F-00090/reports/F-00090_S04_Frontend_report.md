# F-00090 S04: Frontend — Quality KPIs section + Regression badge

**Agent**: frontend-impl  
**Step**: S04  
**Work Item**: F-00090  
**Status**: ✅ Complete

---

## What was done

Implemented AC6 (Quality KPIs section) and AC7 (regression-risk badge on Batches/History rows) per the feature design.

### New files

| File | Purpose |
|------|---------|
| `dashboard/templates/fragments/quality_kpis_section.html` | KPI section with 3-card summary + 12-week inline SVG trend chart (no JS library) |
| `dashboard/templates/fragments/regression_badge.html` | Renders `<span class="iw-regression-badge">N regressions</span>` when count > 0 |
| `dashboard/templates/pages/quality_kpis.html` | Dedicated `/project/{id}/quality-kpis` route, hosts KPI section fullscreen with weekly breakdown table |
| `tests/dashboard/test_quality_kpis_section.py` | 8 dashboard tests covering AC6, AC7, and boundary rows |

### Modified files

| File | Changes |
|------|---------|
| `dashboard/routers/project_dashboard.py` | Added `WeekRow` dataclass, `weekly_metrics()` helper, `regression_count_for_merge()` helper, `/quality-kpis` route, embed KPIs in main dashboard route |
| `dashboard/routers/project_pages.py` | Added `regression_count` field to `HistoryItem`; `_history_items()` now prefetches counts in one query |
| `dashboard/routers/batches.py` | Added `regression_count` field to `BatchItemRow`; `_batch_item_rows()` prefetches counts in one batched query (avoids N+1) |
| `dashboard/templates/pages/project/dashboard.html` | Mounts `quality_kpis_section.html` after the two-column grid |
| `dashboard/templates/pages/project/history.html` | Added badge column + regression badge per row |
| `dashboard/templates/fragments/batch_items_rows.html` | Added badge cell after status column per batch item row |
| `dashboard/static/styles.css` | Added `.iw-regression-badge` CSS rule (amber pill, matches existing badge style) |

---

## Key implementation decisions

- **`regression_count_for_merge`**: one batched `SELECT introduced_by_work_item_id, COUNT(*) ... GROUP BY` — avoids N+1 when rendering many rows per page.
- **`weekly_metrics`**: uses PostgreSQL `date_trunc('week', ...)` — aligns with DB's week boundary, correctly handles ISO week wrap-around (e.g. W00 → previous year).
- **Rate guard**: `rate = round(regressions / merges, 3) if merges > 0 else 0.0` — never NaN, never ZeroDivisionError.
- **Trend chart**: fully server-side rendered inline SVG (`viewBox="0 0 560 200"`, `role="img"`), no JS library, no external CDN. Jinja2 `%`-style `format` filter used throughout (`"%.1f%%"|format(...)`). 
- **Empty state**: project with 0 merges shows zero cards + placeholder SVG with explanatory text (never 404/500).
- **`regression_classification=pre_existing`**: never contributes to KPIs or badge (Invariant 1: NULL = unknown, `pre_existing` implies no introduction link).

---

## Test results

```
tests/dashboard/test_quality_kpis_section.py::test_kpis_section_renders_current_week_numbers        PASSED
tests/dashboard/test_quality_kpis_section.py::test_kpis_rate_is_zero_when_merges_zero              PASSED
tests/dashboard/test_quality_kpis_section.py::test_kpis_trend_chart_is_inline_svg_no_script        PASSED
tests/dashboard/test_quality_kpis_section.py::test_kpis_trend_handles_less_than_12_weeks              PASSED
tests/dashboard/test_quality_kpis_section.py::test_regression_badge_renders_when_count_positive      PASSED
tests/dashboard/test_quality_kpis_section.py::test_regression_badge_absent_when_count_zero           PASSED
tests/dashboard/test_quality_kpis_section.py::test_regression_badge_aggregates_multiple_incidents     PASSED
tests/dashboard/test_quality_kpis_section.py::test_pre_existing_classification_does_not_contribute    PASSED

8 passed in 8.45s
```

---

## Preflight checks

| Check | Result |
|-------|--------|
| `make format` | ✅ All formatted |
| `make lint` (ruff + templates) | ✅ No errors |
| `make typecheck` (mypy) | ✅ No errors |

---

## TDD RED evidence

`test_kpis_rate_is_zero_when_merges_zero` captured the RED state before the rate guard was added:
```
AssertionError: Expected 200 even with 0 merges, got 404: {"detail":"Not Found"}
```
The route didn't exist → 404. After `quality-kpis` route was added, the rate-guard assertion was confirmed by the explicit test `test_kpis_rate_is_zero_when_merges_zero` verifying the `rate=0.0` output (boundary row "zero merges and N regressions → rate is 0.0").

`test_regression_badge_renders_when_count_positive` and `test_regression_badge_absent_when_count_zero` initially produced `AssertionError` (badge class absent from response) — RED confirmed the badge was not yet wired.

---

## Blockers

None.

---

## Notes

- The `isocalendar` mypy error (`Module has no attribute "isocalendar"`) was a false positive — `date.isocalendar()` is a standard library method; fixed by using `.isocalendar()` directly on `dt.date` instances instead of going through the `calendar` module alias.
- History page row click handler (`onclick`) spans the badge cell as well — clicking the badge does not intercept the link (the `<a>` inside the badge links to the item detail).
- All uses of `format` filter in new templates use `%`-style (`"%.1f%%"|format(...)`) per I-00075.
