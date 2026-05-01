# I-00059 S11 Browser Verification Fix Cycle 2/3

The end-to-end browser verification for step S11 of work item I-00059 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/I-00059/ai-dev/active/I-00059/I-00059_Issue_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

## ⚠️ Most Recent Failure (run 2)

browser env setup failed:  Container iw-ai-core-e2e-i00059-e2e-db-1 Created 
 Container iw-ai-core-e2e-i00059-e2e-dashboard-1 Creating 
 Container iw-ai-core-e2e-i00059-e2e-dashboard-1 Created 
 Container iw-ai-core-e2e-i00059-e2e-daemon-stub-1 Creating 
 Container iw-ai-core-e2e-i00059-e2e-daemon-stub-1 Created 
 Container iw-ai-core-e2e-i00059-e2e-db-1 Starting 
 Container iw-ai-core-e2e-i00059-e2e-ollama-1 Starting 
 Container iw-ai-core-e2e-i00059-e2e-ollama-1 Started 
 Container iw-ai-core-e2e-i00059-e2e-db-1 Started 
 Container iw-ai-core-e2e-i00059-e2e-ollama-1 Waiting 
 Container iw-ai-core-e2e-i00059-e2e-db-1 Waiting 
 Container iw-ai-core-e2e-i00059-e2e-ollama-1 Healthy 
 Container iw-ai-core-e2e-i00059-e2e-db-1 Healthy 
 Container iw-ai-core-e2e-i00059-e2e-dashboard-1 Starting 
 Container iw-ai-core-e2e-i00059-e2e-dashboard-1 Started 
 Container iw-ai-core-e2e-i00059-e2e-dashboard-1 Waiting 
 Container iw-ai-core-e2e-i00059-e2e-db-1 Waiting 
 Container iw-ai-core-e2e-i00059-e2e-db-1 Healthy 
 Container iw-ai-core-e2e-i00059-e2e-dashboard-1 Error dependency e2e-dashboard failed to start
dependency failed to start: container iw-ai-core-e2e-i00059-e2e-dashboard-1 exited (1)

## Container Crash Logs

### docker logs iw-ai-core-e2e-i00059-e2e-dashboard-1 (last 50 lines)

