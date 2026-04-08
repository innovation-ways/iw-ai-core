# Step 16: Register InnoForge & End-to-End Verification

## Context

All components are built. Now register InnoForge as the first project and verify the entire system end-to-end.

Read these documents:
- `IW_AI_Core_Migration_Checklist.md` — sections 7 (register InnoForge), 9 (verification)

## Task

### 1. Register InnoForge

Follow the Migration Checklist section 7 exactly:

- [ ] Create `.iw-orch.json` in InnoForge main clone (`/home/sergiog/dev/iw-doc-plan/main/iw-doc-plan/`)
- [ ] Create `.iw-orch.json` in InnoForge dev clone (same project_id)
- [ ] Add to `projects.toml`
- [ ] Run `iw init-project --id innoforge --path /home/sergiog/dev/iw-doc-plan/main/iw-doc-plan --name "InnoForge Document Platform"`
- [ ] Verify: `iw projects list` shows InnoForge
- [ ] Create `ai-dev/workflow.md` in InnoForge repo with the full step pipeline (implementation, reviews, QV gates)
- [ ] Run `iw sync-skills --project innoforge`
- [ ] Verify skills synced (check `.iw-skills-lock.json`)

### 2. Update InnoForge Skills for `iw` CLI

The key skills that need updating to use `iw` CLI instead of markdown tracking:

#### `/iw-new-incident` (and `/iw-new-feature`, `/iw-new-cr`)
Update the SKILL.md to:
- Call `iw next-id --type incident` instead of reading `Incident_tracking.md`
- Call `iw register` instead of appending to tracking file
- Read workflow from `ai-dev/workflow.md` to generate step pipeline

#### `/iw-execute` (or `/execute`)
Update to:
- Read step info from DB via `iw item-status --json`
- Report progress via `iw step-start`, `iw step-done`, `iw step-fail`
- No manifest file reads/writes

#### `/iw-batch-execute`
Update to:
- Call `iw batch-create` and `iw batch-approve`

### 3. End-to-End Verification

Run through the complete verification checklist from Migration Checklist section 9:

#### 3.1 Platform Health
- [ ] PostgreSQL running on configured port
- [ ] `iw daemon start` — no errors
- [ ] Dashboard shows InnoForge at configured port

#### 3.2 Create Work Item
- [ ] `cd` into InnoForge dev clone
- [ ] Run `/iw-new-incident` in Claude Code
- [ ] Verify: ID allocated (I001), design doc created, item registered in DB
- [ ] Verify: item appears in dashboard queue
- [ ] `iw approve I001`

#### 3.3 Batch Execution
- [ ] Create a simple test incident (1-2 steps, easy fix)
- [ ] `iw batch-create I001` → `iw batch-approve BATCH-001`
- [ ] Verify: daemon picks up batch, creates worktree, launches agent
- [ ] Verify: running tasks page shows the step with live duration
- [ ] Wait for completion or test recovery actions

#### 3.4 Recovery Actions
- [ ] Kill a running step from dashboard → verify PID killed, status updated
- [ ] Restart the step → verify new run created, agent re-launches
- [ ] Skip a step → verify workflow advances

#### 3.5 Archive
- [ ] Complete a test item through the full workflow
- [ ] `iw archive I001`
- [ ] Verify: design doc in DB, .tar.zst in archive, active files deleted
- [ ] Verify: dashboard renders archived design doc

#### 3.6 Search
- [ ] `iw search "template"` → returns archived item
- [ ] Dashboard search bar works

#### 3.7 Daemon Resilience
- [ ] Kill daemon while a step is running
- [ ] Restart daemon → verify it detects the running PID or marks as failed
- [ ] No state corruption

### 4. Fix Integration Issues

Document any issues found during verification and fix them. This step may require going back to previous modules.

Common integration issues to watch for:
- Path resolution (relative vs absolute paths across project boundaries)
- CLI tool detection (opencode vs claude in different contexts)
- Skill file path references after sync
- Worktree setup script finding the right iw-ai-core executor path
- Dashboard DB session scoping (async FastAPI vs sync SQLAlchemy)

### 5. Final Quality Check

- [ ] `make check` passes (quality + all tests)
- [ ] Dashboard loads all pages without errors
- [ ] Daemon runs stable for 10+ minutes without errors in the log
- [ ] Create, execute, and archive a real work item end-to-end

## Acceptance Criteria

- [ ] InnoForge registered and visible in dashboard
- [ ] Full cycle works: create incident → approve → batch → execute → merge → archive
- [ ] Recovery actions work: kill, restart, skip from dashboard
- [ ] Search finds archived items
- [ ] Daemon survives crash and recovers
- [ ] All quality gates pass
- [ ] The system is ready for daily use
