# CR-00020: Store work item evidences as BLOBs in the database

**Type**: Change Request
**Priority**: High
**Reason**: Evidences are lost when items are archived (dashboard Evidences tab is permanently empty for every merged/archived item — verified on I-00036)
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

Your job in the S01 Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline (pre-merge dry-run against a
testcontainer, post-merge apply to live DB). If the migration is broken,
the daemon will refuse to merge the batch.

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

Move the authoritative store of work-item screenshots and snapshots from the filesystem (`ai-dev/active/<id>/evidences/{pre,post}/`) into a new PostgreSQL table `work_item_evidences` with `BYTEA` content, ingested at two lifecycle points (`iw approve` for `pre/`, `iw step-done` for `post/` on `browser_verification` steps). The dashboard Evidences tab switches to DB-first reads with a filesystem fallback for in-progress post-evidence. Filesystem writes by agents are unchanged; only the durable copy moves.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. Key references:

- `orch/CLAUDE.md` — table layout, ENUMs, sync SQLAlchemy style, psycopg v3 driver
- `dashboard/CLAUDE.md` — router patterns (thin), htmx fragment conventions, `get_db()` DI, `_list_evidences` / `item_evidence_file` currently at `dashboard/routers/items.py:696` and `:1229`
- `tests/CLAUDE.md` — testcontainer rules, FTS DDL, no DB mocking in integration

Precedent CR for similar BYTEA/log-capture patterns: the `step_runs.log_content` TEXT column (`e5f6a7b8c9d0_add_log_content_to_step_runs.py`). This CR uses the same "capture on lifecycle event" pattern.

## Current Behavior

1. **Ingestion**: agents/skills write files to `ai-dev/active/<item_id>/evidences/pre/` (during `/iw-new-*` design) or `ai-dev/active/<item_id>/evidences/post/` (during qv-browser steps). Nothing is recorded in the DB.
2. **Dashboard rendering**: `dashboard/routers/items.py:_list_evidences()` scans `(worktree or repo_root)/ai-dev/active/<id>/evidences/{pre,post}/` from disk. `item_evidence_file()` serves the image file bytes straight from disk.
3. **Archive**: when a batch is archived, `ai-dev/active/<id>/` is deleted entirely and re-packed into `ai-dev/archives/<project>/<id>.tar.zst`. The tarball contains the evidences but the dashboard does not read from it.
4. **Result**: every merged/archived item's Evidences tab is permanently empty. See `git log --all --oneline -- "ai-dev/active/I-00036/evidences"` — the wip commit created evidences, the archive commit removed them, the Evidences tab has been blank ever since.

## Desired Behavior

1. **Pre-evidence ingestion at approval**: `iw approve <item>` transitions `draft → approved` AND scans `<repo_root>/ai-dev/active/<item>/evidences/pre/` for regular files, upserting each into `work_item_evidences` with `phase='pre'`, `step_id=NULL`.
2. **Post-evidence ingestion at browser step-done**: `iw step-done <item> --step <S>` for `browser_verification` steps — after the existing `validate_browser_evidence_present` check passes — scans `<cwd>/ai-dev/active/<item>/evidences/post/` and upserts each file with `phase='post'`, `step_id=<S>`.
3. **Dashboard reads from DB**: `_list_evidences()` queries the new table. `item_evidence_file()` serves `content` with `content_type`. Filesystem fallback only for post-evidences while a worktree is live and `step-done` has not yet run (so operators can watch progress).
4. **Post-archive view**: even after `ai-dev/active/<id>/` is deleted by the archive step, the Evidences tab keeps showing every captured image, byte-identical.
5. **Agent/skill workflow unchanged**: qv-browser still writes to `evidences/post/`; `/iw-new-*` still writes to `evidences/pre/`. They do not call any new CLI.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `work_item_evidences` table | Does not exist | New table with BYTEA content, unique per (project, item, phase, filename) |
| `EvidencePhase` enum | Does not exist | New PG enum `('pre','post')` |
| `orch/cli/item_commands.py approve` | Flip status, commit | Flip status, then `ingest_phase_from_disk(phase='pre')` before commit |
| `orch/cli/step_commands.py step_done` | Flip status, capture log | Flip status, capture log, then for `browser_verification` → `ingest_phase_from_disk(phase='post', step_id=...)` |
| `dashboard/routers/items.py:_list_evidences` | FS scan of `ai-dev/active/<id>/evidences/{pre,post}/` | DB query against `work_item_evidences`; FS fallback for post-only while worktree alive |
| `dashboard/routers/items.py:item_evidence_file` | Reads bytes from disk | DB lookup → `Response(content, media_type=content_type)`; FS fallback identical scope to above |
| `orch/config.py` | No evidence size knob | New optional `IW_CORE_EVIDENCE_MAX_BYTES` (default 5242880) |
| `docs/IW_AI_Core_Database_Schema.md` | 19 tables documented | 20 tables — new `work_item_evidences` section |
| `CLAUDE.md` Quick Navigation | No evidence row | `Evidences (DB)` row → `orch/evidences.py` |

