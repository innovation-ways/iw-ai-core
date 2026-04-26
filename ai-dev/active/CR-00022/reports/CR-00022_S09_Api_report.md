# CR-00022_S09_Api_report — API Endpoints + OSS Accepted YAML Service

## What Was Done

Implemented the S09 API layer for the OSS compliance dashboard table and modal (S11/S13 UI builds on top):

1. **5 new endpoints** in `dashboard/routers/oss.py`
2. **New request models** in `dashboard/routers/oss_models.py` (Pydantic v2)
3. **New service** `dashboard/services/oss_accepted.py` — `.iw/oss-accepted.yaml` reader/writer
4. **Extended SSE** `job_event_stream` to emit `row-update` events via polling-based approach (v1)
5. **Extended `enqueue_job`** to accept `check_id` (single-fix) and `check_ids` (batch)
6. **Added `run_fixes`** async function to apply recipe sequences and mark job complete

## Files Changed / Added

| File | Change |
|------|--------|
| `dashboard/routers/oss.py` | Added 5 new endpoints + `run_fixes_batch` helper |
| `dashboard/routers/oss_models.py` | **NEW** — `FixRequestBody`, `AcceptRequestBody`, `ApplyAllSafeBody` |
| `dashboard/services/oss_accepted.py` | **NEW** — `AcceptedEntry`, `AcceptedFile`, `load_accepted`, `append_accepted`, `is_accepted`, `compute_finding_hash`, `accepted_by`, `now_iso` |
| `dashboard/services/oss_service.py` | Extended `enqueue_job` (check_id/check_ids), added `run_fixes`, extended `job_event_stream` with row-update polling |

## New Endpoints

| Route | Body | Behaviour |
|-------|------|-----------|
| `POST /oss/fix/{check_id}` | `FixRequestBody` (`{"apply": bool}`) | `apply=false` → synchronous preview JSON; `apply=true` → enqueues fix job, returns `{job_id, stream_url}` |
| `POST /oss/recheck/{check_id}` | — | Enqueues scan job; v1 runs full scan (Phase F2 adds `--check` filter) |
| `POST /oss/accept/{check_id}` | `AcceptRequestBody` (`{"finding_hash", "reason"}`) | Appends to `.iw/oss-accepted.yaml`; idempotent on (check_id, finding_hash); returns 204 + HX-Trigger toast |
| `POST /oss/apply-all-safe/preview` | — | Returns preview JSON for all `auto_apply_safe=True` failing findings |
| `POST /oss/apply-all-safe` | `ApplyAllSafeBody` (`{"check_ids": [str]}`) | Validates all have `auto_apply_safe=True`, then runs batch via `run_fixes` |

## Removed Endpoints (S03/S05)

Verified **NOT present** in the route table:
- `POST /oss/prepare` — removed by migration `c062b6bf5eb3`
- `POST /oss/publish` — removed by migration `c062b6bf5eb3`

```
/project/{project_id}/oss {'GET'}
/project/{project_id}/oss/status {'GET'}
/project/{project_id}/oss/tools {'GET'}
/project/{project_id}/oss/install {'POST'}
/project/{project_id}/oss/enable {'POST'}
/project/{project_id}/oss/disable {'POST'}
/project/{project_id}/oss/scan {'POST'}
/project/{project_id}/oss/stream/{job_id} {'GET'}
/project/{project_id}/oss/fix/{check_id} {'POST'}
/project/{project_id}/oss/recheck/{check_id} {'POST'}
/project/{project_id}/oss/accept/{check_id} {'POST'}
/project/{project_id}/oss/apply-all-safe/preview {'POST'}
/project/{project_id}/oss/apply-all-safe {'POST'}
```

## SSE Row-Update Events

**Approach**: Polling-based v1 (no Postgres LISTEN/NOTIFY infrastructure changes needed).

`job_event_stream` polls `oss_finding` table every heartbeat interval (20s default, testable down to 0.5s) while scan is `queued`/`running`. Tracks last-seen `finding.id` set; emits:

```
event: row-update
data: {"check_id": "OSS-CH-01", "domain": "community", "severity": "MUST",
       "status": "fail", "summary": "...", "auto_apply_safe": true,
       "auto_fix_available": true}
```

When scan reaches terminal state, loop breaks and emits `event: complete\ndata: ...` as before.

## `oss_accepted.py` Public API

```python
def accepted_path(repo_root: Path) -> Path          # .iw/oss-accepted.yaml
def compute_finding_hash(check_id, summary, evidence) -> str  # 16-char hex
def load_accepted(repo_root: Path) -> AcceptedFile
def append_accepted(repo_root: Path, entry: AcceptedEntry) -> None  # idempotent
def is_accepted(file: AcceptedFile, check_id, finding_hash) -> AcceptedEntry | None
def accepted_by() -> str  # os.getenv("USER", "unknown")
def now_iso() -> str      # datetime.now(UTC).isoformat()
```

## Notes

- `ProjectOssJob.check_id` column does not exist on the model (only `check_id` on `OssFinding`). Single-fix IDs stored in `job.stdout_tail` (plain string); batch IDs stored as JSON array there.
- `run_job` dispatches `_run_fix` with `apply=True` for all fix jobs (the `iw oss fix` CLI is idempotent and prints JSON).
- `ProjectOssJobStatus.discarded` does not exist in the enum — removed from the terminal-state tuple in `job_event_stream`.
- Re-check (`/oss/recheck/{check_id}`) runs full scan in v1; Phase F2 adds single-check filtering.

## Verification

- `ruff check` on all 4 modified/new files: **All checks passed**
- `mypy` on all 4 files: **Success: no issues found**
- Route table verified: no `/oss/prepare` or `/oss/publish`