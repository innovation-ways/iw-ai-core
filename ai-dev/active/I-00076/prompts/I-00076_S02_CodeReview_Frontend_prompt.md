# I-00076_S02_CodeReview_Frontend_prompt

**Work Item**: I-00076 -- Per-step CLI/runtime override `<select>` silently clears the override instead of setting it
**Step Being Reviewed**: S01 (frontend-impl)
**Review Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state
(`docker kill|stop|rm|restart`, `docker compose up|down|restart`, `docker volume rm|prune`,
`docker system|container|image prune`). Read-only `docker ps|inspect|logs` and `./ai-core.sh` /
`make` targets are fine.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

S01 edits a Jinja2 template only. There is no migration in scope. If S01 generated or
modified an alembic migration, that is a CRITICAL out-of-scope finding — flag it.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00076 --json`
- `ai-dev/active/I-00076/I-00076_Issue_Design.md` -- the design doc. **Read it BEFORE the code** — especially **Root Cause Analysis**, **Fix Plan → S01 row**, **Acceptance Criteria**, and **Notes** (the working-tree mitigation; the explicitly out-of-scope `w-24`/`cli_label` tweaks).
- `ai-dev/active/I-00076/reports/I-00076_S01_Frontend_report.md` -- S01's report
- `dashboard/templates/fragments/item_overview.html` -- the file S01 changed (review the diff vs `main`)
- `dashboard/static/vendor/htmx/htmx.min.js` -- read-only; confirm your understanding of `hx-disabled-elt` semantics (disable after serialisation, re-enable on completion) and `shouldInclude` excluding disabled controls.
- `dashboard/routers/runtime_overrides.py` -- read-only; the endpoint S01 must NOT have changed.

## Output Files

- `ai-dev/active/I-00076/reports/I-00076_S02_CodeReview_report.md` -- review report

## Context

Tiny surface: one `<select>` in one fragment template. The review is targeted — verify the fix is *correct* (the chosen `option_id` will now be serialised), *minimal* (nothing else touched), and *self-documenting* (a comment explains why the control must not self-disable).

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Before reading the diff, run:
```bash
make format
make lint
```
Any NEW violation introduced by S01 is a **CRITICAL** finding with `category: "conventions"`. (A template edit normally produces none.) If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Correctness against the design contract

- The editable-step `<select>` (in the `{% elif step.status in ('pending', 'failed') %}` branch) **no longer** has `onchange="...disabled...".` There is **no** `this.disabled` and **no** `htmx.trigger(` anywhere on or near it. — CRITICAL if either survives.
- The `<select>` now carries `hx-disabled-elt="this"`. — CRITICAL if missing.
- `hx-patch="/project/{{ item.project_id }}/api/item/{{ item.id }}/step/{{ step.step_id }}/runtime-override"`, `hx-swap="none"`, `name="option_id"`, and the `<option value="">— inherit —</option>` + `{% for opt in runtime_options %}` loop are all still present and unchanged. — HIGH if any is dropped or altered.
- A comment (Jinja `{# … #}` or HTML `<!-- … -->`) immediately above/around the `<select>` explains why it must not self-disable (htmx omits disabled controls → `option_id` dropped → override cleared; use `hx-disabled-elt`; `<select>` already triggers on `change`). — MEDIUM if absent or vague.

### 2. Minimality / scope

- The `class` attribute is unchanged — in particular `w-24` is still `w-24` (NOT `w-48`), and the option text is still `{{ opt.cli_label }}` (NOT `{{ opt.display_name }}`). Those tweaks are explicitly out of scope per the design § Notes; their presence is a HIGH out-of-scope finding.
- No other element in `item_overview.html` changed (the bulk "Apply to remaining steps" control, the read-only badges for non-editable steps, the step pipeline include, the action buttons, the cascade-history include — all untouched). — HIGH if any unrelated change crept in.
- `dashboard/routers/runtime_overrides.py`, `orch/agent_runtime/resolver.py`, and any other `.py` files are unchanged by S01. — CRITICAL if changed.
- No new Tailwind classes added (so no `make css` dependency). — note in report if violated.

### 3. Template hygiene / project conventions — `dashboard/CLAUDE.md`, `CLAUDE.md`

- Fragment still does NOT extend `base.html`.
- No `navigator.clipboard.writeText` introduced (n/a here, but confirm nothing odd was added).
- htmx attribute names are spelled correctly (`hx-disabled-elt`, not `hx-disable-elt` or `hx-disabled`).
- Indentation / quoting matches the surrounding template.

### 4. Behavioural reasoning (no test execution needed here — S03 owns tests)

Walk it mentally: a `<select>` with `hx-patch` + default `change` trigger + `hx-disabled-elt="this"` → user picks an option → htmx serialises `{option_id: <value>}` (element not yet disabled) → disables the element for the request → sends PATCH → server sets `workflow_steps.agent_runtime_option_id` → re-enables on completion. A single request, carrying the value. If you can construct a scenario where the value is still dropped, that's a CRITICAL finding.

## Report

Write `ai-dev/active/I-00076/reports/I-00076_S02_CodeReview_report.md` with a findings table (severity, category, file:line, description, recommended fix) and an overall verdict (`approve` / `request_changes`). Approve only if there are no CRITICAL/HIGH findings.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00076",
  "review_target": "S01",
  "verdict": "approve|request_changes",
  "findings": [
    {"severity": "critical|high|medium|low", "category": "correctness|conventions|scope|security", "location": "dashboard/templates/fragments/item_overview.html:NN", "description": "...", "recommendation": "..."}
  ],
  "preflight": {"format": "ok|fixed", "lint": "ok"},
  "notes": ""
}
```