### Breaking Changes

- **None at the agent/skill level.** FS writes remain the entry point; the new ingest is a DB-side sink added at lifecycle events the agent already triggers.
- **None at the HTTP/dashboard level.** Same URLs, same HTML fragments, same image responses — only the byte source changes.
- **Schema migration** is additive (new enum, new table, no modifications to existing tables). Old items remain queryable; they just have zero rows in the new table.

### Data Migration

- **New schema**: `EvidencePhase` enum + `work_item_evidences` table via Alembic autogenerate.
- **No backfill**: already-archived items (everything merged before this CR ships) stay empty in the Evidences tab. Explicitly out of scope.
- **Reversibility**: full — `downgrade()` drops the table and enum; zero data loss from existing tables since we don't touch them.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | database-impl | `EvidencePhase` enum + `WorkItemEvidence` ORM model + Alembic migration (up/down) + indexes + FK without cascade | — |
| S02 | code-review-impl | Review S01 (schema correctness, no-cascade FK, indexes, enum naming, autogen completeness) | — |
| S03 | backend-impl | `orch/evidences.py` pure ingest helper (`ingest_phase_from_disk`), `orch/config.py` `IW_CORE_EVIDENCE_MAX_BYTES`, hooks in `orch/cli/item_commands.py approve` (pre) and `orch/cli/step_commands.py step_done` (post for browser_verification) | — |
| S04 | code-review-impl | Review S03 (transaction scope, size-limit enforcement, idempotent upsert via `ON CONFLICT`, no agent-facing behaviour changes) | — |
| S05 | api-impl | Rewrite `dashboard/routers/items.py:_list_evidences` and `:item_evidence_file` to read from DB with FS fallback for in-progress post-evidences; keep path-traversal guard on FS fallback | — |
| S06 | code-review-impl | Review S05 (DB-first correctness, FS-fallback scope exactly = in-progress post-only, content-type + streaming, htmx contract unchanged) | — |
| S07 | tests-impl | Unit tests for `ingest_phase_from_disk` (happy path, size limit, idempotent upsert, missing dir, empty dir, non-file entries, permission errors) + integration tests for `iw approve` / `iw step-done` against testcontainer + dashboard tests for DB-sourced evidences and FS fallback window | — |
| S08 | code-review-impl | Review S07 (coverage of all ACs, testcontainer compliance, no DB mocking, fixture isolation, byte-identical content assertions) | — |
| S09 | code-review-final-impl | Cross-layer review: AC1–AC8 coverage, transactional rollback semantics, archive-survival behaviour, docs updates (schema + CLAUDE.md), no regression to existing pre-evidence lookup for in-progress items | — |
| S10 | qv-gate | lint (`make lint`) | — |
| S11 | qv-gate | format (`uv run ruff format --check .`) | — |
| S12 | qv-gate | typecheck (`make typecheck`) | — |
| S13 | qv-gate | unit-tests (`make test-unit`) | — |
| S14 | qv-gate | integration-tests (`make test-integration`) | — |
| S15 | qv-browser | End-to-end: approve an item with pre/ fixture, execute a minimal browser_verification step-done with post/ fixture, delete `ai-dev/active/<id>/`, verify Evidences tab still renders both phases | — |

### Database Changes

- **New tables**: `work_item_evidences`
- **New enums**: `evidence_phase ('pre','post')`
- **Modified tables**: none
- **Migration notes**: Alembic autogenerate against the new ORM model. `FOREIGN KEY (project_id, work_item_id) REFERENCES work_items(project_id, id)` with **NO `ON DELETE CASCADE`** (this is the durability requirement). Index on `(project_id, work_item_id, phase)` for list queries; the unique constraint `(project_id, work_item_id, phase, filename)` doubles as a lookup index for `item_evidence_file`.

### API Changes

- **New endpoints**: none
- **Modified endpoints**:
  - `GET /project/{project_id}/item/{item_id}/tab/evidences` — identical URL + response shape, DB-sourced listing
  - `GET /project/{project_id}/item/{item_id}/evidence/{phase}/{filename}` — identical URL + response, DB-sourced bytes
- **Removed endpoints**: none

### Frontend Changes

- **New components**: none
- **Modified components**: none — `fragments/item_evidences.html` renders the same `EvidenceFile` shape; no template edits needed
- **Removed components**: none

## File Manifest

