# CR-00025 S12 — Backend: One-shot backfill of archived evidences

**Work Item**: CR-00025 — Implement missing evidence-ingestion pipeline (CR-00020 follow-up) and backfill archived items
**Step**: S12
**Agent**: backend-impl
**Completion status**: complete

---

## What was done

`scripts/CR-00025_backfill_evidences.py` was written as a standalone idempotent script that reads zstd-compressed `.tar.zst` archives from each project's archive directory, extracts evidence files, rearranges them into the layout `ingest_phase_from_disk` expects, and ingests `pre` and `post` phases for each archived work item. The script was run once against the live orch DB (port 5433), then deleted.

**Key bug fixed during execution**: `archive_path.stem` for `I-00044.tar.zst` returns `I-00044.tar` (not `I-00044`), so `session.get(WorkItem, (project_id, work_item_id))` was looking up the wrong ID. The fix strips the `.tar.zst` suffix explicitly via `removesuffix(".tar.zst")`.

---

## Command run

```bash
IW_CORE_OPERATOR_APPLY=true uv run python scripts/CR-00025_backfill_evidences.py
```

---

## Before / after row counts

```sql
SELECT count(*) FROM work_item_evidences;
```

| | Row count |
|---|---|
| Before | 5 |
| After | 160 |
| Net new | 155 |

---

## Per-project, per-item summary

Only `iw-ai-core` had archives with evidence files. Other projects (`innoforge`, `cv`, `Podforger`) had no matching archive directories.

### iw-ai-core — inserted rows

| work_item_id | pre | post | status |
|---|---|---|---|
| CR-00008 | 1 | 0 | inserted |
| CR-00009 | 0 | 2 | inserted |
| CR-00010 | 0 | 7 | inserted |
| CR-00011 | 1 | 0 | inserted |
| CR-00012 | 4 | 4 | inserted |
| CR-00013 | 3 | 7 | inserted |
| CR-00018 | 2 | 1 | inserted |
| CR-00019 | 3 | 0 | inserted |
| CR-00020 | 1 | 2 | inserted |
| CR-00022 | 3 | 10 | inserted |
| F-00021 | 0 | 1 | inserted |
| F-00041 | 0 | 1 | inserted |
| F-00055 | 0 | 2 | inserted |
| F-00056 | 1 | 6 | inserted |
| F-00058 | 1 | 6 | inserted |
| F-00059 | 0 | 4 | inserted |
| F-00060 | 0 | 16 | inserted |
| I-00031 | 2 | 2 | inserted |
| I-00033 | 1 | 7 | inserted |
| I-00034 | 0 | 2 | inserted |
| I-00036 | 2 | 0 | inserted |
| I-00037 | 2 | 3 | inserted |
| I-00038 | 0 | 5 | inserted |
| I-00039 | 2 | 5 | inserted |
| I-00040 | 0 | 5 | inserted |
| **I-00044** | **3** | **8** | **inserted** |
| I-00045 | 8 | 2 | inserted |
| I-00046 | 4 | 3 | inserted |

### Skipped (no evidence files in archive)

CR-00002, CR-00003, CR-00006, CR-00014, CR-00015, CR-00016, CR-00017, CR-00021, CR001, F-00001, F-00010, F-00011, F-00012, F-00013, F-00014, F-00020, F-00022, F-00023, F-00037–F-00040, F-00045–F-00049, F-00057, F-00061, F-00062, I-00032, I-00035, I-00041, I-00043, I-00048

---

## I-00044 specifically

Archive: `/home/sergiog/dev/iw-doc-plan/main/iw-ai-core/ai-dev/archives/iw-ai-core/I-00044.tar.zst`

Archive contents: 3 pre PNGs + 8 post PNGs

After backfill: **11 rows inserted (3 pre + 8 post)**

Post-backfill evidence tab screenshot:
`ai-dev/active/CR-00025/evidences/post/CR-00025_I-00044_post_backfill.png`

The screenshot shows the `pre` and `post` galleries populated with the expected screenshots, confirming the dashboard's Evidences tab now renders for this archived item.

---

## Idempotency check (re-run confirmation)

Second run output:

```
INFO: iw-ai-core      | F-00055      |   0 |   0 | skipped: already has 2 rows
INFO: iw-ai-core      | F-00056      |   0 |   0 | skipped: already has 7 rows
...
INFO: iw-ai-core      | I-00044      |   0 |   0 | skipped: already has 11 rows
...
INFO: Before total: 160
INFO: After total:  160
INFO: Net new rows: 0
```

All previously-processed items were skipped. Net new rows on re-run: **0**. Confirms AC7 (idempotency guarantee).

---

## Script deletion confirmation

```bash
$ ls scripts/CR-00025_backfill_evidences.py
ls: cannot access 'scripts/CR-00025_backfill_evidences.py': No such file or directory
```

Script was deleted. `git status` shows a clean working tree (no untracked or modified files from this step).

---

## Preflight checks

| Check | Result |
|---|---|
| `make format` | ruff auto-fixed (1 file) — `scripts/CR-00025_backfill_evidences.py` |
| `make typecheck` | ok — no issues in 192 source files |
| `make lint` | ruff errors in `tests/` only (pre-existing, unrelated to this step) |
| `orch/evidences.py`, `orch/db/session.py`, `orch/db/models.py` lint | all pass |

---

## Notes

`files_changed` is empty — the script was created and deleted within the step (AC8), so no net file change.

Backfill totals: **5 → 160** (net +155 rows). I-00044: **11 rows (3 pre + 8 post)**. Re-running is a no-op. Script deleted.

The 4 pre-existing lint errors in `tests/integration/conftest.py` are pre-existing (unrelated to this step — they existed before CR-00025 and are not touched by any S12 change).