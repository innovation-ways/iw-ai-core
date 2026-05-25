# I-00112_S06_CodeReview_Frontend_prompt

**Work Item**: I-00112 -- Keep-Alive Scheduler logs `status=success` for silent no-op CLI fires
**Step Being Reviewed**: S05 (Frontend)
**Review Step**: S06

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers via pytest fixtures excepted.

## ⛔ Migrations: agents generate, daemon applies

Standard policy. S05 did not touch migrations.

## Input Files

- `uv run iw item-status I-00112 --json`.
- `ai-dev/active/I-00112/I-00112_Issue_Design.md` — design document (especially **AC4**, **Browser Verification Test**).
- `ai-dev/active/I-00112/reports/I-00112_S05_Frontend_report.md` — S05 step report.
- All files listed in S05's `files_changed`.
- `ai-dev/active/I-00112/evidences/pre/I-00112-recent-executions-table.png` — for visual reference.

## Output Files

- `ai-dev/active/I-00112/reports/I-00112_S06_CodeReview_report.md`.

## Context

You are reviewing S05 (Frontend). The step added **Elapsed** and **Output** columns to the Recent Executions fragment so the operator can audit silent no-op fires from the dashboard alone.

## Read the Design Document FIRST

- **AC4** — exact UI contract: two new columns (Elapsed, Output), NULL fallback to `—`, no crash.
- **Browser Verification Test** — S18 will exercise these. The template MUST match what S18 looks for.
- **Notes** — full stdout stored in DB, UI truncates to ~80 chars with hover.

No test files are expected in S05's `files_changed`. Any test file there is a CRITICAL scope violation.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

`make lint` runs `scripts/check_templates.py` — pay attention to any new Jinja2 `format` violation. NEW violations in S05's `files_changed` are CRITICAL.

## Review Checklist

### 1. Template correctness

- The fragment renders five `<th>`: `Fired At / Slot / Status / Elapsed / Output`. Missing column or wrong order is HIGH.
- NULL check on elapsed_ms uses `is not none` (NOT `{% if run.elapsed_ms %}`). The bare-truthy check renders `0 ms` as `—` (timeout branch produces ≈0 ms but is a legitimate captured value) — CRITICAL.
- `run.stdout` is HTML-escaped in the `title` attribute (`{{ run.stdout|e }}`). An unescaped stdout in `title` is **CRITICAL** (XSS-class — the model's reply could contain `"` or `</`).
- The cell body is also escaped (Jinja2's default autoescape handles `{{ run.stdout[:80] }}` — confirm autoescape is on at the template root).
- Truncation uses `[:80]` and the ellipsis `…` only when `|length > 80`. An always-trailing `…` is LOW.

### 2. Fragment rules

- The fragment file MUST NOT extend `base.html` (per `dashboard/CLAUDE.md`). Adding `{% extends … %}` to a fragment is CRITICAL.
- No inline `<script>` tags added — htmx is the interaction model.

### 3. Backend-isolation

- S05 did NOT touch `orch/` (no backend code change). Any `orch/` file in `files_changed` is CRITICAL scope violation.
- Router touched ONLY if `get_recent_runs` was building dicts rather than passing ORM objects (rare). Verify against the file in HEAD.

### 4. Tailwind / CSS

- New Tailwind classes only if they already exist in `dashboard/static/styles.css`. If S05 used a new class (e.g., `xs:whitespace-pre-wrap`), either `make css` was rerun (and `styles.css` is in `files_changed`) or plain CSS rules were appended (and `styles.css` is in `files_changed`). Neither → MEDIUM (fixable): visual breakage on fresh clones.
- Dynamic class construction (`class="text-{{ color }}-500"`) is HIGH — breaks Tailwind JIT purging (per dashboard/CLAUDE.md).

### 5. Jinja2 format-filter rule (I-00075)

- Any `format` filter call uses `%`-style (`"%dm%02ds"|format(m, s)`), never `{}`/`str.format` style. A new `{}` form is CRITICAL — `make lint` would catch it but worth a manual sweep.

### 6. Help partial / styles.css discipline

- If S05 touched `_partials/help/keep_alive.html`, the added text reads naturally and references I-00112. If it touched the partial but the partial does NOT document columns elsewhere, that is MEDIUM (suggestion): out of S05's intended scope.
- If `dashboard/static/styles.css` is in `files_changed`, the diff is purely additive (Tailwind-regenerated output OR appended plain rules). A full file rewrite is MEDIUM (fixable).

### 7. NULL-tolerance manual check

- Open `/system/keep-alive` against pre-fix DB rows (rows with NULL stdout/elapsed_ms — every row before this fix). Verify the template renders `—` for both new columns without raising. If you cannot test this locally, reason about it from the template source: any `{{ run.stdout[:80] }}` evaluated against `None` would raise `TypeError` — confirm the `{% if run.stdout %}` guard precedes the slice.

## Test Verification (NON-NEGOTIABLE)

Run:
```bash
uv run pytest tests/dashboard/ -v -k "keep_alive or recent_runs"
```

Tests that previously asserted on the three-column shape will fail — note them as expected RED (S07 will extend them). Tests that pass against the new five-column shape are existing tests S05 did NOT break.

Do NOT run `make test-unit` / `make test-integration` / `make test-frontend` — those are S16/S17 gates.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | XSS-class unescaped title, fragment extends base, scope violation, missing NULL guard on stdout |
| **HIGH** | Wrong column order, truthy elapsed_ms check (renders 0 ms as —), dynamic class construction, `{}` format-filter |
| **MEDIUM (fixable)** | styles.css missing when new Tailwind class added, full file rewrite |
| **MEDIUM (suggestion)** | Help partial touched but out of S05 scope |
| **LOW** | Always-trailing ellipsis, style nits |

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "I-00112",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "<n> passed, <m> failed (shape-asserting tests; expected — S07 will extend)",
  "notes": ""
}
```

## Lifecycle Commands

```bash
uv run iw step-start I-00112 --step S06
uv run iw step-done I-00112 --step S06 --report ai-dev/active/I-00112/reports/I-00112_S06_CodeReview_report.md
```
