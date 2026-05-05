# I-00069 S01 Backend Report

**Step**: S01 — Backend Implementation
**Agent**: backend-impl
**Work Item**: I-00069 — Downgrade LiveDbConnectionRefusedError to DEBUG/WARNING in test context
**Date**: 2026-05-05

---

## What Was Done

Modified `dashboard/app.py` to narrow the exception handling around the alembic-guard startup probe (lines 147–160). The change adds a specific `except LiveDbConnectionRefusedError` branch that:

1. **In test context** (`IW_CORE_TEST_CONTEXT=true`): logs at `DEBUG` with a single-line message, no traceback.
2. **In non-test context** (daemon/operator): logs at `WARNING` with a single-line message, no traceback.
3. **All other exceptions**: keeps the existing `logger.exception(...)` path at `ERROR` with full traceback (preserving loudness for genuine boot failures).

`app.state.alembic_guard_status = None` is set in all branches, preserving the existing contract.

---

## Files Changed

| File | Change |
|------|--------|
| `dashboard/app.py` | Added `LiveDbConnectionRefusedError` import; added `except LiveDbConnectionRefusedError` branch before the generic `except Exception` |

---

## Import Change

```python
# Added to imports (line 57):
from orch.db.live_db_guard import LiveDbConnectionRefusedError
```

Imports are sorted alphabetically within their group per project conventions.

---

## Code Change (lines 147–160)

```python
    try:
        app.state.alembic_guard_status = check_db_at_head()
    except LiveDbConnectionRefusedError as exc:
        # Guard refused — expected in test context (R0 guard doing its job).
        if os.environ.get("IW_CORE_TEST_CONTEXT") == "true":
            logger.debug(
                "alembic guard skipped: live DB connection refused under IW_CORE_TEST_CONTEXT=true"
            )
        else:
            logger.warning("alembic guard skipped: live DB connection refused: %s", exc)
        app.state.alembic_guard_status = None
    except Exception:  # noqa: BLE001
        logger.exception("alembic guard check failed at startup; continuing")
        app.state.alembic_guard_status = None
```

---

## Preflight Results

| Command | Result |
|---------|--------|
| `make format` | `ok` — 610 files already formatted |
| `make typecheck` | `ok` — `Success: no issues found in 224 source files` |
| `make lint` | `ok` — `All checks passed!` |

---

## Test Results

- **Unit tests**: 2579 passed, 2 pre-existing failures (unrelated to this change — `test_safe_migrate.py::TestApply::test_apply_refuses_in_agent_context` and `test_rollback_refuses_in_agent_context`; confirmed pre-existing via git stash)
- **Pre-existing failures**: 0 new failures introduced by this change

The 2 failing tests in `test_safe_migrate.py` are environment-related failures that existed before this change (verified by stashing changes and re-running).

---

## Notes

- The fix follows the TDD approach: RED confirmed via understanding of the existing bare `except Exception` → GREEN via the minimal exception-narrowing change → REFACTOR not needed.
- No helper functions, no refactoring of surrounding code.
- The `LiveDbConnectionRefusedError` import is placed after `orch.db.alembic_guard` and before `orch.db.identity` to maintain alphabetical ordering within the `orch.db.*` imports.
- The comment `# Guard refused — expected in test context (R0 guard doing its job).` explains the "why" which is non-obvious.