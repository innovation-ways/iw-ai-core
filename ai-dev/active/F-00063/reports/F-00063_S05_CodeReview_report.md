# F-00063 S05 — Code Review Report (S03 API)

**Work item**: F-00063 — Stale Process & Migration Detector
**Step reviewed**: S03 (api-impl)
**Review step**: S05
**Reviewer**: code-review-impl

---

## Summary

The S03 API implementation is well-structured and correct in all security-critical
dimensions. Six endpoints are present, soft-lock and subprocess safety requirements are
met, and all 21 targeted tests pass. One fixable issue was found and fixed during this
review: the `_toast_response` helper used the key `"kind"` instead of `"type"`, which
would have caused all action toasts to silently fall back to the `info` visual style
rather than the intended `success` style.

---

## Findings

### MEDIUM_FIXABLE — Toast payload uses wrong key (`"kind"` vs `"type"`)

**Files**: `dashboard/routers/staleness.py` lines 128–139 (original) and line 602 (alembic upgrade inline trigger)

**Description**: The private `_toast_response` helper constructed `{"showToast": {"message": ..., "kind": "success", ...}}`. The frontend `showToast` JavaScript function in `dashboard/templates/components/toast.html` reads `data.type`, not `data.kind` (line 37: `var type = data.type || 'info'`). An unknown key `"kind"` is silently ignored; the toast renders with the default `"info"` border colour instead of the intended `"success"` green. The same mistake appeared in the inline `showToast` trigger for the alembic upgrade success path (line 602). Additionally, the review checklist explicitly mandates "Uses existing toast trigger helper (don't invent a new one)" — the implementation invented its own helper rather than reusing `_run_helpers.action_response` or matching the `"type"` key used by `actions._action_response`.

**Existing convention**: `dashboard/routers/_run_helpers.py:action_response` and `dashboard/routers/actions.py:_action_response` both use `{"showToast": {"message": ..., "type": ...}}`.

**Fix applied**: Changed `"kind"` → `"type"` in `_toast_response` and the inline alembic trigger. A comment was added to `_toast_response` cross-referencing the JS convention and the existing helpers. The `_toast_response` helper is kept (rather than importing `action_response`) because the staleness router needs variable status codes — 202 for self-restart, 200 for alembic upgrade output — which `action_response` hard-codes to 204.

---

### LOW — Self-restart detection by substring match is fragile

**File**: `dashboard/routers/staleness.py` line 281

```python
status_code = 202 if "restart-dashboard" in command else 204
```

**Description**: The 202 vs 204 branch depends on the literal substring `"restart-dashboard"` appearing in the configured command string. Currently `projects.toml` has `restart_command = "bin/restart-dashboard.sh"`, which does contain the substring. If the helper script is renamed, the detection silently breaks: the endpoint returns 204 instead of 202, meaning the response may not flush before the helper kills the process. The risk is low because the script name is stable and the design note acknowledges this pattern.

**Recommendation** (not fixed): Document the dependency in a code comment, or replace with a config-level boolean flag such as `self_restart = true` on the service block. No action required before merge.

---

### LOW — `_spawn_command` sets soft-lock before spawning; spawn failure leaves lock engaged

**File**: `dashboard/routers/staleness.py` lines 272–277

**Description**: `_check_soft_lock` sets `_service_locks[key] = now` (locking) before `_spawn_command` is called. If `Popen` raises an `OSError` (rare with `shell=True`, but theoretically possible on a read-only filesystem), the lock is already set. The caller gets an unhandled 500 (FastAPI default) and must wait 5 seconds before retrying. This is acceptable per the "single uvicorn worker, dev-only" design scope and is hard to trigger.

**Recommendation**: No action required before merge. The design scope (local dev, `shell=True`, operator-supplied config) makes this a very unlikely failure path.

---

### LOW / SUGGESTION — Missing 429 test coverage for start and stop endpoints

**File**: `tests/dashboard/test_staleness_router.py`

**Description**: `TestServiceStart` and `TestServiceStop` do not include a test for the 429 soft-lock response. The soft-lock path is shared by all three action endpoints through `_check_soft_lock`, and `TestServiceRestart` already covers the 429 contract, so the omission is low risk. The `TestSoftLockExpiry` class only tests restart as well.

**Recommendation**: Add soft-lock tests for start and stop in S07 (additional coverage step). Not blocking.

---

### LOW / SUGGESTION — Alembic `TimeoutExpired` not tested

**File**: `tests/dashboard/test_staleness_router.py`

**Description**: The `alembic_upgrade` endpoint has explicit handling for `subprocess.TimeoutExpired` that returns 502, but there is no test exercising that branch. The code path is correct; the gap is purely in test coverage.

**Recommendation**: Add a test in S07. Not blocking.

---

## Checklist Results

