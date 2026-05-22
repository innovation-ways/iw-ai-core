# CR-00077_S02_CodeReview_prompt

**Work Item**: CR-00077 -- Overlap details popup (read-only)
**Step**: S02
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits
(Standard policy.)

## ⛔ Migrations: agents generate, daemon applies
This CR adds no migrations. Flag any migration file as a CRITICAL finding.

## Input Files

- `ai-dev/active/CR-00077/CR-00077_CR_Design.md`
- `ai-dev/active/CR-00077/reports/CR-00077_S01_API_report.md`
- The S01 diff (read with `git diff HEAD~..HEAD -- dashboard/routers/batches.py` or equivalent)

## Output Files

- `ai-dev/active/CR-00077/reports/CR-00077_S02_CodeReview_report.md` — findings with severities.

## Scope of Review

Per-agent review of S01's API endpoint + grouping helper. Check:

1. **Endpoint contract** (AC1, AC5):
   - URL: `GET /project/{project_id}/batch/{batch_id}/overlap/{held_item_id}`.
   - 200 on success, **404** (not 200, not 500) when no recent event.
   - Read-only — no `db.add(...)`, `db.commit()`, `db.flush()`, no `SELECT FOR UPDATE`.

2. **Query window**:
   - Uses the same 300s window as `_get_scope_statuses`. If S01 introduced a second hardcoded literal, flag as MAJOR with a refactor suggestion.

3. **Grouping helper** (`group_overlap_events`):
   - Pure (no DB, no logging side effects, no `datetime.now()` calls).
   - Most-recent-wins on duplicate `blocking_item_id`s.
   - Insertion order across distinct blocking items preserved.
   - Defensive on missing `event_metadata` keys.
   - Importable from `tests/unit/` (no FastAPI/dashboard runtime dependency in its signature).

4. **Jinja safety**:
   - The endpoint passes the globs list to the template. Verify Jinja autoescape is on for `.html` templates (the dashboard default). A glob like `dashboard/templates/**` must not break HTML rendering.

5. **Fragment discipline**:
   - The new template path is `dashboard/templates/fragments/batch_overlap_modal.html`. Per `dashboard/CLAUDE.md`, fragment templates must NOT extend `base.html`. If S01 created a stub, confirm the stub does not extend `base.html`.

6. **Router hygiene**:
   - The route is mounted on the existing `batches` router. No new router module created.
   - The handler is thin (delegates to the helper); business logic does not creep into the route.

7. **Type hints**:
   - The helper's signature has explicit types (no `Any` leakage).
   - The route handler returns `TemplateResponse`.

8. **Items-fragment context** (regression guard for the S03 trigger):
   - `batch_items_fragment` (`GET /batch/{batch_id}/fragment/items`) now passes
     `batch` in its `TemplateResponse` context. If S01 omitted this, flag as
     **HIGH** — the S03 trigger's `hx-get` URL would lose its `batch_id` after the
     first htmx Items-tab refresh.
   - The change is context-only: the endpoint's URL, status code, and response
     shape are unchanged. If S01 altered any of those, flag as MAJOR.

## Severity Guide

- CRITICAL: contract violation (wrong status code, DB write), schema drift, security issue.
- HIGH: incorrect grouping, missing 404 path, Jinja escape issue.
- MEDIUM: code duplication (e.g. hardcoded 300s), missing type hints.
- LOW: naming, docstring polish.

## Pre-flight Quality Gates

Run `make lint` and `make format-check` on the touched files before completing your review (the review itself does not edit code, but verify the gates would still pass).

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00077",
  "completion_status": "complete",
  "files_changed": [],
  "preflight": {"format": "ok", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "review-only step",
  "tdd_red_evidence": "n/a — review step, no behavioural tests added",
  "blockers": [],
  "notes": "<count of CRITICAL/HIGH/MEDIUM/LOW findings>"
}
```
