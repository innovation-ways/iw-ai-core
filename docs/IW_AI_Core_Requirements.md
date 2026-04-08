# IW AI Core — Functional Requirements

**Project**: IW AI Core (Innovation Ways AI Orchestration Platform)
**Author**: Sergio G. + Claude
**Date**: 2026-04-07
**Version**: 1.0.0
**Status**: Draft

---

## 1. Purpose & Scope

This document defines the functional and non-functional requirements for IW AI Core — a standalone platform that orchestrates AI-assisted software development across multiple projects.

**What IW AI Core is**: A centralized orchestration platform that manages the entire lifecycle of AI work items (features, incidents, change requests) from design through execution, review, quality validation, merge, and archive — across any number of software projects.

**What IW AI Core is NOT**: It is not the LLM itself, not a code editor, and not a CI/CD pipeline. It orchestrates LLM agents (Claude Code, OpenCode) and manages the workflow around them.

---

## 2. User Persona

There is a single user persona for v1:

### The Solo Developer-Operator

**Name**: Sergio (representative)
**Role**: Full-stack developer who uses LLM agents as a force multiplier
**Environment**: Single development machine, multiple project repos

**Daily workflow:**

1. **Morning / Active work**: Uses Claude Code or OpenCode CLI to create new work items (incidents, features, CRs). Reviews designs, refines prompts. Prepares batches of items for execution.

2. **Batch execution**: Approves batches from the dashboard. Launches them. Items execute in parallel via LLM agents in isolated git worktrees.

3. **Monitoring**: Switches to the dashboard to track progress. Checks which items are running, which have completed, which have failed. Intervenes when needed (restart, kill, skip).

4. **Overnight / Background**: Leaves batches running while sleeping or working on other tasks. Expects the system to handle failures gracefully — retry where possible, mark as failed where not, never corrupt state.

5. **Next day**: Reviews completed items. Merges to main. Archives completed work. Publishes to origin. Starts the next cycle.

**Key frustrations with current system:**
- Spends significant time chasing operational issues instead of building software
- Zombie processes that linger after crashes
- Workflows corrupted mid-execution (partial state in JSON manifests)
- OpenCode instances that crash without cleanup
- Restarting a failed step requires manual file editing and deep knowledge of the system internals
- No single view of "what's running right now across everything"
- ID collisions when multiple agents create work items concurrently

**What success looks like:**
- The platform is reliable enough to run overnight batches without intervention
- When something fails, recovery is one click — not 10 minutes of file forensics
- All operational state is visible from the dashboard — no SSH needed
- Adding a new project takes minutes, not days of script copying

---

## 3. Core Workflows

### 3.1. WF-01: Create a Work Item

**Trigger**: Developer runs `/iw-new-incident`, `/iw-new-feature`, or `/iw-new-cr` in Claude Code (inside any registered project repo)

**Flow:**
1. Skill calls `iw next-id` to atomically allocate the next sequential ID
2. LLM creates design document, prompts, and workflow manifest as files in the project repo
3. Skill calls `iw register` to record the work item in the database
4. Work item appears in the dashboard queue with status `draft`

**Requirements:**
- REQ-WF01-01: ID allocation MUST be atomic — no duplicate IDs under any concurrency scenario
- REQ-WF01-02: Work item registration MUST be idempotent — calling `iw register` twice with the same ID has no effect
- REQ-WF01-03: If the LLM session crashes after creating files but before calling `iw register`, the skill's error handling MUST still register the item
- REQ-WF01-04: The `iw` CLI MUST auto-detect the current project from `.iw-orch.json` up the directory tree
- REQ-WF01-05: Design document and prompts MUST be created in the project repo (not iw-ai-core) at `ai-dev/design/active/<ID>/`

### 3.2. WF-02: Review and Approve a Work Item

**Trigger**: Developer reviews a draft work item in the dashboard or CLI

**Flow:**
1. Developer opens the work item in the dashboard — sees design doc, prompts, step pipeline
2. Developer may edit files directly in their editor (content stays in project repo)
3. Developer approves via dashboard button or `iw approve <ID>`
4. Work item status transitions: `draft` -> `approved`
5. Item appears in the "Ready for Execution" queue