| Check | Status | Notes |
|-------|--------|-------|
| All six endpoints present | PASS | GET panel, GET dot, POST restart/start/stop, POST alembic — six total (review prompt says "seven" but the feature design specifies six) |
| 404 for unknown project / service | PASS | All action endpoints return 404 for unknown project or service |
| 409 when command missing | PASS | Tested for restart, start, stop |
| 429 with Retry-After on soft-lock | PASS | Correct; tested for restart; see LOW gap for start/stop |
| 502 for alembic subprocess failure | PASS | rc!=0 path tested |
| 200/204 with HX-Trigger toast on success | PASS after fix | `"kind"` → `"type"` fixed |
| Self-restart returns 202, spawns detached | PASS | 202 path via substring detection; detached via `start_new_session=True` |
| Subprocess: explicit timeout where applicable | PASS | `_ALEMBIC_TIMEOUT=60` on `subprocess.run`; `Popen` is fire-and-forget (no timeout on `Popen` is correct) |
| `start_new_session=True` on restart actions | PASS | `_spawn_command` sets this |
| `cwd=<repo_root>` set explicitly | PASS | `cwd=repo_root or None` (falls back to None only when repo_root is empty string — misconfiguration) |
| `shell=True` documented as intentional | PASS | Module docstring and `noqa: S602` comment |
| Alembic uses arg-list (no shell injection) | PASS | `["alembic", "-c", cfg_path, ...]` with `shell=False` (default) |
| Soft-lock per (project_id, service_name) | PASS | `_service_locks: dict[tuple[str, str], float]` |
| Lock in module-level memory, documented | PASS | Module docstring documents the single-worker assumption |
| Style matches `daemon_control.py` | PASS | Sync endpoints, `HTMLResponse`, `Response`, same import patterns |
| Toast trigger uses correct format | PASS after fix | Fixed to use `"type"` |
| Router registered in `app.py` | PASS | Line 203: `app.include_router(staleness.router)` |
| ruff clean | PASS | `make lint` exits 0 |
| mypy clean | PASS | `make typecheck` exits 0 (190 files) |
| Project / service name validated against config | PASS | Command sourced from config; `service_name` only used as a lookup key |
| `db_url_env` value never logged | PASS | Comment at line 436; only the env var name (not value) is logged on warning |
| No additional secrets introduced | PASS | |
| Tests mock `Popen` and `compute_project_staleness` | PASS | No live subprocesses |
| Panel happy path tested | PASS | `TestStalenessPanel.test_panel_200_for_known_project` |
| Opt-out empty body tested | PASS | `test_panel_empty_body_for_optout_project` |
| 404 tested | PASS | Both panel and dot |
| Restart success tested | PASS | `test_restart_invokes_subprocess_with_command` |
| 429 tested | PASS | `test_restart_returns_429_on_second_post_within_5s` |
| 409 tested | PASS | `test_restart_returns_409_when_no_restart_command` |
| Alembic happy + fail tested | PASS | Both paths covered |

---

## Gate Results

| Gate | Command | Result |
|------|---------|--------|
| Unit tests | `make test-unit` | 1844 passed, 2 skipped |
| Lint | `make lint` | exit 0 |
| Typecheck | `make typecheck` | exit 0 (190 files) |

---

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-impl",
  "work_item": "F-00063",
  "step_reviewed": "S03",
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM_FIXABLE",
      "file": "dashboard/routers/staleness.py",
      "lines": "128-139, 602",
      "description": "_toast_response used 'kind' key; JS showToast reads 'type'; toasts silently rendered as info style. Inline alembic trigger had the same bug. Review checklist mandated using existing toast helper convention.",
      "fix": "Changed 'kind' to 'type' in _toast_response and the alembic upgrade inline trigger. Added clarifying comment."
    },
    {
      "severity": "LOW",
      "file": "dashboard/routers/staleness.py",
      "lines": "281",
      "description": "Self-restart 202/204 branch detected by substring 'restart-dashboard' in command string. Fragile if script is renamed but stable for current projects.toml config.",
      "fix": "None applied; documented as low risk."
    },
    {
      "severity": "LOW",
      "file": "dashboard/routers/staleness.py",
      "lines": "272-277",
      "description": "Soft-lock set before _spawn_command; if Popen raises, lock is engaged and retry blocked for 5s.",
      "fix": "None applied; very unlikely with shell=True and operator-trusted config."
    },
    {
      "severity": "LOW",
      "file": "tests/dashboard/test_staleness_router.py",
      "lines": "407-511",
      "description": "No 429 soft-lock tests for start/stop endpoints. Also no test for alembic TimeoutExpired branch.",
      "fix": "Deferred to S07."
    }
  ],
  "mandatory_fix_count": 1,
  "tests_passed": true,
  "test_summary": "1844 unit tests passed (2 skipped). 21 staleness router tests all green. lint exit 0. typecheck exit 0 (190 files).",
  "notes": "One MEDIUM_FIXABLE issue fixed in-review: toast payload key 'kind' corrected to 'type' to match the existing JS showToast convention. All three gates pass after fix. Three LOW findings documented, none require immediate action."
}
```
