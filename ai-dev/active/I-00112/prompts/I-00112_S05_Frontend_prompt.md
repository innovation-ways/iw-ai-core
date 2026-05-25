# I-00112_S05_Frontend_prompt

**Work Item**: I-00112 -- Keep-Alive Scheduler logs `status=success` for silent no-op CLI fires
**Step**: S05
**Agent**: Frontend

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers via pytest fixtures excepted. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. This step does NOT touch migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00112 --json`.
- `ai-dev/active/I-00112/I-00112_Issue_Design.md` — design document (read **AC4** for the UI contract, **Code Changes** for affected files).
- `ai-dev/active/I-00112/evidences/pre/I-00112-recent-executions-table.png` — pre-fix screenshot of the table you are extending.
- `dashboard/templates/fragments/keep_alive_runs.html` — current Recent Executions table fragment.
- `dashboard/templates/pages/system/keep_alive.html` — the parent page that includes the fragment.
- `dashboard/templates/_partials/help/keep_alive.html` — help text (only touch if it documents columns).
- `dashboard/routers/keep_alive.py` — confirm whether `get_recent_runs()` already exposes the new ORM fields to the template (likely yes — it returns ORM objects).
- S01 and S03 reports — confirm the new fields exist and are populated.

## Output Files

- `dashboard/templates/fragments/keep_alive_runs.html` — extended with **Elapsed** and **Output** columns.
- `dashboard/templates/_partials/help/keep_alive.html` — append a one-line note about the new columns and the stricter success contract (only if the file already documents columns; otherwise leave it).
- `dashboard/templates/pages/system/keep_alive.html` — touch only if a header label change is required (likely none — the fragment owns the table).
- `dashboard/routers/keep_alive.py` — touch only if `get_recent_runs` is not already exposing the fields (likely no touch).
- `dashboard/static/styles.css` — regenerate via `make css` ONLY if you introduced new Tailwind utility classes; commit the regenerated file alongside the template change. (See `dashboard/CLAUDE.md`: prebuilt Tailwind, fresh clones run without `make css`. Also CLAUDE.md root: if `make css` fails / is no-op, append plain CSS rules directly to `styles.css`.)
- `ai-dev/active/I-00112/reports/I-00112_S05_Frontend_report.md` — step report.

## Context

S01 added four new nullable columns (`stdout`, `stderr`, `elapsed_ms`, `returncode`) to `keep_alive_runs`. S03 now writes them on every run. The dashboard's Recent Executions table at `/system/keep-alive` still renders only `Fired At / Slot / Status`, so the operator cannot see the diagnostic detail even though it is in the DB. Your step adds two columns — **Elapsed** and **Output** — to the existing fragment so a suspicious fire can be triaged from the table alone.

Read `ai-dev/active/I-00112/I-00112_Issue_Design.md` first (especially **AC4** and **Browser Verification Test**). Then read `dashboard/CLAUDE.md` for Jinja2 + htmx + Tailwind conventions.

## Requirements

### 1. Extend `dashboard/templates/fragments/keep_alive_runs.html`

Add two new columns AFTER **Status**:

| New column | Source | NULL fallback |
|------------|--------|----------------|
| **Elapsed** | `{{ run.elapsed_ms }} ms` | `—` |
| **Output** | first ~80 chars of `run.stdout` with full string in a `title` attribute | `—` |

Skeleton (adjust to match the existing file's style exactly):

```html
<th class="px-4 py-2">Elapsed</th>
<th class="px-4 py-2">Output</th>
```

```html
<td class="px-4 py-2 font-mono text-xs whitespace-nowrap">
  {% if run.elapsed_ms is not none %}{{ run.elapsed_ms }} ms{% else %}—{% endif %}
</td>
<td class="px-4 py-2 text-xs">
  {% if run.stdout %}
    <span class="font-mono" title="{{ run.stdout|e }}">{{ run.stdout[:80] }}{% if run.stdout|length > 80 %}…{% endif %}</span>
  {% else %}
    —
  {% endif %}
</td>
```

Notes:
- Use `is not none` for `elapsed_ms` — `0 ms` is a legitimate value (timeout branch) and `{% if run.elapsed_ms %}` would render it as `—`.
- `run.stdout|e` escapes the title attribute. Without `|e`, a stdout containing `"` would break the HTML.
- Use Jinja2's built-in slice `[:80]` and `|length` — no Python `format`/`.format(...)` calls (see CLAUDE.md rule about `%`-style format filter, I-00075).
- Match the existing `text-xs` / `font-mono` style of the **Fired At** cell.

