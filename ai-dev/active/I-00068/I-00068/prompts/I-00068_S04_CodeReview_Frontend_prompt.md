# I-00068_S04_CodeReview_Frontend_prompt

**Work Item**: I-00068 -- Recent Activity batch link from "archived" event routes to /item/ instead of /batch/
**Step Being Reviewed**: S03 (frontend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy.

## Input Files

- `uv run iw item-status I-00068 --json` — runtime step state
- `ai-dev/active/I-00068/I-00068_Issue_Design.md` — Design document
- `ai-dev/active/I-00068/reports/I-00068_S03_Frontend_report.md` — S03 report
- `dashboard/templates/pages/project/dashboard.html` — Modified template
- `tests/integration/test_dashboard_pages.py` — Existing tests for regression check

## Output Files

- `ai-dev/active/I-00068/reports/I-00068_S04_CodeReview_report.md`

## Pre-Review Lint & Format Gate

```bash
make lint
make format
```

Report new violations as CRITICAL.

## Review Checklist

### 1. Correctness of the prefix detection

- The condition is `event.entity_id.startswith('BATCH-')` exactly. Case-sensitive. Includes the trailing dash.
- The `BATCH-` branch produces `href="/project/{{ pid }}/batch/{{ entity_id }}"`.
- The `/item/` fallback still applies when `entity_id` does NOT start with `BATCH-`.

### 2. No accidental coverage gaps

- A row with `entity_id="BATCHFOO"` (no dash) does NOT route to `/batch/` (it would fall through to `/item/`). Confirm by reading the conditional.
- A row with `entity_id="batch-00001"` (lowercase) does NOT route to `/batch/`. Confirm.
- A row with `entity_id=None` does NOT enter either branch.

### 3. No regressions to explicit branches

- The three explicit branches (`'batch'`, `'doc_job'`, `'work_item'`) are byte-identical to before. Diff carefully.
- The empty-state ("No recent activity.") branch is unchanged.

### 4. Escape safety

- No `|safe`, no `Markup(...)`, no manual escape disabling.
- `{{ event.entity_id }}` continues to render through Jinja2's default autoescape.

### 5. Project conventions

- No JS changes (per the design — pure template change).
- No new Tailwind classes (per the design).
- Read `dashboard/CLAUDE.md` for any other rules.

### 6. Tests

- The new test in `tests/integration/test_i00068_batch_link_routing.py` (added by S03 or to be expanded by S05) is falsifiable on `main`.
- Existing dashboard tests still pass (run `make test-integration`).

## Test Verification (NON-NEGOTIABLE)

Run `make test-integration`. All dashboard tests must pass.

## Severity Levels

CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.

## Review Result Contract

Same JSON shape as I-00067_S02. `verdict: "pass"` requires zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