**Requirements:**
- REQ-WF02-01: Dashboard MUST render the design document as formatted HTML (from DB Tier 1 content or from file for active items)
- REQ-WF02-02: Dashboard MUST show the complete step pipeline with agent labels and step types
- REQ-WF02-03: Approval MUST be an explicit user action — never automatic
- REQ-WF02-04: Approval MUST be reversible — `iw unapprove <ID>` returns to `draft` (only if not yet in a batch)

### 3.3. WF-03: Plan and Launch a Batch

**Trigger**: Developer selects approved items for batch execution

**Flow:**
1. Developer runs `/iw-batch-execute I001 I002 I003` or selects items in dashboard
2. Platform analyzes dependencies, creates execution groups
3. Batch created with status `planning`
4. Developer reviews the plan (execution order, parallelism)
5. Developer approves the batch: `make batch-launch BATCH=BATCH-001` or dashboard button
6. Batch status: `approved` -> daemon picks it up

**Requirements:**
- REQ-WF03-01: Batch planning MUST analyze `depends_on` fields to determine execution order
- REQ-WF03-02: Independent items MUST be assigned to parallel execution groups
- REQ-WF03-03: Maximum parallelism MUST be configurable per project (default: 4)
- REQ-WF03-04: Batch launch MUST require explicit human approval
- REQ-WF03-05: A single work item MUST NOT be in multiple active batches simultaneously

### 3.4. WF-04: Execute a Work Item (Automated)

**Trigger**: Daemon picks up an approved batch and launches items

**Flow:**
1. Daemon creates git worktree for the item
2. Daemon installs dependencies, syncs skills, writes execution brief
3. Daemon launches LLM agent in the worktree
4. Agent executes steps sequentially: implementation -> code review -> fix cycles -> QV gates
5. Each step reports status via `iw` CLI
6. On completion: daemon merges worktree branch to main

**Requirements:**
- REQ-WF04-01: Worktree creation MUST be done by deterministic bash scripts, never by LLM agents
- REQ-WF04-02: Each step launch MUST record: PID, command, worktree path, CLI tool, timeout, start time
- REQ-WF04-03: Daemon MUST check PID health every poll cycle (kill -0)
- REQ-WF04-04: Daemon MUST detect and mark timed-out steps (per step-type timeout, not global)
- REQ-WF04-05: Daemon MUST detect zombie processes (PID dead but status still 'running')
- REQ-WF04-06: Daemon MUST detect stalled processes (PID alive but no progress for configurable duration)
- REQ-WF04-07: Each step run MUST be a new DB row — never overwrite previous runs
- REQ-WF04-08: Merge queue MUST be sequential per project — one merge at a time
- REQ-WF04-09: If a step fails after max fix cycles, the item MUST be marked as failed and escalated (dashboard notification)
- REQ-WF04-10: Agent MUST never write operational state to files — all state updates go through `iw` CLI to DB

### 3.5. WF-05: Monitor and Recover (Human)

**Trigger**: Developer checks dashboard for progress, or receives failure notification

**Flow:**
1. Developer opens dashboard — sees running tasks, failed tasks, completed tasks
2. For failed tasks: developer clicks [Restart], [Skip], or [Restart from Step N]
3. For stalled tasks: developer clicks [Kill] then [Restart]
4. For completed batches: developer reviews results

**Requirements:**
- REQ-WF05-01: Dashboard MUST show all running steps across all projects with live duration counters
- REQ-WF05-02: Dashboard MUST show failed/needs-attention items with error messages and action buttons
- REQ-WF05-03: [Restart] MUST re-launch the exact same command in the same worktree — no manual setup needed
- REQ-WF05-04: [Kill] MUST send SIGTERM to the process and update DB status immediately
- REQ-WF05-05: [Skip] MUST mark the step as completed and allow the workflow to continue
- REQ-WF05-06: [Restart from Step N] MUST reset all steps >= N to pending and resume from N
- REQ-WF05-07: All actions MUST be available from the dashboard — no SSH/terminal required
- REQ-WF05-08: SSE-powered notifications MUST alert the user when items fail, complete, or stall

### 3.6. WF-06: Archive a Completed Work Item

**Trigger**: Work item is completed and merged

**Flow:**
1. Developer archives via dashboard or `iw archive <ID>`
2. Tier 1: Design doc and reports stored in DB (always viewable, searchable)
3. Tier 2: Full artifacts compressed to `.tar.zst` in `iw-ai-core/archive/`
4. Active files deleted from project repo
5. Item phase: `work` -> `done`

