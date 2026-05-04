# CR-00030 S11 Browser Verification Fix Cycle 3/3

The end-to-end browser verification for step S11 of work item CR-00030 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00030/ai-dev/active/CR-00030/CR-00030_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

## ⚠️ Most Recent Failure (run 3)

browser env setup failed:  Container iw-ai-core-e2e-cr00030-e2e-db-1 Created 
 Container iw-ai-core-e2e-cr00030-e2e-dashboard-1 Creating 
 Container iw-ai-core-e2e-cr00030-e2e-dashboard-1 Created 
 Container iw-ai-core-e2e-cr00030-e2e-daemon-stub-1 Creating 
 Container iw-ai-core-e2e-cr00030-e2e-daemon-stub-1 Created 
 Container iw-ai-core-e2e-cr00030-e2e-ollama-1 Starting 
 Container iw-ai-core-e2e-cr00030-e2e-db-1 Starting 
 Container iw-ai-core-e2e-cr00030-e2e-ollama-1 Started 
 Container iw-ai-core-e2e-cr00030-e2e-db-1 Started 
 Container iw-ai-core-e2e-cr00030-e2e-ollama-1 Waiting 
 Container iw-ai-core-e2e-cr00030-e2e-db-1 Waiting 
 Container iw-ai-core-e2e-cr00030-e2e-ollama-1 Healthy 
 Container iw-ai-core-e2e-cr00030-e2e-db-1 Healthy 
 Container iw-ai-core-e2e-cr00030-e2e-dashboard-1 Starting 
 Container iw-ai-core-e2e-cr00030-e2e-dashboard-1 Started 
 Container iw-ai-core-e2e-cr00030-e2e-db-1 Waiting 
 Container iw-ai-core-e2e-cr00030-e2e-dashboard-1 Waiting 
 Container iw-ai-core-e2e-cr00030-e2e-db-1 Healthy 
 Container iw-ai-core-e2e-cr00030-e2e-dashboard-1 Error dependency e2e-dashboard failed to start
dependency failed to start: container iw-ai-core-e2e-cr00030-e2e-dashboard-1 exited (2)

## Container Crash Logs

### docker logs iw-ai-core-e2e-cr00030-e2e-dashboard-1 (last 50 lines)

[e2e] waiting for DB at e2e-db:5432...
[e2e] applying migrations...
error: Failed to initialize cache at `/home/sergiog/.cache/uv`
  Caused by: failed to create directory `/home/sergiog/.cache/uv`: Permission denied (os error 13)

---

## Original Browser Report (for V table context)

# CR-00030 S11 Browser Verification Report

## Environment
- **Base URL used:** `http://localhost:9951`
- **E2E user:** `dev@example.local`

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Claude 5h label in 'Xh Ym' form | **ENV_DATA_MISSING** | — | Cache file `~/.claude/rate-limits-cache.json` is on the HOST at `/home/sergiog/.claude/rate-limits-cache.json`. The dashboard runs inside a Docker container (`iw-ai-core-e2e-cr00030-e2e-dashboard-1`) whose HOME is `/app` — no `.claude` directory exists inside the container, and the host's `~/.claude/` is not bind-mounted. V1 cannot be set up in this stack. |
| V2 | Claude 7d label unchanged (wall-clock) | **ENV_DATA_MISSING** | — | Same root cause as V1 — the container cannot reach the host's `~/.claude/rate-limits-cache.json`. |
| V3 | Sub-hour 5h label uses minutes only | **ENV_DATA_MISSING** | — | Same root cause — requires writing a cache with `resets_at = now + 25m` to the container's `~/.claude/rate-limits-cache.json`, which doesn't exist and cannot be created in the sandbox. |
| V4 | Missing cache → '5h' placeholder | **pass** | `evidences/post/CR-00030_v4_5h_placeholder.png` | Confirmed: when the container's HOME (`/app`) has no `.claude/rate-limits-cache.json`, the API returns `5h` and `0%` as the fallback. The footer correctly shows "5h" and "0%" for Claude's 5h slot. |
| V5 | No regressions (console, MiniMax, adjacent pages) | **pass** | `evidences/post/CR-00030_v5_no_regressions.png` | No console errors on home page, `/system/status`, or `/project/iw-ai-core/`. MiniMax row shows "5h" / "0%" (placeholder, correct). |

