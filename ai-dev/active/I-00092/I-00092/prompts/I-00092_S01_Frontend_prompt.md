# I-00092_S01_Frontend_prompt

**Work Item**: I-00092 — Auto-merge filter chip never highlights the active filter
**Step**: S01
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Standard policy — see `docs/IW_AI_Core_Agent_Constraints.md`. No docker
commands except testcontainers (fixtures only).

## ⛔ Migrations: agents generate, daemon applies

N/A — this step does not touch alembic.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00092 --json`.
- `ai-dev/active/I-00092/I-00092_Issue_Design.md`
- `ai-dev/active/I-00092/I-00092_Functional.md`
- `dashboard/templates/fragments/auto_merge_events_table.html`
- `dashboard/CLAUDE.md`

## Output Files

- `ai-dev/active/I-00092/reports/I-00092_S01_Frontend_report.md`

## Context

The filter chip row in the auto-merge events table never highlights the
active filter because the template compares the URL query param
(`merge_auto_resolved`) to the chip's short key (`resolved`), which is
permanently False. Fix the comparison plus add accessibility hints.

## Requirements

### 1. Fix the active-chip comparison

In `dashboard/templates/fragments/auto_merge_events_table.html`,
locate the filter loop (lines ~13-21). Replace the active-class branch:

```jinja
{# BEFORE #}
{% if type_filter == key or (key == 'all' and not request.query_params.get('type')) %}bg-primary text-primary-foreground border-primary{% else %}border-border text-muted-foreground{% endif %}

{# AFTER #}
{% set _is_active = (mapped is none and not request.query_params.get('type')) or (mapped is not none and type_filter == mapped) %}
{% if _is_active %}bg-primary text-primary-foreground border-primary{% else %}border-border text-muted-foreground{% endif %}
```

The new logic:
- `all` chip (mapped is None) is active iff there is no `type` query
  param.
- Every other chip is active iff `type_filter` equals its `mapped`
  event_type.

### 2. Add `title` and `aria-pressed`

On each chip's `<a>`, add:

```jinja
title="{{ mapped or 'all event types' }}"
aria-pressed="{{ 'true' if _is_active else 'false' }}"
```

This:
- Shows a tooltip on hover naming the underlying event_type (covers
  AC3 in the design).
- Announces the chip's pressed state to screen readers.

### 3. Do NOT change the chip layout, label text, or URL shape

Renaming labels (`resolved` → `merge_auto_resolved`) is explicitly OUT
of scope per the Functional doc. Keep current labels.

### 4. Keep the rest of the template unchanged

The events table itself, pagination, and empty-state message are
unrelated to this fix.

## Project Conventions

- `dashboard/CLAUDE.md` — Tailwind classes are JIT-purged. Use class
  names that already appear in compiled CSS (`bg-primary`,
  `text-primary-foreground`, `border-primary`, `border-border`,
  `text-muted-foreground` all exist).
- Plain CSS is also acceptable to append to `dashboard/static/styles.css`
  (`make css` is broken; plain rules work as-is) — but you should not
  need new CSS for this fix.

## TDD Requirement

Frontend step — behavioural tests live in S03. For your own
pre-completion verification, run the existing dashboard tests to
confirm you haven't broken anything:

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

1. `make format`
2. `make typecheck`
3. `make lint` (includes `scripts/check_templates.py` Jinja2 validator)

## Test Verification (NON-NEGOTIABLE)

Targeted only:

```bash
uv run pytest tests/dashboard/test_auto_merge_routes.py -v
```

Do NOT run the full suite.

## Migration Verification

N/A.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "frontend-impl",
  "work_item": "I-00092",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["dashboard/templates/fragments/auto_merge_events_table.html"],
  "preflight": {"format": "ok|fixed|skipped:<reason>", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — template-only edit; behavioural tests live in S03",
  "blockers": [],
  "notes": ""
}
```
