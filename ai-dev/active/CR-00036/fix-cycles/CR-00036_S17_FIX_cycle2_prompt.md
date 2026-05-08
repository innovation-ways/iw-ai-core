# CR-00036 S17 Browser Verification Fix Cycle 2/3

The end-to-end browser verification for step S17 of work item CR-00036 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/CR-00036/ai-dev/active/CR-00036/CR-00036_CR_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

## ⚠️ Most Recent Failure (run 5)

browser env setup failed:  Container iw-ai-core-e2e-cr00036-e2e-db-1 Created 
 Container iw-ai-core-e2e-cr00036-e2e-dashboard-1 Creating 
 Container iw-ai-core-e2e-cr00036-e2e-dashboard-1 Created 
 Container iw-ai-core-e2e-cr00036-e2e-daemon-stub-1 Creating 
 Container iw-ai-core-e2e-cr00036-e2e-daemon-stub-1 Created 
 Container iw-ai-core-e2e-cr00036-e2e-db-1 Starting 
 Container iw-ai-core-e2e-cr00036-e2e-ollama-1 Starting 
 Container iw-ai-core-e2e-cr00036-e2e-db-1 Started 
 Container iw-ai-core-e2e-cr00036-e2e-ollama-1 Started 
 Container iw-ai-core-e2e-cr00036-e2e-db-1 Waiting 
 Container iw-ai-core-e2e-cr00036-e2e-ollama-1 Waiting 
 Container iw-ai-core-e2e-cr00036-e2e-ollama-1 Healthy 
 Container iw-ai-core-e2e-cr00036-e2e-db-1 Healthy 
 Container iw-ai-core-e2e-cr00036-e2e-dashboard-1 Starting 
 Container iw-ai-core-e2e-cr00036-e2e-dashboard-1 Started 
 Container iw-ai-core-e2e-cr00036-e2e-db-1 Waiting 
 Container iw-ai-core-e2e-cr00036-e2e-dashboard-1 Waiting 
 Container iw-ai-core-e2e-cr00036-e2e-db-1 Healthy 
 Container iw-ai-core-e2e-cr00036-e2e-dashboard-1 Error dependency e2e-dashboard failed to start
dependency failed to start: container iw-ai-core-e2e-cr00036-e2e-dashboard-1 exited (1)

## Container Crash Logs

### docker logs iw-ai-core-e2e-cr00036-e2e-dashboard-1 (last 50 lines)

[e2e] seeding project + architecture map...
e2e_seed: running fixture ai-dev/active/CR-00036/e2e_fixtures/001_auto_merge_off_batch.py
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
INFO  [alembic.runtime.migration] Running upgrade efd271775dc7 -> 561ddde7f5fb, add_doc_generation_jobs_public_id
INFO  [alembic.runtime.migration] Running upgrade 561ddde7f5fb -> 48218f84b69f, CR-00028 add merge_failed to batch_item_status enum
INFO  [alembic.runtime.migration] Running upgrade 48218f84b69f -> a9861af32872, Add self_assess to step_type enum.
INFO  [alembic.runtime.migration] Running upgrade a9861af32872 -> 4876b3246ff2, Add impacted_paths to work_items (F-00076)
INFO  [alembic.runtime.migration] Backfilled 0 items with impacted_paths (F-00076)
INFO  [alembic.runtime.migration] Running upgrade 4876b3246ff2 -> e53ce8e86a3c, F-00077 chat conversations memory
INFO  [alembic.runtime.migration] Running upgrade e53ce8e86a3c -> 4cc043748e92, Add worktree_db_host/name/user/password columns to batch_items (I-00062)
INFO  [alembic.runtime.migration] Running upgrade 4cc043748e92 -> c35d5b257eab, add report column to doc_generation_jobs
INFO  [alembic.runtime.migration] Running upgrade c35d5b257eab -> 7f1a75bb5c2d, sync schema with model comments and indexes
INFO  [alembic.runtime.migration] Running upgrade 7f1a75bb5c2d -> 1713bc13a11d, add files view diff columns to work_items and step_runs
INFO  [alembic.runtime.migration] Running upgrade 1713bc13a11d -> 7fcf3ddaa283, CR-00036: auto_merge flag on Batch + awaiting_merge_approval gate state
e2e_seed: failed: type object 'Batch' has no attribute 'name'

---

## Original Browser Report (for V table context)

# CR-00036 S17 Browser Verification Report

## Environment
- Base URL used: `http://localhost:9957`
- E2E user: `dev@example.local`
- Work Item: CR-00036
- Step: S17
- Agent: qv-browser
- Date: 2026-05-08

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Toggle on create-batch form | **pass** | `CR-00036_v1_cre

...(report truncated for prompt length)...

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S17` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/CR-00036/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/CR-00036/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
