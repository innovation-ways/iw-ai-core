# CR-00025 S12 — Backend: One-shot backfill of archived evidences (production orch DB)

**Work Item**: CR-00025 — Implement missing evidence-ingestion pipeline (CR-00020 follow-up) and backfill archived items
**Step**: S12
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Same constraints as S01. Read-only `docker ps` / `docker inspect` are
allowed. Never `up` / `down` / `restart` / `prune`.

## ⛔ Migrations: agents generate, daemon applies

This step writes **data** (not DDL) into an existing table. Do NOT run
any `alembic upgrade/downgrade/stamp`. The schema is already correct.

## ⚠️ This step writes to the PRODUCTION orchestration DB

You will be writing rows into the live orch DB on port 5433. This is
explicitly authorised by the user for this CR. The mitigations are
non-negotiable:

1. **Idempotent**: skip any `(project_id, work_item_id, phase)` triple
   that already has rows.
2. **Hard size limit**: `IW_CORE_EVIDENCE_MAX_BYTES` (default 5 MiB) —
   any oversize file aborts the script with a clear error; do NOT
   silently truncate or skip-with-warning.
3. **Read-only over archives**: open `.tar.zst` files in read mode only;
   never extract back into the project source tree.
4. **Before/after row counts**: log and include in the step report.
5. **No commit until success**: the script must wrap the entire backfill
   in a single transaction per archive (or per item) so a mid-run failure
   doesn't leave partial state. If unsure, use one transaction per item
   to balance failure isolation with rollback ability.

If at any point you suspect you are connecting to the wrong DB, STOP
and call `iw step-fail` with a clear reason.

## Input Files

- `uv run iw item-status CR-00025 --json`
- `ai-dev/active/CR-00025/CR-00025_CR_Design.md` — read AC6, AC7, AC8
- `orch/evidences.py` (created in S01) — `ingest_phase_from_disk` is your ingest primitive
- `orch/db/models.py` — `Project`, `WorkItem`, `WorkItemEvidence`, `EvidencePhase`
- `orch/config.py` — `IW_CORE_EVIDENCE_MAX_BYTES`, `get_db_url()` (note: also need the **orch** DB URL helper if separate; see `orch/db/session.py`)

## Output Files

- `scripts/CR-00025_backfill_evidences.py` — created here, **deleted before step-done**
- `ai-dev/active/CR-00025/evidences/post/CR-00025_I-00044_post_backfill.png` — screenshot of populated tab
- `ai-dev/active/CR-00025/reports/CR-00025_S12_Backend_Backfill_report.md` — step report

## Context

CR-00020 added the `work_item_evidences` table but never wrote to it.
S01 of this CR fixed the forward path (new approvals/step-dones now
ingest). This step recovers historical data: every archived work item
across every project has its evidences sitting unread in
`<project_archive_dir>/<project>/<id>.tar.zst`. This script ingests
those bytes into the production orch DB so the dashboard's Evidences
tab finally renders for archived items.

The user explicitly does not want this script to linger as
backwards-compat code. Run it once, verify, delete it, commit. The
squash-merge to main will not include the script.

## Requirements

### 1. Write `scripts/CR-00025_backfill_evidences.py`

A standalone Python script (executable via `uv run python
scripts/CR-00025_backfill_evidences.py`). Structure:

```python
"""One-shot backfill of work_item_evidences from on-disk .tar.zst archives.

Created for CR-00025. Runs against the live orchestration DB. Idempotent
per (project_id, work_item_id, phase): skips items that already have rows.

This script is intentionally one-shot. It is created in CR-00025 S12,
run once against production, and deleted before the step is marked done.
The squash-merge commit to main does NOT include this file.
"""
```

Behaviour:

1. Connect to the live orch DB via `orch.db.session.SessionLocal`. Do
   NOT add a separate connection helper; reuse the existing one.
2. Query all `Project` rows. For each project, derive
   `archive_dir = <project_root>/ai-dev/archives/<project_id>` if the
   project's archive convention matches that path; otherwise read from
   the project config / `Project.archive_dir` if such a field exists
   (check `orch/db/models.py` — note: there is no `archive_dir` column
   on `Project`; the convention is `<repo_root>/ai-dev/archives/<project_id>`).
   For the `iw-ai-core` project the path is
   `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/ai-dev/archives/iw-ai-core/`.
