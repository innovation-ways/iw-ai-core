# F-00063_S06_CodeReview_Frontend_prompt

**Work Item**: F-00063 -- Stale Process & Migration Detector
**Step Being Reviewed**: S04 (frontend-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits

You MUST NOT execute docker container/volume/network mutating commands. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live orch DB. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/F-00063/F-00063_Feature_Design.md`
- `ai-dev/active/F-00063/reports/F-00063_S04_Frontend_report.md`
- All files listed in S04's `files_changed`

## Output Files

- `ai-dev/active/F-00063/reports/F-00063_S06_CodeReview_report.md`

## Context

You are reviewing the dashboard UI built in S04 — three new fragments (panel, dot, confirm dialog), plus the integration into the project home and project list templates.

## Review Checklist

### 1. Visual / structural

- Panel renders Migrations section ABOVE Services section (per design).
- Migrations section omitted entirely when no `[project.alembic]` block.
- Empty staleness (opt-out project) renders literally nothing — confirm via the test rendering an empty fragment.
- Status badges use the documented colours (green / red / grey / blue) and are accessible (text label, not colour-only).
- "Apply migrations first" hint copy appears only when both alembic and at least one service are stale.

### 2. htmx wiring

- Outer `<section>` of the panel has `hx-get`, `hx-trigger="every 15s"`, `hx-swap="outerHTML"`.
- Project home page wrapper has `hx-trigger="load, every 15s"` so it bootstraps and self-refreshes.
- Project list dot has the same auto-refresh pattern.
- Confirm dialog uses the existing dashboard modal pattern (do not reinvent — search `dashboard/templates/fragments/` for a precedent).
- Action POSTs target the correct endpoints from S03.

### 3. Project conventions

- Class names follow the `iw-` prefix convention (or whatever convention dominates the existing CSS).
- Colours come from CSS variables where they exist; literal hex only when no variable exists.
- Jinja2 syntax matches the codebase style (no `{%- -%}` chaos; no inline JS where htmx attributes suffice).
- ruff lint passes (covers JS in `dashboard/static/**/*.js` via `node --check`).

### 4. Accessibility

- Buttons have visible text labels.
- Status icons / dots have `title` or `aria-label` attributes.
- Modal traps focus when open (or follows existing modal accessibility behavior).
- Colour is never the only signal of state.

### 5. Testing

- Template-rendering tests exist for each fragment.
- Tests cover: empty (opt-out), all-up-to-date, alembic-only stale, services-only stale, both stale.
- Tests assert key strings, htmx attributes, button presence/absence.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` (template-rendering tests live under `tests/dashboard/`; this project has no separate `test-frontend` target)
2. `make lint` (covers JS via `node --check`)
3. `make typecheck`

## Severity Levels

CRITICAL / HIGH / MEDIUM_FIXABLE → block merge. Others informational.

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "code-review-impl",
  "work_item": "F-00063",
  "step_reviewed": "S04",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
