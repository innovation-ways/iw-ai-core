# IW AI Core — Migration Checklist

**Project**: IW AI Core (Innovation Ways AI Orchestration Platform)
**Author**: Sergio G. + Claude
**Date**: 2026-04-07
**Version**: 1.0.0
**Status**: Draft

---

## 1. Overview

This is the step-by-step checklist for migrating from InnoForge's embedded AI orchestration system to the standalone IW AI Core platform.

**Approach**: Clean cut. Fresh start. No history import. Shutdown the old system, stand up the new one, verify, go live.

**Pre-conditions:**
- No batches currently executing (finish or stop all active batches first)
- No agents running in worktrees (kill or wait for completion)
- All completed work items in `ai-dev/done/` are acceptable to leave as-is in git history (they won't be migrated)

**Estimated time**: 2-3 days (not counting implementation of iw-ai-core itself)

---

## 2. Phase 1: Create iw-ai-core Repository

### 2.1. Repository Setup

- [ ] Create repo directory: `mkdir /home/sergiog/dev/iw-ai-core`
- [ ] Initialize git: `cd /home/sergiog/dev/iw-ai-core && git init`
- [ ] Create `.gitignore`:
  ```
  .env
  .venv/
  __pycache__/
  *.pyc
  archive/
  logs/
  .daemon.pid
  *.egg-info/
  dist/
  .mypy_cache/
  .ruff_cache/
  .pytest_cache/
  ```
- [ ] Create `.env.example` (from Tech Stack doc section 8.1)
- [ ] Copy `.env.example` to `.env` and adjust values for local environment
- [ ] Create `pyproject.toml` (from Tech Stack doc section 7)
- [ ] Create `Makefile` (from Tech Stack doc section 6)
- [ ] Create `.pre-commit-config.yaml`
- [ ] Create `CLAUDE.md` (platform-level AI context)

### 2.2. Project Structure

Create the directory skeleton:

- [ ] `orch/` — Python package root
- [ ] `orch/__init__.py`
- [ ] `orch/cli/` — Click CLI commands
- [ ] `orch/daemon/` — Daemon main loop + batch manager
- [ ] `orch/db/` — SQLAlchemy models + session
- [ ] `orch/db/migrations/` — Alembic
- [ ] `orch/archive/` — Two-tier archive system
- [ ] `orch/skills/` — Skill sync engine
- [ ] `orch/config.py` — .env loading + configuration
- [ ] `executor/` — Bash scripts
- [ ] `dashboard/` — FastAPI web dashboard
- [ ] `dashboard/routers/`
- [ ] `dashboard/templates/`
- [ ] `dashboard/static/`
- [ ] `skills/` — Master skill copies
- [ ] `templates/` — Default workflow templates
- [ ] `archive/` — Compressed artifacts (with `.gitkeep`)
- [ ] `logs/` — Daemon logs (with `.gitkeep`)
- [ ] `tests/`
- [ ] `tests/unit/`
- [ ] `tests/integration/`
- [ ] `tests/fixtures/`

### 2.3. Dependencies

- [ ] Install uv: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- [ ] Create venv + install deps: `uv sync`
- [ ] Verify: `uv run python -c "import sqlalchemy; import click; import fastapi; print('OK')"`

---

## 3. Phase 2: Database Setup

### 3.1. PostgreSQL Container

- [ ] Create `docker-compose.yml` (from Tech Stack doc section 8.2)
- [ ] Start container: `docker compose up -d`
- [ ] Verify connection: `psql -h localhost -p $IW_CORE_DB_PORT -U $IW_CORE_DB_USER -d $IW_CORE_DB_NAME -c "SELECT 1"`

### 3.2. Schema

- [ ] Create SQLAlchemy models in `orch/db/models.py` (from Database Schema doc)
- [ ] Configure Alembic: `uv run alembic init orch/db/migrations`
- [ ] Update `orch/db/migrations/env.py` to use models + config
- [ ] Generate initial migration: `uv run alembic revision --autogenerate -m "initial schema"`
- [ ] Review generated migration (verify all tables, ENUMs, indexes, triggers)
- [ ] Run migration: `uv run alembic upgrade head`
- [ ] Verify schema: `psql ... -c "\dt"` (should show all 10 tables)
- [ ] Verify ENUMs: `psql ... -c "\dT+"` (should show all enum types)
- [ ] Verify FTS trigger: `psql ... -c "\df work_items_fts_update"`

---

## 4. Phase 3: Port Core Logic

### 4.1. Configuration

- [ ] Implement `orch/config.py` — loads `.env`, builds DB URL, validates required vars
- [ ] Test: missing env var produces clear error, not cryptic crash

### 4.2. Database Session

- [ ] Implement `orch/db/session.py` — engine + session factory (sync SQLAlchemy)
- [ ] Test: session connects to the test container (testcontainers)

### 4.3. `iw` CLI — Core Commands

Port in this order (each is independently testable):

- [ ] `orch/cli/main.py` — Click group entry point
- [ ] `orch/cli/id_commands.py` — `iw next-id`, `iw current-project`
  - Test: concurrent ID allocation produces no duplicates (integration test with threading)
- [ ] `orch/cli/item_commands.py` — `iw register`, `iw approve`, `iw unapprove`, `iw archive`, `iw item-status`
  - Test: register idempotency, state transition validation
- [ ] `orch/cli/step_commands.py` — `iw step-start`, `iw step-done`, `iw step-fail`
  - Test: valid/invalid transitions
- [ ] `orch/cli/batch_commands.py` — `iw batch-create`, `iw batch-approve`, `iw batch-status`, `iw batch-pause`, `iw batch-resume`
  - Test: dependency analysis, execution groups
- [ ] `orch/cli/lock_commands.py` — `iw migration-lock acquire/release/status`
  - Test: concurrent acquisition (integration test)
- [ ] `orch/cli/skill_commands.py` — `iw sync-skills`, `iw init-project`
- [ ] `orch/cli/search_commands.py` — `iw search`
  - Test: FTS query against sample data
- [ ] `orch/cli/daemon_commands.py` — `iw daemon start/stop/status`
- [ ] Register entry point in `pyproject.toml`: `iw = "orch.cli.main:cli"`
- [ ] Install: `uv pip install -e .`
- [ ] Verify: `iw --help` shows all command groups

### 4.4. Daemon

- [ ] `orch/daemon/state_machine.py` — valid state transitions for all entities
  - Port from: `scripts/ai_dev_daemon/state_machine.py`
  - Changes: add new statuses (killed, stalled, merging), use ENUMs
  - Test: all valid transitions pass, all invalid transitions reject
- [ ] `orch/daemon/step_monitor.py` — PID health, timeout, stall, zombie detection
  - New code (not a direct port — current system uses manifest file checks)
  - Test: mock os.kill, freezegun for timeouts
- [ ] `orch/daemon/batch_manager.py` — per-project batch processing
  - Port from: `scripts/ai_dev_daemon/batch_manager.py`
  - Changes: DB queries instead of file scanning, project_id parameterized
  - Test: batch lifecycle with DB state
- [ ] `orch/daemon/merge_queue.py` — sequential merge per project
  - Port from: merge logic in `scripts/ai_dev_daemon/batch_manager.py`
  - Changes: DB-backed queue instead of manifest-based
- [ ] `orch/daemon/project_registry.py` — project discovery, config loading
  - Port from: inline code in `scripts/ai_dev_daemon/daemon.py`
  - Changes: reads `projects.toml`, updates DB
- [ ] `orch/daemon/main.py` — main loop, signal handlers, startup/shutdown
  - Port from: `scripts/ai_dev_daemon/daemon.py`
  - Changes: multi-project loop, DB-backed state, orphan detection on startup
- [ ] `orch/daemon/quota_monitor.py` — LLM quota polling (Phase 2, stub for now)
- [ ] `orch/daemon/git_status.py` — git status per project (Phase 2, stub for now)

### 4.5. Executor Scripts

- [ ] `executor/step_executor.sh` — port from `scripts/step_executor.sh`
  - Changes: add `project_repo_root` parameter, remove manifest file writes (state goes through `iw` CLI)
- [ ] `executor/step_executor_lib.sh` — port from `scripts/step_executor_lib.sh`
  - Changes: replace `set_step_status` (manifest write) with `iw step-done`/`iw step-fail` calls
- [ ] `executor/worktree_setup.sh` — port from `scripts/worktree_setup.sh`
  - Changes: write `execution_brief.json` from DB data, sync skills from iw-ai-core
- [ ] `executor/worktree_commit.sh` — port from `scripts/worktree_commit.sh`
  - Changes: minimal — squash-merge logic stays the same
- [ ] Test executor scripts manually against InnoForge repo

### 4.6. Archive System

- [ ] `orch/archive/archiver.py` — Tier 1 (DB content) + Tier 2 (compress to .tar.zst)
  - New code
  - Test: archive creates DB content + compressed file, verify extraction
- [ ] `orch/archive/extractor.py` — on-demand extraction to tmp with TTL cleanup
  - New code
  - Test: extract, verify files, verify cleanup after TTL

### 4.7. Skill Sync Engine

- [ ] `orch/skills/sync.py` — version comparison, copy, lock file management
  - New code
  - Test: sync copies new skills, skips overrides, updates lock file

---

## 5. Phase 4: Dashboard

### 5.1. Foundation

- [ ] `dashboard/app.py` — FastAPI application factory
- [ ] `dashboard/dependencies.py` — DB session dependency, project context
- [ ] `dashboard/static/theme.css` — Discord theme CSS variables (from Dashboard Design doc)
- [ ] `dashboard/templates/base.html` — Shell layout with sidebar, htmx, Tailwind CDN, dark mode
- [ ] `dashboard/templates/components/` — Jinja2 macros (status_badge, step_pipeline, card, etc.)
- [ ] Verify: `make dashboard-start` serves at `http://localhost:$IW_CORE_DASHBOARD_PORT`

### 5.2. Pages (in priority order)

- [ ] Project selector (`/`)
- [ ] Running tasks (`/system/running`) — the most important page
- [ ] Project dashboard (`/project/{id}/`)
- [ ] Batch list (`/project/{id}/batches`)
- [ ] Batch detail (`/project/{id}/batch/{bid}`)
- [ ] Work item detail (`/project/{id}/item/{iid}`) with tabs (overview, design doc, reports, artifacts)
- [ ] Queue & backlog (`/project/{id}/queue`)
- [ ] History (`/project/{id}/history`)
- [ ] System status (`/system/status`)

### 5.3. Action Endpoints

- [ ] Kill step: `POST /project/{id}/api/item/{iid}/kill-step/{n}`
- [ ] Restart step: `POST /project/{id}/api/item/{iid}/restart-step/{n}`
- [ ] Skip step: `POST /project/{id}/api/item/{iid}/skip-step/{n}`
- [ ] Restart from step N: `POST /project/{id}/api/item/{iid}/restart-from/{n}`
- [ ] Batch approve/pause/resume/archive

### 5.4. SSE

- [ ] `dashboard/routers/sse.py` — event stream endpoint
- [ ] Live running table updates
- [ ] Toast notifications for failures/completions

---

## 6. Phase 5: Skills Migration

### 6.1. Master Skills (copy to iw-ai-core/skills/)

Platform skills (workflow and orchestration):

- [ ] `iw-new-incident` — update to use `iw next-id` + `iw register` instead of markdown tracking
- [ ] `iw-new-feature` — same updates
- [ ] `iw-new-cr` — same updates
- [ ] `iw-batch-execute` — update to use `iw batch-create` + `iw batch-approve`
- [ ] `iw-batch-status` — update to use `iw batch-status`
- [ ] `iw-batch-stop` — update to use `iw batch-pause`
- [ ] `iw-workflow` / `iw-execute` — update to read workflow from `ai-dev/workflow.md`, report via `iw` CLI
- [ ] `iw-review-design` — minimal changes (reads design files, no state writes)

Content and brand skills (no state interaction — copy as-is):

- [ ] `iw-brand-config`
- [ ] `iw-blog-writer`
- [ ] `iw-tech-doc-writer`
- [ ] `iw-pitch-deck`
- [ ] `iw-promo-writer`
- [ ] `iw-doc-generator`
- [ ] `iw-doc-system`
- [ ] `iw-draw-io`
- [ ] `iw-diagram-generator`

### 6.2. Default Workflow Templates

- [ ] Copy `ai-dev/templates/Feature_Design_Template.md` to `iw-ai-core/templates/`
- [ ] Copy `ai-dev/templates/Issue_Design_Template.md`
- [ ] Copy `ai-dev/templates/CR_Design_Template.md`
- [ ] Copy all other templates (Implementation, CodeReview, QV, etc.)

### 6.3. OpenCode Agents (stay in project repos)

These are implementation agents specific to each project. They stay in the project repo (`.opencode/agents/`):

- [ ] Verify all InnoForge agents still work: `backend-impl`, `frontend-impl`, `api-impl`, `database-impl`, etc.
- [ ] No changes needed — agents read prompts and write code, they don't interact with the orchestration state

### 6.4. OpenCode Commands (port orchestration commands to iw-ai-core skills)

Current `.opencode/commands/` that handle orchestration:

- [ ] `execute.md` → port logic to `iw-ai-core/skills/iw-execute/`
- [ ] `execute_batch.md` → port to `iw-ai-core/skills/iw-batch-execute/`
- [ ] `batch_status.md` → port to `iw-ai-core/skills/iw-batch-status/`
- [ ] `batch_stop.md` → port to `iw-ai-core/skills/iw-batch-stop/`
- [ ] `iw-new-incident.md` → port to `iw-ai-core/skills/iw-new-incident/`
- [ ] `iw-new-feature.md` → port to `iw-ai-core/skills/iw-new-feature/`
- [ ] `iw-new-cr.md` → port to `iw-ai-core/skills/iw-new-cr/`
- [ ] `analyze_item.md` → port to `iw-ai-core/skills/analyze-item/`
- [ ] `fix_item.md` → port to `iw-ai-core/skills/fix-item/`

Project-specific commands (stay in project repo):

- [ ] `e2e-test.md` — InnoForge-specific, stays

---

## 7. Phase 6: Register InnoForge

### 7.1. Create Project Config

- [ ] Create `/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan/.iw-orch.json`:
  ```json
  {
    "project_id": "innoforge",
    "display_name": "InnoForge Document Platform",
    "repo_root": "/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan",
    "dev_clone": "/home/sergiog/dev/iw-doc-plan/development/iw-doc-plan",
    "id_prefixes": { "Feature": "F", "Issue": "I", "ChangeRequest": "CR", "Batch": "BATCH" },
    "worktree_base": ".worktrees",
    "ai_dev_dir": "ai-dev",
    "cli_tool": "opencode",
    "quality_gates": ["ruff", "mypy", "pytest", "coverage", "semgrep"],
    "max_parallel": 4,
    "branch_prefix": "agent",
    "timeout_overrides": {}
  }
  ```
- [ ] Also create `.iw-orch.json` in the development clone (same `project_id`)

### 7.2. Register in Platform

- [ ] Add to `iw-ai-core/projects.toml`:
  ```toml
  [[project]]
  id = "innoforge"
  path = "/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan"
  enabled = true
  ```
- [ ] Register in DB: `iw init-project --id innoforge --path /home/sergiog/dev/iw-doc-plan/main/iw-doc-plan --name "InnoForge Document Platform"`
- [ ] Verify: `iw projects list` shows InnoForge

### 7.3. Create Workflow Definition

- [ ] Create `ai-dev/workflow.md` in InnoForge repo defining the step pipeline:
  - Implementation steps (Backend, Frontend, API, Database, Pipeline, Template)
  - Per-agent code review after each implementation step
  - Global code review
  - Individual QV gate steps (lint, format, typecheck, arch, security, tests)
  - Browser verification (conditional)

### 7.4. Sync Skills

- [ ] Run `iw sync-skills --project innoforge`
- [ ] Verify: `.claude/skills/` in both clones has updated skills
- [ ] Verify: InnoForge-specific skills (`innoforge-testing`, `innoforge-ui`) are preserved as overrides

### 7.5. Prepare ai-dev Directory

- [ ] Create `ai-dev/design/active/` if it doesn't exist
- [ ] Verify `ai-dev/workflow.md` exists
- [ ] Verify `ai-dev/templates/` exists with project-specific templates (if any)

---

## 8. Phase 7: Cleanup InnoForge

### 8.1. Stop Old System

- [ ] Stop the old daemon: check for `.ai-dev-daemon.pid` and kill the process
- [ ] Stop the old dashboard: kill the process on port 9898
- [ ] Verify: no old daemon or dashboard processes running

### 8.2. Delete Moved Files

These files have been ported to iw-ai-core and are no longer needed in InnoForge:

- [ ] `scripts/ai_dev_daemon/` → now `iw-ai-core/orch/daemon/`
- [ ] `scripts/ai_dashboard/` → now `iw-ai-core/dashboard/`
- [ ] `scripts/step_executor.sh` → now `iw-ai-core/executor/`
- [ ] `scripts/step_executor_lib.sh` → now `iw-ai-core/executor/`
- [ ] `scripts/worktree_setup.sh` → now `iw-ai-core/executor/`
- [ ] `scripts/worktree_commit.sh` → now `iw-ai-core/executor/`
- [ ] `scripts/worktree_verify.sh` → now `iw-ai-core/executor/`
- [ ] `scripts/batch_dispatcher.sh` → now `iw-ai-core/orch/daemon/`
- [ ] `scripts/batch_launch.sh` → now `iw-ai-core/orch/daemon/`

### 8.3. Delete Replaced Files

These files are replaced by the database:

- [ ] `ai-dev/tracking/Features_tracking.md` → now `id_sequences` table
- [ ] `ai-dev/tracking/Incident_tracking.md` → now `id_sequences` table
- [ ] `ai-dev/tracking/Change_Request_tracking.md` → now `id_sequences` table
- [ ] `ai-dev/tracking/Batch_tracking.md` → now `id_sequences` table
- [ ] `ai-dev/tracking/migration_lock.json` → now `migration_locks` table
- [ ] Delete the entire `ai-dev/tracking/` directory
- [ ] `ai-dev/work/` (if exists) — execution state now in DB. Delete any remaining manifest JSONs.

### 8.4. Delete Ported Skills and Commands

These are now master copies in iw-ai-core (synced to project via `iw sync-skills`):

- [ ] `.opencode/commands/execute.md` → now in iw-ai-core skills
- [ ] `.opencode/commands/execute_batch.md` → now in iw-ai-core skills
- [ ] `.opencode/commands/batch_status.md` → now in iw-ai-core skills
- [ ] `.opencode/commands/batch_stop.md` → now in iw-ai-core skills
- [ ] `.opencode/commands/iw-new-incident.md` → now in iw-ai-core skills
- [ ] `.opencode/commands/iw-new-feature.md` → now in iw-ai-core skills
- [ ] `.opencode/commands/iw-new-cr.md` → now in iw-ai-core skills
- [ ] `.opencode/commands/analyze_item.md` → now in iw-ai-core skills
- [ ] `.opencode/commands/fix_item.md` → now in iw-ai-core skills

Keep project-specific commands:
- [ ] `.opencode/commands/e2e-test.md` — InnoForge-specific

### 8.5. Update Makefile

Replace old targets that call deleted scripts with new targets that call `iw` CLI:

- [ ] `worktree-new` → `iw worktree-new` or delegate to iw-ai-core
- [ ] `worktree-merge` → `iw worktree-merge` or delegate
- [ ] `worktree-cleanup` → `iw worktree-cleanup` or delegate
- [ ] `worktree-list` → `iw worktree-list` or delegate
- [ ] `batch-launch` → `iw batch-approve $(BATCH)`
- [ ] `batch-status` → `iw batch-status $(BATCH)`
- [ ] `batch-pause` → `iw batch-pause $(BATCH)`
- [ ] `batch-resume` → `iw batch-resume $(BATCH)`
- [ ] `ai-dashboard` → remove (dashboard is now at iw-ai-core)
- [ ] Remove all `worktree-*` targets that reference deleted scripts

### 8.6. Update CLAUDE.md

- [ ] Remove references to `scripts/ai_dev_daemon/`, `scripts/ai_dashboard/`
- [ ] Remove references to `ai-dev/tracking/` files
- [ ] Remove references to `ai-dev/work/` manifest JSONs
- [ ] Add reference to iw-ai-core platform and `iw` CLI
- [ ] Update workflow section to reference `ai-dev/workflow.md` and `iw` CLI
- [ ] Update batch execution section to reference `iw` CLI
- [ ] Update branch strategy section (agent branches now managed by iw-ai-core daemon)

### 8.7. Update ai-dev/CLAUDE.md

- [ ] Remove references to markdown tracking files
- [ ] Remove references to `ai-dev/work/` folder and manifest JSONs
- [ ] Update workflow section: state goes through `iw` CLI, not file writes
- [ ] Update folder structure: only `ai-dev/design/active/` exists (no `done/`, no `tracking/`, no `work/`)
- [ ] Update step lifecycle to reference `iw step-start`/`iw step-done`/`iw step-fail`

### 8.8. Keep (do NOT delete)

- [ ] `ai-dev/design/active/` — active work items (in-flight)
- [ ] `ai-dev/design/done/` — historical archive (leave in git history, don't add new items)
- [ ] `ai-dev/templates/` — project-specific prompt templates (if any overrides)
- [ ] `ai-dev/workflow.md` — workflow step definition
- [ ] `.claude/skills/` — synced from iw-ai-core + project overrides
- [ ] `.opencode/agents/` — project-specific implementation agents (unchanged)
- [ ] `.opencode/commands/e2e-test.md` — project-specific

---

## 9. Phase 8: Verification

### 9.1. Platform Health

- [ ] `docker compose ps` — PostgreSQL running on configured port
- [ ] `iw daemon start` — daemon starts without errors
- [ ] `iw daemon status` — shows running, 1 project enabled
- [ ] Open dashboard at `http://localhost:$IW_CORE_DASHBOARD_PORT` — project selector shows InnoForge
- [ ] Click InnoForge → project dashboard loads

### 9.2. End-to-End: Create Work Item

- [ ] `cd /home/sergiog/dev/iw-doc-plan/development/iw-doc-plan`
- [ ] Run `/iw-new-incident` in Claude Code
- [ ] Verify: `iw next-id` returns I001 (fresh start)
- [ ] Verify: design doc created in `ai-dev/design/active/I001/`
- [ ] Verify: `iw register` records item in DB
- [ ] Verify: item appears in dashboard queue
- [ ] `iw approve I001` — status changes to approved
- [ ] Verify: dashboard shows I001 as approved

### 9.3. End-to-End: Batch Execution

- [ ] Create a small test incident (simple fix, 1-2 steps)
- [ ] `iw batch-create I001 --project innoforge`
- [ ] `iw batch-approve BATCH-001`
- [ ] Verify: daemon picks up batch (check dashboard or `iw batch-status BATCH-001`)
- [ ] Verify: worktree created at `.worktrees/I001/`
- [ ] Verify: agent launches, PID recorded in DB
- [ ] Verify: running tasks page shows the step with live duration
- [ ] Wait for completion (or kill and restart to test recovery)
- [ ] Verify: merge succeeds
- [ ] Verify: dashboard shows item as merged

### 9.4. End-to-End: Recovery Actions

- [ ] Create another test item, start execution
- [ ] Click [Kill] on a running step — verify PID killed, status updated
- [ ] Click [Restart] on the killed step — verify new run created, agent re-launches
- [ ] Click [Skip] on a failed step — verify workflow advances to next step

### 9.5. End-to-End: Archive

- [ ] Complete a test item through the full workflow
- [ ] `iw archive I001 --project innoforge`
- [ ] Verify: design doc in `work_items.design_doc_content` (query DB)
- [ ] Verify: `.tar.zst` exists in `archive/innoforge/I001.tar.zst`
- [ ] Verify: `ai-dev/design/active/I001/` deleted from project repo
- [ ] Verify: dashboard renders design doc for I001 (from DB)

### 9.6. End-to-End: Search

- [ ] `iw search "template" --project innoforge`
- [ ] Verify: returns the archived test item
- [ ] Verify: dashboard search bar works

### 9.7. Daemon Resilience

- [ ] Start a batch with an executing item
- [ ] Kill the daemon: `kill $(cat .daemon.pid)`
- [ ] Restart: `iw daemon start`
- [ ] Verify: daemon detects running PID (if still alive) or marks as failed (if dead)
- [ ] Verify: no state corruption — items resume or are correctly marked

---

## 10. Phase 9: Commit & Go Live

- [ ] Commit iw-ai-core repo: `git add -A && git commit -m "feat: initial IW AI Core platform"`
- [ ] Commit InnoForge cleanup: `git add -A && git commit -m "chore: remove embedded AI orchestration (moved to iw-ai-core)"`
- [ ] Start daily use with the new system
- [ ] Monitor for issues over the first week
- [ ] After 1 week of stable operation: delete `ai-dev/design/done/` from InnoForge (optional — the history is in git if ever needed)

---

## 11. Rollback Plan

If the migration fails and you need to go back:

1. Stop iw-ai-core daemon: `iw daemon stop`
2. Stop iw-ai-core dashboard
3. Git revert the InnoForge cleanup commit: `git revert HEAD`
4. Restart old daemon: `python -m scripts.ai_dev_daemon`
5. Restart old dashboard: `make ai-dashboard`
6. Everything is back to file-based tracking

The old system's files are in git history even after deletion. A single `git revert` restores them.

---

## 12. Post-Migration Cleanup (After 1 Week Stable)

- [ ] Remove `ai-dev/design/done/` from InnoForge (large folder, no longer needed — DB has the content)
- [ ] Remove old `.opencode/commands/` that were ported (if not already done in Phase 7)
- [ ] Run `git gc --aggressive` on InnoForge repo to reclaim space
- [ ] Back up `iw-ai-core/archive/` directory (not in git — needs separate backup)
- [ ] Set up a cron job or script for regular archive backups
- [ ] Document the new workflow in InnoForge's CLAUDE.md for future reference
