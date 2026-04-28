# CR-00025: Implement missing evidence-ingestion pipeline (CR-00020 follow-up) and backfill archived items

**Type**: Change Request
**Priority**: Medium
**Reason**: CR-00020 (merged 2026-04-24, commit `34990ad`) added the `work_item_evidences` table, ORM model, and dashboard reads, but the S03 backend agent silently descoped the actual ingestion hooks. The table is empty in the live DB (verified: 0 rows), so every archived item's Evidences tab is blank — the user observed this on I-00044. The bytes survive in `ai-dev/archives/<project>/<id>.tar.zst` but the dashboard cannot reach them.
**Created**: 2026-04-28
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

This CR adds **no DDL** — the table already exists. There is no migration
to write. If a step seems to need one, STOP and raise a blocker.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Description

Wire up the missing evidence-ingestion pipeline that CR-00020 specified but
never delivered. Add `orch/evidences.py:ingest_phase_from_disk(...)` and hook
it into `iw approve` (phase=`pre`) and `iw step-done` for `browser_verification`
steps (phase=`post`). Add `IW_CORE_EVIDENCE_MAX_BYTES` (default 5 MiB) with
hard-fail on oversize. Run a one-shot backfill against the production orch DB
to recover evidences from existing `.tar.zst` archives, then delete the
backfill script before merge. Also add the post-archive regression test that
the original CR-00020 S15 qv-browser step was supposed to perform but missed.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules.
Key references for this CR:

- `orch/CLAUDE.md` — sync SQLAlchemy 2.0 style, psycopg v3 driver, append-only
  audit tables (this CR is **not** append-only — `work_item_evidences` is upsert
  by `(project_id, work_item_id, phase, filename)`).
- `dashboard/CLAUDE.md` — `_list_evidences` and `item_evidence_file` already
  read DB-first with FS fallback for in-progress post-evidence; **no dashboard
  changes** are needed.
- `tests/CLAUDE.md` — testcontainer rules, FTS DDL, no DB mocking in
  integration tests.
