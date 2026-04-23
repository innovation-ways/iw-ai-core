# F-00058 S16 Browser Verification Fix Cycle 1/2

The end-to-end browser verification for step S16 of work item F-00058 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# F-00058 S16 Browser Verification Report

**Work Item**: F-00058 -- OSS compliance dashboard view + status pill
**Step**: S16
**Agent**: qv-browser
**Base URL used**: `http://localhost:9950`
**Overall status**: FAIL

---

## Pass/Fail Table

| ID | Name | Status | Notes |
|----|------|--------|-------|
| V1 | OSS Status frame on each page | FAIL | 500 error on `/oss/status` htmx fragment; oss_status_frame throws `subprocess.CalledProcessError` when `git rev-parse HEAD` fails in `/app` (no git repo in E2E container) |
| V2 | OSS disabled state + install modal | FAIL | Same 500 on `/oss/status` — the dashboard page itself renders but the OSS Status frame never loads |
| V3 | Install-now + enable flow | FAIL | Same root cause |
| V4 | Scan + SSE progress | FAIL | Same root cause |
| V5 | Results tree | FAIL | Same root cause |
| V6 | Prepare + CLI block | FAIL | Same root cause |
| V7 | Stale banner | FAIL | Same root cause |
| V8 | No regressions | FAIL | Same root cause |

---

## Root Cause Analysis

**File**: `dashboard/services/oss_service.py:95-115` (`_git_head` function)

```python
def _git_head(repo_root: str) -> str | None:
    ...
    result = subprocess.run(
        [str(git_path), "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=10,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    # ↑ CalledProcessError is NOT caught here — it propagates up
```

The `subprocess.run()` call raises `subprocess.CalledProcessError` when git exits non-zero (e.g., `/app` is not a git repo). This exception is **not** caught inside `_git_head`, so it propagates to the FastAPI route handler for `GET /oss/status`, returning a 500.

The E2E stack's `e2e-dashboard` container has `repo_root="/app"` but `/app` is a plain directory (not a git clone), so `git rev-parse HEAD` fails with exit code 128.

**Fix needed**: Wrap the `subprocess.run` call in a try/except to catch `subprocess.SubprocessError` (the base class for both `CalledProcessError` and `FileNotFoundError`), log a warning, and return `None` gracefully. This would make the stale check return `is_fresh=False` with message "git unavailable" instead of crashing the page.

---

## E2E Fixture Created

An e2e seed fixture was created at:
```
ai-dev/active/F-00058/e2e_fixtures/001_oss_seed.py
```

This seeds:
- `oss-demo`: project with `oss_enabled=True`, one completed `oss_scan` (pill_color=yellow), 6 tool runs, 4 findings across 3 domains, head_sha deliberately mismatched (for V7 stale banner).
- `oss-clean`: project with `oss_enabled=True`, no scans (for gray-pill state).

The fixture was verified to apply correctly against the E2E DB (port 5482):
```sql
SELECT id, oss_enabled FROM projects ORDER BY id;
-- ('iw-ai-core', False), ('oss-clean', True), ('oss-demo', True)

SELECT COUNT(*) FROM oss_scan;
-- 1 row for 'oss-demo'
```

---

## Console Errors Observed

All throughout browsing:
- `ReferenceError: module is not defined` at `highlight.js/core.js:2595` — pre-existing, not related to OSS.
- `[ERROR] Failed to load resource: the server responded with a status of 500 (Internal Server Error) @ http://localhost:9950/project/oss-demo/oss/status:0` — **this is the OSS bug**.

---

## Screenshots Captured

| File | Description |
|------|-------------|
| `evidences/post/F-00058_v1_oss_frame_loading.png` | oss-demo dashboard page showing "Loading OSS status…" spinner |

---

## ENV_DATA_MISSING Classification

N/A — the fixture `001_oss_seed.py` was successfully applied. The failure is a **CODE DEFECT** in `_git_head()`.

---

## Subagent Result Contract

```json
{
  "step": "S16",
  "agent": "qv-browser",
  "work_item": "F-00058",
  "overall_status": "fail",
  "base_url_used": "http://localhost:9950",
  "verifications": [
    {"id": "V1", "name": "frame on each page", "status": "fail", "screenshot": "evidences/post/F-00058_v1_oss_frame_loading.png", "notes": "500 on /oss/status — _git_head CalledProcessError not caught"},
    {"id": "V2", "name": "disabled state + install modal", "status": "fail", "screenshot": "", "notes": "Same root cause"},
    {"id": "V3", "name": "install-now + enable flow", "status": "fail", "screenshot": "", "notes": "Same root cause"},
    {"id": "V4", "name": "scan + SSE", "status": "fail", "screenshot": "", "notes": "Same root cause"},
    {"id": "V5", "name": "results tree", "status": "fail", "screenshot": "", "notes": "Same root cause"},
    {"id": "V6", "name": "prepare + CLI block", "status": "fail", "screenshot": "", "notes": "Same root cause"},
    {"id": "V7", "name": "stale banner", "status": "fail", "screenshot": "", "notes": "Same root cause"},
    {"id": "V8", "name": "no regressions", "status": "fail", "screenshot": "", "notes": "Same root cause"}
  ],
  "console_errors_observed": [
    "ReferenceError: module is not defined at highlight.js/core.js:2595 (pre-existing, unrelated)",
    "500 Internal Server Error at /project/oss-demo/oss/status:0 (OSS bug)"
  ],
  "screenshots": ["evidences/post/F-00058_v1_oss_frame_loading.png"],
  "notes": "All V1-V8 FAIL due to _git_head() in oss_service.py not catching CalledProcessError when git rev-parse HEAD fails in /app (no git repo in E2E container). Fix: wrap subprocess.run in try/except for SubprocessError in _git_head(). E2E seed fixture created at ai-dev/active/F-00058/e2e_fixtures/001_oss_seed.py and verified applied."
}
```


## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/F-00058/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
3. The failing Vs map to files typically in:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