### 2. Verify `get_recent_runs` already exposes the new fields

In `dashboard/routers/keep_alive.py`, find the route that returns the runs fragment (likely `GET /api/keep-alive/runs`). The handler calls `get_recent_runs(db, limit=10)` from `orch.keep_alive_service`. That function returns `KeepAliveRun` ORM objects, which after S01 carry `stdout` / `stderr` / `elapsed_ms` / `returncode` attributes — no router change should be required. Verify by reading the handler; if it builds a list of dicts (rather than passing the ORM objects through), add the new fields to that dict, otherwise leave the router untouched.

### 3. Help-partial update (only if documenting columns)

Read `dashboard/templates/_partials/help/keep_alive.html`. If it documents the Recent Executions columns, append one line:

> The **Elapsed** and **Output** columns capture the actual CLI round-trip time and the model's reply, so you can verify a fire really anchored the usage window. A row is only labelled **Success** when the call returned a non-empty reply in ≥500 ms (I-00112).

If the help partial does NOT currently list columns, leave it untouched — adding column docs is out of scope.

### 4. CSS regeneration (only if new Tailwind classes were introduced)

The example template above uses `whitespace-nowrap` — that class is widely used in the repo so it is already in the prebuilt `dashboard/static/styles.css`. Verify with `grep -F whitespace-nowrap dashboard/static/styles.css` before reaching for `make css`. If you introduced a NEW Tailwind utility not already present, run:

```bash
make css
```

If `make css` reports "Nothing to be done" or the Tailwind toolchain fails (postcss-selector-parser missing — I-00067), append the equivalent plain CSS rules directly to `dashboard/static/styles.css`. Plain CSS is served as-is.

Commit `dashboard/static/styles.css` only if it actually changed.

### 5. Do NOT touch any other file

- **Do NOT** touch `orch/` (any backend file) — S03's scope.
- **Do NOT** touch migrations or models — S01's scope.
- **Do NOT** add or modify test files — S07's scope.

## Project Conventions

Read `dashboard/CLAUDE.md` and the root `CLAUDE.md` for:
- Routers are thin — business logic stays in `orch/`.
- Fragment templates MUST NOT extend `base.html`.
- htmx POSTs return HTML fragments that replace the `hx-target` element.
- Jinja2 `format`-filter calls MUST be `%`-style: `"%dm%02ds"|format(m, s)`. Never `str.format`-style — it raises `TypeError` at render only when real data hits the branch (I-00075).
- `noqa` codes must include the rule.

## TDD Requirement

This is a presentational change. No new behavioural test is owned by S05; S07 will add tests that drive the route. Use `tdd_red_evidence: "n/a — template + presentational changes only; behavioural coverage owned by S07"`.

If you find yourself implementing a regression test as part of S05 (e.g., a `tests/dashboard/test_keep_alive_recent_runs_columns.py`), STOP — that file belongs to S07.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

1. **`make format`** — auto-fixes formatting drift.
2. **`make typecheck`** — zero errors involving touched files. (Templates are not type-checked, but if you touched the router, mypy still runs against it.)
3. **`make lint`** — zero errors. `scripts/check_templates.py` runs as part of `make lint` and validates Jinja2 `format` filter usage.

## Test Verification

Run only:
```bash
uv run pytest tests/dashboard/ -v -k "keep_alive or recent_runs"
```

If existing dashboard tests for keep_alive assert on the **shape** of the rendered table (column count, specific headers), they will fail. Note them under `notes` — S07 will rewrite/extend them.

Do NOT run `make test-unit` / `make test-integration` / `make test-frontend` (the latter is S16's downstream gate).

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "Frontend",
  "work_item": "I-00112",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/templates/fragments/keep_alive_runs.html"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "<n> passed",
  "tdd_red_evidence": "n/a — template + presentational changes only; behavioural coverage owned by S07",
  "blockers": [],
  "notes": "Router required no changes (get_recent_runs already passes ORM objects to the template). Help partial: <touched/untouched>. styles.css: <regenerated/untouched>. NULL elapsed/stdout render as '—'."
}
```

## Lifecycle Commands

```bash
uv run iw step-start I-00112 --step S05
mkdir -p ai-dev/active/I-00112/reports
uv run iw step-done I-00112 --step S05 --report ai-dev/active/I-00112/reports/I-00112_S05_Frontend_report.md
```