- Original design: `ai-dev/archives/iw-ai-core/CR-00020.tar.zst → CR-00020_CR_Design.md`.
- Smoking-gun report: `ai-dev/archives/iw-ai-core/CR-00020.tar.zst → reports/CR-00020_S03_Backend_report.md`
  ("The `approve` command does not ingest pre-evidences. … This is a known gap
  but falls outside CR-00020's scope.").

## Current Behavior

1. `iw approve <ID>` — `orch/cli/item_commands.py:approve` (lines 470-504)
   transitions `draft → approved` and calls `ensure_active_files_committed`.
   It does **not** scan `ai-dev/active/<id>/evidences/pre/` and does **not**
   insert into `work_item_evidences`.
2. `iw step-done <ID> --step <S>` — `orch/cli/step_commands.py:step_done`
   (lines 271-347). For `browser_verification` step types it calls
   `validate_browser_evidence_present` (line 51) which only **checks** that
   `evidences/post/` is non-empty; it does **not** copy bytes into the DB.
3. The dashboard's `_list_evidences` (`dashboard/routers/items.py:700`) queries
   `work_item_evidences` first, then falls back to FS for in-progress
   post-evidence within a live worktree.
4. The archiver (`orch/archive/archiver.py:120`) runs `shutil.rmtree(work_item_dir)`
   when `cleanup=True`, deleting `ai-dev/active/<id>/` — including its
   `evidences/` tree.
5. Result: once an item is archived, the FS source is gone, the DB row count
   for `work_item_evidences` is **zero across all projects** (verified
   2026-04-28), and the dashboard's Evidences tab shows "No evidences
   captured for this item." for every archived item. The bytes still exist
   inside `ai-dev/archives/<project>/<id>.tar.zst` but nothing reads them.

Pre-evidence: `ai-dev/active/CR-00025/evidences/pre/CR-00025_I-00044_blank_evidences_tab.png`
shows the "No evidences captured for this item." empty state on
`http://iw-dev-01:9900/project/iw-ai-core/item/I-00044/tab/evidences`,
despite I-00044's archive containing 3 pre + 8 post PNGs.

## Desired Behavior

1. `iw approve <ID>` ingests every regular file in
   `<repo_root>/ai-dev/active/<id>/evidences/pre/` into `work_item_evidences`
   with `phase='pre'`, `step_id=NULL`, before commit. Idempotent on re-run.
2. `iw step-done <ID> --step <S>` for `browser_verification` step types — after
   the existing `validate_browser_evidence_present` check passes — ingests
   every regular file in `<cwd>/ai-dev/active/<id>/evidences/post/` with
   `phase='post'`, `step_id=<S>`. Idempotent.
3. A new `orch/evidences.py:ingest_phase_from_disk(...)` pure helper is the
   single ingestion point used by both hooks. Upserts by `(project_id,
   work_item_id, phase, filename)`, MIME-sniffs by extension via
   `mimetypes.guess_type` (no new deps), and **hard-fails** with a clear
   error when any file exceeds `IW_CORE_EVIDENCE_MAX_BYTES` (no silent skip).
4. A one-shot script `scripts/CR-00025_backfill_evidences.py` connects to the
   production orch DB via `IW_CORE_ORCH_DB_*` env vars, iterates every
   `Project` row, opens each `<archive_dir>/<project>/<id>.tar.zst`, extracts
   `evidences/{pre,post}/` into a tmpdir, and calls
   `ingest_phase_from_disk(...)` against the live DB. Idempotent per
   `(project_id, work_item_id, phase)`: skips if any rows already exist for
   that triple. Logs row counts before/after. After running and verifying
   I-00044's Evidences tab on the production dashboard, the script is
   **deleted** in the same step's commit.
5. After this CR ships:
   - New work items capture pre evidences at approve and post evidences at
     browser-verification step-done.
   - Archived items already on disk (including I-00044) regain their
     evidences via the backfill.
   - The dashboard's Evidences tab shows captured screenshots for every
     archived item.
   - A new integration test
     (`tests/integration/test_evidences_lifecycle.py::test_evidences_visible_after_archive_cleanup`)
     guards against regression of the original gap by simulating the full
     approve → ingest → archive-with-cleanup → `_list_evidences` flow.

## Impact Analysis

### Affected Components

| Component | Current State | Changed To |
|-----------|---------------|------------|
| `orch/evidences.py` | Does not exist | New module: `ingest_phase_from_disk(session, project_id, work_item_id, phase, root, step_id=None, max_bytes=...)` |
| `orch/config.py` | No evidence-size knob | Add `IW_CORE_EVIDENCE_MAX_BYTES` (int, default `5 * 1024 * 1024`) |
| `orch/cli/item_commands.py` `approve` | Flips status, commits | Flips status, then `ingest_phase_from_disk(phase='pre', step_id=None)` before commit |
| `orch/cli/step_commands.py` `step_done` | Validates browser evidence presence; flips status | Same, plus `ingest_phase_from_disk(phase='post', step_id=<S>)` for `browser_verification` step types after the validate check |
| `dashboard/routers/items.py` | DB-first read with FS fallback | Unchanged — already correct |
| `work_item_evidences` table | 0 rows | Populated for new approvals/step-dones; backfilled for existing archives |
| `scripts/CR-00025_backfill_evidences.py` | Does not exist | One-shot script (created in S12, deleted in same step before commit) |
| `tests/unit/test_evidences_ingest.py` | Does not exist | New unit tests for the helper |
| `tests/integration/test_evidences_lifecycle.py` | Does not exist | New integration tests covering approve/step-done ingestion + post-archive visibility regression |
| `docs/IW_AI_Core_Database_Schema.md` | Says CR-00020 wires up ingestion at approve/step-done | Same prose, but a small "Implemented in CR-00025" cross-reference noting the table was empty until CR-00025 |
| `CLAUDE.md` Quick Navigation | No evidences row | Add `Evidences ingestion → orch/evidences.py` row |

### Breaking Changes

- **None at the agent/skill level.** Filesystem writes by qv-browser and the
  `iw-new-*` skills remain the entry point. The new ingest is a DB-side sink
  invoked at lifecycle events the agent already triggers.
- **None at the dashboard/HTTP level.** `_list_evidences` and
  `item_evidence_file` are unchanged; they already read DB-first.
- **Behavioural change**: `iw approve` and `iw step-done` will now hard-fail
  if any single evidence file exceeds `IW_CORE_EVIDENCE_MAX_BYTES`. This is
  intentional per the user's call (option `a` — never silently lose data).

### Data Migration

- **No DDL.** The table, enum, FK, and indexes already exist (migration
  `d6b67d4ecb9f_add_work_item_evidences.py` shipped with CR-00020).
- **One-shot data backfill** from `ai-dev/archives/<project>/<id>.tar.zst`
  into `work_item_evidences`. Idempotent per `(project_id, work_item_id,
  phase)`: skips if any rows already exist for that triple, so re-running
  the script is safe but a no-op for already-backfilled items. The script
  is deleted in the same step it runs in — the squash-merge to main will
  not include it.
- **Reversibility**: `DELETE FROM work_item_evidences WHERE created_at >
  '<deploy timestamp>';` (the table has `captured_at` as the only timestamp;
  for full reversal, simply `TRUNCATE work_item_evidences` — the bytes are
  still in the on-disk archives). The new code paths are reverted by
  `git revert` of the squash-merge commit.

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | Create `orch/evidences.py:ingest_phase_from_disk`. Add `IW_CORE_EVIDENCE_MAX_BYTES` to `orch/config.py`. Hook the helper into `orch/cli/item_commands.py:approve` (pre, step_id=NULL) and `orch/cli/step_commands.py:step_done` (post, step_id=<S>, only when `step_type == browser_verification`). Update `docs/IW_AI_Core_Database_Schema.md` and `CLAUDE.md` Quick Navigation. | — |
| S02 | code-review-impl | Review S01: transaction scope (ingest must run inside the same `get_session` transaction as the status flip; rollback semantics if ingest raises), size-limit hard-fail correctness, MIME extension map covers PNG/JPEG/WEBP/GIF/PDF/TXT/MD/YAML/JSON, upsert via `ON CONFLICT (project_id, work_item_id, phase, filename) DO UPDATE`, no agent-facing surface change, no new external deps. | — |
| S03 | tests-impl | Unit tests for `ingest_phase_from_disk` (happy path, oversize hard-fail, idempotent upsert, missing dir tolerated, empty dir tolerated, non-file entries ignored, byte-identical content via SHA256). Integration tests for `iw approve` and `iw step-done` ingestion paths against a real testcontainer. **Regression test**: simulate full approve → ingest pre → step-done with browser_verification → ingest post → `archive_work_item(cleanup=True)` → assert `_list_evidences(...)` still returns DB rows after `ai-dev/active/<id>/` is gone (the gap S15 of CR-00020 missed). | — |
| S04 | code-review-impl | Review S03: coverage of all ACs, no DB mocking in integration tests, fixture isolation, byte-identical content assertions, regression test actually exercises archiver cleanup. | — |
| S05 | code-review-final-impl | Cross-layer: AC1–AC8 coverage, transactional correctness, archive-survival behaviour, docs synced, no regression to existing `_list_evidences` FS fallback. | — |
| S06 | qv-gate | `make lint` | — |
| S07 | qv-gate | `make format-check` | — |
| S08 | qv-gate | `make typecheck` | — |
| S09 | qv-gate | `make test-unit` | — |
| S10 | qv-gate | `make allure-integration` | — |
| S11 | qv-browser | E2E verification of the **new ingestion path** in the isolated worktree stack. Approve a fixture work item with a pre/ screenshot, drive a browser_verification step-done with a post/ screenshot, screenshot the dashboard's Evidences tab, then delete `ai-dev/active/<id>/` and screenshot the tab again — must remain populated. | — |
| S12 | backend-impl | Write `scripts/CR-00025_backfill_evidences.py`, run it against the production orch DB (using `IW_CORE_ORCH_DB_*`), screenshot `http://iw-dev-01:9900/project/iw-ai-core/item/I-00044/tab/evidences` showing the now-populated tab into `evidences/post/`, then **delete the script** before completing. | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No DDL. Table, enum, FK, and indexes were created
  by `d6b67d4ecb9f_add_work_item_evidences.py` in CR-00020. This CR is
  pure code + data backfill.

### API Changes

- **New endpoints**: None
- **Modified endpoints**: None
- **Removed endpoints**: None

### Frontend Changes

- **New components**: None
- **Modified components**: None
- **Removed components**: None

The dashboard already reads DB-first; no template or htmx changes needed.

## File Manifest

All files for this work item live under `ai-dev/active/CR-00025/`:

| File | Type | Purpose |
|------|------|---------|
| `CR-00025_CR_Design.md` | Design | This document |
| `workflow-manifest.json` | Manifest | Step definitions for the daemon |
| `evidences/pre/CR-00025_I-00044_blank_evidences_tab.png` | Pre-evidence | Empty Evidences tab on the production dashboard |
| `prompts/CR-00025_S01_Backend_prompt.md` | Prompt | S01 implementation instructions |
| `prompts/CR-00025_S02_CodeReview_Backend_prompt.md` | Prompt | S02 review instructions |
| `prompts/CR-00025_S03_Tests_prompt.md` | Prompt | S03 test instructions |
| `prompts/CR-00025_S04_CodeReview_Tests_prompt.md` | Prompt | S04 review instructions |
| `prompts/CR-00025_S05_CodeReview_Final_prompt.md` | Prompt | S05 cross-layer review instructions |
| `prompts/CR-00025_S11_BrowserVerification_prompt.md` | Prompt | S11 qv-browser instructions |
| `prompts/CR-00025_S12_Backend_Backfill_prompt.md` | Prompt | S12 backfill + cleanup instructions |

Files modified by implementation (tracked here for batch-planner overlap analysis):

- `orch/evidences.py` (create)
- `orch/config.py` (modify)
- `orch/cli/item_commands.py` (modify)
- `orch/cli/step_commands.py` (modify)
- `tests/unit/test_evidences_ingest.py` (create)
- `tests/integration/test_evidences_lifecycle.py` (create)
- `docs/IW_AI_Core_Database_Schema.md` (modify)
- `CLAUDE.md` (modify)
- `scripts/CR-00025_backfill_evidences.py` (create in S12, delete in S12)

Reports are created during execution under `ai-dev/active/CR-00025/reports/`.

## Acceptance Criteria

### AC1: `iw approve` ingests pre evidences

```
Given a work item X-99999 with two files in
      <repo_root>/ai-dev/active/X-99999/evidences/pre/ (PNG + YAML)
When `iw approve X-99999` is run from the repo root
Then the item transitions draft → approved, AND
     work_item_evidences contains exactly 2 rows for
     (project, X-99999, 'pre') with step_id=NULL,
     correct content_type (image/png, application/yaml or text/yaml),
     size_bytes equal to the file size on disk, and content
     byte-identical to the file (SHA256 match).
```

### AC2: `iw step-done` ingests post evidences only for browser_verification

```
Given a work item X-99999 with one file in
      <cwd>/ai-dev/active/X-99999/evidences/post/screenshot.png
And the workflow step S05 has step_type='browser_verification' and is in_progress
When `iw step-done X-99999 --step S05` is run
Then the step transitions to completed, AND
     work_item_evidences gains exactly 1 row with phase='post',
     step_id='S05', and content byte-identical to the file.

Given the same setup but step_type='implementation'
When `iw step-done X-99999 --step S05` is run
Then NO new rows are inserted into work_item_evidences.
```

### AC3: Idempotent ingestion

```
Given AC1 has just run and 2 rows exist for (project, X-99999, 'pre')
When the file ai-dev/active/X-99999/evidences/pre/screenshot.png is
     overwritten with new bytes (different SHA256, different size)
And `iw approve X-99999` is re-run via a manual idempotent path
     (or the underlying ingest_phase_from_disk is called again)
Then the row count for (project, X-99999, 'pre') stays at 2,
     AND the row's content matches the NEW bytes (upsert overwrote).
```

### AC4: Hard-fail on oversize

```
Given a work item X-99999 with one file in evidences/pre/
      that is larger than IW_CORE_EVIDENCE_MAX_BYTES
When `iw approve X-99999` is run
Then the command exits non-zero with a clear error message naming
     the offending file and its size, AND
     the work item status remains 'draft' (transaction rolled back), AND
     no rows are inserted into work_item_evidences for this item.
```

### AC5: Post-archive visibility (regression guard for CR-00020 gap)

```
Given a work item X-99999 has been approved (pre ingested) and a
      browser_verification step has step-done'd (post ingested)
When `archive_work_item(db, project_id, 'X-99999', archive_dir,
      cleanup=True)` runs and deletes ai-dev/active/X-99999/
Then `_list_evidences(item, project, db, worktree_path=None)` still
     returns all pre and post EvidenceFile rows from the DB,
     AND `item_evidence_file(...)` serves byte-identical content for
     each filename via the DB lookup path.
```

### AC6: Backfill recovers I-00044

```
Given the production orch DB has 0 rows in work_item_evidences for
      (project_id='iw-ai-core', work_item_id='I-00044')
And ai-dev/archives/iw-ai-core/I-00044.tar.zst contains 3 pre + 8 post PNGs
When `python scripts/CR-00025_backfill_evidences.py` runs against the prod DB
Then work_item_evidences gains exactly 11 rows for I-00044
     (3 pre + 8 post), AND
     http://iw-dev-01:9900/project/iw-ai-core/item/I-00044/tab/evidences
     renders both phase galleries, AND
     a screenshot of the populated tab is saved as
     ai-dev/active/CR-00025/evidences/post/CR-00025_I-00044_post_backfill.png.
```

### AC7: Backfill is idempotent and skips populated items

```
Given AC6 has just run and I-00044 has 11 rows
When `python scripts/CR-00025_backfill_evidences.py` is re-run
Then the row count for I-00044 stays at 11
     AND the script logs "skipped: I-00044 (already has 11 rows)".
```

### AC8: Backfill script is deleted before merge

```
Given S12 has run successfully and the post-evidence screenshot is captured
When the agent calls `iw step-done` for S12
Then `scripts/CR-00025_backfill_evidences.py` no longer exists in the
     worktree, AND `git status` shows it as deleted (or never tracked
     after deletion in the same step's commit).
```

## Rollback Plan

- **Database**: `TRUNCATE work_item_evidences;` (the bytes are still
  recoverable from `ai-dev/archives/<project>/<id>.tar.zst`). No reverse
  migration needed because no DDL changed.
- **Code**: `git revert <squash-merge-commit>` reverts the
  CLI hooks, the `orch/evidences.py` module, the config knob, the doc
  updates, and the tests. The dashboard reads remain functional (already
  shipped in CR-00020).
- **Data**: No data loss. The original on-disk archives are not modified
  by ingestion or backfill — both are read-only against `.tar.zst`.

## Dependencies

- **Depends on**: CR-00020 (table, enum, model, dashboard reads, migration)
- **Blocks**: None

## TDD Approach

- **Unit tests** (`tests/unit/test_evidences_ingest.py`):
  - Happy path: 2 PNG + 1 YAML in a temp dir, assert returned count, row
    count, content_type per file, byte-identical content.
  - Oversize hard-fail: file > `max_bytes` raises `EvidenceTooLargeError`
    (or equivalent), no rows inserted, transaction not committed by helper
    (helper does not commit; caller controls commit).
  - Idempotent upsert: run twice, second run with overwritten file content,
    assert single row with new content.
  - Missing dir: tolerated, returns 0.
  - Empty dir: tolerated, returns 0.
  - Non-file entries (subdir, symlink): ignored.
  - Unknown extension: defaults to `application/octet-stream`.
- **Integration tests** (`tests/integration/test_evidences_lifecycle.py`):
  - `iw approve` ingests pre evidences end-to-end (real testcontainer,
    real DB, real CLI invocation via `CliRunner`).
  - `iw step-done` for `browser_verification` ingests post evidences;
    `iw step-done` for `implementation` does not.
  - Hard-fail on oversize during `iw approve` rolls back the status flip.
  - **Post-archive regression**: full lifecycle (approve → step-done →
    `archive_work_item(cleanup=True)`) → `_list_evidences` still returns
    all rows. This is the test that should have caught the original gap.
- **Updated tests**: None expected. The existing
  `tests/integration/test_work_item_evidence.py` covers the model in
  isolation and remains valid.

## Notes

- **Why `phase` enum check, not `step.opencode_agent.startswith('qv-browser')`**:
  the canonical signal is `WorkflowStep.step_type == StepType.browser_verification`,
  which `validate_browser_evidence_present` already uses.
- **Transaction scope**: `ingest_phase_from_disk` writes via the caller's
  session and does **not** call `session.commit()`. The CLI command's
  `with get_session() as session:` block owns the commit boundary, so a
  failed ingest rolls back the status flip — required for AC4.
- **Why hard-fail on oversize (option `a`) vs skip-with-warning**: the user
  explicitly chose hard-fail. Rationale: silently dropping evidence is the
  exact failure mode CR-00020 was meant to prevent; an operator can shrink
  the file and re-run.
- **Backfill script lives only in S12**: the user does not want lingering
  one-shot code in `scripts/`. The script is created, run, verified, and
  deleted within the same step's working tree. The squash-merge commit
  contains no trace of it.
- **The backfill writes to the production orch DB from inside an agent
  worktree.** This is unusual but explicitly authorised by the user.
  Mitigations: idempotent skip-if-rows-exist per `(project, item, phase)`,
  hard size limit, before/after row-count logging in the step report,
  read-only `tarfile.open` against `.tar.zst` archives.
- **qv-browser stack vs production dashboard**: S11 verifies the new
  ingestion path against the isolated worktree's e2e dashboard. S12
  verifies the backfill outcome by pointing playwright at the production
  dashboard at `http://iw-dev-01:9900` (which the agent worktree can
  reach). This split is necessary because the worktree's e2e DB does not
  contain I-00044.
- **Why no migration**: `work_item_evidences` already exists on the live
  DB. `alembic current` confirms `d6b67d4ecb9f` is applied.