3. Glob `<archive_dir>/*.tar.zst`.
4. For each archive:
   a. Derive `work_item_id` from the filename stem (e.g. `I-00044.tar.zst`
      → `I-00044`).
   b. Look up the `WorkItem` row; if missing, log a warning and skip.
   c. Check existing row count for `(project_id, work_item_id)` across
      all phases. If non-zero, log `skipped: <id> (already has N rows)`
      and continue. **This is the idempotency guarantee for AC7.**
   d. Open the archive **read-only** with `tarfile.open(fileobj=...,
      mode="r|")` wrapping a `zstandard.ZstdDecompressor.stream_reader`.
      Extract only paths matching `<id>/evidences/{pre,post}/*` into a
      tmpdir (use `tempfile.TemporaryDirectory()` so cleanup is automatic).
   e. Re-arrange the tmpdir so it looks like
      `<tmpdir>/ai-dev/active/<id>/evidences/{pre,post}/*` — exactly
      the layout `ingest_phase_from_disk` expects.
   f. Open a session, call `ingest_phase_from_disk(...)` for `pre` and
      then for `post`, then `session.commit()`. If any call raises,
      rollback and log the failure but continue with the next archive.
5. After processing all archives, print a summary table:
   `<project_id> | <work_item_id> | pre_inserted | post_inserted | status`.
6. Print before/after totals for `work_item_evidences`.

The script must be safe to re-run (AC7).

### 2. Run the backfill

From inside the worktree:

```bash
uv run python scripts/CR-00025_backfill_evidences.py
```

Capture the script's stdout/stderr to the report.

Sanity-check: the I-00044 archive contains 3 pre + 8 post PNGs (verified
2026-04-28). After the run, the script's summary line for I-00044 must
show `3 pre, 8 post`. If it shows anything else, STOP and investigate
before proceeding.

### 3. Capture post-backfill evidence (AC6)

```bash
playwright-cli kill-all
playwright-cli open "http://iw-dev-01:9900/project/iw-ai-core/item/I-00044/tab/evidences"
playwright-cli screenshot
cp .playwright-cli/page-*.png ai-dev/active/CR-00025/evidences/post/CR-00025_I-00044_post_backfill.png
```

The screenshot must show populated `pre` and `post` galleries — NOT the
"No evidences captured for this item." empty state. Compare against the
pre-evidence at
`ai-dev/active/CR-00025/evidences/pre/CR-00025_I-00044_blank_evidences_tab.png`
(which is the "before" screenshot, captured at design time).

### 4. Re-run idempotency check (AC7)

Run the script a second time:

```bash
uv run python scripts/CR-00025_backfill_evidences.py
```

It must process zero items (every item already has rows). The summary
must list every previously-processed item with `status=skipped`. Capture
this output in the report as evidence for AC7.

### 5. Delete the script (AC8)

```bash
rm scripts/CR-00025_backfill_evidences.py
git status   # confirm scripts/CR-00025_backfill_evidences.py is shown as deleted
```

The deletion must happen in the same commit as any other changes from
this step (none expected). After `iw step-done`, `git status` in the
worktree must NOT show `scripts/CR-00025_backfill_evidences.py` as
present or untracked.

### 6. Report

`ai-dev/active/CR-00025/reports/CR-00025_S12_Backend_Backfill_report.md`
must contain:

- The exact command run.
- Before total: `SELECT count(*) FROM work_item_evidences;` (run via
  `uv run python -c ...` against the orch DB).
- After total: same query.
- Per-project, per-item summary (paste the script's stdout).
- Confirmation that I-00044 specifically gained 11 rows (3 pre + 8 post).
- Path to the post-backfill screenshot.
- Confirmation that re-running is a no-op.
- Confirmation that the script has been deleted (`ls
  scripts/CR-00025_backfill_evidences.py` returns "No such file").

## Pre-flight Quality Gates (NON-NEGOTIABLE)

After all step actions complete and before reporting `completion_status:
complete`:

1. `make format` — auto-fix.
2. `make typecheck` — must report zero errors involving files you
   touched. Note: since the script is deleted, it will not appear in
   typecheck output. Verify the `orch/evidences.py` and CLI files from
   S01 still typecheck cleanly (your changes here should not have
   touched them).
3. `make lint` — zero errors.

## Subagent Result Contract

```json
{
  "step": "S12",
  "agent": "backend-impl",
  "work_item": "CR-00025",
  "completion_status": "complete|partial|blocked",
  "files_changed": [],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "no new tests in this step (S03 covered the helper)",
  "blockers": [],
  "notes": "scripts/CR-00025_backfill_evidences.py created, run, and deleted within this step. Backfill totals: <before> -> <after>. I-00044: 11 rows (3 pre + 8 post). Re-run idempotent: yes."
}
```

`files_changed` should be empty (the script was created and deleted
within the step, so no net change). If somehow you needed to modify
something else (e.g. a one-line fix in the helper to support the
backfill case), list it here and explain in `notes`.