**Requirements:**
- REQ-WF06-01: Design document content MUST be stored in `work_items.design_doc_content` (DB)
- REQ-WF06-02: Step reports MUST be stored in `workflow_steps.report_content` (DB)
- REQ-WF06-03: Full artifacts MUST be compressed to `.tar.zst` in `archive/<project_id>/`
- REQ-WF06-04: Project repo files MUST be deleted after successful archive
- REQ-WF06-05: Archive MUST be idempotent — running twice has no adverse effect
- REQ-WF06-06: Dashboard MUST render archived design docs instantly from DB (no file extraction needed)

### 3.7. WF-07: Search Across Work Items

**Trigger**: Developer searches for past work items by keyword or context

**Flow:**
1. Developer types a query in the dashboard search bar
2. PostgreSQL full-text search matches against design docs and reports
3. Results ranked by relevance, showing title, summary, project, type, date

**Requirements:**
- REQ-WF07-01: Full-text search MUST work across all projects (or filtered to one)
- REQ-WF07-02: Search MUST cover `design_doc_content` and `report_content`
- REQ-WF07-03: Results MUST show relevance-ranked matches with context snippets
- REQ-WF07-04: Search MUST return results within 500ms for up to 10,000 work items

### 3.8. WF-08: View Full Artifacts (On-Demand)

**Trigger**: Developer wants to see prompts, evidences, logs for an archived item

**Flow:**
1. Developer clicks "View Full Artifacts" on an archived work item
2. Backend extracts `.tar.zst` to a temporary directory
3. Dashboard shows a file browser with all artifacts
4. On navigate away, temporary files are cleaned up (TTL-based)

**Requirements:**
- REQ-WF08-01: Archive extraction MUST complete within 2 seconds for typical items
- REQ-WF08-02: Extracted files MUST be read-only — no editing through the dashboard
- REQ-WF08-03: Temporary files MUST be cleaned up automatically after configurable TTL (default: 10 min)
- REQ-WF08-04: Multiple concurrent extractions MUST be supported (different items)

### 3.9. WF-09: Onboard a New Project

**Trigger**: Developer wants to manage a new project with IW AI Core

**Flow:**
1. Developer runs `iw init-project --id my-project --path /path/to/repo`
2. CLI creates `.iw-orch.json` in the project root
3. CLI registers the project in `projects.toml`
4. CLI creates `ai-dev/design/active/`, `ai-dev/workflow.md`
5. CLI syncs base skills to `.claude/skills/`
6. Project appears in the dashboard project selector
7. Daemon auto-discovers the project on next config reload

**Requirements:**
- REQ-WF09-01: Project onboarding MUST be a single CLI command
- REQ-WF09-02: The command MUST create all required files and DB entries
- REQ-WF09-03: The project MUST appear in the dashboard within one daemon poll cycle
- REQ-WF09-04: ID sequences MUST start at 1 for the new project (independent from other projects)
- REQ-WF09-05: The project MUST be fully isolated — no shared state with other projects except LLM quota

---

## 4. Functional Requirements by Component

### 4.1. `iw` CLI

The command-line interface that bridges LLM agents and the database.

| ID | Requirement | Priority |
|----|------------|----------|
| REQ-CLI-01 | MUST be installable via `pip install -e .` and available on PATH as `iw` | P0 |
| REQ-CLI-02 | MUST auto-detect current project from `.iw-orch.json` up the directory tree | P0 |
| REQ-CLI-03 | MUST provide `iw next-id --type <type>` for atomic ID allocation | P0 |
| REQ-CLI-04 | MUST provide `iw register <ID> <title>` for work item registration | P0 |
| REQ-CLI-05 | MUST provide `iw approve <ID>` and `iw unapprove <ID>` for status transitions | P0 |
| REQ-CLI-06 | MUST provide `iw step-start`, `iw step-done`, `iw step-fail` for agent state reporting | P0 |
| REQ-CLI-07 | MUST provide `iw archive <ID>` for two-tier archival | P0 |
| REQ-CLI-08 | MUST provide `iw sync-skills` for skill distribution | P0 |
| REQ-CLI-09 | MUST provide `iw init-project` for new project onboarding | P0 |
| REQ-CLI-10 | MUST provide `iw batch-create`, `iw batch-approve`, `iw batch-status` | P0 |
| REQ-CLI-11 | MUST provide `iw migration-lock acquire/release/status` | P0 |
| REQ-CLI-12 | MUST provide `iw daemon start/stop/status` | P1 |
| REQ-CLI-13 | MUST provide `iw search <query>` for full-text search from terminal | P1 |
| REQ-CLI-14 | MUST provide `iw current-project` to print the current project ID | P0 |
| REQ-CLI-15 | All commands MUST exit with code 0 on success, non-zero on failure | P0 |
| REQ-CLI-16 | All commands MUST produce structured JSON output when `--json` flag is passed | P1 |
| REQ-CLI-17 | MUST validate inputs before DB writes (e.g., valid status transitions, existing project IDs) | P0 |
| REQ-CLI-18 | MUST provide clear, actionable error messages on failure | P0 |

