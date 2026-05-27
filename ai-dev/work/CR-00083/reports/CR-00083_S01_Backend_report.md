# CR-00083 S01 Backend Report

**Work Item**: CR-00083 — Performance-budget test layer (pytest-benchmark assertions with regression-alert baselines)
**Step**: S01
**Agent**: backend-impl
**Status**: ✅ Complete

---

## What Was Done

Added the `pytest-benchmark` dependency and registered the `perf` marker in `pyproject.toml`, so perf tests are excluded from default `make test-unit` / `make test-integration` runs.

### Changes

| File | Change |
|------|--------|
| `pyproject.toml` | Added `pytest-benchmark>=4.0,<5` to `[dependency-groups] dev`; added `perf` marker description to `markers`; appended `and not perf` to `addopts` |

### `uv.lock` regenerated

```
uv lock
Resolved 202 packages in 404ms
Added py-cpuinfo v9.0.0
Added pytest-benchmark v4.0.0
```

Import verification: `uv run python -c "import pytest_benchmark"` → `OK: 4.0.0` ✅

---

## Marker Isolation Smoke Test

A throwaway stub was created at `tests/perf/test_stub_marker_check.py`, then:

| Invocation | Result |
|---|---|
| `uv run pytest tests/perf/ --collect-only --no-cov` | 1 deselected, 0 selected — stub correctly excluded by `addopts` |
| `uv run pytest tests/perf/ -m perf --collect-only --no-cov` | 1 collected — `-m perf` picks it up correctly |

Stub deleted and `tests/perf/` removed before continuing. No residual state.

---

## Preflight Quality Gates

| Gate | Result |
|------|--------|
| `make format` | `All checks passed!` |
| `make typecheck` | `Success: no issues found in 276 source files` |
| `make lint` | `All checks passed!` |

---

## TDD Evidence

`tdd_red_evidence: "n/a — dependency + marker configuration only; behavioural perf tests are introduced in S02 onward"`

---

## Blocker Notes

None.

---

## Scope Discipline

S01 touched only `pyproject.toml` and `uv.lock`. No `tests/perf/` package created (owned by S02). No production code, Makefile, or documentation modified.
