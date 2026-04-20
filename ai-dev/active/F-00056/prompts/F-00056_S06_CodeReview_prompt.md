# F-00056_S06_CodeReview_prompt

**Work Item**: F-00056 -- Work Item Execution Report — Retry Pattern & Pain-Point Visibility
**Step Being Reviewed**: S05 (api-impl)
**Review Step**: S06

---

## Input Files

- `ai-dev/active/F-00056/F-00056_Feature_Design.md` -- Design document (API Changes, AC2, AC8, AC10, Invariants 6, 7)
- `ai-dev/active/F-00056/reports/F-00056_S05_API_report.md`
- `dashboard/routers/items.py` — the two new routes

## Output Files

- `ai-dev/active/F-00056/reports/F-00056_S06_CodeReview_report.md`

## Review Checklist

### 1. Architecture Compliance

- The two new route functions match the exact signature and style of `item_tab_fix_cycles` and `item_tab_reports` (FastAPI dependencies, session injection, return type).
- The tab route returns a bare HTML fragment; the standalone page wraps via `base.html`. Verify which template each renders.
- Both routes delegate to `assemble_execution_report` — no inline DB assembly logic in the router.

### 2. Code Quality

- 404 handling matches sibling routes' pattern (same helper or same exception).
- No duplication between the two handlers beyond what sibling pairs already duplicate; DRY only where siblings are DRY.
- No error-swallowing try/except that masks 500s.

### 3. Project Conventions

- Read `dashboard/CLAUDE.md`.
- Route path format, parameter naming, and response class match siblings.

### 4. Security

- No unsafe template rendering paths (e.g., passing raw `error_message` into a context that bypasses Jinja autoescape).
- No auth bypass — sibling routes' auth pattern (if any) is mirrored.

### 5. Testing

- At least one integration test asserts HTTP 200 for a seeded item on both routes, HTTP 404 for an unknown item. S09 adds more, but a minimal smoke test is expected at this step.

### 6. No-regression (Invariant 7)

- No edits to existing `item_tab_*` functions, existing templates (beyond what S07 handles), or router registration code unless strictly necessary. Flag any existing-code diffs.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit`
2. `make test-integration`
3. `uv run ruff check dashboard/`
4. `uv run mypy dashboard/`

## Review Result Contract

Standard JSON. `verdict=pass` only if zero CRITICAL + zero HIGH + zero MEDIUM_FIXABLE.
