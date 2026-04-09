# CR-00002 S02: Code Review — Backend sort logic

## Review Scope

Review ALL changes made in S01 (backend sort logic in `dashboard/routers/project_pages.py`).

## Review Checklist

1. **Correctness**: Do all 6 sort columns map to valid SQLAlchemy expressions?
2. **Security**: Is the `sort_by` whitelist enforced? No user input should reach `order_by()` without validation.
3. **NULL handling**: Does duration/completed_at sorting handle NULL values correctly?
4. **Defaults**: Are fallback defaults applied for invalid params?
5. **Backward compatibility**: Does the page render identically when no sort params are provided?
6. **Type safety**: Do the new params have correct type annotations? Does mypy pass?
7. **Style**: Line length ≤ 100 (ruff), consistent with existing code patterns.

## What to Check

- `dashboard/routers/project_pages.py` — all changes
- Run `ruff check dashboard/routers/project_pages.py`
- Run `mypy dashboard/routers/project_pages.py`