## Console / Network Errors
- None observed on any page visited (home, `/system/status`, `/project/iw-ai-core/`).

## No Regressions
- **MiniMax row**: displays correctly — "5h" label and "0%" (placeholder, consistent with no API key configured).
- **Additional pages checked**: `/system/status` page loaded cleanly with no errors. `/project/iw-ai-core/` loaded cleanly with no errors.
- **API endpoint**: `GET /api/usage/llm/fragment` returns a valid HTML fragment with no errors (returns 200, correct fallback content).

## Screenshots captured
- `ai-dev/active/CR-00030/evidences/post/CR-00030_v4_5h_placeholder.png` — V4: Claude 5h shows "5h" fallback, 0%
- `ai-dev/active/CR-00030/evidences/post/CR-00030_v5_no_regressions.png` — V5: Project page, no console errors

## Root cause (V1, V2, V3 failure — ENV_DATA_MISSING)

The E2E dashboard container (`iw-ai-core-e2e-cr00030-e2e-dashboard-1`) runs with `HOME=/app`. There is no `.claude` directory inside the container, and the host's `/home/sergiog/.claude/rate-limits-cache.json` is not bind-mounted into the container.

The cache file location in `orch/llm_usage.py:43` is:
```python
_RATE_LIMITS_FILE = Path.home() / ".claude/rate-limits-cache.json"
```

`Path.home()` resolves to `/app` inside the container, so `_read_rate_limits_cache()` always returns `None` for both windows, causing the fallback `5h` / `7d` / `0%` to be displayed regardless of what the host's cache contains.

**This is an environment gap, not a code defect.** The fix-cycle agent cannot fix this by editing `llm_usage.py` — the cache file path is correct; the issue is that the E2E stack's containerization doesn't provide a writable HOME with the Claude rate-limits cache mounted.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "qv-browser",
  "work_item": "CR-00030",
  "overall_status": "fail",
  "base_url_used": "http://localhost:9951",
  "verifications": [
    {"id": "V1", "name": "Claude 5h label in 'Xh Ym' form", "status": "ENV_DATA_MISSING", "screenshot": "", "notes": "Container HOME=/app, host ~/.claude not mounted. Cache file not accessible."},
    {"id": "V2", "name": "Claude 7d label unchanged (wall-clock)", "status": "ENV_DATA_MISSING", "screenshot": "", "notes": "Same root cause as V1."},
    {"id": "V3", "name": "Sub-hour 5h label minutes-only", "status": "ENV_DATA_MISSING", "screenshot": "", "notes": "Same root cause — container cannot write to its own ~/.claude/."},
    {"id": "V4", "name": "Missing cache -> '5h' placeholder", "status": "pass", "screenshot": "evidences/post/CR-00030_v4_5h_placeholder.png", "notes": "Confirmed: fallback '5h' and '0%' renders correctly when cache is absent."},
    {"id": "V5", "name": "No regressions (console, MiniMax, adjacent pages)", "status": "pass", "screenshot": "evidences/post/CR-00030_v5_no_regressions.png", "notes": "No console errors on any visited page."}
  ],
  "console_errors_observed": [],
  "screenshots": [
    "ai-dev/active/CR-00030/evidences/post/CR-00030_v4_5h_placeholder.png",
    "ai-dev/active/CR-00030/evidences/post/CR-00030_v5_no_regressions.png"
  ],
  "notes": "V1/V2/V3 are ENV_DATA_MISSING due to containerization. V4 and V5 pass. Overall: fail."
}
```

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S11` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/CR-00030/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/CR-00030/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**ESCALATION**: This is the FINAL browser fix cycle (3/3). **PREFER honest escalation over a Hail-Mary fix that drifts from the design spec.** If you cannot make every failing V pass while staying aligned with the design doc above, document which V's remain and why so the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
