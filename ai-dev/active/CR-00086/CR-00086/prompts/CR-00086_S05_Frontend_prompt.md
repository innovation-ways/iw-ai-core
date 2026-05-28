# CR-00086_S05_Frontend_prompt

**Work Item**: CR-00086 -- Self-dashboarding of test health
**Step**: S05
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Same as the other implementation prompts. Read-only `docker ps/inspect/logs` allowed; `make` / `./ai-core.sh` targets allowed. Anything else forbidden.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migration work in this step. You MUST NOT run `alembic upgrade/downgrade/stamp`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00086 --json`.
- `ai-dev/active/CR-00086/CR-00086_CR_Design.md` -- Design document (read **Desired Behavior**, AC4, AC5, **Frontend Changes**)
- `ai-dev/work/CR-00086/reports/CR-00086_S03_Backend_report.md` -- S03 report (gives you the service API + CLI summary shape)
- `dashboard/routers/tests.py` -- existing Tests view router
- `dashboard/routers/quality.py` -- existing Quality view router
- `dashboard/templates/fragments/` -- existing htmx fragment templates (study an existing one for style)
- `dashboard/templates/pages/` -- find the Tests and Quality page templates (`grep -r "Test.*Quality\|quality.*tests" dashboard/templates/`)
- `orch/jobs/aggregator.py` -- existing unified Jobs aggregator (study how code-index jobs are added)
- `orch/test_health_service.py` -- new service from S03

## Output Files

- `ai-dev/work/CR-00086/reports/CR-00086_S05_Frontend_report.md` -- Step report
- `dashboard/templates/fragments/test_health_panel.html` (new)
- `dashboard/routers/tests.py` (modified — adds endpoint + mount)
- `dashboard/routers/quality.py` (modified — adds endpoint + mount, sharing the partial helper)
- `dashboard/templates/pages/<tests>.html` and `<quality>.html` (one-line htmx mount each — paths discovered by grep)
- `orch/jobs/aggregator.py` (modified — adds `test-health-capture` row type to the union)
- `tests/dashboard/test_test_health_panel.py` (new)
- `tests/unit/test_test_health_sparkline.py` (new)
- `tests/integration/test_jobs_aggregator_test_health.py` (new)

## Context

You are implementing the **Frontend panel + Jobs integration** step of **CR-00086**. The panel shows four metric cards with inline SVG sparklines drawn server-side from snapshot rows. The Jobs aggregator gets a new union branch so each capture appears as a job row.

Read `CLAUDE.md` and `dashboard/CLAUDE.md` first.

## Requirements

### 1. dashboard/templates/fragments/test_health_panel.html

- Four metric cards in a responsive grid (use existing Tailwind utility classes from the Tests page — do NOT add new global CSS unless `make css` is broken; the project rule allows a direct edit to `dashboard/static/styles.css` in that fallback case).
- Each card shows:
  - Metric label (human-readable: "Mutation Score", "Coverage", "Flaky Tests", "Assertion Baseline").
  - Latest value (formatted appropriately: percentage for mutation/coverage, integer for the other two).
  - Delta vs. previous snapshot, with an up/down arrow (and a neutral dash when there is no prior snapshot).
  - An inline SVG sparkline of up to 30 snapshots, server-rendered (no JS chart library).
- **Empty-state placeholder**: when a metric has zero snapshots, render `<p class="...">no data yet</p>` and do NOT emit an empty `<svg>` or `NaN` text. AC5 mandates this.
- **Combined empty state**: when ALL four metrics are empty, render a single panel-level message ("Test health data will appear after the first capture runs") instead of four placeholders.

### 2. SVG sparkline helper

Build the SVG path server-side. Inputs: list of `(ts, value)` tuples. Output: an `<svg>` element with one `<path d="M x0,y0 L x1,y1 ...">` and small endpoint circles. Keep it under ~40 lines. Place the helper next to the panel — either in the Jinja template via a macro, or in a small helper module imported by both router endpoints (avoid duplication).

### 3. Router endpoints (shared partial)

- `dashboard/routers/tests.py`: add `GET /projects/{slug}/test-health` returning the rendered fragment.
- `dashboard/routers/quality.py`: add the same `GET /projects/{slug}/test-health` endpoint (or share via a single route mounted from a shared module).
- **CRITICAL**: factor the fragment-prep code into ONE helper. Copy-pasting between tests.py and quality.py is a code-review failure (S06 will check).

### 4. Mount in page templates

In whichever templates power the Tests and Quality pages (`grep` for them — likely `dashboard/templates/pages/tests.html` and `dashboard/templates/pages/quality.html`), add ONE htmx include block:

```html
<div hx-get="/projects/{{ project.slug }}/test-health"
     hx-trigger="load"
     hx-swap="innerHTML">
  <!-- placeholder while loading -->
