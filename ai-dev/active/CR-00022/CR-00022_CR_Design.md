# CR-00022: OSS Compliance — per-finding fixes, table+modal UX, no branch creation

**Type**: Change Request
**Priority**: High
**Reason**: (a) Branch creation in `prepare`/`publish` modes has caused incidents where the local branch was switched without the user noticing; (b) the cards-with-tooltip UX makes individual checks hard to understand and the all-or-nothing Prepare button does not match how users want to triage findings.
**Created**: 2026-04-25
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

Replace the OSS module's branch-creating `prepare` and `publish` workflow with per-finding fixes that write directly to the working tree (no branch, no worktree, no auto-commit). Replace the dashboard cards-with-tooltip layout with a domain-grouped collapsible table whose `…` button opens a rich modal explaining each test, the risk of shipping with it failing, and how to fix it. Honor accepted-risk decisions in CI via a checked-in `.iw/oss-accepted.yaml` file.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key references:

- `dashboard/CLAUDE.md` — FastAPI + Jinja2 + htmx + Tailwind; routers thin; fragments don't extend `base.html`; `make css` rebuilds Tailwind.
- `orch/CLAUDE.md` — SQLAlchemy 2.0 sync; psycopg v3; Alembic 1.13+; sole source of truth in PostgreSQL.
- `tests/CLAUDE.md` — testcontainers only; never psycopg2; replace URL prefix; run `FTS_FUNCTION_SQL` + `FTS_TRIGGER_SQL` after `create_all`.
- `docs/IW_AI_Core_Agent_Constraints.md` — Docker R1, Migrations R2.

## Current Behavior

The OSS module exposes three modes (`scan` / `make_oss` / `publish`) reachable from both the CLI (`uv run iw oss scan|prepare|publish`) and the dashboard's three-button row. `prepare` and `publish` provision a throwaway worktree at `/tmp/oss-{uuid}` (`dashboard/services/oss_service.py:300 _run_worktree`) and create a prep branch `iw-oss-publish/prep-{job_id}` on the project repo (`oss_service.py:232 _prep_branch_name`). On success the job enters `awaiting_review`; on discard the prep branch is deleted via `git branch -D` (`oss_service.py:558 delete_branch_proc`). These flows have caused incidents where the local branch was switched without the user noticing.

The dashboard page (`dashboard/templates/pages/project/oss.html`) renders findings as expandable per-domain cards built from the `findings_by_domain` dict in `dashboard/routers/oss.py:101`. Each finding sits inside a domain card with a hover-only tooltip exposing four prose sections (Why this check exists, Risk if failing, If you publish anyway, Remediation) sourced from `dashboard/utils/oss_copy.py` (`DOMAIN_CONTEXT`, `SEVERITY_IMPACT`, `STATUS_COPY`). Per-test prose lives only at the *domain* and *severity* level — there is no per-check authored copy. On scan completion the page does `window.location.reload()`. There is no way to fix a single finding from the UI; the only remediation paths are the all-or-nothing `Prepare` button or manual edits.

`ProjectOssJob` carries `worktree_path`, `branch_name`, `commit_sha`, `files_changed_summary`; `ProjectOssJobKind` carries `prepare`, `publish` enum values; `OssScanMode` carries `make_oss`, `publish`; `ProjectOssJobStatus` carries `awaiting_review`, `discarded`. CI (`.github/workflows/compliance-scan.yml`) runs gitleaks + pinact and fails the build on any secret hit; there is no concept of accepted residual risk.

## Desired Behavior

Only `scan` and per-finding `fix` remain. No branch creation, no worktree provisioning, no `publish` mode. The dashboard renders all findings in a single domain-grouped collapsible **table** with columns `Group | Test | Type (MUST/SHOULD/INFO) | Status (Pass/Fail/Skipped) | Details`. The `…` button in Details opens a centered modal with sections: What this test checks, How it tests, Risk if you ship anyway, Evidence, How to fix, Preview (diff or full content for auto-apply-safe fixes), References. Modal footer actions: **Apply** (visible only when `auto_apply_safe=True`), **Re-run check**, **Mark accepted**, Close.