### 4.2. Daemon

The single-process orchestration engine that manages all projects.

| ID | Requirement | Priority |
|----|------------|----------|
| REQ-DMN-01 | MUST run as a single Python process managing all registered projects | P0 |
| REQ-DMN-02 | MUST poll the database every configurable interval (default: 60s) | P0 |
| REQ-DMN-03 | MUST discover and process approved batches for all enabled projects | P0 |
| REQ-DMN-04 | MUST launch worktree setup via deterministic bash scripts (never LLM) | P0 |
| REQ-DMN-05 | MUST launch LLM agents for each step and record PID, command, worktree path | P0 |
| REQ-DMN-06 | MUST check PID health every poll cycle via `kill -0` | P0 |
| REQ-DMN-07 | MUST detect and handle timed-out steps (per step-type dynamic timeout) | P0 |
| REQ-DMN-08 | MUST detect zombie processes (PID dead, status still 'running') and mark as failed | P0 |
| REQ-DMN-09 | MUST detect stalled processes (PID alive, no progress) and mark as stalled | P0 |
| REQ-DMN-10 | MUST process merge queue sequentially per project (one merge at a time) | P0 |
| REQ-DMN-11 | MUST emit events to `daemon_events` table for all significant state transitions | P0 |
| REQ-DMN-12 | MUST survive crashes gracefully — on restart, resume from DB state (no lost work) | P0 |
| REQ-DMN-13 | MUST NOT corrupt DB state under any failure scenario (transactions, not partial writes) | P0 |
| REQ-DMN-14 | MUST reload project configuration on SIGHUP without full restart | P1 |
| REQ-DMN-15 | MUST enforce migration lock — only one item per project may create Alembic migrations | P0 |
| REQ-DMN-16 | MUST track git status per project (uncommitted, unpushed, worktree count) | P1 |
| REQ-DMN-17 | MUST monitor LLM quota (Claude, MiniMax) and cache results | P1 |
| REQ-DMN-18 | MUST support auto-publish after batch completion (optional per batch) | P2 |
| REQ-DMN-19 | MUST write PID file for single-instance enforcement | P0 |
| REQ-DMN-20 | MUST clean up orphaned worktrees on startup (from previous crashes) | P1 |

### 4.3. Dashboard

The web-based management interface.