</div>
```

Place it under the existing gates summary; do NOT touch unrelated sections of those page templates.

### 5. Jobs aggregator hook

Edit `orch/jobs/aggregator.py` to include a new branch in the union returning rows with `job_type='test-health-capture'`. Match the existing pattern (look at how `CodeIndexJob` rows are added). Source rows come from `test_health_snapshots` itself — group by `(project_id, ts truncated to the minute)` so one capture invocation produces ONE job row regardless of how many metrics it wrote.

### 6. TDD tests (RED FIRST)

Write these tests BEFORE the production code; capture RED snippets in `tdd_red_evidence`:

- `tests/dashboard/test_test_health_panel.py`:
  - `test_panel_renders_with_snapshots` — seed 4 metrics with 5 snapshots each; GET `/projects/iw-ai-core/test-health`; assert 200 + 4 metric labels in body + 4 `<svg>` tags + 4 path strings starting with `M `.
  - `test_panel_empty_state_per_metric` — seed only `mutation_score`; GET; assert 3 `no data yet` placeholders + 1 `<svg>`.
  - `test_panel_combined_empty_state` — seed nothing; GET; assert ONE combined empty-state message, no per-metric placeholders.
  - `test_tests_page_mounts_panel` — GET `/projects/iw-ai-core/tests`; assert the page body contains the htmx mount block.
- `tests/unit/test_test_health_sparkline.py`:
  - `test_sparkline_ascending_values` — given ascending `[1, 2, 3, 4, 5]`, the resulting SVG path's y-coords are monotonically decreasing (SVG y axis is inverted).
  - `test_sparkline_empty_returns_placeholder` — given `[]`, the helper returns the empty-state SVG (or `None`, depending on your design — assert what your code actually does).
- `tests/integration/test_jobs_aggregator_test_health.py`:
  - `test_capture_appears_in_jobs_view` — after a capture, the aggregator union returns one row with `job_type='test-health-capture'`.
  - `test_multiple_captures_one_job_row_per_minute` — two captures in the same minute → one job row, not four.

## Project Conventions

- `dashboard/CLAUDE.md` — htmx fragment conventions, Jinja2 `%`-style format filter (NEVER `str.format`-style — see I-00075).
- Tailwind: prefer existing utilities; if `make css` is broken, append plain CSS to `dashboard/static/styles.css` (project rule).
- Server-rendered SVG only — no JS chart library, no new client-side JS dependencies.

## TDD Requirement

RED-Green-Refactor. Capture RED snippets. Forbidden RED shapes: ImportError, SyntaxError, fixture/collection errors.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. `make format`
2. `make typecheck`
3. `make lint` (this includes `scripts/check_templates.py` — the Jinja2 format-filter linter)

Populate `preflight`.

## Test Verification (NON-NEGOTIABLE)

Targeted only:

```bash
uv run pytest tests/dashboard/test_test_health_panel.py tests/unit/test_test_health_sparkline.py tests/integration/test_jobs_aggregator_test_health.py -v
```

Do NOT run `make test-integration` or `make test-dashboard` for the full suite.

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "frontend-impl",
  "work_item": "CR-00086",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/test_health_panel.html",
    "dashboard/routers/tests.py",
    "dashboard/routers/quality.py",
    "dashboard/templates/pages/tests.html",
    "dashboard/templates/pages/quality.html",
    "orch/jobs/aggregator.py",
    "tests/dashboard/test_test_health_panel.py",
    "tests/unit/test_test_health_sparkline.py",
    "tests/integration/test_jobs_aggregator_test_health.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_test_health_panel.py::test_panel_renders_with_snapshots — AssertionError: 404 != 200  // captured RED before adding the route",
  "blockers": [],
  "notes": ""
}
```
