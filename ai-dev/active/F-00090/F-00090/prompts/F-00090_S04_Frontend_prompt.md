# F-00090_S04_Frontend_prompt

**Work Item**: F-00090 -- Regression-rate tracking
**Step**: S04
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy applies. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

This step leaves migrations unchanged.

## Input Files

- **Runtime step state** — `uv run iw item-status F-00090 --json`.
- `ai-dev/active/F-00090/F-00090_Feature_Design.md` — AC6, AC7 are your targets.
- `ai-dev/active/F-00090/reports/F-00090_S01_Database_report.md` and `F-00090_S02_Backend_report.md`.
- `dashboard/routers/project_dashboard.py` — per-project home; mount-point for KPI section.
- `dashboard/routers/batches.py` — Batches/History rows; mount-point for badge.
- `dashboard/templates/fragments/` — directory for new fragments.

## Output Files

- `ai-dev/active/F-00090/reports/F-00090_S04_Frontend_report.md` — step report.
- New: `dashboard/templates/fragments/quality_kpis_section.html`
- New: `dashboard/templates/fragments/regression_badge.html`
- New: `dashboard/templates/pages/quality_kpis.html`
- Modified: `dashboard/routers/project_dashboard.py` (KPI section + dedicated route)
- Modified: `dashboard/routers/batches.py` (badge on row renderer)
- New: `tests/dashboard/test_quality_kpis_section.py`

## Context

You are implementing the **Quality KPIs section** (per-project home + dedicated route) and the **regression-risk badge** on Batches/History rows. ACs: AC6 (KPIs) and AC7 (badge).

Read the design first. Read `CLAUDE.md` and `dashboard/CLAUDE.md`.

## Requirements

### 1. Read-only KPI computation

Add helpers (in `dashboard/routers/project_dashboard.py` or a small helper module — match existing patterns) that compute:

- `weekly_metrics(project_id, weeks=12) -> list[WeekRow]` where `WeekRow = {iso_week: str, merges: int, regressions: int, rate: float}`. `merges` is the count of `WorkItem` rows with `status='done'` whose merge week matches; `regressions` is the count of `WorkItem` rows with `regression_classification='regression' AND introduced_by_work_item_id IS NOT NULL` whose `classified_at` falls in the week. **Rate guard**: when `merges == 0`, rate is `0.0` (not NaN, not divide-by-zero).
- `regression_count_for_merge(project_id, merge_item_id) -> int` — number of Incidents with `introduced_by_work_item_id == merge_item_id`. Used by the badge.

These helpers are read-only and live next to the routers; you can also extract them to a small module if scope warrants.

### 2. Quality KPIs section + dedicated page

- New fragment `dashboard/templates/fragments/quality_kpis_section.html` renders the current week's `merges / regressions / rate` plus a **12-week trend chart as inline SVG** (server-side rendered; no `<script>` tags, no JS library). The chart is two stacked lines (merges, regressions) on a shared X axis labelled by ISO week.
- Mount the fragment in the per-project home (`project_dashboard.py`) — match the existing section pattern.
- Add a dedicated route `GET /project/{project_id}/quality-kpis` rendering `dashboard/templates/pages/quality_kpis.html`, which simply hosts the same fragment full-screen plus a longer history table.
- Handle empty state: a project with zero merges shows the section with zeros and a placeholder chart (e.g. an empty SVG with a note "No merges yet"). Do NOT 404 or 500.

### 3. Regression-risk badge on Batches/History rows

- New fragment `dashboard/templates/fragments/regression_badge.html` accepts `count` and renders `<span class="iw-regression-badge">{count} regressions</span>` when `count > 0`, otherwise renders nothing.
- In `dashboard/routers/batches.py`, the row renderer for merged items must call `regression_count_for_merge(...)` for each row and pass the count to the badge fragment. **N+1 risk**: if the rows page renders many items, compute the counts in a single batched query (one `SELECT introduced_by_work_item_id, COUNT(*) ... GROUP BY introduced_by_work_item_id WHERE introduced_by_work_item_id = ANY(:ids)`), not one query per row.
- Add a CSS rule for `.iw-regression-badge` in `dashboard/static/styles.css` (plain CSS — see I-00067) for color and spacing. Match existing badge style.

### 4. Dashboard tests — `tests/dashboard/test_quality_kpis_section.py`

Cover AC6, AC7, and the Boundary rows:

- `test_kpis_section_renders_current_week_numbers`
- `test_kpis_rate_is_zero_when_merges_zero` — Boundary row "zero merges and N regressions"
- `test_kpis_trend_chart_is_inline_svg_no_script` — assert the response contains `<svg` and does NOT contain `<script`
- `test_kpis_trend_handles_less_than_12_weeks` — Boundary row "<12 weeks of history"
- `test_regression_badge_renders_when_count_positive`
- `test_regression_badge_absent_when_count_zero` — Boundary row N==0
- `test_regression_badge_aggregates_multiple_incidents` — Boundary row "two regressions point to the same merge"
- `test_pre_existing_classification_does_not_contribute` — Invariant 1 + Boundary row "pre_existing"

Use the existing dashboard test fixtures + testcontainer. Seed work items + classifications directly via the session fixture.

### 5. RED-first discipline (NON-NEGOTIABLE)

Write the failing tests first. Capture an `AssertionError` from one in `tdd_red_evidence`.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md`. Key constraints:

- **MUST** keep Jinja2 `format`-filter calls `%`-style: `"%dm%02ds"|format(m, s)` — never `str.format`-style. See I-00075. The KPI section likely formats percentages and counts — be careful here.
- No new JS libraries — trend chart is inline SVG.
- Plain CSS in `dashboard/static/styles.css` (Tailwind toolchain may be broken in worktrees — I-00067).
- Project-namespaced routes — `/project/{id}/quality-kpis`, never global.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint`

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_quality_kpis_section.py -v
```

Do NOT run the full dashboard test suite.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "frontend-impl",
  "work_item": "F-00090",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/project_dashboard.py",
    "dashboard/routers/batches.py",
    "dashboard/templates/fragments/quality_kpis_section.html",
    "dashboard/templates/fragments/regression_badge.html",
    "dashboard/templates/pages/quality_kpis.html",
    "dashboard/static/styles.css",
    "tests/dashboard/test_quality_kpis_section.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "tests/dashboard/test_quality_kpis_section.py: N passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_quality_kpis_section.py::test_kpis_rate_is_zero_when_merges_zero — AssertionError: ZeroDivisionError (RED before rate guard added)",
  "blockers": [],
  "notes": ""
}
```