All files for this work item live under `ai-dev/active/CR-00020/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00020_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/CR-00020_S01_Database_prompt.md` | Prompt | Create enum + ORM model + migration |
| `prompts/CR-00020_S02_CodeReview_prompt.md` | Prompt | Review S01 |
| `prompts/CR-00020_S03_Backend_prompt.md` | Prompt | Ingest helper + config var + CLI hooks |
| `prompts/CR-00020_S04_CodeReview_prompt.md` | Prompt | Review S03 |
| `prompts/CR-00020_S05_API_prompt.md` | Prompt | Dashboard router rewrite |
| `prompts/CR-00020_S06_CodeReview_prompt.md` | Prompt | Review S05 |
| `prompts/CR-00020_S07_Tests_prompt.md` | Prompt | Unit + integration + dashboard tests |
| `prompts/CR-00020_S08_CodeReview_prompt.md` | Prompt | Review S07 |
| `prompts/CR-00020_S09_CodeReview_Final_prompt.md` | Prompt | Final cross-layer review |
| `prompts/CR-00020_S15_BrowserVerification_prompt.md` | Prompt | Playwright QV at dashboard port 9900 (isolated worktree stack) |
| `evidences/pre/CR-00020-before-empty-evidences-tab.png` | Evidence | Baseline screenshot of the broken Evidences tab on archived I-00036 |

Expected production-code files to be created/modified by implementation steps:

- `orch/db/models.py` — `EvidencePhase`, `WorkItemEvidence` (modify)
- `orch/db/migrations/versions/<new>_add_work_item_evidences.py` — Alembic migration (new)
- `orch/config.py` — `IW_CORE_EVIDENCE_MAX_BYTES` + `load_config` wiring (modify)
- `orch/evidences.py` — new pure ingest module
- `orch/cli/item_commands.py` — hook ingest into `approve` (modify)
- `orch/cli/step_commands.py` — hook ingest into `step_done` (modify)
- `dashboard/routers/items.py` — DB-first reads, FS fallback (modify)
- `tests/unit/test_evidences_ingest.py` — new
- `tests/integration/test_evidences_cli.py` — new
- `tests/dashboard/test_evidences_db_source.py` — new
- `docs/IW_AI_Core_Database_Schema.md` — document new table (modify)
- `CLAUDE.md` — Quick Navigation row (modify)

## Acceptance Criteria

### AC1: Pre-evidences ingested on approval

```
Given a work item X-99999 in draft status with regular files at
      ai-dev/active/X-99999/evidences/pre/shot1.png and /shot2.yml
When `iw approve X-99999` is run from the repo root
Then the item transitions draft → approved, AND
     work_item_evidences contains two rows for (project, X-99999, 'pre', *)
     with step_id=NULL, correct content_type (image/png, text/yaml),
     size_bytes equal to the file size on disk, and content byte-identical
     to the file (SHA256 match).
```

### AC2: Post-evidences ingested on browser step-done

```
Given an in-progress browser_verification step S11 for X-99999 with files at
      ai-dev/active/X-99999/evidences/post/V1_shot.png and /V2_shot.png
When `iw step-done X-99999 --step S11 --report <path>` is run
Then the step transitions in_progress → completed, AND
     work_item_evidences contains two rows with phase='post', step_id='S11',
     correct content_type, size_bytes, and byte-identical content.
```

### AC3: Re-ingest is idempotent (upsert)

```
Given work_item_evidences already has a row for (P, X, 'post', 'V1_shot.png')
When ingest runs again and the file on disk now has different bytes
Then no duplicate row is created (unique key (project, item, phase, filename)), AND
     the existing row's content, content_type, size_bytes, captured_at
     are updated via ON CONFLICT DO UPDATE, AND
     the row's id (UUID) is unchanged.
```

### AC4: Size limit enforced; partial ingest prevented

```
Given ai-dev/active/X/evidences/pre/ contains ok.png (100KB) and huge.png (10MB)
  and IW_CORE_EVIDENCE_MAX_BYTES defaults to 5242880 (5MB)
When `iw approve X` is run
Then the CLI exits with code 1 and stderr names 'huge.png' and its size, AND
     work_item_evidences contains zero rows for X (transaction rolled back —
     ok.png was NOT partially ingested), AND
     the item status stays 'draft' (the status flip is in the same transaction).
```

### AC5: Dashboard serves from DB after FS deletion (archive simulation)

```
Given item X has evidences ingested in both phases
  and the on-disk directory ai-dev/active/X/ has been removed (simulating archive)
When GET /project/{pid}/item/X/tab/evidences is requested
Then the HTML response lists all pre + post evidences, AND
     GET /project/{pid}/item/X/evidence/pre/<filename> returns 200 with
     the correct Content-Type and bytes byte-identical to what was ingested.
```

