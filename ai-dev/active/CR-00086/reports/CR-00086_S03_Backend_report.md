# CR-00086 S03 Backend — Step Report

**Step**: S03 (backend-impl)
**Work Item**: CR-00086 — Self-dashboarding of test health
**Date**: 2026-05-28
**Agent**: backend-impl

---

## What Was Done

Implemented the **Backend service + CLI** step of CR-00086: a new `orch/test_health_service.py`
that reads four artefact sources and writes snapshots, and a new `iw test-health-capture`
CLI command wired into the Typer app.

## Files Changed

| File | Change |
|------|--------|
| `orch/test_health_service.py` | **New** — service with `read_sources`, `capture_snapshot`, `latest`, `trend` |
| `orch/cli/test_health_commands.py` | **New** — `test-health-capture` Click command |
| `orch/cli/main.py` | **Modified** — wired `test_health_capture` into CLI |
| `tests/unit/test_test_health_service.py` | **New** — 14 unit tests |
| `tests/integration/test_test_health_service.py` | **New** — 8 integration tests |
| `pyproject.toml` | **Modified** — added per-file ignores for `test_health_service.py` |

## TDD Cycle

| Phase | Evidence |
|-------|----------|
| **RED** | All 22 tests failed with `ModuleNotFoundError: No module named 'orch.test_health_service'` before the service module was created |
| **GREEN** | After creating `orch/test_health_service.py` + `test_health_commands.py`: 22 passed, 0 failed |
| **REFACTOR** | Fixed `dict` → `dict[str, object]` for mypy strict mode; added `suppress` for `flake_count` parse; added `check=False` to subprocess call; added per-file ruff ignores for S110 (try/except/pass for optional pyproject.toml fail_under) and S603/S607 (trusted repo scripts) |

## Service API

Three public functions in `orch/test_health_service.py`:

- `read_sources(repo_root: str, *, flake_summary_json: Path | None = None) -> dict[str, tuple[float, dict[str, object]] | None]`
  Reads all four sources; missing source → `None` + one WARNING. Never raises.

- `capture_snapshot(session, project_id: str, metric: str, value: float, meta: dict[str, object]) -> TestHealthSnapshot`
  Upsert on `(project_id, metric, ts_truncated_to_minute)`. Idempotent within the same minute.

- `latest(session, project_id: str) -> dict[str, TestHealthSnapshot]` and
  `trend(session, project_id: str, metric: str, limit: int = 30) -> list[TestHealthSnapshot]`

### Artefact Readers

| Source | Reader | Notes |
|--------|--------|-------|
| Mutation JSON | `_read_mutation_score()` → `_parse_mutation_json()` | Handles both CR-00080 shape (`score` at root) and CR-00059 shape (`metrics.score`). Dispatch behind helper so future shape changes are one-file edits. |
| Coverage JSON | `_read_coverage_pct()` | Reuses the path resolution pattern (`tests/output/coverage/coverage.json` + `pyproject.toml`). Does NOT re-implement XML parsing — reads the same JSON format as `dashboard/services/coverage_service.py`. |
| Flaky log | `_read_flaky_count()` | Primary: direct JSON artefact (`flake_summary_json`). Fallback: invoke `scripts/flake_detect_aggregate.py` with run log files and parse "Found N flaky test(s):" from stdout. |
| Assertion baseline | `_read_baseline_size()` | Line-count of `tests/assertion_free_baseline.txt`. Excludes comment lines (leading `#`) and blank lines. |

### CLI Command

```
iw test-health-capture --project <slug>
```

- Looks up project by slug (exit code 2 if not found)
- Calls `read_sources()`
- Calls `capture_snapshot()` for each non-None metric
- Prints JSON summary to stdout: `{"project": "...", "captured": [...], "skipped": [...]}`
- Exit 0 on success (including no-op captures); exit 1 on DB errors

## Jobs Aggregator Hook

The aggregator reads `test_health_snapshots` by grouping rows on `(project_id, ts_minute)`:
one capture invocation writes four metric rows all sharing the same `ts_minute` value, so
S05 can aggregate by `(project_id, ts)` to show **one job row per capture invocation** regardless
of how many metrics were written. The integration test `test_capture_writes_four_rows_sharing_same_ts_minute`
confirms all four rows share the same `ts_minute`, enabling S05 to add a `test-health-capture`
`JobType` entry with a group-by query on `(project_id, date_trunc('minute', ts))`.

## Pre-flight Results

| Gate | Result |
|------|--------|
| `make format` | ok |
| `make typecheck` | ok (mypy strict — `dict[str, object]`, Session type hints) |
| `make lint` | ok (ruff + check_templates.py) |

## Test Results

```
tests/integration/test_test_health_service.py  8 passed
tests/unit/test_test_health_service.py         14 passed
22 passed in 6.55s
```

The `TestHealthSnapshot` PytestCollectionWarning is benign — pytest mistakenly tries to
collect the SQLAlchemy ORM model class (named `TestHealthSnapshot`) as a test class because
it has a constructor. The model class is imported at module level for use in tests; the
warning is harmless and does not affect test behavior.

## TDD RED Evidence

```
tests/unit/test_test_health_service.py::TestMutationJsonParsing::test_read_mutation_score_new_shape
FAILED — ModuleNotFoundError: No module named 'orch.test_health_service'
  tests/unit/test_test_health_service.py:43: ModuleNotFoundError: No module named 'orch.test_health_service'

tests/integration/test_test_health_service.py::TestCaptureSnapshot::test_capture_writes_row
FAILED — ModuleNotFoundError: No module named 'orch.test_health_service'
  (same pattern for all 8 integration tests)
```

All 22 tests failed with `ModuleNotFoundError` before `orch/test_health_service.py` was created.
After implementation: **22 passed, 0 failed**.

## Notes

- The `TestHealthSnapshot` model already existed in `orch/db/models.py` (S01 created it).
  The integration tests import it directly at module level.
- `read_sources` accepts a `flake_summary_json` kwarg to support direct JSON input in tests
  (bypassing the subprocess invocation of `flake_detect_aggregate.py`).
- The `_read_flaky_count` function falls back to script invocation when no JSON artefact
  is provided — this path is exercised only when running against a live repo with run logs.
- Ruff S110 (try/except/pass) is allowed for the optional `pyproject.toml` fail_under read —
  the threshold is a nice-to-have metadata field; failing to read it is non-fatal.
- Ruff S603/S607 (subprocess) is allowed for `flake_detect_aggregate.py` — only trusted
  repo scripts under version control are invoked.

## Next Step

S04 (`code-review-impl`) reviews S01 + S03. S05 (`frontend-impl`) implements the dashboard
panel and Jobs aggregator wiring — the aggregator hook documented above connects to the
`test_health_snapshots` table via a group-by on `(project_id, ts_minute)`.
