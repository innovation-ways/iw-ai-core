# F-00062_S10_CodeReview_prompt

**Work Item**: F-00062 -- Per-worktree container isolation for parallel AI-agent development
**Step Being Reviewed**: S09 (frontend-impl)
**Review Step**: S10

---

## ⛔ Docker is off-limits

S09 added read-only `docker ps` enrichment and POST handlers that call `worktree_compose.down()`. Verify NO new state-changing docker subprocess calls were added in `dashboard/routers/`. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No alembic execution against live orch DB. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- Design doc (AC10), S01-S09 reports
- `dashboard/routers/worktrees.py` (modified)
- `dashboard/templates/pages/system/worktrees.html` (modified)
- `dashboard/templates/fragments/worktree_table.html` (modified)
- `tests/dashboard/test_worktrees_view.py` (new/modified)

## Output Files

- `ai-dev/active/F-00062/reports/F-00062_S10_CodeReview_report.md`

## Context

You are reviewing the dashboard extension for the Worktree Health view. Risks: N+1 docker calls per page load, missing CSRF on POST handlers, broken htmx fragments, JS regressions caught by `make lint`.

## Review Checklist

### 1. Performance
- `_collect_worktrees` issues at most ONE `docker ps` call per page render (label-filtered once, then a map lookup per row). Reject N+1 patterns.
- `is_alive`-per-row is forbidden — verify the implementation aggregates.

### 2. Route handlers
- POST handlers follow the existing CSRF / auth pattern (look at other POST handlers in `dashboard/routers/`)
- Force teardown endpoint validates `batch_item_id` exists before calling `down()`; orphan teardown reads labels safely (no shell injection from container_id)
- Logs stream endpoint caps duration (≤60s) to prevent runaway connections
- Logs endpoint uses `docker logs --since=...` or `--tail=...` to bound output

### 3. Template correctness
- New columns render for ALL row types (active, legacy, orphan) — orphan rows render even when their BatchItem fields are missing
- Open link is omitted when `app_port is None` (no broken `http://localhost:None/`)
- htmx attributes are syntactically correct
- Orphan row CSS class is applied conditionally
- Reuse of existing CSS classes (no unnecessary new files)

### 4. JS linting
- `make lint` (which includes `node --check` on `dashboard/static/**/*.js`) passes
- No new JS file unless absolutely necessary

### 5. Tests
- Three tests from S09's "Tests" section exist and pass
- Tests use the existing dashboard test client patterns (no new test infrastructure)

### 6. Project conventions
- Read `CLAUDE.md` and `dashboard/CLAUDE.md`
- htmx + Jinja2 (no new SPA framework)
- SSE for streaming logs matches the daemon-events feed pattern

### 7. Accessibility / UX
- Table column headers are clear (e.g., "DB :Port", not abbreviated to "DBP")
- Action icons have `title=` or `aria-label=`
- Force teardown has `hx-confirm` to prevent fat-finger destructive actions
- Orphan rows are visually distinguishable (color/badge)

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass
2. `make lint` — pass (JS lint included)
3. Manually open `/worktrees` in your worktree's dashboard if the dev environment is up; confirm rendering is sane

## Severity Levels

| Severity | Examples |
|----------|----------|
| CRITICAL | New state-changing docker call in dashboard code; force-teardown missing auth/CSRF; logs endpoint enables shell injection |
| HIGH | N+1 docker calls; broken htmx; orphan rows don't render; legacy items break the page |
| MEDIUM_FIXABLE | Missing aria-label; missing hx-confirm; missing test |
| MEDIUM_SUGGESTION | Reuse opportunity; clearer column heading |
| LOW | Style |

## Review Result Contract

```json
{
  "step": "S10",
  "agent": "code-review-impl",
  "work_item": "F-00062",
  "step_reviewed": "S09",
  "verdict": "pass|fail",
  "findings": [...],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
