# CR-00090 S01 Backend Report

## Work Item
CR-00090 — Fix E2E Polling Suppression — Replace UA Sniffing with IW_CORE_E2E_MODE Env Var

## Step
S01 — Backend Implementation

## Agent
backend-impl

---

## Summary

Implemented the backend half of CR-00090: added `get_e2e_mode()` to `orch/config.py` and injected `_e2e_mode` into the global Jinja2 template context in `dashboard/app.py`.

---

## Files Changed

| File | Change |
|------|--------|
| `orch/config.py` | Added `get_e2e_mode() -> bool` function; added to `__all__` export list |
| `dashboard/app.py` | Imported `get_e2e_mode` from `orch.config`; assigned to `templates.env.globals["_e2e_mode"]` |
| `tests/unit/test_config.py` | Added `test_get_e2e_mode_truthy_values` (parametrized, 8 cases) and `test_get_e2e_mode_absent` |

---

## TDD Evidence

### RED Phase
```
$ uv run pytest tests/unit/test_config.py -v -k "e2e"

AttributeError: module 'orch.config' has no attribute 'get_e2e_mode'
```
All 9 test cases failed with `AttributeError` — as expected before the implementation existed.

### GREEN Phase
```
$ uv run pytest tests/unit/test_config.py -v -k "e2e"

tests/unit/test_config.py::test_get_e2e_mode_truthy_values[TRUE-True] PASSED
tests/unit/test_config.py::test_get_e2e_mode_absent PASSED
tests/unit/test_config.py::test_get_e2e_mode_truthy_values[false-False] PASSED
tests/unit/test_config.py::test_get_e2e_mode_truthy_values[-False] PASSED
tests/unit/test_config.py::test_get_e2e_mode_truthy_values[1-True] PASSED
tests/unit/test_config.py::test_get_e2e_mode_truthy_values[True-True] PASSED
tests/unit/test_config.py::test_get_e2e_mode_truthy_values[0-False] PASSED
tests/unit/test_config.py::test_get_e2e_mode_truthy_values[true-True] PASSED
tests/unit/test_config.py::test_get_e2e_mode_truthy_values[anything-False] PASSED

9 passed, 21 deselected in 0.23s
```

---

## Implementation Details

### `orch/config.py` — `get_e2e_mode()`

```python
def get_e2e_mode() -> bool:
    """Return True when IW_CORE_E2E_MODE is set to a truthy value ('1' or 'true', case-insensitive).

    Used by the dashboard to suppress HTMX polling in E2E verification containers.
    Reads the env var at call time (not import time) so tests can monkeypatch it.
    """
    return os.environ.get("IW_CORE_E2E_MODE", "").lower() in ("1", "true")
```

- Values `"true"`, `"1"`, `"TRUE"`, `"True"` → `True`
- Absent, empty, `"false"`, `"0"`, or any other value → `False`
- Reads `os.environ` at call time — safe for `monkeypatch.setenv()` tests (no `importlib.reload` used)
- Exported via `__all__`

### `dashboard/app.py` — `_e2e_mode` global injection

```python
from orch.config import get_e2e_mode

templates.env.globals["_e2e_mode"] = get_e2e_mode()
```

Injected at app construction time (not per-request), immediately after `static_v`. This makes `_e2e_mode` available in every Jinja2 template without requiring each route handler to pass it explicitly.

---

## Pre-flight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ `uv run ruff format --check .` — 943 files already formatted |
| `make typecheck` | ✅ `uv run mypy orch/ dashboard/` — Success: no issues found in 281 source files |
| `make lint` | ✅ `uv run python scripts/check_templates.py` + `uv run ruff check .` — All checks passed! |

---

## Test Results

```
$ uv run pytest tests/unit/test_config.py -v -k "e2e"
9 passed, 21 deselected in 0.23s
```

---

## Notes

- No migration needed (confirmed by design doc §"No migration required")
- The `__all__` list in `orch/config.py` was updated to include `get_e2e_mode` so it is publicly exported alongside the other `get_*()` functions
- The injection point in `dashboard/app.py` (after `static_v`, before `app.state.templates = templates`) ensures the global is available on all `TemplateResponse` renders
- `S02` (frontend-impl) will update templates to OR `_e2e_mode` with the existing UA heuristic: `{% set _headless = _e2e_mode or ('headlesschrome' in _ua) or ('playwright' in _ua) %}`
