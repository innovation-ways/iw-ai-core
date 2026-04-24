# CR-00019: Selection-driven OSS Prepare with reviewable worktree lifecycle

**Type**: Change Request
**Priority**: Medium
**Reason**: The current OSS Prepare flow generates auto-fixes inside a throwaway worktree that is force-removed the moment the subprocess exits, destroying the fixes it just produced. The "→ Fix via Prepare" link rendered under every failing finding is a dead stub (`href="#"`). The card UI forces an all-or-nothing choice — users have no control over which fixes to apply. Selection-driven, reviewable fixes are needed before Prepare is actually usable.
**Created**: 2026-04-24
**Status**: Draft

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against
a testcontainer, post-merge apply to live DB). If the migration is
broken, the daemon will refuse to merge the batch.

Allowed for agents:
  - alembic revision --autogenerate -m "..."   (writes a file only)
  - alembic history / current / show           (read-only)
  - Running migrations inside testcontainer fixtures
    (tests/conftest.py does this — agents don't call it directly)

Allowed for OPERATORS only (not agents):
  - uv run iw migrations list-pending          (read-only, safe for anyone)
  - uv run iw migrations dry-run               (testcontainer, safe)
  - uv run iw migrations apply --i-am-operator (refuses if IW_CORE_AGENT_CONTEXT=true)
  - Direct invocation via ./ai-core.sh or make db-migrate (operator entry points)

If your task seems to require applying a migration to the live DB,
STOP and raise a blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Description

Rework the per-project OSS tab so users pick exactly which failing compliance findings to auto-fix, and so the Prepare run produces a persistent, reviewable artifact instead of ephemeral work. The existing card layout is replaced with a grouped, filterable table with per-row checkboxes and a details modal. The Prepare worktree moves from `/tmp/` to `{project.working_dir}/.worktrees/oss-prep-<job_id>/` (same directory the agent worktrees live in), stays alive after the subprocess exits, and enters a new `awaiting_review` job state. Two new actions — **Accept fix** (squash-merges the prep branch into main) and **Discard fix** (drops the branch and worktree) — move the job to its terminal state.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Pay particular attention to:

- `dashboard/CLAUDE.md` — thin routers, Jinja2 + htmx + prebuilt Tailwind, SSE patterns.
- `orch/CLAUDE.md` — sync SQLAlchemy 2.0, append-only tables, Alembic migrations generated-only.
- `tests/CLAUDE.md` — testcontainer-only DB tests, `FTS_FUNCTION_SQL` / `FTS_TRIGGER_SQL` setup.
- `docs/IW_AI_Core_Agent_Constraints.md` — docker & migration off-limits rules.

## Current Behavior

1. **OSS tab layout** (`dashboard/templates/pages/project/oss.html`) — renders findings as a stack of domain cards. Each card expands to show its findings with hover tooltips. Every failing finding with `auto_fix_available=true` gets a `<a href="#">→ Fix via Prepare</a>` link (`oss.html:305`, `oss_domain_card.html:51`) that has no JS handler — clicking it does nothing.

2. **Prepare button** (`oss.html:34-42`, `data-oss-action="prepare"`) — triggers `POST /project/{id}/oss/prepare` which creates a `ProjectOssJob(kind=prepare)`, spawns a daemon thread, returns a stream URL for SSE.

3. **Worker** (`dashboard/services/oss_service.py::_run_worktree`, lines 210-296):
   - Creates a random-path worktree `/tmp/oss-<uuid>` via `git worktree add … HEAD`.
   - Runs `uv run iw oss prepare --project <id>` inside it.
   - On exit (success or failure), force-removes the worktree via `git worktree remove --force`.
   - Marks the job `complete`/`error` based on exit code.

4. **`iw oss prepare`** (`orch/cli/oss_commands.py:198-203`) — alias for `iw oss scan --mode make_oss`.

5. **`run_make_oss`** (`skills/iw-oss-publish/scripts/scan.py:158-305`):
   - Creates/switches to branch `iw-oss-publish/prep-YYYY-MM-DD`.
   - Applies every finding with `status ∈ {fail, human_required} AND auto_fix_available=true`.
   - Plus four unconditional **"always-try"** fixes: `OSS-ENV-03`, `OSS-ENV-04`, `OSS-SEC-04`, `PRE-COMMIT-CONFIG` (`scan.py:252`).
   - Stages changes via `git add -A` but **never commits**.
   - Returns exit code from the post-fix scan.

6. **Net result** — because the worktree is force-removed on exit, the staged changes never reach any persistent ref. The prep branch, cut from HEAD, is left pointing at HEAD with no commits. The user sees updated stdout in the UI, the job goes green/red, and nothing is actually applied.

7. **Concurrency** — `_running_job_of_kind` in `dashboard/routers/oss.py` only blocks new Prepare jobs while one is currently `running`.

8. **Findings data model** (`orch/db/models.py::OssFinding`, `skills/iw-oss-publish/scripts/lib/types.py::Finding`) — carries `summary`, `detail`, `remediation`, `osps_control`, `auto_fix_available`, but has no per-check `rationale` or OSPS-doc URL.

See `evidences/pre/CR-00019-before-oss-tab.png` and `CR-00019-before-expanded-card.png` for captured current state, including the dead "→ Fix via Prepare" links under failing findings.

## Desired Behavior

### New OSS tab layout

- Top action row: **Scan** (kept), **Publish** (kept). The **Prepare** button is **removed** — selection + the in-table button is the only entry point.
- Replace the domain-card layout with a **table grouped by domain/module**. Columns:
  1. **Checkbox** (rendered per row, conditionally enabled).
  2. **Module** — domain display name (e.g. "Secrets scanning", "CI / CD surface").
  3. **Title** — `finding.summary`.
  4. **Severity** — MUST / SHOULD / INFO / MAY pill.
  5. **Status** — Pass / Fail / Skipped / Human required.
  6. **Details** — `…` button that opens a modal.
- Collapsible domain section headers with per-group counts (pass / MUST / SHOULD / skipped) and a **group-level "select all failing in this group"** checkbox that toggles every enabled checkbox in that group.
- Sort within each group: MUST → SHOULD → INFO → MAY.
- Top-level **filter chips**: `All` · `Failing only` (DEFAULT) · `MUST only`. The default is "Failing only" so users see their work, not the noise.
- When the last scan is stale (`scan_summary.is_stale`), the Fix button is **disabled** with a tooltip "Re-scan first" and a visible banner. Scan button remains active.

### Checkbox rule

| Finding | Checkbox |
|--------|----------|
| `auto_fix_available = true` (fail OR human_required) | **Enabled** |
| `auto_fix_available = false` (any status) | Rendered disabled, tooltip "Manual action — see details" |
| `status = pass` | No checkbox |
| `status = skip` | No checkbox |

### Details modal (`…` click)

A centered dialog showing (in order):
1. Check ID, severity pill, status pill, OSPS control reference.
2. **Summary** — `finding.summary`.
3. **Why this matters** — `finding.rationale` (new field). Falls back to `finding.detail` when rationale is empty.
4. **Details** — `finding.detail` (only if distinct from rationale).
5. **Remediation** — `finding.remediation`.
6. **OSPS control link** — external link derived from `osps_control` (see below).

### Rationale field and OSPS link

- Add `rationale: str = ""` and (derived) `osps_control_url: str | None = None` to the `Finding` dataclass (`skills/iw-oss-publish/scripts/lib/types.py`).
- Persist `rationale` in `oss_finding.rationale` (new nullable TEXT column).
- Author one paragraph of rationale for every check in `skills/iw-oss-publish/scripts/checks/*.py` — covering all 16 check modules (~25–30 check IDs total). The rationale explains *why* the check exists, *what risk* it mitigates, and *who* is affected if it's wrong.
- OSPS link pattern: `https://baseline.openssf.org/#<osps_control>` (e.g. `OSPS-LE-03.01` → `https://baseline.openssf.org/#OSPS-LE-03.01`). Derive at render time in the modal; do not store the URL.

### Selection → Prepare flow

1. User ticks one or more row checkboxes. Button reads "Prepare fix (N selected)" and enables when N ≥ 1 (and scan is fresh).
2. Click → **confirm dialog** listing every selected `check_id` with its summary. User clicks Confirm or Cancel.
3. Confirm fires `POST /project/{id}/oss/prepare` with a JSON body `{"checks": ["OSS-LIC-01", "OSS-LIC-06", ...]}`.
4. Dashboard creates a `ProjectOssJob(kind=prepare, status=queued)` and the worker kicks off.

### New Prepare worker

- **Worktree location**: `{project.working_dir}/.worktrees/oss-prep-<job_id>/` — same directory as agent worktrees (verified at `orch/daemon/batch_manager.py:333`, `orch/daemon/project_registry.py:16`). This makes them discoverable to the existing `/system/worktrees` page.
- Resolve and record `base_sha` (main's HEAD at Prepare start) on the job row.
- Invoke `uv run iw oss prepare --project <id> --check OSS-LIC-01 --check OSS-LIC-06 …` (one `--check` per selected ID).
- Stream stdout to `stdout_tail` as today (SSE preserved).
- **On clean exit (exit_code == 0 AND staged files > 0)**:
  - From inside the worktree, `git commit -m "chore: prepare for public OSS release"` (single commit on prep branch).
  - Capture `commit_sha` (HEAD of prep branch).
  - Capture `files_changed_summary` = output of `git diff --stat base_sha..HEAD`.
  - Capture `branch_name` = `iw-oss-publish/prep-<job_id>`.
  - Set status = **`awaiting_review`**. **Do NOT remove the worktree.**
- **On clean exit with no staged files**: set status = `complete` with a note "No changes produced"; remove the worktree (nothing to review).
- **On error exit (exit_code != 0)**: behave as today — remove the worktree, set status = `error`, populate `error_message`.

### New `iw oss prepare --check` contract

- `iw oss prepare` now accepts `--check <ID>` one or more times. When one or more `--check` flags are present, only those check IDs are applied (plus any always-try fixes they individually opt into — but the blanket always-try list is dropped).
- `--check` is required at least once. Calling `iw oss prepare --project <id>` with no `--check` exits non-zero with a clear error. (This is a deliberate behavior change: there is no longer a "fix everything" mode from the CLI — the dashboard enforces explicit selection, and scripting callers must say what they mean.)
- `run_make_oss` (`skills/iw-oss-publish/scripts/scan.py`) receives the filter and iterates only over findings whose `check_id` is in the set. The unconditional `always_try = ["OSS-ENV-03", "OSS-ENV-04", "OSS-SEC-04", "PRE-COMMIT-CONFIG"]` line at `scan.py:252` is **deleted**. If any of those checks is still valuable, its result must surface as a regular finding with `auto_fix_available=true` — the scanner already emits them.
- Skill edits mirror to `.claude/skills/iw-oss-publish/` per repo convention. IW-AI-DEV and InnoForge mirrors are flagged in the CR's Notes for a follow-up sync (handled by `iw skills sync`, not in scope of this CR to push).

### Awaiting-review card (UI)

When any `ProjectOssJob` for this project has `status = awaiting_review`, render a prominent card above the Scan/Publish row showing:

- "Prepare fix pending review — job #N" heading.
- Worktree path (copy-to-clipboard).
- Branch name.
- Files-changed summary (`git diff --stat` captured at commit time — preformatted monospace block).
- Days-pending age (e.g. "Waiting 2 days").
- Two buttons:
  - **Accept fix** — primary, triggers `POST /project/{id}/oss/jobs/{job_id}/accept`.
  - **Discard fix** — secondary/destructive, triggers `POST /project/{id}/oss/jobs/{job_id}/discard`. Requires a confirm dialog: "Discard the auto-fix for job #N? The worktree and branch will be deleted."

### Accept endpoint

`POST /project/{project_id}/oss/jobs/{job_id}/accept`:

1. Load the job; verify it's in `awaiting_review`. 409 otherwise.
2. Resolve current `main` HEAD in the project's repo root. If it differs from `base_sha` on the job row, return **409 `{"detail": "main has advanced since Prepare ran — discard this job and re-run Prepare"}`**. No force-push, no auto-rebase.
3. From the project repo root (not the worktree):
   - `git merge --squash <branch_name>`
   - `git commit -m "chore: prepare for public OSS release (oss-prep-job-<N>)"`
4. Delete the prep branch: `git branch -D <branch_name>`.
5. Remove the worktree: `git worktree remove --force <worktree_path>`.
6. Update job row: `status = complete`, `completed_at = now()`.

Each git invocation is logged; failures set `status = error` with a descriptive `error_message` and return 500.

### Discard endpoint

`POST /project/{project_id}/oss/jobs/{job_id}/discard`:

1. Load the job; verify it's in `awaiting_review`. 409 otherwise.
2. **Idempotent**:
   - `git worktree remove --force <worktree_path>` — if the path is already gone, log warn and continue.
   - `git branch -D <branch_name>` — if the branch is already gone, log warn and continue.
3. Update job row: `status = discarded`, `completed_at = now()`.

### Concurrency gating

Extend `_running_job_of_kind` (`dashboard/routers/oss.py`) so `prepare` is blocked when a job exists in either `running` OR `awaiting_review`. Return 409 with detail: `"Prepare job #<N> is awaiting review — accept or discard it first"`.

### Worktrees-page surfacing

Update `dashboard/routers/worktrees.py` so its enumerator lists `.worktrees/oss-prep-*` entries alongside the agent worktrees. They render with a distinct badge ("OSS prep") and link to the OSS tab of the owning project.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `project_oss_job_status` PG enum | `queued, running, complete, error, cancelled` | Adds `awaiting_review`, `discarded` |
| `project_oss_job` table | Columns: …, `worktree_path`, `stdout_tail`, `error_message` | + `base_sha`, `branch_name`, `commit_sha`, `files_changed_summary` (all nullable) |
| `oss_finding` table | No rationale | + `rationale` (nullable TEXT) |
| `Finding` dataclass (skill) | No rationale | + `rationale: str = ""` field; `to_dict()` surfaces it |
| Every check module (`skills/iw-oss-publish/scripts/checks/*.py`) | Findings emit summary/detail/remediation | Every finding also emits a per-check rationale paragraph |
| `iw oss prepare` CLI | Accepts only `--project` | Also accepts `--check <ID>` (repeatable, required ≥1) |
| `run_make_oss` skill function | Applies all fail+auto_fix findings + 4 always-try fixes | Applies only findings whose ID is in `--check` set; always-try list deleted |
| `dashboard/services/oss_service.py::_run_worktree` | `/tmp/oss-<uuid>`, force-removed on exit | `{working_dir}/.worktrees/oss-prep-<job_id>`, persists after clean exit in `awaiting_review` state |
| `dashboard/routers/oss.py` | Scan / prepare / publish / install routes + stream | Adds `/jobs/{id}/accept` and `/jobs/{id}/discard` routes; extends `_running_job_of_kind` |
| `dashboard/routers/worktrees.py` | Lists agent worktrees only | Also lists OSS-prep worktrees |
| OSS page template | Card layout with dead "Fix via Prepare" links | Grouped table + details modal + confirm dialog + awaiting-review card |
| Prepare top button | Present | Removed |
| "Fix via Prepare" anchor | Dead href="#" in two templates | Removed (selection + table-level button replaces it) |

### Breaking Changes

- **CLI contract**: `iw oss prepare` now requires `--check` at least once. External callers (CI, scripts) that relied on the "fix everything" behavior must either enumerate the checks they want or stop relying on this CLI. There are no known external callers; the dashboard is the only invoker in this repo.
- **Skill behavior**: the four always-try fixes (`OSS-ENV-03`, `OSS-ENV-04`, `OSS-SEC-04`, `PRE-COMMIT-CONFIG`) are no longer applied unconditionally. If they're surfaced as findings, the user must select them like any other fix.
- **UI**: the card layout is replaced entirely. Any external doc or muscle memory pointing at "click Prepare at the top of the OSS tab" is obsolete.
- **Dashboard API**: `POST /project/{id}/oss/prepare` now accepts (and requires) a JSON body `{"checks": [...]}`. The route remains at the same path; the shape is the break.

No database-persisted user data is lost. No public API (external to this repo) changes.

### Data Migration

- **Required**: one Alembic migration adds two enum values and five columns.
- **Enum additions** (`project_oss_job_status`):
  - `awaiting_review`
  - `discarded`
  - Use `op.execute("ALTER TYPE project_oss_job_status ADD VALUE IF NOT EXISTS 'awaiting_review'")` with `ALTER TYPE` wrapped per PG rules (requires transaction-per-value — each `ADD VALUE` in its own `op.execute` call, AND the migration must set `transactional=False` or use `with op.get_context().autocommit_block():` because `ALTER TYPE ADD VALUE` cannot run inside a transaction block on older PG versions; target >=12 uses of "IF NOT EXISTS" is safe). Verify the house Alembic helper or replicate the pattern used when `ProjectOssJobStatus` was first introduced (migration `824e6e6f34ee_add_oss_compliance_tables.py`).
- **Column additions** on `project_oss_job` (all nullable, no backfill required):
  - `base_sha` (TEXT, nullable)
  - `branch_name` (TEXT, nullable)
  - `commit_sha` (TEXT, nullable)
  - `files_changed_summary` (TEXT, nullable)
- **Column addition** on `oss_finding` (nullable, no backfill required):
  - `rationale` (TEXT, nullable)
  - **Backfill policy**: no backfill. Pre-migration `OssFinding` rows keep `rationale = NULL`. The details modal (S09) falls back to `finding.detail` when `rationale` is empty, so legacy rows render without loss. The next scan (which runs through the S03 skill) populates `rationale` for every newly-emitted finding, and persistence is append-only per project (scans are rolled over, not patched), so stale NULL rows naturally age out as scans are re-run.
- **Reversibility**:
  - Columns: `op.drop_column` in down-migration — fully reversible.
  - Enum values: **forward-only**. Postgres does not support `DROP VALUE` from an enum. The down-migration documents this limitation and is a no-op for the enum (columns still drop). If rollback is ever needed to a state before those enum values were added, the only path is to drop and recreate the type — which is destructive and not attempted.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Alembic migration + `orch/db/models.py` updates + `docs/IW_AI_Core_Database_Schema.md` | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | backend-impl | Skill contract: rationale fields + OSPS link + `--check` filter + drop always-try, mirror to `.claude/skills` | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | backend-impl | CLI `--check` flag + worker rewrite (persistent worktree, auto-commit, awaiting_review) + concurrency gating | — |
| S06 | code-review-impl | Review S05 | — |
| S07 | api-impl | `/jobs/{id}/accept` + `/jobs/{id}/discard` routes + surfacing in `/system/worktrees` | — |
| S08 | code-review-impl | Review S07 | — |
| S09 | frontend-impl | OSS tab rewrite: table, filter chips, modal, confirm dialog, awaiting-review card, remove Prepare button + dead links, `make css` | — |
| S10 | code-review-impl | Review S09 | — |
| S11 | tests-impl | Migration test, skill filter, CLI flag, worker awaiting-review lifecycle, accept/discard routes, concurrency, table render, rationale+OSPS link | — |
| S12 | code-review-impl | Review S11 | — |
| S13 | code-review-final-impl | Cross-layer final review | — |
| S14..S18 | qv-gate | lint, format, typecheck, unit-tests, integration-tests | — |
| S19 | qv-browser | End-to-end browser verification of the new OSS flow | — |

### Database Changes

- **New tables**: None.
- **Modified tables**:
  - `project_oss_job`: + `base_sha`, `branch_name`, `commit_sha`, `files_changed_summary`.
  - `oss_finding`: + `rationale`.
- **Enum changes**: `project_oss_job_status` adds `awaiting_review` and `discarded`.
- **Migration notes**: `ALTER TYPE … ADD VALUE` cannot run inside a transaction on PG < 12. Use `op.execute` with `IF NOT EXISTS` and match the `autocommit_block` / `transactional = False` pattern used by existing enum-add migrations in this repo (inspect `orch/db/migrations/versions/` for a precedent). Down-migration drops the columns; enum value removal is documented as not supported.

### API Changes

- **New endpoints**:
  - `POST /project/{project_id}/oss/jobs/{job_id}/accept` → JSON 200 `{status: "complete", files_changed: N}`; 409 if main moved; 409 if not in `awaiting_review`; 500 on git failure (rolls job back to `awaiting_review`).
  - `POST /project/{project_id}/oss/jobs/{job_id}/discard` → JSON 200 `{status: "discarded"}`; idempotent on missing worktree/branch; 409 if not in `awaiting_review`.
- **Modified endpoints**:
  - `POST /project/{project_id}/oss/prepare` now accepts and requires JSON body `{"checks": ["OSS-LIC-01", ...]}`. Empty list → 400.
- **Removed endpoints**: None.

### Frontend Changes

- **New components**:
  - Grouped findings table (`templates/pages/project/oss.html` or a new fragment).
  - Per-finding details modal.
  - Pre-Prepare confirm dialog listing selected check_ids.
  - Awaiting-review card with Accept / Discard buttons.
- **Modified components**:
  - OSS tab action row — `Prepare` button removed.
  - Filter chips (All / Failing only / MUST only).
  - `/system/worktrees` — OSS-prep worktrees shown with a badge.
- **Removed components**:
  - Domain-card finding stack (`templates/fragments/oss_domain_card.html`) — retained as a template only if still used by the scan-history view; otherwise deleted.
  - Dead "→ Fix via Prepare" anchors (`oss.html:305`, `oss_domain_card.html:51`).

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/CR-00019/CR-00019_CR_Design.md` | Design | This document |
| `ai-dev/active/CR-00019/workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `ai-dev/active/CR-00019/prompts/CR-00019_S01_Database_prompt.md` | Prompt | S01 DB migration + models |
| `ai-dev/active/CR-00019/prompts/CR-00019_S02_CodeReview_prompt.md` | Prompt | S02 review of S01 |
| `ai-dev/active/CR-00019/prompts/CR-00019_S03_Backend_prompt.md` | Prompt | S03 skill + rationale + filter |
| `ai-dev/active/CR-00019/prompts/CR-00019_S04_CodeReview_prompt.md` | Prompt | S04 review of S03 |
| `ai-dev/active/CR-00019/prompts/CR-00019_S05_Backend_prompt.md` | Prompt | S05 CLI + worker rewrite |
| `ai-dev/active/CR-00019/prompts/CR-00019_S06_CodeReview_prompt.md` | Prompt | S06 review of S05 |
| `ai-dev/active/CR-00019/prompts/CR-00019_S07_API_prompt.md` | Prompt | S07 accept/discard routes |
| `ai-dev/active/CR-00019/prompts/CR-00019_S08_CodeReview_prompt.md` | Prompt | S08 review of S07 |
| `ai-dev/active/CR-00019/prompts/CR-00019_S09_Frontend_prompt.md` | Prompt | S09 UI rewrite |
| `ai-dev/active/CR-00019/prompts/CR-00019_S10_CodeReview_prompt.md` | Prompt | S10 review of S09 |
| `ai-dev/active/CR-00019/prompts/CR-00019_S11_Tests_prompt.md` | Prompt | S11 test coverage |
| `ai-dev/active/CR-00019/prompts/CR-00019_S12_CodeReview_prompt.md` | Prompt | S12 review of S11 |
| `ai-dev/active/CR-00019/prompts/CR-00019_S13_CodeReview_Final_prompt.md` | Prompt | S13 cross-layer review |
| `ai-dev/active/CR-00019/prompts/CR-00019_S19_BrowserVerification_prompt.md` | Prompt | S19 end-to-end browser verification |
| `ai-dev/active/CR-00019/evidences/pre/CR-00019-before-oss-tab.png` | Evidence | Before: OSS tab summary |
| `ai-dev/active/CR-00019/evidences/pre/CR-00019-before-oss-full-page.png` | Evidence | Before: full OSS page capture |
| `ai-dev/active/CR-00019/evidences/pre/CR-00019-before-expanded-card.png` | Evidence | Before: dead "Fix via Prepare" links |

Reports are created during execution under `ai-dev/work/CR-00019/reports/`.

## Acceptance Criteria

### AC1: Dead link is gone and selection drives fixes

```
Given the OSS tab for a project that has several failing findings with auto_fix_available=true
When the user views the page
Then there is no "→ Fix via Prepare" link under any finding
And there is no "Prepare" button in the top action row
And there is a grouped table with a checkbox in the leftmost column of every finding
And the "Prepare fix (N selected)" button is disabled with N = 0
```

### AC2: Checkbox enablement rule

```
Given a scan result with a mix of finding states
When the table renders
Then rows with auto_fix_available=true and status ∈ {fail, human_required} show an enabled checkbox
And rows with auto_fix_available=false show a disabled checkbox with tooltip "Manual action — see details"
And rows with status=pass or status=skip render no checkbox
```

### AC3: Filter chips and grouping

```
Given the OSS tab with findings across multiple domains and severities
When the page first loads
Then the active filter is "Failing only" and only fail/human_required rows are visible
And findings are grouped by domain under collapsible headers with pass/MUST/SHOULD/skip counts
And within each domain findings are sorted MUST → SHOULD → INFO → MAY
When the user clicks "MUST only"
Then only rows with severity=MUST are visible
When the user clicks "All"
Then every row (including pass/skip) is visible
```

### AC4: Details modal

```
Given a finding row
When the user clicks the "…" button in the Details column
Then a modal opens with: check ID, severity pill, status pill, summary, rationale paragraph, detail (if distinct), remediation, and an external link whose href is https://baseline.openssf.org/#<osps_control>
And pressing Escape or clicking the backdrop closes the modal
```

### AC5: Confirm dialog before firing Prepare

```
Given the user has selected two findings (e.g. OSS-LIC-01 and OSS-LIC-06)
When they click "Prepare fix (2 selected)"
Then a confirm dialog lists both check IDs with their summaries
And clicking Cancel dismisses the dialog without firing a job
And clicking Confirm POSTs /project/{id}/oss/prepare with body {"checks":["OSS-LIC-01","OSS-LIC-06"]}
```

### AC6: Worker creates a persistent, reviewable worktree

```
Given a Prepare job is fired with at least one selected check
When the iw oss prepare subprocess exits cleanly with staged changes
Then a worktree exists at {project.working_dir}/.worktrees/oss-prep-<job_id>/
And the prep branch iw-oss-publish/prep-<job_id> holds a single commit "chore: prepare for public OSS release"
And the job row has status=awaiting_review with base_sha, branch_name, commit_sha, and files_changed_summary populated
And the worktree is NOT removed
```

### AC7: Awaiting-review card and its actions

```
Given a ProjectOssJob is in awaiting_review for this project
When the user opens the OSS tab
Then a card above the action row shows worktree path, branch, files-changed summary, days-pending, and Accept / Discard buttons
```

### AC8: Accept — happy path

```
Given an awaiting_review job and main has not moved since base_sha
When the user clicks Accept fix and confirms
Then main receives one new squash-merge commit with message "chore: prepare for public OSS release (oss-prep-job-<N>)"
And the prep branch is deleted
And the worktree is removed
And the job row is complete with completed_at set
```

### AC9: Accept — main moved refusal

```
Given an awaiting_review job whose base_sha no longer matches main's current HEAD
When the user clicks Accept fix
Then the endpoint returns 409 with message telling the user to re-run Prepare
And the worktree and branch are untouched
And the job stays in awaiting_review
```

### AC10: Discard — idempotent

```
Given an awaiting_review job
When the user clicks Discard (and confirms)
Then the prep branch is deleted, the worktree is removed, and the job is marked discarded
And calling Discard a second time (e.g. worktree already manually removed) still succeeds with status=discarded and logs a warn about the already-missing paths
```

### AC11: Concurrency gating

```
Given one Prepare job is in running or awaiting_review
When the user tries to fire another Prepare
Then the endpoint returns 409 with message "Prepare job #<N> is awaiting review — accept or discard it first" (or the running variant)
```

### AC12: Stale scan disables the Fix button

```
Given scan_summary.is_stale is true
When the OSS tab renders
Then the "Prepare fix (N selected)" button is disabled even when N ≥ 1
And a banner tells the user to re-scan first
```

### AC13: Rationale + OSPS link surfaced end-to-end

```
Given every check module emits a rationale paragraph per finding
When a scan completes
Then oss_finding.rationale is populated on every row
And the details modal renders the rationale
And the details modal shows a link to https://baseline.openssf.org/#<osps_control> for findings that have an osps_control
```

### AC14: `/system/worktrees` surfaces OSS-prep worktrees

```
Given a Prepare job is in awaiting_review
When the user opens /system/worktrees
Then the OSS-prep worktree is listed alongside agent worktrees with an "OSS prep" badge and a link back to the owning project's OSS tab
```

### AC15: Publish flow is untouched

```
Given the Publish button at the top of the OSS tab
When the user clicks it
Then the behavior is identical to before this CR — tmp worktree, no awaiting-review state, job completes as today
```

## Rollback Plan

- **Database**:
  - Columns added on `project_oss_job` and `oss_finding` drop cleanly on down-migration.
  - Enum values added to `project_oss_job_status` are **forward-only** (PG limitation). Rolling back to a state before those values requires dropping and recreating the type (destructive) and is not provided. If rollback is needed, the safe path is: (a) revert the code to the previous commit, (b) leave the two extra enum values in place, harmless — they will simply never be written. The `status` column will only contain legacy values.
- **Code**: `git revert` the squash-merge commit for this CR. The worker falls back to the old throwaway-worktree behavior automatically (code is the sole source of that behavior).
- **Data**: No pre-existing user data is touched. Jobs already in `complete`/`error` remain valid. Any job that happened to land in the new `awaiting_review`/`discarded` states before rollback would need manual cleanup (update to `complete`/`error`) — flagged in the rollback checklist.

## Dependencies

- **Depends on**: None.
- **Blocks**: None (future work to apply the same lifecycle to Publish is scoped as a follow-up CR).

## TDD Approach

- **Unit tests**:
  - `Finding.to_dict()` surfaces `rationale`.
  - `run_make_oss` honors the `--check` filter (only iterates matching IDs, no always-try fixes applied).
  - CLI parses `--check` as repeatable.
  - Accept / discard route verifies status transitions and gating in isolation.
- **Integration tests** (testcontainer PG):
  - Alembic migration applies cleanly (enum values present, columns exist).
  - Worker awaiting-review lifecycle: subprocess mocked to stage files → worktree persists → status=awaiting_review → commit sha populated.
  - Accept route happy path (requires real git repo fixture with a main branch) — squash-merge lands, worktree removed, status=complete.
  - Accept route refuses when base_sha ≠ current main.
  - Discard route happy path + idempotency (run twice, second call still succeeds).
  - Concurrency gating: attempting a second Prepare when one is in awaiting_review returns 409.
  - Table rendering: given a mixture of findings, verify grouping, sort order, filter chip behavior, checkbox enablement.
  - Modal renders rationale + OSPS link HTML when present.
- **Updated tests**:
  - `tests/integration/test_oss_dashboard_*` — expect the new route shape on `/oss/prepare` (JSON body with checks).
  - `tests/integration/test_oss_scanner.py` — expect `rationale` on every emitted `Finding`.
  - `tests/integration/test_oss_cli.py` — exercise the `--check` flag.

## Notes

- **Skill mirror sync**: edits under `skills/iw-oss-publish/` must be propagated to `.claude/skills/iw-oss-publish/` within this CR. Edits must ALSO be propagated to the IW-AI-DEV and InnoForge repos (per user memory `feedback_skills_sync.md`). That cross-repo sync is out of scope of CR-00019 itself — it runs via `iw skills sync` after merge and is called out in the merge-to-main checklist for the operator.
- **Always-try fixes**: dropping the four unconditional fixes is a deliberate behavior change. If any of them is critical to "normal" OSS hygiene, it will still surface as a regular `auto_fix_available` finding and the user can select it. If after this CR any user reports a regression where a previously-auto-applied fix no longer appears, the fix is not to restore the always-try list but to ensure the corresponding check emits a finding with `auto_fix_available=true`.
- **OSPS control URL derivation**: the link pattern `https://baseline.openssf.org/#<osps_control>` is computed at render time in Jinja (no DB column needed). If a control has no osps_control value, no link is rendered.
- **Prep branch naming**: `iw-oss-publish/prep-<job_id>` (not date-based) to prevent collisions when two jobs on the same day end up in awaiting_review in sequence.
- **Security**: Accept is a destructive action on main. Dashboard-wide auth is out of scope (matches current app). Mitigation: the moved-main refusal protects against stale merges; the confirm dialog gives the user a final checkpoint.
- **Accept TOCTOU window**: the moved-main check (`git rev-parse main`) and the squash-merge are two separate git invocations. Between them, main could advance (another operator pushes, or a concurrent daemon merge lands). With this repo's single-daemon + single-dashboard-instance model and low write rate to any given project's main, the practical risk is negligible and we do not take a filesystem or DB lock around the pair. If this ever becomes an issue in practice, the fix is a `git merge --ff-only` pre-flight inside the same accept handler, or an advisory lock keyed on `project_id`. Flagged here so reviewers aren't surprised.
- **Stale-pending worktrees**: no auto-cleanup in this CR. The awaiting-review card shows "Waiting N days" so operators can notice. If this becomes a hygiene problem, a follow-up CR can add a TTL sweep.
