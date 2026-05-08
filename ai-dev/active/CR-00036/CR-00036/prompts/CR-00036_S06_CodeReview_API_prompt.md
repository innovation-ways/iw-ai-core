# CR-00036_S06_CodeReview_prompt

**Work Item**: CR-00036 -- Batch-level auto_merge toggle with operator-approved manual merge
**Step Being Reviewed**: S05 (api-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/CR-00036/CR-00036_CR_Design.md`
- `ai-dev/work/CR-00036/reports/CR-00036_S05_API_report.md`
- All files listed in S05's `files_changed`.

## Output Files

- `ai-dev/work/CR-00036/reports/CR-00036_S06_CodeReview_report.md`

## Context

You are reviewing the FastAPI route additions for CR-00036: `approve-merge`, `update_batch_auto_merge`, and the create-batch-from-selection extension.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations on changed files → CRITICAL findings under `category: conventions`.

## Review Checklist

### 1. Route correctness

- `approve-merge` URL pattern matches sibling `restart-merge` (`/actions/item/{item_id}/approve-merge`).
- HTTP methods are `POST` for state changes.
- Routes are registered (verify by reading `dashboard/app.py` if needed).

### 2. Status code semantics

- 404 on missing item / batch.
- 409 on wrong-state transition (already-merged item, batch in `executing`).
- 200/204 on success with `_action_response` toast.
- No 500 on operator errors.

### 3. Form parsing

- Checkbox handling honors the htmx convention: missing key → `False`. Misimplementing this turns "uncheck" into a no-op.
- No silent acceptance of arbitrary string values.

### 4. Service delegation

- `approve-merge` delegates to `orch.services.batch_item_approval.approve_merge` — does NOT replicate the status-check or DaemonEvent emission inline.
- `update_batch_auto_merge` performs only the status precondition + assignment; no other state manipulation.
- No new business logic in the router (per `dashboard/CLAUDE.md`).

### 5. SSE / refresh wiring

- `approve-merge` triggers item-overview re-render via existing SSE event.
- `update_batch_auto_merge` triggers batch-header re-render via existing event.
- No new SSE channels are added.

### 6. Auth / authorization

- Routes follow the same auth model as sibling routes (`restart-merge`, `update_batch_max_parallel`). No new gate, no removed check.

### 7. Create-batch-from-selection

- The form field is optional and falls back to project default.
- The hardcoded `auto_publish=False` is left untouched (out of scope).
- The `Batch(...)` constructor receives the resolved `auto_merge` value.

### 8. Tests

- Coverage matches the test list in S05's prompt.
- Integration tests use `db_session` fixture (testcontainer), not the live DB.

## Test Verification (NON-NEGOTIABLE)

`make test-unit` and `make test-integration` MUST pass.

## Severity Levels

| Severity | Examples |
|----------|----------|
| CRITICAL | Route missing/registered under wrong path; checkbox handling silently drops "uncheck" updates |
| HIGH | Wrong status code on rejection; missing project precondition; route bypasses service layer |
| MEDIUM (fixable) | Missing test, weak error message, doc drift |
| LOW | Nitpick |

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "CR-00036",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