| ID | Requirement | Priority |
|----|------------|----------|
| **Navigation & Layout** | | |
| REQ-DASH-01 | MUST provide a project selector showing all registered projects with status badges | P0 |
| REQ-DASH-02 | MUST scope all pages by project via URL prefix `/project/{id}/` | P0 |
| REQ-DASH-03 | MUST provide a cross-project system view at `/system/` | P0 |
| **Running Tasks View** | | |
| REQ-DASH-04 | MUST show all currently running steps across all projects at `/system/running` | P0 |
| REQ-DASH-05 | MUST show live duration counters for running steps (updated via SSE) | P0 |
| REQ-DASH-06 | MUST show PID, agent label, step type, and project for each running step | P0 |
| REQ-DASH-07 | MUST show failed/needs-attention items with error messages | P0 |
| REQ-DASH-08 | MUST show recently completed steps (configurable time window, default: 1 hour) | P1 |
| **Batch Management** | | |
| REQ-DASH-09 | MUST list all batches per project with status, item count, progress | P0 |
| REQ-DASH-10 | MUST show batch detail: items, execution groups, timeline, logs | P0 |
| REQ-DASH-11 | MUST provide batch actions: approve, pause, resume, archive | P0 |
| **Work Item Management** | | |
| REQ-DASH-12 | MUST show work item detail: design doc, step pipeline, reports, metrics | P0 |
| REQ-DASH-13 | MUST render design documents as formatted HTML (from DB for archived, from file for active) | P0 |
| REQ-DASH-14 | MUST show step pipeline with status indicators, durations, run counts | P0 |
| **One-Click Actions** | | |
| REQ-DASH-15 | MUST provide [Kill] button for running steps — sends SIGTERM immediately | P0 |
| REQ-DASH-16 | MUST provide [Restart] button for failed steps — re-launches stored command | P0 |
| REQ-DASH-17 | MUST provide [Skip] button for failed steps — marks as completed, advances workflow | P0 |
| REQ-DASH-18 | MUST provide [Restart from Step N] — resets all steps >= N to pending | P0 |
| REQ-DASH-19 | MUST provide [Re-queue] for failed batch items — resets to pending | P1 |
| REQ-DASH-20 | Destructive actions (kill, skip) MUST require confirmation dialog | P0 |
| **Queue & Backlog** | | |
| REQ-DASH-21 | MUST show pending items: drafts awaiting review, approved awaiting execution | P0 |
| REQ-DASH-22 | MUST allow selecting multiple items to create a batch | P1 |
| **History & Archive** | | |
| REQ-DASH-23 | MUST show completed items with filterable history (by type, date, project) | P0 |
| REQ-DASH-24 | MUST render archived design docs instantly from DB (Tier 1) | P0 |
| REQ-DASH-25 | MUST provide "View Full Artifacts" for on-demand archive extraction (Tier 2) | P1 |
| **Search** | | |
| REQ-DASH-26 | MUST provide a search bar with full-text search across design docs and reports | P1 |
| REQ-DASH-27 | MUST show search results with relevance ranking, snippets, and project context | P1 |
| **Notifications** | | |
| REQ-DASH-28 | MUST push real-time notifications via SSE for: item failed, batch completed, step stalled | P0 |
| REQ-DASH-29 | Notifications MUST appear as toast messages (auto-dismiss, click to navigate) | P1 |
| **Analytics** | | |
| REQ-DASH-30 | MUST show per-project analytics: success rate, fix cycle frequency, avg completion time | P2 |
| REQ-DASH-31 | MUST show agent effectiveness breakdown (which agents trigger most fix cycles) | P2 |
| REQ-DASH-32 | MUST show quality gate failure distribution (lint/tests/types/coverage) | P2 |
| **Tests View** | | |
| REQ-DASH-33 | MUST show test execution history per project (pass/fail counts, trends) | P2 |
| REQ-DASH-34 | MUST highlight flaky tests (tests that alternate pass/fail) | P2 |
| **Documentation View** | | |
| REQ-DASH-35 | MUST show documentation generation status per project | P2 |
| REQ-DASH-36 | MUST allow triggering doc regeneration from the dashboard | P2 |
| **System Status** | | |
| REQ-DASH-37 | MUST show daemon health: uptime, PID, last poll time, poll count | P0 |
| REQ-DASH-38 | MUST show LLM quota usage (Claude 5h/7d, MiniMax) with color-coded bars | P1 |
| REQ-DASH-39 | MUST show git status per project (uncommitted, unpushed, active worktrees) | P1 |
| **Technology** | | |
| REQ-DASH-40 | MUST use server-side rendering (FastAPI + Jinja2 + htmx) — no SPA, no build pipeline | P0 |
| REQ-DASH-41 | MUST use SSE for real-time updates — no WebSocket, no polling from browser | P0 |
| REQ-DASH-42 | MUST listen on a dedicated port (default: 9900) separate from any project's ports | P0 |

### 4.4. Database

PostgreSQL as the single source of truth for all operational state.

