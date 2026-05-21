# CR-00070_S02_Frontend_prompt

**Work Item**: CR-00070 -- Show Resolved Agent + Model Instead of "Inherit" in Step Runtime Dropdowns
**Step**: S02
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

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR introduces no migration and no schema change. Not applicable to this
step.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00070 --json`.
- `ai-dev/active/CR-00070/CR-00070_CR_Design.md` -- Design document (authoritative spec)
- `ai-dev/work/CR-00070/reports/CR-00070_S01_Backend_report.md` -- S01 report (the `inherited_runtime_label` context variable it added)

## Output Files

- `ai-dev/work/CR-00070/reports/CR-00070_S02_Frontend_report.md` -- Step report

## Context

You are implementing the template half of **CR-00070**. S01 already computes
an `inherited_runtime_label` context variable and passes it into the
`item_steps_table.html` template from all three render paths. Your job is to
consume that variable so the runtime `<select>` empty options show the
resolved agent + model with an `(inherited)` suffix instead of `— inherit —`.

Read `ai-dev/active/CR-00070/CR-00070_CR_Design.md` first — the **Desired
Behavior**, **Frontend Changes**, and **Acceptance Criteria** sections are
the authoritative spec. Read `S01`'s report to confirm the exact context
variable name and whether it is a string or `None`. Then read
`dashboard/CLAUDE.md`.

## Requirements

### 1. Relabel the per-step `<select>` empty option

In `dashboard/templates/fragments/item_steps_table.html`, the per-step
runtime `<select>` (around line 74) currently renders:

```
<option value="">— inherit —</option>
```

Change the label so it reads `{{ inherited_runtime_label }} (inherited)`
when `inherited_runtime_label` is set — for example `Pi + MiniMax 2.7
(inherited)`. The element MUST keep `value=""` unchanged.

### 2. Relabel the "Apply to remaining steps" bulk `<select>` empty option

The bulk `<select>` at the table footer (around line 244) currently renders
the same `<option value="">— inherit —</option>`. Apply the identical
relabel: `{{ inherited_runtime_label }} (inherited)`, keeping `value=""`.

### 3. Align the bulk `<select>` non-empty option labels to `display_name`

The bulk dropdown's non-empty options currently use
`{{ opt.cli_label }} / {{ opt.model_label }}`. Change them to
`{{ opt.display_name }}` so the bulk list is consistent with the per-step
list (which already uses `display_name`) and with the requester's example
format ("Pi + MiniMax 2.7").

### 4. Graceful fallback when nothing resolves

`inherited_runtime_label` may be `None` (the `agent_runtime_options`
catalogue has no enabled rows — AC5). When it is falsy, the empty option
MUST fall back to a neutral label `— inherit —` rather than rendering
` (inherited)` with an empty model name. Use a Jinja2 conditional/default so
the steps table always renders.

### 5. Template-render test

Add/extend a test in `tests/dashboard/test_runtime_override_templates.py`
that asserts the rendered steps table shows `... (inherited)` in both the
per-step and the bulk empty options, that `— inherit —` no longer appears
when an option resolves, and that the `None`/empty-catalogue case falls back
to `— inherit —` without error. Also assert an item-level override changes
the displayed inherited label (AC3).

## Project Conventions

Read `dashboard/CLAUDE.md` for:

- Fragment templates under `templates/fragments/` MUST NOT extend `base.html`.
- Jinja2 `format`-filter calls must stay `%`-style (a project hard rule) —
  not relevant unless you add one, but do not introduce `str.format`-style
  filter calls.
- Tailwind CSS is prebuilt; do not introduce dynamically-constructed classes.
  This change is text-only and should need no new CSS — if a class is needed,
  follow the `make css` / plain-CSS rules in `CLAUDE.md`.

Match the existing markup style of `item_steps_table.html`. This is a
text-label change only — do NOT alter `<select>` `name`, `value`, htmx
attributes (`hx-patch`, `hx-target`, `hx-swap`, `hx-disabled-elt`), or the
non-empty per-step options.

## TDD Requirement

Follow TDD (Red-Green-Refactor): write the failing template-render test
first, run it targeted (`uv run pytest tests/dashboard/test_runtime_override_templates.py -v`),
confirm it fails for the right reason (assertion on missing `(inherited)`
text), then make it pass, then refactor.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`, run in order and fix issues
in files you touched:

1. **`make format`**
2. **`make typecheck`**
3. **`make lint`** — note `make lint` runs `scripts/check_templates.py` over
   Jinja2 templates; it must pass.

Record each in the `preflight` object.

## Test Verification (NON-NEGOTIABLE)

Run only the targeted test you wrote/modified:

```bash
uv run pytest tests/dashboard/test_runtime_override_templates.py -v
```

Do NOT run `make test-integration` — that is the S07 QV gate. Do not report
`tests_passed: true` unless the targeted test passes with zero failures.

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "frontend-impl",
  "work_item": "CR-00070",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/dashboard/test_runtime_override_templates.py::test_x — AssertionError: ...  // captured RED run",
  "blockers": [],
  "notes": ""
}
```
