# I-00052 S02 CodeReview Backend Report

## What was done

Reviewed S01 implementation of `_capture_crashed_container_logs` helper and its call site.

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/browser_env.py` | Added `_capture_crashed_container_logs(compose_log, tail=50)` helper |
| `orch/daemon/batch_manager.py` | Updated error recording to append container crash logs to `error_msg` |

## Lint & Format Gate

- `ruff check orch/daemon/browser_env.py orch/daemon/batch_manager.py` — **PASS** (0 violations)
- `ruff format --check` — **PASS** (already formatted)

## Review Findings

### Correctness Checklist

| Item | Status | Notes |
|------|--------|-------|
| Regex `r"container\s+([\w\-]+)\s+exited\s+\(\d+\)"` correctly extracts container names | **PASS** | Mentally tested against `"dependency failed to start: container iw-ai-core-e2e-f00067-e2e-dashboard-1 exited (1)"` — extracts `iw-ai-core-e2e-f00067-e2e-dashboard-1` |
| `dict.fromkeys()` used for deduplication | **PASS** | Line 466 preserves insertion order |
| `subprocess.run` uses list form (not `shell=True`) | **PASS** | Line 474: `["docker", "logs", name, "--tail", str(tail)]` |
| Both `stdout` and `stderr` captured | **PASS** | `capture_output=True` captures both streams |
| `timeout=10` prevents blocking | **PASS** | Line 477 |
| Entire per-container block inside `except Exception` | **PASS** | Lines 472–483 |
| Empty string returned when no names found or all calls fail | **PASS** | Lines 467–468 and 484–485 |
| `batch_manager.py` passes FULL compose output | **PASS** | Line 890 reads full output; line 893 passes it |

### Safety Checklist

| Item | Status | Notes |
|------|--------|-------|
| No new imports added | **PASS** | `subprocess` and `re` already imported |
| `# noqa: S603` present on `subprocess.run` | **PASS** | Line 473 |
| `# noqa: BLE001` present on `except Exception` | **PASS** | Line 482 |
| Only `docker logs` called (no other docker commands) | **PASS** | Only `["docker", "logs", ...]` |

### Integration Checklist

| Item | Status | Notes |
|------|--------|-------|
| Full compose output read before slicing tail | **PASS** | Line 890 reads full `compose_output`; line 892 slices `lines[-20:]` |
| `container_crash_logs` appended at end of `error_msg` | **PASS** | Line 897: `f"browser env setup failed: {log_tail}{container_crash_logs}"` |

### AC Verification

| AC | Status | Evidence |
|----|--------|----------|
| AC1: crash logs in `error_message` | **PASS** | `container_crash_logs` concatenated into `error_msg` at line 897 |
| AC2: safe fallback (no raise) | **PASS** | `except Exception` at line 482 catches all; no `raise` anywhere |
| AC3: empty input → empty string, no subprocess | **PASS** | Early return at line 467 if `container_names` is empty |

## Observations

1. **Minor: Unnecessary `# noqa: S607`** — Line 473 has `# noqa: S603, S607` but `S607` (shell=True) does not apply since the command is in list form. This is harmless but misleading. Not a critical issue.

## Overall Status

**pass**

- Mandatory fix count: 0
- Findings: 0 critical, 0 high, 1 low (unnecessary S607 noqa)

(End of file - total 77 lines)