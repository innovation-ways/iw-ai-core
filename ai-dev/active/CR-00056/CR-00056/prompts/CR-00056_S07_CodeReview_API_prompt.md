# CR-00056_S07_CodeReview_API_prompt

**Work Item**: CR-00056 -- Surface step prompts in dashboard (Prompt column + modal viewer)
**Step Being Reviewed**: S06 (api-impl)
**Review Step**: S07

---

## ⛔ Docker is off-limits / Migrations: agents generate, daemon applies

Standard policies.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00056 --json`
- `ai-dev/active/CR-00056/CR-00056_CR_Design.md` — focus on `AC4`, `AC5`, `AC7`, `AC9`
- `ai-dev/work/CR-00056/reports/CR-00056_S06_API_report.md`
- All files in S06 `files_changed`
- `dashboard/CLAUDE.md` — fragment template rules

## Output Files

- `ai-dev/work/CR-00056/reports/CR-00056_S07_CodeReview_report.md`

## Context

S06 added the new route `GET /project/{pid}/item/{iid}/step/{step_id}/prompt-modal`, extended `StepDetail.has_prompt`, and created a placeholder fragment template.

## Read the Design Document FIRST

- `AC4` — Prompt column with View button (driven by `has_prompt`)
- `AC5` — modal opens, returns 200 with correct structure
- `AC7` — sections for initial + fix-cycle prompts
- `AC9` — 404 on project/item mismatch (not 403, not 500)

## Pre-Review Lint & Format Gate

```bash
make lint
make format
```

NEW violations → CRITICAL.

## Review Checklist

### 1. Architecture Compliance

- Route is defined on the existing `router` in `dashboard/routers/items.py` (mounted under `/project/{project_id}`) — confirm by reading router definition.
- Fragment template does NOT extend `base.html` — open the template, confirm no `{% extends "base.html" %}`.
- `has_prompt` is added to `StepDetail`, not elsewhere. The field has a sensible default (`False`).

### 2. Code Quality

- Route uses `Depends(get_db)` for the session.
- 404 cases use `HTTPException(status_code=404)`, not bare `Response(status_code=404)`.
- Sections list construction handles edge cases:
  - No StepRuns → 404
  - StepRuns exist but all have prompt_text=NULL and fix_prompt_text=NULL → 404
  - First StepRun has prompt_text=NULL but later ones have fix_prompt_text → still useful; the modal should render the fix sections.
  - Multiple fix cycles → all shown, in chronological order.
- Cycle numbering: confirm cycle N for a retry StepRun matches the `FixCycle.cycle_number` for that fix cycle, OR matches `run_number - 1`. Whichever S06 chose, it must be consistent so the UI label is accurate.

### 3. Project Conventions

- Match sibling route patterns in `dashboard/routers/items.py` (signature, return type, `templates.TemplateResponse(...)` shape).
- Routers are thin — the aggregation logic for sections is acceptable inline (small enough). If it grew >40 lines, factor it out.

### 4. Performance

- `has_prompt` population in `_get_steps()` must NOT cause N+1 queries. Acceptable patterns: single aggregate subquery, or Python-side check over already-fetched StepRuns. **CRITICAL** if there's a `db.query(StepRun).filter(...)` inside a `for step in steps` loop.

### 5. Security

- `project_id` is part of every WHERE clause — no info leak across projects. Verify by reading the query.
- Prompt text is rendered through Jinja's default autoescape — confirm the template does NOT use `|safe` on the prompt content (XSS risk if a malicious prompt contains `<script>`).

### 6. Testing

- A new test file `tests/dashboard/test_prompt_modal_route.py` exists with at least one happy-path test.
- The test uses `TestClient` (not real HTTP).
- No live-DB writes.

### 5a. TDD RED Evidence

- API steps add new endpoints — confirm `tdd_red_evidence` shows the test failing with a 404 or AssertionError before the implementation. An import error is NOT valid RED.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/dashboard/test_prompt_modal_route.py -v
```

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview",
  "work_item": "CR-00056",
  "step_reviewed": "S06",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
