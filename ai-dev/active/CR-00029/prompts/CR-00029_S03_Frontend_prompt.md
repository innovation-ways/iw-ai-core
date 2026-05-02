# CR-00029_S03_Frontend_prompt

**Work Item**: CR-00029 -- Add Restart button to the synthetic Worktree Setup (S00) row
**Step**: S03
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Allowed: testcontainers, read-only `docker ps/inspect/logs`, `./ai-core.sh`, `make`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live DB.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00029 --json`
- `ai-dev/active/CR-00029/CR-00029_CR_Design.md`
- `ai-dev/active/CR-00029/reports/CR-00029_S01_Backend_report.md`
- `ai-dev/active/CR-00029/reports/CR-00029_S02_CodeReview_Backend_report.md`

## Output Files

- `dashboard/templates/components/action_button.html` — new macro added
- `dashboard/templates/fragments/item_overview.html` — modified
- `ai-dev/active/CR-00029/reports/CR-00029_S03_Frontend_report.md`

## Context

Read `CLAUDE.md` and `dashboard/CLAUDE.md`. The dashboard uses Jinja2 + htmx + prebuilt Tailwind CSS. Existing action buttons live in `dashboard/templates/components/action_button.html` and follow a consistent confirm-dialog pattern (`hx-get` to a confirm endpoint that returns the dialog fragment; the dialog then POSTs the action).

S01 added the backend POST endpoint at `/project/{project_id}/api/item/{item_id}/restart-setup` and registered the dialog wording with the generic dispatcher (`_ITEM_ACTION_LABELS["restart-setup"]`), which is exposed at `GET /project/{project_id}/api/confirm-item/restart-setup/{item_id}`. It also exposed `step.restartable: bool` on the synthetic S00 StepDetail.

## Requirements

### 1. Add `restart_setup_button` macro

In `dashboard/templates/components/action_button.html`, add a new macro that mirrors `restart_merge_button`:

```jinja
{% macro restart_setup_button(project_id, item_id) %}
  <button
    hx-get="/project/{{ project_id }}/api/confirm-item/restart-setup/{{ item_id }}"
    hx-target="#confirm-dialog"
    hx-swap="innerHTML"
    class="px-2 py-1 bg-secondary text-secondary-foreground rounded text-xs font-medium hover:opacity-90 transition-opacity"
    title="Restart setup (delete worktree, reset all steps)"
    {{ write_button_attrs(request) }}>
    ↻ Restart Setup
  </button>
{% endmacro %}
```

URL prefix is `/project/{{ project_id }}/api/confirm-item/restart-setup/{{ item_id }}` — this matches the generic dispatcher `confirm_item_dialog` registered on the actions router (`prefix="/project/{project_id}/api"`). It is consistent with the existing `restart_merge_button`'s URL.

### 2. Update `item_overview.html`

In `dashboard/templates/fragments/item_overview.html` (around line 90–107), the action column currently reads:

```jinja
{% if step.step_id == 'MERGE' and step.status == 'failed' %}
  <div class="flex items-center justify-end gap-1">
    {{ restart_merge_button(item.project_id, item.id) }}
  </div>
{% elif not step.is_synthetic %}
  ...
{% endif %}
```

Insert a new branch BEFORE `{% elif not step.is_synthetic %}`:

```jinja
{% elif step.is_synthetic and step.step_id == 'S00' and step.restartable %}
  <div class="flex items-center justify-end gap-1">
    {{ restart_setup_button(item.project_id, item.id) }}
  </div>
{% elif not step.is_synthetic %}
  ...
```

Also ensure the macro is imported at the top of `item_overview.html`. Check the existing imports — likely `{% from "components/action_button.html" import restart_button, skip_button, kill_button, restart_merge_button %}` or similar. Add `restart_setup_button` to that import list.

### 3. No regression in existing button flows

After the change:

- MERGE row with status=failed → `restart_merge_button` renders (unchanged)
- Synthetic S00 with `restartable=True` → `restart_setup_button` renders (NEW)
- Synthetic S00 with `restartable=False` → no button (unchanged)
- Other synthetic rows (e.g., MERGE with status != failed) → no button (unchanged)
- Non-synthetic rows with status in {failed, needs_fix} → restart + skip buttons (unchanged)
- Non-synthetic rows with status=in_progress → kill button (unchanged)

Read the diff carefully — the new branch should be additive with zero impact on the existing flows.

### 4. Tailwind / CSS

The macro uses `bg-secondary text-secondary-foreground` — these classes are already in use by `restart_merge_button` and `restart_button`, so no `make css` regeneration is needed. If you accidentally introduce a new utility class, run `make css`.

### 5. Smoke check

S05 owns the deterministic verification (template + endpoint + integration tests). For S03, the unit tests in `make test-unit` are sufficient — do **not** rely on a specific live item being in a setup-failed state. The formal browser verification happens in S13 with a self-contained e2e fixture.

## Project Conventions

- Fragment templates do NOT extend `base.html`
- Macros from `components/` are imported at the top of the consumer template
- htmx targets / swaps match the existing patterns
- No hand-written JavaScript

## TDD Requirement

Authoritative tests are in S05. For S03, just verify the dev-server smoke render works.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint` — also runs `node --check` on `dashboard/static/**/*.js`

## Test Verification (NON-NEGOTIABLE)

`make test-unit` must pass.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "frontend-impl",
  "work_item": "CR-00029",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/components/action_button.html",
    "dashboard/templates/fragments/item_overview.html"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": "URL prefix used by the macro, dev smoke screenshot path"
}
```
