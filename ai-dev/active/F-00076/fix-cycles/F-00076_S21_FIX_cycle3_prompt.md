# F-00076 S21 Browser Verification Fix Cycle 3/3

The end-to-end browser verification for step S21 of work item F-00076 failed. The qv-browser agent ran V1..V(n) against the isolated E2E stack (dashboard + DB built from this worktree) and reported code defects. Apply the minimum patch to make every failing V pass; the daemon will rebuild the E2E stack and re-run the browser checks.

## Design Doc — Source of Truth (READ FIRST)

The design document for this work item is the authoritative spec for the change. Read it before applying any fix:

- **Path**: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/.worktrees/F-00076/ai-dev/active/F-00076/F-00076_Feature_Design.md`
- Why this matters: prior fix cycles on this codebase have failed because the agent trusted the failure-report's *root-cause hypothesis* and drifted away from the design doc's explicit fix spec. **The design doc wins when the two disagree.**

## Diagnostic Hypothesis — Browser Verification Report

The report below is **one hypothesis** about what's broken. The qv-browser agent's *Root Cause* and `file:line` callouts are useful clues, but they are not the spec. Verify against the design doc above before applying any fix; the spec wins on conflict.

## ⚠️ Most Recent Failure (run 3)

browser env setup failed:  Container iw-ai-core-e2e-f00076-e2e-db-1 Created 
 Container iw-ai-core-e2e-f00076-e2e-dashboard-1 Creating 
 Container iw-ai-core-e2e-f00076-e2e-dashboard-1 Created 
 Container iw-ai-core-e2e-f00076-e2e-daemon-stub-1 Creating 
 Container iw-ai-core-e2e-f00076-e2e-daemon-stub-1 Created 
 Container iw-ai-core-e2e-f00076-e2e-db-1 Starting 
 Container iw-ai-core-e2e-f00076-e2e-ollama-1 Starting 
 Container iw-ai-core-e2e-f00076-e2e-db-1 Started 
 Container iw-ai-core-e2e-f00076-e2e-ollama-1 Started 
 Container iw-ai-core-e2e-f00076-e2e-ollama-1 Waiting 
 Container iw-ai-core-e2e-f00076-e2e-db-1 Waiting 
 Container iw-ai-core-e2e-f00076-e2e-ollama-1 Healthy 
 Container iw-ai-core-e2e-f00076-e2e-db-1 Healthy 
 Container iw-ai-core-e2e-f00076-e2e-dashboard-1 Starting 
 Container iw-ai-core-e2e-f00076-e2e-dashboard-1 Started 
 Container iw-ai-core-e2e-f00076-e2e-dashboard-1 Waiting 
 Container iw-ai-core-e2e-f00076-e2e-db-1 Waiting 
 Container iw-ai-core-e2e-f00076-e2e-db-1 Healthy 
 Container iw-ai-core-e2e-f00076-e2e-dashboard-1 Error dependency e2e-dashboard failed to start
dependency failed to start: container iw-ai-core-e2e-f00076-e2e-dashboard-1 exited (1)

## Container Crash Logs

### docker logs iw-ai-core-e2e-f00076-e2e-dashboard-1 (last 50 lines)

[e2e] seeding project + architecture map...
e2e_seed: running fixture ai-dev/active/CR-99025/e2e_fixtures/001_cr99025_evidence_fixture.py
e2e_seed: running fixture ai-dev/active/CR-99026/e2e_fixtures/001_cr99026_oversize_fixture.py
e2e_seed: running fixture ai-dev/active/F-00055/e2e_fixtures/001_f00055_workflow.py
e2e_seed: running fixture ai-dev/active/F-00076/e2e_fixtures/001_f00076_held_item.py
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
e2e_seed: failed: (psycopg.errors.InvalidTextRepresentation) invalid input syntax for type integer: "iw-ai-core:F-00076-S21-HELD:item_held_for_scope"
CONTEXT:  unnamed portal parameter $1 = '...'
[SQL: SELECT daemon_events.id AS daemon_events_id, daemon_events.project_id AS daemon_events_project_id, daemon_events.event_type AS daemon_events_event_type, daemon_events.entity_id AS daemon_events_entity_id, daemon_events.entity_type AS daemon_events_entity_type, daemon_events.message AS daemon_events_message, daemon_events.metadata AS daemon_events_metadata, daemon_events.created_at AS daemon_events_created_at 
FROM daemon_events 
WHERE daemon_events.id = %(pk_1)s::INTEGER]
[parameters: {'pk_1': 'iw-ai-core:F-00076-S21-HELD:item_held_for_scope'}]
(Background on this error at: https://sqlalche.me/e/20/9h9h)

---

## Original Browser Report (for V table context)

# F-00076 S21 Browser Verification Report

## Environment
- Base URL used: `http://localhost:9912` (from `$IW_BROWSER_BASE_URL`)
- E2E user: `dev@example.local` (from `$IW_BROWSER_E2E_USER`)
- Worktree: `F-00076` | Step: `S21`

