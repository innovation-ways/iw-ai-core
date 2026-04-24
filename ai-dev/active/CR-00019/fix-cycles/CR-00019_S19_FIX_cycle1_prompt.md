# CR-00019 S19 Browser Verification Fix Cycle 1/2

The end-to-end browser verification for step S19 of work item CR-00019 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Browser Verification Report

browser env setup failed:  Container iw-ai-core-e2e-cr00019-e2e-ollama-1 Created 
 Container iw-ai-core-e2e-cr00019-e2e-db-1 Created 
 Container iw-ai-core-e2e-cr00019-e2e-dashboard-1 Creating 
 Container iw-ai-core-e2e-cr00019-e2e-dashboard-1 Created 
 Container iw-ai-core-e2e-cr00019-e2e-ollama-1 Starting 
 Container iw-ai-core-e2e-cr00019-e2e-db-1 Starting 
 Container iw-ai-core-e2e-cr00019-e2e-ollama-1 Started 
 Container iw-ai-core-e2e-cr00019-e2e-db-1 Started 
 Container iw-ai-core-e2e-cr00019-e2e-db-1 Waiting 
 Container iw-ai-core-e2e-cr00019-e2e-ollama-1 Waiting 
 Container iw-ai-core-e2e-cr00019-e2e-ollama-1 Healthy 
 Container iw-ai-core-e2e-cr00019-e2e-db-1 Healthy 
 Container iw-ai-core-e2e-cr00019-e2e-dashboard-1 Starting 
 Container iw-ai-core-e2e-cr00019-e2e-dashboard-1 Started 
 Container iw-ai-core-e2e-cr00019-e2e-db-1 Waiting 
 Container iw-ai-core-e2e-cr00019-e2e-ollama-1 Waiting 
 Container iw-ai-core-e2e-cr00019-e2e-dashboard-1 Waiting 
 Container iw-ai-core-e2e-cr00019-e2e-db-1 Healthy 
 Container iw-ai-core-e2e-cr00019-e2e-ollama-1 Healthy 
container iw-ai-core-e2e-cr00019-e2e-dashboard-1 exited (255)

## Where to look

1. Read the **Issues Found** section above for a root-cause diagnosis and `file:line` references. Trust it and start there.
2. Screenshots are under `ai-dev/active/CR-00019/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
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