| ID | Requirement | Priority |
|----|------------|----------|
| REQ-DB-01 | MUST use PostgreSQL on a configurable port (via `.env`) separate from project databases | P0 |
| REQ-DB-02 | MUST use composite keys `(project_id, id)` for project isolation | P0 |
| REQ-DB-03 | MUST use `FOR UPDATE` row locks for atomic ID allocation | P0 |
| REQ-DB-04 | MUST store design doc content in `work_items.design_doc_content` (Tier 1) | P0 |
| REQ-DB-05 | MUST store step reports in `workflow_steps.report_content` (Tier 1) | P0 |
| REQ-DB-06 | MUST maintain full-text search index via `tsvector` on design docs | P1 |
| REQ-DB-07 | MUST track archive metadata (path, size, timestamp) for Tier 2 content | P0 |
| REQ-DB-08 | MUST use Alembic for schema migrations | P0 |
| REQ-DB-09 | Schema MUST support future pgvector extension for RAG without breaking changes | P2 |
| REQ-DB-10 | All state transitions MUST be transactional — no partial writes | P0 |

### 4.5. Archive System

Two-tier content storage for completed work items.

| ID | Requirement | Priority |
|----|------------|----------|
| REQ-ARC-01 | MUST store searchable content (design docs, reports) in PostgreSQL (Tier 1) | P0 |
| REQ-ARC-02 | MUST compress full artifacts to `.tar.zst` in `archive/<project_id>/` (Tier 2) | P0 |
| REQ-ARC-03 | Archive directory MUST NOT be tracked in git | P0 |
| REQ-ARC-04 | MUST delete active files from project repo after successful archive | P0 |
| REQ-ARC-05 | MUST support on-demand extraction to tmp for artifact viewing | P1 |
| REQ-ARC-06 | Extracted tmp files MUST auto-cleanup after configurable TTL | P1 |
| REQ-ARC-07 | `iw archive` MUST be idempotent | P0 |
| REQ-ARC-08 | MUST support bulk archive: `iw archive --all-completed --project <id>` | P1 |

### 4.6. Skills Distribution

Package-like management of Claude Code skills across projects.

| ID | Requirement | Priority |
|----|------------|----------|
| REQ-SKL-01 | Master skills MUST live in `iw-ai-core/skills/` | P0 |
| REQ-SKL-02 | `iw sync-skills` MUST copy updated skills to project's `.claude/skills/` | P0 |
| REQ-SKL-03 | Project-specific skill overrides MUST take precedence over platform skills | P0 |
| REQ-SKL-04 | MUST track installed skill versions via `.iw-skills-lock.json` | P1 |
| REQ-SKL-05 | `iw sync-skills --check` MUST report outdated skills without modifying anything | P1 |
| REQ-SKL-06 | Skills MUST use `iw` CLI for all DB interactions (never direct DB access) | P0 |

### 4.7. Configuration Management

All runtime configuration MUST be externalized. No hardcoded ports, URLs, paths, or credentials anywhere in the codebase.

| ID | Requirement | Priority |
|----|------------|----------|
| REQ-CFG-01 | ALL ports, URLs, paths, and credentials MUST be configurable via environment variables | P0 |
| REQ-CFG-02 | A `.env` file in the repo root MUST be the primary source for local development configuration | P0 |
| REQ-CFG-03 | A `.env.example` file MUST be committed to git with all variables documented (values blank or set to safe defaults) | P0 |
| REQ-CFG-04 | The actual `.env` file MUST be in `.gitignore` — never committed | P0 |
| REQ-CFG-05 | `docker-compose.yml` MUST read all ports and credentials from `.env` — no hardcoded values | P0 |
| REQ-CFG-06 | The daemon, dashboard, and CLI MUST read configuration from environment variables (with `.env` auto-loading) | P0 |
| REQ-CFG-07 | Every configurable value MUST have a sensible default so the platform starts with just `.env.example` copied to `.env` | P1 |
| REQ-CFG-08 | Configuration errors (missing required vars, invalid values) MUST produce clear error messages at startup, not cryptic runtime failures | P0 |

### 4.8. Workflow Configuration

How workflow steps are defined and managed.

| ID | Requirement | Priority |
|----|------------|----------|
| REQ-WKF-01 | Each project MUST define its workflow in `ai-dev/workflow.md` | P0 |
| REQ-WKF-02 | Workflow definition MUST specify: step types, agent labels, step order, timeout hints | P0 |
| REQ-WKF-03 | Skills (`/iw-new-incident` etc.) MUST read `workflow.md` to generate the step pipeline — not hardcode steps | P0 |
| REQ-WKF-04 | Adding a new step type to a project MUST only require editing `workflow.md` — not modifying skill code | P0 |
| REQ-WKF-05 | `workflow.md` MUST support conditional steps (e.g., browser verification only if `browser_verification: true`) | P1 |
| REQ-WKF-06 | `workflow.md` MUST support per-step timeout overrides | P1 |
| REQ-WKF-07 | Workflow changes MUST NOT affect in-flight work items — they use the snapshot from creation time | P0 |

