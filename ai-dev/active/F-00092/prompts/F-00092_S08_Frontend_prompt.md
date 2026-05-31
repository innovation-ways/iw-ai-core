# F-00092_S08_Frontend_prompt

**Work Item**: F-00092 — Tier-1 orchestration DB backups
**Step**: S08
**Agent**: frontend-impl

---

## ⛔ Docker is off-limits

Read-only Docker introspection only.

## ⛔ Migrations: agents generate, daemon applies

No migrations in this step.

## Input Files

- `uv run iw item-status F-00092 --json`.
- `ai-dev/active/F-00092/F-00092_Feature_Design.md` — **Frontend Changes**, AC6.
- `orch/jobs/aggregator.py` — how the unified jobs view aggregates job sources.
- `dashboard/routers/jobs_ui.py` + its Jinja2 template(s) — how rows render.
- S01 report — `DbBackupJob` columns.

## Output Files

- `ai-dev/active/F-00092/reports/F-00092_S08_Frontend_report.md`.

## Context

Surface `DbBackupJob` records in the existing unified Jobs view, alongside the
other background jobs. This project's dashboard is server-rendered (Jinja2 + htmx).

## Requirements

### 1. Aggregator (`orch/jobs/aggregator.py`)

Add `DbBackupJob` as a source so backup jobs appear in the unified job list, mapped
to the same unified shape the other job sources use (id, kind/type label, status,
created/updated timestamps, a human label — e.g. type `db_backup`, showing
scheduled/manual + label). Follow the existing pattern for the other job models
exactly.

### 2. Jobs UI (`dashboard/routers/jobs_ui.py` + template)

Ensure backup jobs render correctly in the jobs table (status badge, timestamp, a
sensible label/description). Reuse existing row rendering; only extend where a new
job kind needs a display string or icon.

Hard rules:
- **Jinja2 `format` filter must be `%`-style**: `"%dm%02ds"|format(m, s)`, never
  `str.format`-style (raises `TypeError` at render — enforced by `make lint`).
- Append any plain CSS directly to `dashboard/static/styles.css` if `make css`
  reports nothing to do (per CLAUDE.md).
- No new JSON API endpoint is required.

The render assertion test (`tests/dashboard/`) is authored in S11; design the
mapping so a `DbBackupJob` row renders deterministically.

## Project Conventions

Read `CLAUDE.md` (Dashboard) and `dashboard/CLAUDE.md`. Match existing aggregator
mapping + template patterns.

## TDD Requirement

The dashboard render test is in S11. For this step, manually confirm the view
renders with a seeded backup job (or via a quick targeted check) and note it.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

`make format`, `make typecheck`, `make lint` (lint includes template checks).

## Test Verification (NON-NEGOTIABLE)

Targeted only. Do not run the full suite.

## Subagent Result Contract

```json
{
  "step": "S08",
  "agent": "frontend-impl",
  "work_item": "F-00092",
  "completion_status": "complete",
  "files_changed": ["orch/jobs/aggregator.py", "dashboard/routers/jobs_ui.py", "dashboard/templates/..."],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "targeted render check ok",
  "tdd_red_evidence": "n/a — UI surfacing; render test in S11",
  "blockers": [],
  "notes": ""
}
```
