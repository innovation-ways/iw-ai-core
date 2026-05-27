# F-00090 S16 Browser Verification Report

- Work item: F-00090
- Step: S16
- Base URL used: `http://localhost:9923`
- Seed refresh: `docker compose -p "$COMPOSE_PROJECT_NAME" exec e2e-dashboard uv run python scripts/e2e_seed.py`

## Verification Results

| ID | Check | Status | Notes |
|---|---|---|---|
| V1 | Classification form on Incident detail | PASS | On `I-00990`, regression classification section present with searchable introduced-by input, commit SHA placeholder, all 3 radios (Regression/Pre-existing/Unknown), enabled Classify button. |
| V2 | Quality KPIs show classified regression | PASS | `quality-kpis` page shows merges/week=1, regressions/week=1, rate=100.0%; trend chart present; weekly row `2026-W22` has non-zero regressions. |
| V3 | Regression badge on merged row | PASS | History row `F-00990` shows badge text `1 regression`; HTML contains `class="iw-regression-badge"`. |
| V4 | Empty-state no-merges project | N/A | No zero-merge project exists in current E2E seed data; AC6 zero-merge guard covered by unit test `test_kpis_rate_is_zero_when_merges_zero`. |
| V5 | No regressions in adjacent flows | PASS | Throughput/quality KPI card still renders on project home; Incident detail status/design/step sections still render; non-regression rows show no badge; no console error logs produced. |

## V0 Pre-flight Sanity

PASS. All referenced routes returned HTTP 200:
- `/`
- `/project/iw-ai-core/`
- `/project/iw-ai-core/history`
- `/project/iw-ai-core/item/I-00990`
- `/project/iw-ai-core/quality-kpis`

No unhandled JS/HTMX console errors observed (`.playwright-cli/console-*.log`: none generated).

## Issues Found

None.

## Screenshots

- `ai-dev/active/F-00090/evidences/post/F-00090_v1_classification_form.png`
- `ai-dev/active/F-00090/evidences/post/F-00090_v2_quality_kpis_section.png`
- `ai-dev/active/F-00090/evidences/post/F-00090_v3_regression_badge.png`
- `ai-dev/active/F-00090/evidences/post/F-00090_v4_empty_state.png`
- `ai-dev/active/F-00090/evidences/post/F-00090_v5_no_regressions.png`

## No regressions observed

- Existing KPI section on project dashboard renders correctly.
- Incident detail baseline sections (status/header, tabs including Design Document, step pipeline table) render correctly.
- History rows without linked regressions do not display regression badges.