## Status
**FAIL** — `ENV_DATA_MISSING`

---

## Verifications

| ID | Name | Status | Screenshot | Notes |
|----|------|--------|------------|-------|
| V1 | Item overview shows declared Impacted Paths | **fail** | — | `impacted_paths` column does not exist in E2E DB (schema behind head). E2E DB shows alert: "Or

...(report truncated for prompt length)...

## Pre-fix Procedure

1. **Read the design doc** at the path above. Look for a `Detailed Fix Specification` section or any spec for `S21` / the implementation step that this V suite verifies.
2. **Diff the target template / route / fixture against the spec.** List deviations explicitly before editing — missing attributes, wrong selectors, dropped guards. Browser failures are very often the *implementation* drifting from a spec the design doc already got right.
3. **Apply the minimum patch** to align code with the spec; failing V's should resolve as a side effect of that alignment.
4. **If the report's root-cause hypothesis disagrees with the spec, the spec wins.** Note the disagreement in your output rather than silently following the report.

## Where to look

1. The design doc above is authoritative for *what should be true*.
2. The Diagnostic Hypothesis above points at *what's currently false*; `file:line` references and screenshots are corroborating evidence, not gospel.
3. Screenshots are under `ai-dev/active/F-00076/evidences/post/` — open the ones named in the report's `v1_*`, `v2_*`, ... columns to see expected vs. actual.
4. The failing Vs typically map to:
   - `dashboard/templates/**` — if the UI rendered the wrong element
   - `dashboard/routers/**` — if an HTTP route returned the wrong status/fragment
   - `orch/cli/**` — if a CLI command emitted the wrong exit code or message
   - `orch/daemon/**` or `orch/db/**` — if a state transition is wrong
   - `scripts/e2e_*` — if the E2E stub/entrypoint diverged from the code-under-test's contract
   - `ai-dev/active/F-00076/e2e_fixtures/` — if the E2E seed is missing rows the V step needs

## Constraints

1. **Only fix the reported V(n) failures.** Do not refactor unrelated code.
2. **Preserve existing behavior** for every V that already passed — the report table flags passing Vs; do not regress them.
3. **Follow project conventions.** Read `CLAUDE.md` for patterns.
4. Do **NOT** start/stop `docker compose`, run `make e2e-up`, or invoke `playwright-cli` — the orchestrator owns the E2E stack and will rebuild it before the next browser run.
5. Run any fast unit tests near the code you touched to catch regressions before the expensive E2E re-run.


**ESCALATION**: This is the FINAL browser fix cycle (3/3). **PREFER honest escalation over a Hail-Mary fix that drifts from the design spec.** If you cannot make every failing V pass while staying aligned with the design doc above, document which V's remain and why so the human reviewer can act on the evidence.

**IMPORTANT**: Do NOT call `iw step-done` or `iw step-fail`. Simply apply the fixes and exit. The orchestrator re-launches the browser verification automatically.