Per-check copy lives in a YAML catalog (`dashboard/services/oss_check_catalog.yaml`) authored once during this CR via online research per check ID; the catalog is the single source of presentation copy and is enforced complete by a CI test that AST-walks every `Finding(id=...)` literal.

Failing checks expose a per-finding **Apply** action that runs `uv run iw oss fix <CHECK_ID> --apply` from the dashboard, writing the fix directly into the user's working tree (no branch, no commit, idempotent). Each fix recipe is registered under `orch/oss/fix_recipes/`. Findings without an auto-apply path show no Apply button — the modal is information-only with manual remediation steps.

Accepted-risk decisions persist in `.iw/oss-accepted.yaml` (committed to the repo). The dashboard reads this file on render and groups matched findings into an "Accepted" section at the bottom of the table. The CI workflow (`compliance-scan.yml`) reads the same file from the checked-out repo and downgrades matched MUST findings to warnings in the SARIF emitted to GitHub Code Scanning, so accept decisions made in the UI are honored by CI without a database round-trip.

Default table filter is "Failing/Human-required only" with severity chips (MUST/SHOULD/INFO) and an All toggle. Sort within group: severity desc then status desc. Scan progress emits **row-level** SSE updates so checks transition Pass/Fail/Skipped in place — no full-page reload. A bounded "Apply all safe" bulk action shows a preview dialog with a per-file checklist (all checked by default; user can deselect any) and applies only `auto_apply_safe=True` fixes to the working tree.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `ProjectOssJobKind` enum | `scan / prepare / publish / install` | `scan / install / fix` |
| `OssScanMode` enum | `scan / make_oss / publish` | `scan` only (consider dropping enum if only one value) |
| `ProjectOssJobStatus` enum | `…/ awaiting_review / discarded` | `queued / running / complete / error / cancelled` (drop awaiting_review, discarded) |
| `ProjectOssJob` columns | + `worktree_path / branch_name / commit_sha / files_changed_summary` | drop all four |
| `OssFinding` columns | + `auto_fix_available` | + new `auto_apply_safe` BOOL nullable=False default false |
| CLI `iw oss prepare` | runs scan in `make_oss` mode | **removed** |
| CLI `iw oss publish` | runs scan in `publish` mode | **removed** |
| CLI `iw oss fix` | does not exist | new: `iw oss fix <CHECK_ID> [--apply] [--project <id>]` |
| Dashboard `POST /oss/prepare` | enqueues prepare job | **removed** |
| Dashboard `POST /oss/publish` | enqueues publish job | **removed** |
| Dashboard `POST /oss/fix/{check_id}` | does not exist | new: enqueues fix job for one check |
| Dashboard `POST /oss/recheck/{check_id}` | does not exist | new: re-runs one check |
| Dashboard `POST /oss/accept/{check_id}` | does not exist | new: appends to `.iw/oss-accepted.yaml` |
| Dashboard `POST /oss/apply-all-safe` | does not exist | new: runs preview + applies selected safe fixes |
| `dashboard/services/oss_service.py` | `_run_worktree`, `_prep_branch_name`, `_git_commit_info`, `discard_job`, `WORKTREE_KINDS` | all removed; new fix-runner orchestrator + `.iw/oss-accepted.yaml` reader/writer |
| `dashboard/services/oss_check_catalog.{py,yaml}` | does not exist | new: loader + per-check copy |
| `orch/oss/fix_recipes/` | does not exist | new: per-check idempotent recipes |
| `dashboard/templates/pages/project/oss.html` | cards-with-tooltip, three buttons, full reload on scan complete | table grouped by domain (collapsible), single `Scan` button + bulk `Apply all safe`, modal opens from row, SSE row updates |
| `templates/fragments/oss_finding_modal.html` | does not exist | new |
| `templates/fragments/oss_table.html` | does not exist | new |
| `templates/fragments/oss_apply_all_safe_modal.html` | does not exist | new |
| `templates/fragments/oss_domain_card.html` | renders domain card | **deleted** |
| `templates/fragments/oss_install_modal.html` | install tools modal | **deleted** (or kept if `install` flow stays — see Notes) |
| `skills/iw-oss-publish/SKILL.md` | three-mode skill (scan/make_oss/publish) | rewritten as scan-only + per-finding fix |
| `.github/workflows/compliance-scan.yml` | gitleaks + pinact, hard-fail on any secret | reads `.iw/oss-accepted.yaml`; downgrades matched MUST in SARIF; scan exits non-zero only for unaccepted MUSTs |