---

## 5. Non-Functional Requirements

### 5.1. Reliability

| ID | Requirement | Priority |
|----|------------|----------|
| REQ-REL-01 | Daemon MUST survive crashes — on restart, resume all in-progress work from DB state | P0 |
| REQ-REL-02 | No single failure (process crash, timeout, network blip) MUST leave the DB in an inconsistent state | P0 |
| REQ-REL-03 | Daemon MUST detect and clean up zombie processes on every poll cycle | P0 |
| REQ-REL-04 | Daemon MUST detect orphaned worktrees on startup and report them | P0 |
| REQ-REL-05 | Step execution MUST be idempotent where possible — restarting a step MUST NOT corrupt the worktree | P0 |
| REQ-REL-06 | Overnight batch execution (8+ hours) MUST complete without human intervention for items that don't have code issues | P0 |
| REQ-REL-07 | Platform MUST handle graceful shutdown (SIGTERM) — finish current merges, mark running steps as interrupted | P0 |

### 5.2. Performance

| ID | Requirement | Priority |
|----|------------|----------|
| REQ-PERF-01 | Dashboard page loads MUST complete within 500ms | P0 |
| REQ-PERF-02 | `iw next-id` MUST return within 100ms (even under 10 concurrent calls) | P0 |
| REQ-PERF-03 | Full-text search MUST return within 500ms for up to 10,000 work items | P1 |
| REQ-PERF-04 | Archive extraction MUST complete within 2 seconds for typical items | P1 |
| REQ-PERF-05 | Daemon poll cycle MUST complete within 5 seconds (all projects combined) | P0 |
| REQ-PERF-06 | Platform MUST support at least 10 concurrent step executions across all projects | P0 |

### 5.3. Observability

| ID | Requirement | Priority |
|----|------------|----------|
| REQ-OBS-01 | All significant events MUST be logged to `daemon_events` table | P0 |
| REQ-OBS-02 | Daemon MUST log to both file and stdout with configurable log level | P0 |
| REQ-OBS-03 | Dashboard MUST show daemon uptime, last poll time, and event count | P0 |
| REQ-OBS-04 | Each step run MUST have a dedicated log file accessible from the dashboard | P0 |
| REQ-OBS-05 | Failed steps MUST include human-readable error messages in the DB | P0 |

### 5.4. Data Integrity

| ID | Requirement | Priority |
|----|------------|----------|
| REQ-INT-01 | All DB writes MUST be transactional — no partial state on failure | P0 |
| REQ-INT-02 | ID sequences MUST guarantee uniqueness under concurrent access | P0 |
| REQ-INT-03 | State machine transitions MUST be validated — no invalid status jumps | P0 |
| REQ-INT-04 | Archived design doc content MUST be immutable — no updates after archival | P0 |
| REQ-INT-05 | Step runs MUST be append-only — never update or delete previous runs | P0 |

---

## 6. Constraints

### 6.1. Hard Constraints (Non-Negotiable)

| Constraint | Rationale |
|-----------|-----------|
| Single developer, single machine | This is a personal productivity tool, not a SaaS product |
| Permissive OSS only (MIT, BSD, Apache) | Innovation Ways licensing policy — no AGPL, no proprietary |
| No SPA build pipeline | Dashboard is an internal tool — server-rendered HTML is simpler and sufficient |
| PostgreSQL for state | Already on the machine, proven, supports FTS and future pgvector |
| Bash for executor scripts | Deterministic, no LLM involvement in state transitions |
| Python for daemon + CLI | Consistent with InnoForge backend, access to SQLAlchemy |
| Git worktree isolation | Proven pattern for parallel execution without branch conflicts |

### 6.2. Soft Constraints (Strong Preferences)

| Constraint | Rationale |
|-----------|-----------|
| 60-second poll cycle | Balance between responsiveness and system load |
| htmx for interactivity | Progressive enhancement, zero build step, proven in current dashboard |
| SSE for real-time updates | Simpler than WebSocket, sufficient for dashboard needs |
| Zstandard for archive compression | Faster decompression than gzip, better ratio |
| Sync SQLAlchemy for daemon | Single-threaded polling loop, async adds complexity for no benefit |

