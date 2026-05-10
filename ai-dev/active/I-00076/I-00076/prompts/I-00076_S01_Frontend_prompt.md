# I-00076_S01_Frontend_prompt

**Work Item**: I-00076 -- Per-step CLI/runtime override `<select>` silently clears the override instead of setting it
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:
  1. Testcontainers spun up by pytest fixtures.
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets.

If your task seems to require a prohibited command, STOP and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step does NOT generate or modify any alembic migration — it edits one Jinja2
template. Do NOT run any alembic command.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00076 --json` over the design-time `workflow-manifest.json` (CR-00023).
- `ai-dev/active/I-00076/I-00076_Issue_Design.md` -- the design document. Read **Root Cause Analysis**, **Fix Plan → S01 row**, **Affected Components**, **Acceptance Criteria**, and **Notes** carefully.
- `dashboard/templates/fragments/item_overview.html` -- the file you will edit (the editable-step CLI `<select>`, in the block guarded by `{% elif step.status in ('pending', 'failed') %}`, roughly lines 73–95).
- `dashboard/static/vendor/htmx/htmx.min.js` -- read-only; htmx 2.0.3. Background: htmx's `shouldInclude()` excludes elements that have the `disabled` attribute from request serialisation, which is why `this.disabled = true` before the PATCH drops `option_id`. `hx-disabled-elt` was designed to disable a control *after* serialisation and re-enable it on completion.
- `dashboard/routers/runtime_overrides.py` -- read-only; `patch_step_runtime_override` is correct (absent `option_id` legitimately means "clear / inherit"). Do not touch it.
- `dashboard/CLAUDE.md` -- htmx patterns; the prebuilt-Tailwind / plain-CSS rule (no new CSS classes are needed here).

## Output Files

- `dashboard/templates/fragments/item_overview.html` -- the fixed template
- `ai-dev/active/I-00076/reports/I-00076_S01_Frontend_report.md` -- step report

## Context

You are fixing the per-step CLI/runtime override `<select>` in the dashboard's item-detail **Overview** tab. The current handler `onchange="this.style.opacity='0.5'; this.disabled=true; htmx.trigger(this, 'change');"` disables the `<select>` *before* htmx serialises the PATCH, so the chosen `option_id` is omitted from the request body and the override is silently cleared instead of set. The redundant `htmx.trigger(this, 'change')` also double-fires the PATCH (a `<select>` already triggers htmx on `change` by default).

## Requirements

### 1. Replace the self-disabling `onchange` with `hx-disabled-elt="this"`

In `dashboard/templates/fragments/item_overview.html`, in the editable-step branch (`{% elif step.status in ('pending', 'failed') %}`), the `<select>` currently looks like:

```html
<select
  class="text-xs border border-border rounded bg-background text-foreground px-1 py-0.5 cursor-pointer w-24"
  hx-patch="/project/{{ item.project_id }}/api/item/{{ item.id }}/step/{{ step.step_id }}/runtime-override"
  hx-swap="none"
  name="option_id"
  onchange="this.style.opacity='0.5'; this.disabled=true; htmx.trigger(this, 'change');">
  <option value="">— inherit —</option>
  {% for opt in runtime_options %}
    <option value="{{ opt.id }}" {% if step.runtime_option_id == opt.id %}selected{% endif %}>{{ opt.cli_label }}</option>
  {% endfor %}
</select>
```

Change it to:
- **Remove** the `onchange="..."` attribute entirely (it is the bug; the visual feedback it provided is now covered by `hx-disabled-elt`).
- **Add** `hx-disabled-elt="this"` — htmx will add `disabled` to the `<select>` only *after* computing the request parameters, and re-enable it when the request completes, so `option_id` is still sent.
- Keep `hx-patch`, `hx-swap="none"`, `name="option_id"`, the `<option>` loop, and the `class` exactly as they are. **Do not** change the `w-24` width, the `cli_label` in the option text, or anything else in the file.
- Add a short Jinja comment immediately above the `<select>` (or an HTML comment) explaining: this control must NOT self-disable in an `onchange` handler — htmx omits disabled form controls from the request body (`shouldInclude`), which would drop `option_id` and clear the override instead of setting it; use `hx-disabled-elt` so htmx disables it only after serialising; a `<select>` already triggers htmx on `change` by default so no explicit `htmx.trigger` is needed.

Resulting markup should be equivalent to:

```html
{# Do NOT disable this <select> in an onchange handler — htmx omits disabled
   form controls from the request body (shouldInclude), which drops option_id
   and clears the override instead of setting it. Use hx-disabled-elt so htmx
   disables it only after serialising the value. A <select> already triggers
   htmx on `change` by default — no explicit htmx.trigger needed. #}
<select
  class="text-xs border border-border rounded bg-background text-foreground px-1 py-0.5 cursor-pointer w-24"
  hx-patch="/project/{{ item.project_id }}/api/item/{{ item.id }}/step/{{ step.step_id }}/runtime-override"
  hx-swap="none"
  hx-disabled-elt="this"
  name="option_id">
  <option value="">— inherit —</option>
  {% for opt in runtime_options %}
    <option value="{{ opt.id }}" {% if step.runtime_option_id == opt.id %}selected{% endif %}>{{ opt.cli_label }}</option>
  {% endfor %}
</select>
```

### 2. Do not touch anything else

The bulk "Apply to remaining steps" control (`hx-vals="javascript:{option_id: ...}"` on a button) is unaffected — leave it. `dashboard/routers/runtime_overrides.py` and `orch/agent_runtime/resolver.py` are correct — do not modify them.

### 3. No CSS rebuild needed

This change adds no new Tailwind classes, so `make css` is not required.

## Project Conventions

Read `CLAUDE.md` and `dashboard/CLAUDE.md`. Fragments under `templates/fragments/` must not extend `base.html` (this one already doesn't — keep it that way). Routers are thin; business logic stays in `orch/`. Match existing template style.

## TDD Requirement

The reproduction/regression tests are S03's job (a separate `tests-impl` step). For this step, after editing the template, sanity-check the render path quickly (e.g. `uv run pytest tests/dashboard/test_runtime_override_templates.py -q`) to confirm nothing breaks, but the new assertions land in S03 — do not duplicate that work here.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:
1. `make format` — auto-fixes formatting drift.
2. `make typecheck` — zero errors involving files you touched (a template edit shouldn't introduce any; note pre-existing ones).
3. `make lint` — zero errors (the JS-lint step in `make lint` ignores templates; this should be clean).

Populate the `preflight` object in your result contract.

## Test Verification (NON-NEGOTIABLE)

Run the targeted dashboard test that exercises this template:
```bash
uv run pytest tests/dashboard/test_runtime_override_templates.py -q
```
Do **NOT** run `make test-integration` or `make test-unit` — those are downstream QV gates.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00076",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/templates/fragments/item_overview.html"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok|skipped:<reason>", "lint": "ok|skipped:<reason>"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
