# CR-00020_S05_API_prompt

**Work Item**: CR-00020 -- Store work item evidences as BLOBs in the database
**Step**: S05
**Agent**: api-impl

---

## ⛔ Docker is off-limits
See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies
See `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00020/CR-00020_CR_Design.md` — Design (ACs, especially AC5 and AC7)
- `ai-dev/active/CR-00020/reports/CR-00020_S03_Backend_report.md` — confirms schema + ingest are live
- `dashboard/routers/items.py` — existing `_list_evidences` at line ~696 and `item_evidence_file` at line ~1229 (modify these)
- `dashboard/routers/items.py` — `EvidenceFile` dataclass at line ~218 (shape preserved)
- `dashboard/CLAUDE.md` — router conventions (thin routers, htmx patterns)

## Output Files

- `dashboard/routers/items.py` — MODIFIED: `_list_evidences` and `item_evidence_file` are DB-first with FS fallback for in-progress post
- `ai-dev/active/CR-00020/reports/CR-00020_S05_API_report.md` — step report

## Context

Switch the dashboard's Evidences tab to read from `work_item_evidences` instead of scanning the filesystem. Keep the exact URL shape and the exact `EvidenceFile` return type so the Jinja template (`fragments/item_evidences.html`) continues to work unchanged.

The FS fallback is narrow by design: **post-evidences only, only while a worktree is active for the item, only if DB has no post rows yet** (i.e., step-done hasn't run). Pre-evidences always come from DB once approved. No merged/archived item ever hits the FS.

Read the design's "Desired Behavior" and AC5/AC7 carefully. Both URLs stay identical:
- `GET /project/{pid}/item/{id}/tab/evidences` — HTML fragment
- `GET /project/{pid}/item/{id}/evidence/{phase}/{filename}` — image bytes

## Requirements

### 1. `_list_evidences()` — DB-first

Replace the current FS scan with:

1. Query `work_item_evidences` for the item:
   ```python
   rows = db.scalars(
       select(WorkItemEvidence)
       .where(
           WorkItemEvidence.project_id == project.id,
           WorkItemEvidence.work_item_id == item.id,
       )
       .order_by(WorkItemEvidence.phase, WorkItemEvidence.filename)
   ).all()
   ```
2. Convert to `list[EvidenceFile]`. The existing `EvidenceFile` dataclass has fields `filename`, `phase` (str), `abs_path` (str), `size_bytes` (int). Since DB rows have no `abs_path`, set it to a sentinel like `f"db://{evidence.id}"` OR refactor to drop `abs_path` if the template doesn't use it. Check `dashboard/templates/fragments/item_evidences.html` — if `abs_path` is unused there, simply omit it or set to empty string.
3. **FS fallback for in-progress post-evidences**: if `bi and bi.worktree_info and bi.worktree_info.get("path")` AND no rows in the DB have `phase='post'`, scan `<worktree>/ai-dev/active/<id>/evidences/post/` for files and append them to the result with `phase='post'` (and no corresponding DB id). Deduplicate by filename.
4. Keep the function signature compatible with the existing call in `item_tab_evidences`.

### 2. `item_evidence_file()` — DB-first with narrow FS fallback

Replace the FS read with:

```python
row = db.scalar(
    select(WorkItemEvidence)
    .where(
        WorkItemEvidence.project_id == project.id,
        WorkItemEvidence.work_item_id == item.id,
        WorkItemEvidence.phase == EvidencePhase(phase),  # 'pre' | 'post'
        WorkItemEvidence.filename == filename,
    )
)
if row is not None:
    return Response(content=row.content, media_type=row.content_type)

# FS fallback — ONLY for post-phase on an in-progress item with a live worktree.
if phase == "post":
    bi = _get_batch_item(project.id, item.id, db)
    worktree_path = (bi.worktree_info or {}).get("path") if bi else None
    if worktree_path:
        evidence_path = Path(worktree_path) / "ai-dev" / "active" / item.id / "evidences" / "post" / filename
        # Keep existing path-traversal guard:
        try:
            evidence_path.resolve().relative_to(
                (Path(worktree_path) / "ai-dev" / "active" / item.id / "evidences").resolve()
            )
        except ValueError as err:
            raise HTTPException(status_code=403, detail="Access denied") from err
        if evidence_path.is_file():
            content_type, _ = mimetypes.guess_type(filename)
            return Response(content=evidence_path.read_bytes(), media_type=content_type or "application/octet-stream")

raise HTTPException(status_code=404, detail="Evidence file not found")
```

Do not allow FS fallback for `phase == "pre"` — once approved, DB is canonical for pre. If a pre row is missing, it's a 404, not an FS peek. This matches AC5's "after archive still works" guarantee.

### 3. Imports

Add at the top of `dashboard/routers/items.py`:
- `from orch.db.models import EvidencePhase, WorkItemEvidence`

Ensure `Response`, `Path`, `mimetypes`, `HTTPException`, `select` are already imported or add them.

### 4. `EvidenceFile` dataclass

If the template uses `abs_path`, keep the field and populate it with a synthetic value for DB rows (e.g., empty string). If it does not, drop the field — fewer fields = less dead code. Check the template before deciding.

### 5. No changes to other routes

- `item_tab_evidences` itself just calls `_list_evidences` — no changes needed.
- Keep `mimetypes` import — still used for FS-fallback MIME detection.

## Project Conventions

- `dashboard/routers/items.py` follows the thin-router pattern — keep business logic small, delegate DB queries to `db.scalars`/`db.scalar`.
- htmx fragment template (`fragments/item_evidences.html`) MUST continue to render; the data shape must match.
- `get_db()` from `dashboard.dependencies` yields the session — use it as the current DI pattern does.
- Fragment templates do NOT extend `base.html`.

## TDD Requirement

S07 owns the test suite. For S05, confirm by manual smoke test that the Evidences tab still loads for an item that has no DB rows (should be empty, not crash) and for an item that has FS evidences (should render via fallback for in-progress).

Do NOT modify the Jinja template — S07 will verify the template still matches.

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit` and `make test-integration` — both must pass.
2. `make lint`, `make format --check`, `make typecheck` must pass.
3. Smoke test the dashboard locally: navigate to an existing item's Evidences tab and confirm it loads without error (it may be empty — that's fine, data is from prior items).

## Subagent Result Contract

```json
{
  "step": "S05",
  "agent": "api-impl",
  "work_item": "CR-00020",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "dashboard/routers/items.py"
  ],
  "tests_passed": true,
  "test_summary": "",
  "blockers": [],
  "notes": ""
}
```
