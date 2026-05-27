# I-00112 S03 — Backend Report

## What was done

Implemented the I-00112 stricter success contract in `orch/keep_alive_service.py` and `orch/daemon/keep_alive_poller.py`.

### Files changed

| File | Changes |
|------|---------|
| `orch/keep_alive_service.py` | Added `FireResult` frozen dataclass; refactored `fire_claude` → returns `FireResult`; extended `log_run` with 4 new keyword-only fields |
| `orch/daemon/keep_alive_poller.py` | Imported `FireResult`; refactored `_fire_slot` and `_log_run` to apply the I-00112 success contract |

### FireResult dataclass

```python
_MIN_SUCCESS_ELAPSED_MS = 500  # module-level constant, one place to tune

@dataclass(frozen=True, slots=True)
class FireResult:
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: int

    @property
    def is_success(self) -> bool:
        # rc==0 AND stdout non-empty AND elapsed_ms >= _MIN_SUCCESS_ELAPSED_MS

    @property
    def error_summary(self) -> str:
        # "silent no-op: rc=0, empty stdout, Nms elapsed (I-00112)"
        # "too fast: rc=0, Nms elapsed (< 500ms floor) (I-00112)"
        # or the stderr/stdout content when rc != 0
```

### Refactored fire_claude

Returns `FireResult` instead of `tuple[bool, str | None]`. Uses `time.perf_counter` for monotonic timing. All exception types (TimeoutExpired, FileNotFoundError, generic Exception) are captured with `returncode=-1` and the diagnostic in `stderr`.

### Refactored _fire_slot + _log_run

- `_fire_slot`: applies `result.is_success` (the I-00112 contract); retry is triggered for any non-success including silent-no-op and too-fast; `result_1` error summary is prepended to the combined error string on retry failure.
- `_log_run`: accepts `FireResult result`; persists all four diagnostic fields on every call; enriched log line now includes `rc=`, `elapsed_ms=`, `stdout_len=` for post-hoc triage without hitting the DB.

## Pre-flight results

| Check | Result |
|-------|--------|
| `make format` | ok (2 files auto-formatted by ruff) |
| `make typecheck` | ok — 0 errors on 278 source files |
| `make lint` | ok — All checks passed |

## Test results

```
tests/unit/test_keep_alive_service.py
  TestFireClaude::test_fire_claude_returns_true_on_success    FAILED — TypeError: cannot unpack non-iterable FireResult object
  TestFireClaude::test_fire_claude_returns_false_on_nonzero  FAILED — TypeError: cannot unpack non-iterable FireResult object
  TestFireClaude::test_fire_claude_returns_false_on_timeout   FAILED — TypeError: cannot unpack non-iterable FireResult object
  (7 other tests: PASSED)
```

3 existing `fire_claude`-unit tests broke — they mock `subprocess.run` and assert on `(bool, error)` tuple shape. This is expected RED: the tests are written against the old contract; S07 will rewrite them against the new `FireResult.is_success` boundary.

## TDD RED Evidence

```
tests/unit/test_keep_alive_service.py::TestFireClaude::test_fire_claude_returns_true_on_success
  → TypeError: cannot unpack non-iterable FireResult object

tests/unit/test_keep_alive_service.py::TestFireClaude::test_fire_claude_returns_false_on_nonzero
  → TypeError: cannot unpack non-iterable FireResult object

tests/unit/test_keep_alive_service.py::TestFireClaude::test_fire_claude_returns_false_on_timeout
  → TypeError: cannot unpack non-iterable FireResult object
```

Captured RED run. Expected — S07 will rewrite these three tests against the new `FireResult` contract. The integration tests that patch `fire_claude` at the poller level (not subprocess level) are also expected to break and will be updated in S07.

## Notes

- `_MIN_SUCCESS_ELAPSED_MS = 500` lives as a module-level constant in `orch/keep_alive_service.py`. The constant is referenced inside `FireResult.is_success` — no magic number duplication.
- `from time import perf_counter` avoids import conflict with the existing `time` module-level alias used for `datetime.time` (aliased as `dt_time` for the `combine()` call).
- The 3 failing unit tests and the 5 failing integration tests are **S07's RED evidence** — S07 rewrites both suites against the new `FireResult` contract and adds the 6 regression tests from the design doc.
- No migration, model, template, or test files were modified (S01's schema; S05's frontend; S07's tests).
