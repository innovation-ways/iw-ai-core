# CR-00086_S06_CodeReview_prompt

**Work Item**: CR-00086 -- Self-dashboarding of test health
**Step Being Reviewed**: S05 (frontend-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Same policy. Read-only `docker ps/inspect/logs` plus `make` / `./ai-core.sh` targets only.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migration work here. You MUST NOT run `alembic upgrade/downgrade/stamp`.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00086 --json`.
- `ai-dev/active/CR-00086/CR-00086_CR_Design.md` -- Design (read AC4, AC5, Frontend Changes, TDD Approach)
- `ai-dev/work/CR-00086/reports/CR-00086_S05_Frontend_report.md`
- All files in S05's `files_changed`

## Output Files

- `ai-dev/work/CR-00086/reports/CR-00086_S06_CodeReview_report.md`

## Context

You are reviewing the **Frontend panel + Jobs aggregator** work for CR-00086.

## Read the Design Document FIRST

- AC4 — panel renders four metric cards, four `<svg>` tags, no console errors.
- AC5 — empty-state placeholder per metric AND combined empty state.
- TDD Approach — note every test file the design names; cross-check against S05 `files_changed`. Missing one is CRITICAL.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint           # includes scripts/check_templates.py (Jinja2 format filter)
make format
```

Report new violations as CRITICAL `category: conventions`.

## Review Checklist

### 1. Architecture Compliance

- The two router endpoints (tests.py + quality.py) share ONE partial-render helper. Copy-pasted fragment-prep code is a HIGH finding.
- The Jobs aggregator addition follows the existing union pattern (e.g., `select(...).union_all(...)` mirroring `CodeIndexJob`). Python-side concatenation is a MEDIUM-fixable finding.
- The fragment template uses Jinja2 `%`-style format filters where applicable — NEVER `{}.format`-style (project hard rule, I-00075). If `scripts/check_templates.py` would catch it, raise CRITICAL.

### 2. Code Quality

- **Empty-state per metric (AC5)**: open the test asserting the placeholder and confirm it checks for the `no data yet` text, not an empty `<svg>` and not `NaN`. If the test merely asserts a 200 status, raise CRITICAL.
- **Combined empty state**: a separate test exists and asserts ONE message (not four placeholders). If missing, HIGH.
- **Sparkline correctness**: the unit test confirms ascending values produce decreasing y-coords (SVG y axis inverted). If the test asserts increasing y-coords for ascending values, the chart will render upside-down — CRITICAL.
- **Jobs aggregator de-duplication**: the multiple-captures-same-minute test exists and asserts ONE job row, not four. If missing, HIGH (the design called this out — each capture run is one job, not one job per metric).

### 3. Project Conventions

- `dashboard/CLAUDE.md` — htmx patterns followed.
- No new client-side JS dependencies added.
- Existing Tailwind utility classes reused; new global CSS only via the documented fallback path.

### 4. Security

- No untrusted user input rendered without escaping. The metric values come from the DB but should still be passed through Jinja's autoescape (verify the template doesn't use `|safe` on metric values).
- The htmx `hx-get` URL pattern matches the existing route conventions (no path traversal via the `slug` param).

### 5. Testing

- Cross-check every test file in the design's TDD section against S05 `files_changed`. Missing entries are CRITICAL.
- Spot-check at least one new assertion using the mutation-test heuristic: would this test fail if the production line it covers regressed? If not, raise HIGH.

### 5a. TDD RED Evidence

- S05 is a behaviour-implementing step; the report MUST carry `tdd_red_evidence` with a plausible failure snippet (NOT ImportError or collection error).
- For one new behavioural test, reason about whether it would fail against the pre-change code. If it would pass without the new code, raise HIGH.

## Pre-flight Page Sanity (preview of what qv-browser will check)

You don't need to launch a browser, but read the fragment template and the page templates and confirm:

- Every `hx-target="#X"`, `hx-include="#X"`, `aria-controls="X"`, `aria-labelledby="X"`, `href="#X"`, `for="X"` reference in the new fragment resolves to an id present in the rendered HTML.
- The htmx mount block in the page templates correctly references the new endpoint URL.

Dangling references are MEDIUM-fixable findings here (CRITICAL when qv-browser catches them later).

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_test_health_panel.py tests/unit/test_test_health_sparkline.py tests/integration/test_jobs_aggregator_test_health.py -v
```

Any failure is a CRITICAL finding.

## Severity Levels

Standard table. Use `verdict: pass` only if zero CRITICAL + HIGH + MEDIUM-fixable findings.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "CR-00086",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
