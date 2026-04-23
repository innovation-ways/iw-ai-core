# F-00058 S16 Browser Verification Fix Cycle 2/2

The end-to-end browser verification for step S16 of work item F-00058 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

# F-00058 S16 Browser Verification Report

**Step**: S16 — qv-browser
**Overall Status**: FAIL

## Environment

- **Base URL used**: `http://localhost:9950`
- **E2E user**: `dev@example.local`

## Seed Data Verified (via direct DB query)

| Project | oss_enabled | Scans | Findings | Tool Runs | Notes |
|---------|-------------|-------|----------|----------|-------|
| `oss-demo` | true | 1 (yellow pill) | 4 | 6 | Seeding confirmed ✓ |
| `oss-clean` | true | 0 (gray pill) | 0 | 0 | Seeding confirmed ✓ |
| `iw-ai-core` | false | 0 (disabled) | 0 | 0 | Seeding confirmed ✓ |

## Verification Results

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | OSS Status frame on each page | **FAIL** | — | oss-demo/oss/status returns HTTP 500; frame never loads |
| V2 | Disabled state + install modal | **FAIL** | — | oss-status-frame returns HTTP 500 for oss-demo; cannot test V2/V3 until V1 passes |
| V3 | Install-now + Enable flow | **BLOCKED** | — | Blocked by V1/V2 |
| V4 | Scan + SSE progress | **BLOCKED** | — | Blocked by V1/V2 |
| V5 | Results tree | **BLOCKED** | — | Blocked by V1/V2 |
| V6 | Prepare + CLI block | **BLOCKED** | — | Blocked by V1/V2 |
| V7 | Stale banner | **BLOCKED** | — | Blocked by V1/V2 |
| V8 | No regressions | **FAIL** | — | oss-status-frame returns HTTP 500 on all project pages |

## Issue Found

**Code Defect** — `FileNotFoundError: [Errno 2] No such file or directory: 'git'` in `dashboard/services/oss_service.py:_git_head()`

### Root Cause

The dashboard container (`iw-ai-core-e2e-f00058-e2e-dashboard-1`) lacks the `git` binary in its PATH. The `_git_head()` function at `oss_service.py:95` tries `subprocess.run(["git", "which", "git"])` as its first operation, which throws `FileNotFoundError` when git is absent.

This error propagates through `compute_freshness()` → `scan_summary()` → `oss_status_frame()` route, causing a 500 on every `GET /project/{id}/oss/status` call for projects with `oss_enabled=true` and existing scans.

**Affected code path** (`oss_service.py:530–569`):
```python
def compute_freshness(project_id: str, session: Session) -> dict[str, Any]:
    ...
    current_sha = _git_head(project.repo_root)   # ← crashes here when git missing
    ...
    is_fresh = current_sha == last_sha           # ← never reached
```

### What Works

- `GET /project/oss-clean/oss/status` — returns 200 with gray pill (because `latest_scan()` is None, `_git_head` is never called)
- `GET /project/iw-ai-core/oss/status` — returns 200 with "Install OSS" disabled-state CTA (because `oss_enabled=false`)
- Direct DB queries from the worktree confirm seed data is correct
- `curl http://localhost:9950/health` returns 200

### What Fails

- `GET /project/oss-demo/oss/status` — returns HTTP 500 because:
  1. `oss_enabled=true` and there is a scan → enters the `elif oss_enabled and scan_summary` branch
  2. `scan_summary()` calls `compute_freshness()` to determine staleness
  3. `compute_freshness()` calls `_git_head('/app')` which throws uncaught `FileNotFoundError`

## Screenshot Evidence

No screenshots taken — the oss-status-frame returns HTTP 500 before any page content renders.

## No Regressions Observed

N/A — the core OSS frame is broken so regression testing of adjacent flows is not meaningful.

## Fix Recommendation

The `compute_freshness()` function should handle the missing git binary gracefully:

```python
def compute_freshness(project_id: str, session: Session) -> dict[str, Any]:
    ...
    current_sha = _git_head(project.repo_root)
    if current_sha is None:
        return {
            "is_fresh": False,
            "last_scan_sha": last_sha,
            "current_sha": None,
            "message": "git unavailable — cannot determine freshness",
        }
    ...
```

The existing code already returns `None` from `_git_head` on failure (via the `except` clause at line 113), but the caller (`compute_freshness`) does not guard against a `None` current_sha. Adding a guard will make the staleness check degrade gracefully when git is unavailable, while still surfacing the yellow/green/red pill and findings for projects that have been scanned.

## Console Errors

- `highlight.js/core.js:2595:1 — ReferenceError: module is not defined` (JS error from CDN version of highlight.js — cosmetic, not related to OSS feature)
- `FileNotFoundError: 'git'` in `oss_service.py:97` — **root cause of 500 errors**


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


**ESCALATION**: This is the FINAL browser fix cycle (2/2). If you cannot resolve every failing verification, document which remain and why so the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