### AC6: Evidences survive work_item deletion (no cascade)

```
Given work_item_evidences has rows for item X and the work_items row for X exists
When the work_items row is deleted directly
Then the work_item_evidences rows for X remain (no CASCADE), AND
     querying them by (project_id, work_item_id) still returns them.
```

### AC7: In-progress post-evidences visible via FS fallback

```
Given a browser_verification step for X is in_progress and the agent has already
      written one screenshot to <worktree>/ai-dev/active/X/evidences/post/V1.png
  and `iw step-done` has NOT yet been called (so DB has no post rows for X)
When GET /project/{pid}/item/X/tab/evidences is requested
Then the Evidences tab lists V1.png under post-evidences (sourced from FS), AND
     GET /project/{pid}/item/X/evidence/post/V1.png returns the FS bytes.
```

### AC8: Items without evidences folders are a no-op

```
Given item Y has no ai-dev/active/Y/evidences/ directory (or it is empty)
When `iw approve Y` and later `iw step-done Y --step <browser_step>` are run
Then both commands succeed, AND
     work_item_evidences contains zero rows for Y (no error, no empty row).
```

## Rollback Plan

- **Database**: full reverse migration — `alembic downgrade -1` drops the table and enum. No data touched in existing tables, so zero data loss.
- **Code**: revert the merge commit. Agents/skills were never changed, so there's no lingering FS behaviour to unwind.
- **Data**: no backup restore needed. Evidences captured between this merge and the rollback will be lost from the DB, but the on-disk copy (still being written by agents) remains for any not-yet-archived item. Already-archived items were never in scope for backfill, so nothing is lost that was viewable before.

## Dependencies

- **Depends on**: None — independent DB migration + backend + dashboard work.
- **Blocks**: None currently planned.

## TDD Approach

- **Unit tests (`tests/unit/test_evidences_ingest.py`, no DB)**:
  - Build a `tmp_path` mock-FS; exercise `ingest_phase_from_disk` against an in-memory fake session (or parametrised session abstraction)
  - Happy path: 2 files → 2 upsert operations recorded
  - Size limit: one file >max → raises; no upserts recorded
  - Missing dir / empty dir / subdirs-only → 0 upserts, no error
  - Non-regular entries (symlinks pointing outside, sockets) → skipped
  - MIME detection fallback to `application/octet-stream` for unknown extensions

- **Integration tests (`tests/integration/test_evidences_cli.py`, testcontainer)**:
  - AC1 fixture: create item + pre/ files → `iw approve` → assert rows, byte-identical content
  - AC2 fixture: create item + browser_verification step in_progress + post/ files → `iw step-done` → assert rows
  - AC3: run ingest twice with different content → same UUID, updated content
  - AC4: oversized file → CLI exit 1, zero rows, status not flipped
  - AC6: delete `work_items` row → evidences rows remain (query-check)

- **Dashboard tests (`tests/dashboard/test_evidences_db_source.py`, TestClient + testcontainer)**:
  - AC5: ingest rows, delete on-disk dir, GET tab → HTML lists evidences; GET image URL → 200 with bytes
  - AC7: in-progress step with post/ on disk but no DB rows → FS fallback surfaces it
  - Path traversal still blocked on FS fallback (existing assertion carries over)

- **Updated tests**: existing dashboard tests that mock `_list_evidences` (if any) need to be updated to match the new signature/data source. S07 will audit.

## Notes

- **Size cap rationale**: 5MB covers full-page Playwright screenshots at 2× DPI (typically ≤2MB) with margin. Configurable via env for special cases.
- **Why not a new CLI for explicit upload?** Agents already write files to the canonical location at canonical times. Piggybacking on `iw approve` / `iw step-done` avoids touching any agent/skill and keeps the durable-copy write atomic with the status transition.
- **Transaction scope**: each CLI invocation is one transaction. Ingest runs inside the existing session's `with get_session() as session:` block, so a size-limit failure rolls back both the ingest AND the status flip. This is the "all-or-nothing" guarantee in AC4.
- **FS fallback narrowness**: the fallback applies only to post-evidences AND only when a worktree is active for the item (i.e., `BatchItem.worktree_info['path']` exists). Pre-evidences always come from DB once approved — no fallback. This keeps the dashboard code simple and avoids "FS-shows-different-thing-than-DB" confusion for merged items.
- **Risks**:
  - DB size growth — mitigated by 5MB cap + unique-key upsert (no duplicate accumulation). Expected <100MB/year based on current batch cadence.
  - `pg_dump` backups grow linearly with evidence count; acceptable for current scale. If this becomes a concern, a future CR can move to filesystem-backed pointers — the table API stays the same.
  - BYTEA over the wire — fine for ≤5MB images, no streaming needed.
