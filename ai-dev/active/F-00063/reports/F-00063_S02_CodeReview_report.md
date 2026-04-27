# F-00063 S02 — Code Review Report (Backend)

**Work item**: F-00063 — Stale Process & Migration Detector
**Step reviewed**: S01 (backend-impl)
**Reviewer**: code-review-impl (S02)
**Verdict**: PASS (after fixes)

---

## Summary

The S01 backend implementation is well-structured and largely correct. The `orch/staleness/` package is clean (no dashboard imports), all subprocess calls use explicit timeouts and `check=False`, error paths return safe values rather than raising, and the `projects.toml` seed is valid. The only mandatory fix was two missing unit tests explicitly required by the review checklist: pgrep cwd-outside-repo rejection and pgrep multiple-match warning. Both were added and all gates re-verified.

---

## Files Reviewed

| File | Status |
|------|--------|
| `orch/staleness/__init__.py` | OK |
| `orch/staleness/config.py` | OK |
| `orch/staleness/detection.py` | OK |
| `orch/staleness/git_lookup.py` | OK |
| `orch/staleness/alembic_check.py` | OK |
| `orch/staleness/service.py` | OK (1 LOW noted) |
| `orch/daemon/project_registry.py` | OK |
| `bin/restart-dashboard.sh` | OK |
| `projects.toml` | OK |
| `tests/unit/staleness/test_config.py` | OK |
| `tests/unit/staleness/test_detection.py` | FIXED (2 tests added) |
| `tests/unit/staleness/test_git_lookup.py` | OK |
| `tests/unit/staleness/test_alembic_check.py` | OK |
| `tests/unit/staleness/test_service.py` | OK |

---

## Findings

### MEDIUM_FIXABLE — F1: Missing pgrep unit tests (FIXED)

**File**: `tests/unit/staleness/test_detection.py`

The review checklist explicitly requires: "Tests cover at least: … cwd-outside-repo rejection, multiple-pgrep-match warning." Both were present for `pidfile` and `port` strategies but absent for `pgrep`:

- `test_pgrep_cwd_outside_repo_returns_none` — verifies that a process matching the pattern but running with cwd outside `repo_root` is not returned.
- `test_pgrep_multiple_matches_returns_oldest_with_warning` — verifies that when two processes match the pattern, the oldest (lowest `starttime_jiffies`) is selected and a `WARNING` log is emitted.

**Fix applied**: Both tests added to `TestFindRunningPidPgrep`. All 1844 unit tests pass.

---

### LOW — F2: Docker service deferred without test

**File**: `orch/staleness/service.py` lines 135–149

`_compute_service_staleness` returns `not_running` for `detect.type == "docker"` with a comment "detection deferred to API layer (S03)". This is intentional and documented, but there is no unit test in `test_service.py` asserting this behavior. Not mandatory to fix in S01 — the S03/S07 steps will add docker service coverage. Noted for the S07 tests step.

---

### LOW — F3: Empty `watch_paths` list admitted without warning

**File**: `orch/staleness/config.py` line 127–128; `orch/staleness/git_lookup.py` lines 121–143

`ServiceConfig.from_dict` validates that `watch_paths` is not `None` but does not reject an empty list `[]`. When `watch_paths=[]` and `ignore_paths=[]`, `commits_since` builds an empty pathspec list. `git log SHA..main -- ` (trailing `--` with no pathspecs) returns **all** commits, causing a false-positive stale result. In practice, the seed configuration and the config example never use `watch_paths=[]`, so this is unlikely to be triggered. However, a validator warn or guard would be more defensive. Deferred as a low-priority follow-up.

---

### LOW — F4: `repo_root` fallback to `Path("")` in `service.py`

**File**: `orch/staleness/service.py` line 267

```python
repo_root = Path(project_entry.get("repo_root", ""))
```

`Path("")` resolves to the current working directory (`Path('.')`). If a project entry somehow lacks `repo_root` (which `project_registry.py` would reject at DB-sync time, so this can't happen via the normal path), detection would silently use the wrong directory. A defensive `or raise` or explicit `Path(repo_root_str) if repo_root_str else ...` would be cleaner, but the existing guardrail in `project_registry.py` makes this unexploitable in production.

---

## Architecture & Convention Compliance

| Check | Result |
|-------|--------|
| No cross-layer imports (`orch/staleness/` → `dashboard/`) | PASS |
| All subprocess calls have explicit timeout + `check=False` | PASS |
| No `shell=True` with interpolated strings | PASS |
| `pathlib.Path` throughout (no string path concatenation) | PASS |
| UTC `datetime` with explicit `tzinfo=timezone.utc` | PASS |
| `compute_project_staleness` re-reads `projects.toml` on every call | PASS |
| Error paths return None/status="not_running"/"unknown" (never raise to caller) | PASS |
| Staleness config validation in `project_registry.py` is non-breaking (log + continue) | PASS |
| No hardcoded ports, credentials, or DB URLs | PASS |
| Lazy import of `orch.staleness.config` in `project_registry.py` to avoid circular import | PASS |
| ruff + mypy clean | PASS |
| `bin/restart-dashboard.sh` is executable (0755), sleeps before kill, uses SIGTERM + SIGKILL fallback | PASS |
| `projects.toml` TOML syntax valid; parses correctly with `tomllib` | PASS |
| No live DB or live git repo used in unit tests | PASS |

---

## Test Verification (post-fix)

| Gate | Command | Result |
|------|---------|--------|
| Unit tests | `make test-unit` | **1844 passed, 2 skipped** |
| Lint | `make lint` | **exit 0** |
| Typecheck | `make typecheck` | **exit 0 (189 source files)** |

---

## Subagent Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00063",
  "step_reviewed": "S01",
  "verdict": "pass",
  "findings": [
    {
      "id": "F1",
      "severity": "MEDIUM_FIXABLE",
      "file": "tests/unit/staleness/test_detection.py",
      "description": "Missing pgrep unit tests: cwd-outside-repo rejection and multiple-match warning. Both required by the review checklist.",
      "resolution": "FIXED — added test_pgrep_cwd_outside_repo_returns_none and test_pgrep_multiple_matches_returns_oldest_with_warning"
    },
    {
      "id": "F2",
      "severity": "LOW",
      "file": "orch/staleness/service.py",
      "description": "Docker service detection deferred to S03 with no unit test asserting not_running fallback.",
      "resolution": "Deferred to S07 tests step."
    },
    {
      "id": "F3",
      "severity": "LOW",
      "file": "orch/staleness/config.py",
      "description": "Empty watch_paths=[] accepted; would cause git log to match all commits (false-positive stale).",
      "resolution": "No change — low operational risk given real configs always specify paths."
    },
    {
      "id": "F4",
      "severity": "LOW",
      "file": "orch/staleness/service.py",
      "description": "repo_root fallback to Path('') resolves to cwd; unexploitable due to project_registry guard.",
      "resolution": "No change — existing upstream validation makes this unreachable in production."
    }
  ],
  "mandatory_fix_count": 1,
  "tests_passed": true,
  "test_summary": "1844 passed, 2 skipped (2 new pgrep tests added)",
  "notes": "One MEDIUM_FIXABLE finding fixed in place (2 missing pgrep tests). Zero CRITICAL/HIGH findings. All three gates green after fix."
}
```