[e2e] seeding project + architecture map...
e2e_seed: running fixture ai-dev/active/CR-99025/e2e_fixtures/001_cr99025_evidence_fixture.py
e2e_seed: running fixture ai-dev/active/CR-99026/e2e_fixtures/001_cr99026_oversize_fixture.py
e2e_seed: running fixture ai-dev/active/F-00055/e2e_fixtures/001_f00055_workflow.py
e2e_seed: running fixture ai-dev/active/I-00059/e2e_fixtures/001_i00059_doc_job.py
INFO  [alembic.runtime.migration] Running upgrade 6d7d3b4a3b83 -> 7e8f9a0b1c2d, Add archived_at column to batches table.
INFO  [alembic.runtime.migration] Running upgrade 7e8f9a0b1c2d -> 8e995f56934c, add run_type to test_runs
INFO  [alembic.runtime.migration] Running upgrade 8e995f56934c -> 6a5e03db855a, add_project_docs_tables
INFO  [alembic.runtime.migration] Running upgrade 6a5e03db855a -> 73a7ae48b82b, add_doc_job_agent_columns
INFO  [alembic.runtime.migration] Running upgrade 73a7ae48b82b -> add_doc_lint_warnings, add_doc_lint_warnings
INFO  [alembic.runtime.migration] Running upgrade add_doc_lint_warnings -> add_doc_job_trigger_reason, add_doc_job_trigger_reason
INFO  [alembic.runtime.migration] Running upgrade add_doc_job_trigger_reason -> add_doc_broken_links, add_doc_broken_links
INFO  [alembic.runtime.migration] Running upgrade add_doc_broken_links -> add_doc_types_functional, add_doc_type_product_overview_feature_catalog
INFO  [alembic.runtime.migration] Running upgrade add_doc_types_functional -> add_doc_type_research, add_doc_type_research
INFO  [alembic.runtime.migration] Running upgrade add_doc_type_research -> add_doc_section_guides, add_doc_section_guides
INFO  [alembic.runtime.migration] Running upgrade add_doc_section_guides -> add_section_guides_snapshot_to_jobs, add_section_guides_snapshot_to_jobs
INFO  [alembic.runtime.migration] Running upgrade add_section_guides_snapshot_to_jobs -> add_doc_type_guides, Add doc_type_guides table.
INFO  [alembic.runtime.migration] Running upgrade add_doc_type_guides -> add_guide_snapshot_to_jobs, Add guide_snapshot to doc_generation_jobs.
INFO  [alembic.runtime.migration] Running upgrade add_guide_snapshot_to_jobs -> add_doc_instance_guides, Add doc_instance_guides table.
INFO  [alembic.runtime.migration] Running upgrade add_doc_instance_guides -> b9f2c7a1e8d4, Add code_index_jobs table for Code Understanding feature.
INFO  [alembic.runtime.migration] Running upgrade b9f2c7a1e8d4 -> c4d5e6f7a8b9, Add Research value to work_item_type enum.
INFO  [alembic.runtime.migration] Running upgrade c4d5e6f7a8b9 -> a5c7d2f1e9b3, Add browser_verification value to fix_trigger enum.
INFO  [alembic.runtime.migration] Running upgrade a5c7d2f1e9b3 -> fb7e5859d479, add_fix_summary_to_fix_cycles
INFO  [alembic.runtime.migration] Running upgrade fb7e5859d479 -> 4d5e6f7a8b9c, Add entity_type column to daemon_events.
INFO  [alembic.runtime.migration] Running upgrade 4d5e6f7a8b9c -> 824e6e6f34ee, add oss compliance tables
INFO  [alembic.runtime.migration] Running upgrade 824e6e6f34ee -> 2bd86f8c105c, add iw core instance
INFO  [alembic.runtime.migration] Running upgrade 2bd86f8c105c -> 637c16395a0b, add pending migration log
INFO  [alembic.runtime.migration] Running upgrade 637c16395a0b -> 13014259ab68, add project oss job
INFO  [alembic.runtime.migration] Running upgrade 13014259ab68 -> 3035dfc20db5, add qv_baselines table (F-00061)
INFO  [alembic.runtime.migration] Running upgrade 3035dfc20db5 -> 1fb2eb17b580, add functional_doc columns to work_items
INFO  [alembic.runtime.migration] Running upgrade 1fb2eb17b580 -> 74f9b2350784, Add doc_index_jobs table for hybrid doc Q&A feature.
INFO  [alembic.runtime.migration] Running upgrade 1fb2eb17b580 -> 9ef17911f546, CR-00019: add awaiting_review/discarded to project_oss_job_status enum, add columns to project_oss_job and oss_finding
INFO  [alembic.runtime.migration] Running upgrade 9ef17911f546, 74f9b2350784 -> d6b67d4ecb9f, add work_item_evidences
INFO  [alembic.runtime.migration] Running upgrade d6b67d4ecb9f -> 40af3b76e1d5, CR-00021 rebase pipeline phase
INFO  [alembic.runtime.migration] Running upgrade 40af3b76e1d5 -> 550aecbbd42b, F-00062: add worktree compose stack columns and setup_failed status to batch_items
INFO  [alembic.runtime.migration] Running upgrade 550aecbbd42b -> c062b6bf5eb3, CR-00022 OSS redesign: drop prepare/publish, add auto_apply_safe
INFO  [alembic.runtime.migration] Running upgrade c062b6bf5eb3 -> cr00023workflow, CR-00023: add command/gate/timeout_secs to workflow_steps
INFO  [alembic.runtime.migration] Running upgrade cr00023workflow -> cr00024warned50, CR-00024: add warned_50pct_at to step_runs
INFO  [alembic.runtime.migration] Running upgrade cr00024warned50 -> 09457f0ef2e6, add oss_finding_detail table
INFO  [alembic.runtime.migration] Running upgrade 09457f0ef2e6 -> bd4ed52cad71, I-00042 add migration_invalid and migration_rolled_back to batch_item_status
INFO  [alembic.runtime.migration] Running upgrade bd4ed52cad71 -> fdf63560ff02, Add public_id (O-XXXXX) to project_oss_job and backfill
INFO  [alembic.runtime.migration] Running upgrade fdf63560ff02 -> add_diagram_doc_type, add_diagram_doc_type
INFO  [alembic.runtime.migration] Running upgrade add_diagram_doc_type -> 66366e97079b, Add public_id (CM-XXXXX) to code_index_jobs and backfill
INFO  [alembic.runtime.migration] Running upgrade add_diagram_doc_type -> 4d9ec0083240, f00074_add_keepalive_tables
INFO  [alembic.runtime.migration] Running upgrade 4d9ec0083240, 66366e97079b -> efd271775dc7, merge_f00074_keepalive_and_cm_public_id
e2e_seed: failed: (psycopg.errors.ForeignKeyViolation) insert or update on table "doc_generation_jobs" violates foreign key constraint "doc_generation_jobs_doc_id_fkey"
DETAIL:  Key (doc_id)=(iw-ai-core:code-index) is not present in table "project_docs".
[SQL: INSERT INTO doc_generation_jobs (id, project_id, doc_id, status, requested_at, started_at, completed_at, agent_output, error, agent_pid, skill_used, trigger_reason, lint_warnings, duration_seconds, section_guides_snapshot, guide_snapshot, created_at) VALUES (%(id)s::VARCHAR, %(project_id)s::VARCHAR, %(doc_id)s::VARCHAR, %(status)s, %(requested_at)s::TIMESTAMP WITH TIME ZONE, %(started_at)s::TIMESTAMP WITH TIME ZONE, %(completed_at)s::TIMESTAMP WITH TIME ZONE, %(agent_output)s::VARCHAR, %(error)s::VARCHAR, %(agent_pid)s::INTEGER, %(skill_used)s::VARCHAR, %(trigger_reason)s::VARCHAR, %(lint_warnings)s::JSONB, %(duration_seconds)s::INTEGER, %(section_guides_snapshot)s::JSONB, %(guide_snapshot)s::VARCHAR, %(created_at)s::TIMESTAMP WITH TIME ZONE)]
[parameters: {'id': '2fb5a9a9-4b2d-4fb0-9209-d27f0bdf4435', 'project_id': 'iw-ai-core', 'doc_id': 'iw-ai-core:code-index', 'status': 'failed', 'requested_at': dateti

...(report truncated for prompt length)...

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S11` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/I-00059/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/I-00059/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