---

## 7. Phasing

### 7.1. Phase 1 — Core Platform (MVP)

**Goal**: Replace the current file-based system with a functional DB-backed platform. All current capabilities preserved, operational reliability dramatically improved.

**Scope**:
- `iw` CLI: all P0 commands (next-id, register, approve, step-start/done/fail, archive, sync-skills, init-project, batch-create/approve)
- Daemon: batch execution, step monitoring, PID tracking, timeout handling, zombie detection, merge queue
- Dashboard: project selector, running tasks view, batch management, work item detail, one-click actions (kill, restart, skip), SSE notifications
- Database: full schema, Alembic migrations, atomic ID allocation
- Archive: Tier 1 (DB content) + Tier 2 (compressed archives)
- Skills: sync-skills distribution, project overrides
- Workflow: `workflow.md` template-driven step generation
- Executor: worktree setup, step executor, worktree commit (ported from InnoForge)

**Not in Phase 1**: Analytics, Tests view, Documentation view, full-text search, LLM quota monitoring, auto-publish, git status panel.

### 7.2. Phase 2 — Enhanced Dashboard & Search

**Goal**: Add the views and search capabilities that make the dashboard a complete operational hub.

**Scope**:
- Full-text search across design docs and reports
- Analytics dashboard (success rates, fix cycles, agent effectiveness)
- LLM quota monitoring (Claude, MiniMax)
- Git status panel per project
- History with filters (type, date, project)
- Toast notifications with click-to-navigate
- Execution timeline (Gantt view) per batch
- Auto-publish after batch completion

### 7.3. Phase 3 — Tests, Docs, and Intelligence

**Goal**: Extend the platform with test management, documentation tracking, and AI-powered features.

**Scope**:
- Tests view: execution history, flaky test detection, trends
- Documentation view: doc generation status, regeneration triggers
- AI summaries on archive (auto-generated 2-3 line summaries)
- RAG: pgvector embeddings, semantic search ("find incidents similar to this")
- Dynamic workflow editor in dashboard (v2 of workflow configuration)

---

## 8. Acceptance Criteria Summary

The platform is considered ready for daily use when:

1. A developer can create a work item (`/iw-new-incident`) and see it in the dashboard within 60 seconds
2. A batch of 4 items can execute overnight without human intervention (for items without code issues)
3. Any failed step can be restarted with a single click from the dashboard
4. The developer can identify all running tasks, their duration, and their status from one dashboard page
5. Zombie processes are automatically detected and cleaned up — never left running indefinitely
6. No operational task requires SSH, file editing, or knowledge of internal file structure
7. Adding a new project takes one CLI command and is visible in the dashboard within 60 seconds
8. Archived work items are viewable (design doc, reports) instantly from the dashboard
9. The platform handles a total of 10+ concurrent agent executions across projects without degradation

---

## Appendix A: Glossary

| Term | Definition |
|------|-----------|
| **Work Item** | A unit of work: Feature (F), Incident/Issue (I), or Change Request (CR) |
| **Batch** | A group of work items scheduled for parallel execution |
| **Step** | One phase of a work item's workflow (e.g., implementation, code review, QV) |
| **Step Run** | A single execution attempt of a step (multiple runs if retried) |
| **Fix Cycle** | A retry loop triggered by code review findings or QV gate failures |
| **Worktree** | An isolated git checkout where an agent executes a work item |
| **Tier 1** | Content stored in PostgreSQL for instant access (design docs, reports) |
| **Tier 2** | Content compressed to archive for on-demand access (prompts, evidences, logs) |
| **Daemon** | The always-running Python process that orchestrates execution |
| **`iw` CLI** | The command-line tool that bridges agents and the database |
| **Skill** | A Claude Code / OpenCode skill that provides specific workflow capabilities |

## Appendix B: Requirement Priority Key

| Priority | Meaning |
|----------|---------|
| **P0** | Must have for Phase 1 (MVP). Platform is not usable without this. |
| **P1** | Should have for Phase 1. Important but the platform works without it. |
| **P2** | Phase 2 or later. Nice to have, not blocking daily use. |
