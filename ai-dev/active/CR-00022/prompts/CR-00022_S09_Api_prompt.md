# CR-00022_S09_Api_prompt

**Work Item**: CR-00022
**Step**: S09
**Agent**: api-impl (Phase D/E — endpoints + SSE row updates + accepted-yaml service)

---

## ⛔ Docker / Migrations off-limits

Standard rules.

## Input Files

- Design + reports from S03, S05, S07
- `dashboard/routers/oss.py` (post-S03)
- `dashboard/services/oss_service.py` (post-S07)
- `orch/oss/fix_recipes/__init__.py` (registry from S07)

## Output Files

- Modified: `dashboard/routers/oss.py` — new endpoints
- New: `dashboard/services/oss_accepted.py` — `.iw/oss-accepted.yaml` reader/writer
- Modified: `dashboard/services/oss_service.py` — SSE row-update event emission
- `ai-dev/active/CR-00022/reports/CR-00022_S09_Api_report.md`

## Context

This step adds the HTTP endpoints the new dashboard table and modal will call (S11/S13 build the UI), and the service for reading/writing `.iw/oss-accepted.yaml`. It also extends the SSE stream to emit per-check row-update events instead of relying on full-page reloads.

## Requirements

### 1. New endpoints in `dashboard/routers/oss.py`

```python
@router.post("/oss/fix/{check_id}", response_class=Response)
def oss_fix(
    project_id: str,
    check_id: str,
    payload: FixRequestBody,            # body: {"apply": bool}
    db: Session = Depends(get_db),
) -> Any:
    """Preview or apply a single fix recipe. Returns JSON with file list / diff / new content."""
```

```python
@router.post("/oss/recheck/{check_id}", response_class=Response)
def oss_recheck(
    project_id: str,
    check_id: str,
    db: Session = Depends(get_db),
) -> Any:
    """Re-run one check against the working tree. Updates the OssFinding row;
    triggers a row-update SSE event."""
```

```python
@router.post("/oss/accept/{check_id}", response_class=Response)
def oss_accept(
    project_id: str,
    check_id: str,
    payload: AcceptRequestBody,         # body: {"finding_hash": str, "reason": str}
    db: Session = Depends(get_db),
) -> Any:
    """Append an accepted-risk entry to .iw/oss-accepted.yaml in the project's working tree."""
```

```python
@router.post("/oss/apply-all-safe/preview", response_class=Response)
def oss_apply_all_safe_preview(project_id: str, db: Session = Depends(get_db)) -> Any:
    """Return list of (check_id, target_files, diff_or_content) for every
    auto_apply_safe=True failing finding, so the UI can render the deselectable preview."""
```

```python
@router.post("/oss/apply-all-safe", response_class=Response)
def oss_apply_all_safe(
    project_id: str,
    payload: ApplyAllSafeBody,           # body: {"check_ids": list[str]}
    db: Session = Depends(get_db),
) -> Any:
    """Apply selected recipes sequentially. Subprocess each via run_fixes()."""
```

Use Pydantic v2 request body classes (`FixRequestBody`, `AcceptRequestBody`, `ApplyAllSafeBody`) defined in `dashboard/routers/oss_models.py` (new file).

### 2. `dashboard/services/oss_accepted.py`

```python
from __future__ import annotations
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated
from pydantic import BaseModel, Field
import yaml


class AcceptedEntry(BaseModel):
    check_id: Annotated[str, Field(min_length=1)]
    finding_hash: Annotated[str, Field(min_length=1)]
    reason: Annotated[str, Field(min_length=1)]
    accepted_at: str
    accepted_by: str


class AcceptedFile(BaseModel):
    accepted: list[AcceptedEntry] = []


def accepted_path(repo_root: Path) -> Path:
    return repo_root / ".iw" / "oss-accepted.yaml"


def compute_finding_hash(check_id: str, summary: str, evidence: dict | None) -> str:
    """Stable SHA-256 over (check_id, summary, sorted-evidence-JSON). 8 hex chars."""
    h = hashlib.sha256()
    h.update(check_id.encode())
    h.update(b"\x00")
    h.update(summary.encode())
    h.update(b"\x00")
    if evidence is not None:
        import json
        h.update(json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode())
    return h.hexdigest()[:16]


def load_accepted(repo_root: Path) -> AcceptedFile:
    path = accepted_path(repo_root)
    if not path.exists():
        return AcceptedFile(accepted=[])
    raw = yaml.safe_load(path.read_text()) or {}
    return AcceptedFile.model_validate(raw)


def append_accepted(repo_root: Path, entry: AcceptedEntry) -> None:
    """Idempotent: if (check_id, finding_hash) is already accepted, no-op."""
    path = accepted_path(repo_root)
    file = load_accepted(repo_root)
    if any(e.check_id == entry.check_id and e.finding_hash == entry.finding_hash
           for e in file.accepted):
        return
    file.accepted.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(file.model_dump(), sort_keys=False, default_flow_style=False))


def is_accepted(file: AcceptedFile, check_id: str, finding_hash: str) -> AcceptedEntry | None:
    for e in file.accepted:
        if e.check_id == check_id and e.finding_hash == finding_hash:
            return e
    return None
```