### Breaking Changes

- **CLI**: `iw oss prepare` and `iw oss publish` removed. Any script invoking them breaks. No external callers known — internal admin tool.
- **Dashboard routes**: `POST /project/{id}/oss/prepare` and `POST /project/{id}/oss/publish` return 404. No external callers known.
- **DB enum values pruned**: `ProjectOssJobKind.{prepare,publish}`, `OssScanMode.{make_oss,publish}`, `ProjectOssJobStatus.{awaiting_review,discarded}` — pruning a Postgres enum requires `ALTER TYPE` and is non-trivial; data migration deletes referencing rows first.
- **DB columns dropped**: `ProjectOssJob.{worktree_path,branch_name,commit_sha,files_changed_summary}`. Existing rows with non-null values lose those values.

### Data Migration

- **Pre-migration data**: delete all rows in `project_oss_job` with `kind in ('prepare','publish')`; delete all rows in `oss_scan` with `mode in ('make_oss','publish')`; delete all rows in `project_oss_job` with `status in ('awaiting_review','discarded')` (these only exist for prepare/publish jobs and would already be gone, but explicit is safer).
- **Schema migration**: drop columns `worktree_path`, `branch_name`, `commit_sha`, `files_changed_summary` from `project_oss_job`; recreate `project_oss_job_kind` enum without `prepare`/`publish` (Postgres requires recreate-cast-drop pattern); recreate `ossscan_mode` enum without `make_oss`/`publish`; recreate `project_oss_job_status` enum without `awaiting_review`/`discarded`; add column `auto_apply_safe BOOLEAN NOT NULL DEFAULT false` on `oss_finding`.
- **Reversibility**: not reversible without restoring the live DB from backup. Deleted rows are gone. Confirmed acceptable as hard cleanup in the design discussion.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | Phase A migration: drop prepare/publish enum values + columns + delete historical rows; add `auto_apply_safe` to OssFinding; ORM updates; schema docs | — |
| S02 | code-review-impl | Review S01 | — |
| S03 | backend-impl | Phase A code removal: rip `_run_worktree`, `_prep_branch_name`, `_git_commit_info`, `discard_job`, `WORKTREE_KINDS` from oss_service; remove `prepare`/`publish` from CLI + scanner mode plumbing; rewrite SKILL.md scan-only + fix | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | backend-impl | Phase B catalog: `oss_check_catalog.py` loader (Pydantic + cache + debug hot-reload); enumerate IDs (run scan + AST-walk); populate `oss_check_catalog.yaml` for every check via online research; backfill `auto_apply_safe` flag on each `Finding(...)` constructor | — |
| S06 | code-review-impl | Review S05 — catalog completeness, brand voice, schema validation | — |
| S07 | backend-impl | Phase C CLI: `iw oss fix <CHECK_ID> [--apply]` + idempotent fix-recipe registry under `orch/oss/fix_recipes/`; per-recipe contract (preview + apply, idempotent) | — |
| S08 | code-review-impl | Review S07 — recipe idempotency, no git mutation, working-tree-only writes | — |
| S09 | api-impl | Phase D/E APIs: per-check fix/recheck/accept routes, apply-all-safe route + preview JSON, `.iw/oss-accepted.yaml` reader/writer service, SSE row-level events | — |
| S10 | code-review-impl | Review S09 — auth, CSRF, status codes, working-tree-only invariant, SSE event shape | — |
| S11 | frontend-impl | Phase D dashboard: replace `oss.html` with domain-grouped collapsible table; new modal fragment; filter chips with default = failing/human-required; SSE row-level updates replacing reload; delete dead fragments | — |
| S12 | code-review-impl | Review S11 — accessibility (focus trap, ESC), htmx, JS lint, Tailwind purge, modal contract | — |
| S13 | frontend-impl | Phase E UI: per-row Re-run icon, Mark-accepted modal with reason input, Apply-all-safe preview dialog with deselectable per-file checkboxes | — |
| S14 | code-review-impl | Review S13 | — |
| S15 | backend-impl | Phase E CI integration: update `.github/workflows/compliance-scan.yml` to read `.iw/oss-accepted.yaml` and downgrade matched MUST findings in SARIF; document file format | — |
| S16 | code-review-impl | Review S15 — workflow correctness, SARIF schema | — |
| S17 | tests-impl | Tests: catalog-completeness (AST), accept-yaml round-trip, fix-recipe idempotency, dashboard routes for new endpoints, migration tests for hard cleanup, SSE row-update event shape, plus updates to existing OSS tests | — |
| S18 | code-review-impl | Review S17 — coverage map vs ACs | — |
| S19 | backend-impl | Phase F cleanup: delete dead templates/skill files; prune docs; one-time housekeeping for stale `.git/worktrees/oss-*` and `refs/heads/iw-oss-publish`; rewrite skill `references/` (drop history_rewrite/fix_recipes/modes prepare-publish sections) | — |
| S20 | code-review-impl | Review S19 — no orphan refs to prepare/publish anywhere in repo | — |
| S21 | code-review-final-impl | Global cross-layer review — completeness vs design, brand voice consistency, idempotency, working-tree-only invariant, no orphan worktree/branch references | — |
| S22 | qv-gate | `make lint` | — |
| S23 | qv-gate | `uv run ruff format --check .` | — |
| S24 | qv-gate | `make typecheck` | — |
| S25 | qv-gate | `make test-unit` | — |
| S26 | qv-gate | `make test-integration` (timeout 900) | — |
| S27 | qv-browser | Browser verification — verify scan + table + modal + per-finding fix + accept-risk + apply-all-safe + SSE in isolated worktree stack | — |

