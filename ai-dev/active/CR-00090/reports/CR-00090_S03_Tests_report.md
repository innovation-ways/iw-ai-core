# CR-00090 S03 Tests Report

**Work Item**: CR-00090 — Fix E2E Polling Suppression — Replace UA Sniffing with IW_CORE_E2E_MODE Env Var
**Step**: S03
**Agent**: tests-impl
**Status**: ✅ complete

---

## Summary

Added test coverage for CR-00090:
- Verified `tests/unit/test_config.py` — S01 already covered all required `get_e2e_mode()` cases
- Created `tests/dashboard/test_e2e_mode.py` — new dashboard tests for AC1, AC2, and AC5

---

## Files Changed

| File | Change |
|------|--------|
| `tests/dashboard/test_e2e_mode.py` | **New** — 7 tests covering AC1, AC2, AC5 |
| `tests/unit/test_config.py` | No changes needed — S01 already covered all required cases (8 parametrized + 1 absent) |

---

## Test Coverage

### Unit Tests (`tests/unit/test_config.py`) — S01 already complete

S01 added 9 parametrized tests for `get_e2e_mode()` covering:

| Value | Expected |
|-------|----------|
| `"true"` | `True` |
| `"1"` | `True` |
| `"TRUE"` | `True` |
| `"True"` | `True` |
| `""` (empty) | `False` |
| `"false"` | `False` |
| `"0"` | `False` |
| `"anything"` | `False` |
| absent (env var not set) | `False` |

All 9 pass — no gaps found.

### Dashboard Tests (`tests/dashboard/test_e2e_mode.py`) — New

7 new tests in 3 classes:

**`TestWorktreeBadgeE2eMode`** (base.html sidebar worktree badge):
- `test_polling_suppressed_when_e2e_mode_true` — AC1: `hx-trigger="never"` present, `hx-get` absent
- `test_polling_present_when_e2e_mode_off` — AC2: `hx-trigger="never"` absent, `hx-get` present

**`TestStalenessDotE2eMode`** (staleness_dot.html fragment):
- `test_staleness_dot_suppresses_polling_when_e2e_mode_true` — AC1: `hx-trigger="never"` present, `hx-get` absent
- `test_staleness_dot_polls_when_e2e_mode_off` — AC2: `hx-trigger="every 15s"` present, `hx-get` present
- `test_staleness_dot_renders_dot_class_when_e2e_mode_true` — Visual indicator preserved; only polling suppressed

**`TestE2eModeGlobalPresent`** (AC5 — `_e2e_mode` global):
- `test_e2e_mode_global_usable_in_sidebar_when_e2e_true` — 200 response + `hx-trigger="never"` confirms global is usable
- `test_e2e_mode_global_usable_in_sidebar_when_e2e_false` — 200 response + `hx-get` present confirms global is usable

---

## Key Implementation Finding

Discovered that the staleness router creates its own module-level `Jinja2Templates` instance at import time (separate from `create_app()`'s instance). Both instances need `_e2e_mode` injected. Solution: set the env var before `create_app()` AND patch `staleness_mod.templates.env.globals["_e2e_mode"]` after app creation.

```python
# In fixture:
monkeypatch.setenv("IW_CORE_E2E_MODE", "true")   # BEFORE create_app()
app = create_app()
# ...
from dashboard.routers import staleness as staleness_mod
staleness_mod.templates.env.globals["_e2e_mode"] = get_e2e_mode()
```

---

## Test Results

```
$ uv run pytest tests/unit/test_config.py -v -k "e2e" --no-cov -q
9 passed, 21 deselected in 0.26s

$ uv run pytest tests/dashboard/test_e2e_mode.py -v --no-cov -q
7 passed in 7.79s
```

---

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | ✅ `uv run ruff format --check .` — 944 files already formatted |
| `make typecheck` | ✅ `uv run mypy orch/ dashboard/` — 0 errors in 281 source files |
| `make lint` | ✅ `uv run ruff check .` — All checks passed |

---

## Notes

- No changes to `tests/unit/test_config.py` were needed — S01's parametrized test already covers all required cases including the "absent env var" case.
- ERA001 violations in comments (`# -- text` format) were resolved by removing the multi-line block comments that preceded each test class, since the class docstring already describes the section's purpose.
- The `Project` type annotation fix (`"Project"` → `Project`) resolved 3 mypy errors.