`accepted_by` for now: `os.getenv("USER", "unknown")` or pull from auth context if present (see `dashboard/dependencies.py`).

`accepted_at`: `datetime.now(UTC).isoformat()`.

### 3. SSE row-update events

Currently `oss_stream` (in `dashboard/routers/oss.py`) and `job_event_stream` (in `dashboard/services/oss_service.py`) emit a `progress` event per stdout line and a `complete` event at end. Add a new event type `row-update` emitted when the scan persists a finding.

The cleanest path:
1. After each `Finding` is persisted by `orch/oss/persistence.py`, write a row to a new lightweight pubsub channel (Postgres `LISTEN/NOTIFY`, OR a simple in-memory broadcaster keyed by `scan_id`).
2. `job_event_stream` subscribes to the channel and emits `event: row-update\ndata: {<finding-json>}\n\n` for each row.

**Simpler alternative** acceptable for v1: poll the `oss_finding` table in `job_event_stream` while `scan_status in ('pending','running')`, diff against last seen IDs, and emit `row-update` events for new rows. Less elegant but no infrastructure changes.

Frontend (S11) consumes via `EventSource.addEventListener('row-update', …)` and patches `<tr id="row-OSS-CH-01">` in place.

Document the event-data shape in the report:
```json
{"check_id": "OSS-CH-01", "domain": "community", "severity": "MUST", "status": "fail",
 "summary": "README missing", "auto_apply_safe": true, "auto_fix_available": true,
 "finding_hash": "a1b2c3d4..."}
```

### 4. Endpoint behaviour details

**`/oss/fix/{check_id}`**:
- Validates `check_id` exists in registry (`orch.oss.fix_recipes.get_recipe`); 404 if not.
- For `apply=False`: returns the preview JSON synchronously (no job row needed).
- For `apply=True`: enqueues a `ProjectOssJob(kind=fix)` row, spawns the subprocess via `_run_fix`, returns `{"job_id": …, "stream_url": …}`.

**`/oss/recheck/{check_id}`**:
- Subprocess: `python3 .claude/skills/iw-oss-publish/scripts/scan.py --check OSS-CH-01` (S03 should not have removed `--check` — verify; if not yet supported, this CR adds it as part of S15 or here, name it `--only-check`).
- For v1 if single-check scan is too invasive, fall back to: re-run full scan filtered to one domain, OR simply mark this endpoint as "TODO Phase F2" and route the UI button to a full re-scan with a toast saying "Re-running all checks". Recommend: implement filter-by-check ID in the scanner since the scanner already iterates per-check.

**`/oss/accept/{check_id}`**:
- Body validates `finding_hash` matches current finding (defensive; not strictly required for write, but prevents stale UI from accepting the wrong instance).
- Calls `append_accepted(project.repo_root, AcceptedEntry(...))`.
- Returns 204 + `HX-Trigger` toast.

**`/oss/apply-all-safe/preview`**:
- Iterates current scan's findings; for every `auto_apply_safe=True` + `status=fail`, calls `recipe.preview(repo_root)` and collects results.
- Returns `[{check_id, target_files, full_contents, diffs, notes}, ...]`.

**`/oss/apply-all-safe`**:
- Body lists user-selected `check_ids` (subset of preview).
- Validates every ID in the list has `auto_apply_safe=True` (defensive — UI MUST not allow others, but server enforces).
- Spawns subprocess sequence via `run_fixes(project, job_id, session_factory, check_ids, apply=True)`.

### 5. Removed endpoints (sanity)

Confirm these are no longer registered (S03 deleted them):
- `POST /oss/prepare`
- `POST /oss/publish`

Run:
```bash
uv run python -c "
from dashboard.app import create_app
app = create_app()
for r in app.routes:
    if 'oss' in str(getattr(r, 'path', '')):
        print(r.path, r.methods if hasattr(r, 'methods') else '-')
"
```
Confirm no `/oss/prepare` or `/oss/publish` paths.

### 6. Verification

```bash
make lint
# Manual smoke (against the running dashboard at port 9900):
curl -s -X POST http://localhost:9900/project/iw-ai-core/oss/fix/OSS-CH-01 \
  -H 'Content-Type: application/json' -d '{"apply": false}' | jq .
curl -s -X POST http://localhost:9900/project/iw-ai-core/oss/accept/OSS-CH-99 \
  -H 'Content-Type: application/json' \
  -d '{"finding_hash": "deadbeef", "reason": "test"}' | head
# .iw/oss-accepted.yaml should contain the entry; second call no-ops.
```

## Project Conventions

- Routers thin — delegate to services (`dashboard/CLAUDE.md`).
- Pydantic v2 request bodies, never raw `dict` / `Any`.
- htmx-friendly responses where the UI uses htmx (HX-Trigger toasts), JSON where it doesn't.
- No CSRF tokens needed — the dashboard runs same-origin, but document the assumption.

## TDD Requirement

Route tests live in `tests/integration/test_oss_dashboard_routes.py` (S17). For S09 itself, manual curl smokes are sufficient.

## Output / Report

Report contains:
- New endpoint list with route + body schema
- New service module with public API summary
- SSE event-data shape decision (LISTEN/NOTIFY vs polling)
- Manual smoke results
- Removed-endpoint verification

End with `iw step-done` / `iw step-fail`.