Adjust steps based on change scope. Agent slugs: `database-impl`, `backend-impl`, `api-impl`, `frontend-impl`, `tests-impl`, `code-review-impl`, `code-review-final-impl`, `qv-gate`, `qv-browser`.

### Database Changes

- **New tables**: None.
- **Modified tables**:
  - `project_oss_job` — drop columns `worktree_path`, `branch_name`, `commit_sha`, `files_changed_summary`; recreate enum `project_oss_job_kind` without `prepare`/`publish` and add `fix`; recreate enum `project_oss_job_status` without `awaiting_review`/`discarded`.
  - `oss_scan` — recreate enum `ossscan_mode` without `make_oss`/`publish`.
  - `oss_finding` — add column `auto_apply_safe BOOLEAN NOT NULL DEFAULT false`.
- **Migration notes**: Postgres enum value removal requires the recreate-cast-drop pattern (create new enum, alter columns to use it via USING cast, drop old enum, rename new to old). Pre-migration DELETEs MUST run first to remove rows that reference the dropped enum values, otherwise the cast fails.

### API Changes

- **New endpoints**:
  - `POST /project/{id}/oss/fix/{check_id}` — preview + apply for one check (body: `{"apply": bool}`).
  - `POST /project/{id}/oss/recheck/{check_id}` — re-run one check; emits an SSE row-update event.
  - `POST /project/{id}/oss/accept/{check_id}` — append to `.iw/oss-accepted.yaml` (body: `{"finding_hash": str, "reason": str}`).
  - `POST /project/{id}/oss/apply-all-safe/preview` — return list of files that `auto_apply_safe=True` recipes would touch.
  - `POST /project/{id}/oss/apply-all-safe` — apply selected recipes (body: `{"check_ids": [str]}`).
  - `GET /project/{id}/oss/stream` — SSE row-level updates during scan (replaces reload-on-complete pattern).
- **Modified endpoints**:
  - `GET /project/{id}/oss` — render new table layout; pass catalog + accepted-yaml data to template.
- **Removed endpoints**:
  - `POST /project/{id}/oss/prepare`
  - `POST /project/{id}/oss/publish`

### Frontend Changes

- **New components / fragments**:
  - `templates/pages/project/oss.html` — full rewrite to table layout grouped by domain (collapsible).
  - `templates/fragments/oss_table.html` — body fragment for the table (htmx-swappable).
  - `templates/fragments/oss_finding_modal.html` — modal markup.
  - `templates/fragments/oss_apply_all_safe_modal.html` — preview/checklist modal.
- **Modified components**:
  - `dashboard/static/styles.css` — regenerated by `make css` after template edits.
- **Removed components**:
  - `templates/fragments/oss_domain_card.html`
  - `templates/fragments/oss_install_modal.html` (only if the install flow is folded into the catalog/setup; otherwise kept).

## File Manifest

All files for this work item live under `ai-dev/active/CR-00022/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00022_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `evidences/pre/CR-00022-before-oss-cards-view.png` | Evidence | Pre-state — cards layout |
| `evidences/pre/CR-00022-before-oss-domain-expanded.png` | Evidence | Pre-state — Secrets domain expanded |
| `evidences/pre/CR-00022-before-oss-tooltip-hover.png` | Evidence | Pre-state — hover tooltip |
| `prompts/CR-00022_S01_Database_prompt.md` | Prompt | Phase A schema + ORM |
| `prompts/CR-00022_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/CR-00022_S03_Backend_prompt.md` | Prompt | Phase A code removal |
| `prompts/CR-00022_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/CR-00022_S05_Backend_prompt.md` | Prompt | Phase B catalog |
| `prompts/CR-00022_S06_CodeReview_prompt.md` | Prompt | Review S05 |
| `prompts/CR-00022_S07_Backend_prompt.md` | Prompt | Phase C CLI + recipes |
| `prompts/CR-00022_S08_CodeReview_prompt.md` | Prompt | Review S07 |
| `prompts/CR-00022_S09_Api_prompt.md` | Prompt | Phase D/E API endpoints + SSE |
| `prompts/CR-00022_S10_CodeReview_prompt.md` | Prompt | Review S09 |
| `prompts/CR-00022_S11_Frontend_prompt.md` | Prompt | Phase D table + modal + SSE updates |
| `prompts/CR-00022_S12_CodeReview_prompt.md` | Prompt | Review S11 |
| `prompts/CR-00022_S13_Frontend_prompt.md` | Prompt | Phase E per-row + bulk + accept UX |
| `prompts/CR-00022_S14_CodeReview_prompt.md` | Prompt | Review S13 |
| `prompts/CR-00022_S15_Backend_prompt.md` | Prompt | Phase E CI workflow honoring accepted YAML |
| `prompts/CR-00022_S16_CodeReview_prompt.md` | Prompt | Review S15 |
| `prompts/CR-00022_S17_Tests_prompt.md` | Prompt | Test suite — completeness, idempotency, routes, migration |
| `prompts/CR-00022_S18_CodeReview_prompt.md` | Prompt | Review S17 |
| `prompts/CR-00022_S19_Backend_prompt.md` | Prompt | Phase F cleanup + skill rewrite |
| `prompts/CR-00022_S20_CodeReview_prompt.md` | Prompt | Review S19 |
| `prompts/CR-00022_S21_CodeReview_Final_prompt.md` | Prompt | Global cross-layer review |
| `prompts/CR-00022_S27_BrowserVerification_prompt.md` | Prompt | QV browser verification |

QV-gate steps S22..S26 are command-only entries in the manifest (no prompt file required).

Reports are created during execution under `ai-dev/work/CR-00022/reports/`.

## Acceptance Criteria

### AC1: No branch or worktree is ever created by OSS flows

```
Given a clean working tree on `main`
When the user clicks Scan, Apply on a finding, Re-run on a finding, or Apply-all-safe in the dashboard
Then `git branch --list 'iw-oss-publish/*'` returns empty
And `ls /tmp/oss-*` returns no directories
And the user's currently-checked-out branch is unchanged
```

### AC2: `iw oss prepare` and `iw oss publish` no longer exist

```
Given the post-CR build
When the user runs `uv run iw oss prepare` or `uv run iw oss publish`
Then both commands fail with "No such command" and exit non-zero
And `uv run iw oss --help` does not list `prepare` or `publish`
```

### AC3: Dashboard renders findings as a domain-grouped table with a `…` modal

```
Given a completed scan with at least one MUST failure
When the user opens `/project/{id}/oss`
Then the page renders a table with columns Group / Test / Type / Status / Details
And findings are grouped under collapsible domain headers
And the Details column shows a `…` button on every row
When the user clicks `…` on a failing finding with `auto_apply_safe=True`
Then a modal opens with sections: What this test checks, How it tests, Risk if you ship anyway, Evidence, How to fix, Preview, References
And the footer shows Apply, Re-run check, Mark accepted, Close
```

### AC4: Per-check catalog has an entry for every check ID

```
Given the production catalog at `dashboard/services/oss_check_catalog.yaml`
When the catalog-completeness test runs
Then every `Finding(id="…")` literal across `skills/iw-oss-publish/scripts/checks/*.py` has a corresponding YAML entry
And every YAML entry has non-empty `what_it_checks`, `how_it_tests`, `risk_if_failing`, `how_to_fix`
And the test fails with a clear message naming any missing check IDs
```

### AC5: Per-finding Apply writes to the working tree only — never to git

```
Given a failing finding with `auto_apply_safe=True` (e.g., OSS-CH-01 missing README)
And HEAD is at SHA X
When the user clicks Apply in the modal
Then the target file appears as an unstaged change in `git status`
And `git rev-parse HEAD` still returns SHA X
And no commit was created
And no branch was created or switched
And re-running Apply does not duplicate content (idempotent)
```

### AC6: Accept-risk persists to `.iw/oss-accepted.yaml` and is honored by CI

```
Given a failing MUST finding for OSS-CH-01
When the user clicks Mark accepted in the modal and submits a reason
Then `.iw/oss-accepted.yaml` in the working tree gains an entry with check_id, finding_hash, reason, accepted_at, accepted_by
And the dashboard moves the finding into the Accepted group
When the user commits the file and pushes
Then `.github/workflows/compliance-scan.yml` reads the file
And the matched MUST finding is downgraded to a warning in SARIF
And the workflow exits 0 (not 1) provided no other unaccepted MUSTs exist
```

### AC7: Database migration is hard and irreversible — historical rows for prepare/publish are deleted

```
Given a live DB with rows where project_oss_job.kind in ('prepare','publish')
And rows where oss_scan.mode in ('make_oss','publish')
When the migration runs
Then those rows are deleted before the enum recreate
And the columns worktree_path, branch_name, commit_sha, files_changed_summary are dropped from project_oss_job
And ProjectOssJobKind enum no longer contains prepare or publish
And ProjectOssJobKind enum contains a new value `fix`
And OssScanMode enum no longer contains make_oss or publish
And ProjectOssJobStatus enum no longer contains awaiting_review or discarded
And oss_finding has a new auto_apply_safe BOOLEAN column with default false
```

### AC8: Scan progress streams row-level updates — no full-page reload

```
Given the user is on /project/{id}/oss with a prior scan visible
When the user clicks Scan
Then each check completion emits an SSE row-update event
And the corresponding `<tr>` is patched in place with new status and severity
And no `window.location.reload()` is invoked at any point
And the page header pill updates without a full reload
```

### AC9: Apply-all-safe is bounded, previewable, and deselectable

```
Given a scan with N findings where M are auto_apply_safe=True
When the user clicks Apply all safe
Then a preview dialog lists every file each of the M recipes would touch
And every file is checked by default
And the user can deselect individual files
When the user clicks Apply
Then only the selected recipes execute against the working tree
And no branch is created
And no commit is created
And the preview dialog closes
And the table refreshes via SSE row updates
```

### AC10: Apply-all-safe never operates on findings without auto_apply_safe=True

```
Given a scan with at least one finding where auto_apply_safe=False (e.g., OSS-SEC history secret)
When the user opens the Apply-all-safe preview dialog
Then no row in the dialog corresponds to that finding
When the user clicks Apply
Then no recipe for that finding is executed
And the finding remains unchanged
```

### AC11: Stale prep branches and worktrees from prior runs are cleaned up

```
Given the local repo has refs/heads/iw-oss-publish and 8 .git/worktrees/oss-* directories from prior runs
When Phase F cleanup runs
Then `git worktree list --porcelain` lists no worktrees with prefix `oss-`
And `git branch --list 'iw-oss-publish*'` returns empty
And `git branch --list 'iw-oss-publish/prep-*'` returns empty
```

### AC12: Browser verification confirms the full flow end-to-end

```
Given an isolated e2e stack reachable at $IW_BROWSER_BASE_URL
When the QV browser agent runs the scan, opens a finding modal, applies a fix, accepts a risk, and runs apply-all-safe
Then each interaction succeeds without console errors
And the working tree of the e2e checkout reflects all applied fixes and the appended .iw/oss-accepted.yaml
And no branch was created or switched at any step
```

## Rollback Plan

- **Database**: Migration is **not reversible** without restoring the live DB from a backup taken before merge. Deleted rows for kind in (prepare, publish) and mode in (make_oss, publish) are gone. If rollback is required: restore `iw_ai_core` schema from the most recent pre-merge backup, then `git revert` the merge commit. Coordinate with the operator before any rollback attempt.
- **Code**: Single squash-merge commit; revert via `git revert <merge-sha>`. Note that reverting code without restoring the DB will leave the schema mismatched with the ORM (missing enum values, dropped columns) and the dashboard will fail at startup. Treat code rollback and DB rollback as a single coordinated action.
- **Data**: `.iw/oss-accepted.yaml` files in managed projects are unaffected by rollback (they are separate repos). No data loss for those.

## Dependencies

- **Depends on**: None (the `c9ff6d7` OSS prep commit on `iw-ai-core/main` is a precondition only in that the catalog-population step uses this repo to enumerate check IDs; it is not a blocking dependency).
- **Blocks**: None.

## TDD Approach

- **Unit tests**:
  - `tests/unit/test_oss_catalog_completeness.py` — AST-walks `skills/iw-oss-publish/scripts/checks/*.py`, asserts every `Finding(id=...)` literal exists in `oss_check_catalog.yaml` with non-empty mandatory fields.
  - `tests/unit/test_oss_check_catalog_loader.py` — schema validation, hot-reload-in-debug behavior, cache hit semantics in production.
  - `tests/unit/test_oss_accepted_yaml.py` — round-trip read/write, deterministic finding_hash, append semantics, schema validation.
  - `tests/unit/test_oss_fix_recipes_idempotent.py` — for each registered recipe: applying twice is a no-op (file state identical after second apply); preview matches actual write.
- **Integration tests**:
  - `tests/integration/test_oss_migration.py` — extend with assertions: dropped columns absent; enum values pruned; pre-migration delete of prepare/publish rows verified; new `auto_apply_safe` column exists with default false.
  - `tests/integration/test_oss_dashboard_routes.py` — `/oss/fix/{check_id}` (preview + apply), `/oss/recheck/{check_id}`, `/oss/accept/{check_id}`, `/oss/apply-all-safe/preview` and `/oss/apply-all-safe`. Removed routes return 404.
  - `tests/integration/test_oss_dashboard_sse.py` — extend with row-update event shape and ordering.
  - `tests/integration/test_oss_cli.py` — `iw oss fix <CHECK_ID>` and `--apply` semantics; `iw oss prepare` and `iw oss publish` removed.
  - `tests/integration/test_oss_dashboard_service.py` — fix-runner orchestrator, accepted-yaml join, no worktree provisioning under any code path.
- **Updated tests**:
  - `tests/integration/test_project_oss_job_migration.py` — assert dropped columns and pruned enum values.
  - `tests/integration/test_oss_persistence.py` — drop assertions referencing make_oss/publish modes.
  - `tests/integration/test_oss_scanner.py` — drop mode parametrization; add `auto_apply_safe` propagation.
  - `tests/integration/test_oss_dashboard_templates_extras.py` — replace cards-template assertions with table-template assertions.
  - `tests/integration/test_oss_dashboard_boundary.py` — `dashboard.routers.oss.oss_prepare` and `oss_publish` removed.

## Notes

### Open question: keep or remove `install` flow?

The current `ProjectOssJobKind.install` and `oss_install_modal.html` install Tier-1 tooling (gitleaks, syft, etc.). This CR's design discussion did not explicitly cover the install flow. **Default**: keep `install` kind and `oss_install_modal.html` since they are independent of prepare/publish — the install button stays as a separate action. If the review concludes install should also fold into the catalog/setup, raise as a follow-up CR.

### Idempotency contract for fix recipes

Every recipe must satisfy: applying the recipe twice in succession yields the same on-disk state as applying it once. Template-render recipes (LICENSE, SECURITY.md) overwrite the file — naturally idempotent. Patch-style recipes (e.g., adding lines to `.gitignore`) MUST detect the existing pattern and no-op if already present. Tests in `test_oss_fix_recipes_idempotent.py` enforce this for every registered recipe.

### `.iw/oss-accepted.yaml` schema

```yaml
# Findings consciously accepted as residual risk.
# Each entry suppresses one specific finding instance from CI blocking.
accepted:
  - check_id: OSS-CH-01
    finding_hash: a1b2c3d4   # stable hash of (check_id + summary + evidence_json)
    reason: "Internal-only project, no public users"
    accepted_at: "2026-04-25T14:30:00Z"
    accepted_by: "user@example.com"
```

`finding_hash` is computed deterministically; if a check rewords its `summary` text, the hash changes and the accept entry no longer matches — by design, so behavioral changes re-prompt for review.

### CI integration shape

`compliance-scan.yml` step ordering:
1. Run scan as today.
2. Read `.iw/oss-accepted.yaml` (tolerate missing file).
3. Match findings by (check_id + finding_hash); for each match, downgrade SARIF severity from `error` to `warning` and annotate `message.text` with the accepted reason.
4. Exit non-zero only if any unaccepted MUST finding remains.

### Brand voice

Catalog copy follows `doc-system/` editorial guidelines (concise, plain English, no emoji, second-person address where natural). Each S05 catalog entry should be reviewable as standalone product copy, not as commit-log prose.

### Risks

- **Catalog drift** — mitigated by `test_oss_catalog_completeness.py` running in CI; any new check without a catalog entry fails the build.
- **Finding-hash brittleness** — accepting a finding today may not match tomorrow if the check rewords its summary. Acceptable for v1; documented in the catalog page.
- **"Apply all safe" misuse** — explicit confirmation dialog with deselectable checklist + `auto_apply_safe=False` filter prevents bulk-applying anything risky. Code review enforces working-tree-only invariant.
- **Migration irreversibility** — coordinated with operator; pre-merge dry-run against testcontainer + post-merge live apply is the standard daemon flow (see CR-00021 / CR-00017).
