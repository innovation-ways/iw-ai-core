# Step 10: Archive System

## Context

The CLI `iw archive` command (step 05) has a stub for Tier 2 compression. Now implement the full two-tier archive system.

Read these documents:
- `IW_AI_Core_Architecture.md` — section 7 (Two-Tier Content Storage)

## Task

### 1. Archiver (`orch/archive/archiver.py`)

Implement `archive_work_item(db, project_id, item_id, archive_dir, cleanup=True)`:

**Tier 1 — Store searchable content in DB:**
1. Read design doc from `design_doc_path` on disk → store in `work_items.design_doc_content`
2. Read each step's report from `report_file` path → store in `workflow_steps.report_content`
3. The FTS trigger auto-updates `design_doc_search` tsvector
4. Update `work_items.phase = 'done'`, `archived_at = now()`

**Tier 2 — Compress to archive:**
1. Locate the work item folder: `{project_repo}/ai-dev/design/active/{item_id}/`
2. Create tar archive, compress with zstandard (level 3)
3. Write to `{archive_dir}/{project_id}/{item_id}.tar.zst`
4. Record `archive_path`, `archive_size_bytes` in DB

**Cleanup:**
5. If `cleanup=True`: delete the source folder from the project repo
6. If `cleanup=False` (--no-cleanup flag): leave source files

**Idempotency:** If already archived (archived_at is set), skip Tier 2 but refresh Tier 1 content.

Also implement `archive_all_completed(db, project_id, archive_dir)`:
- Query all work items with status=completed and archived_at IS NULL
- Archive each one

### 2. Extractor (`orch/archive/extractor.py`)

Implement on-demand extraction for the dashboard "Full Artifacts" view:

#### `extract_archive(project_id, item_id, archive_dir, tmp_dir) -> Path`
1. Find archive: `{archive_dir}/{project_id}/{item_id}.tar.zst`
2. Extract to: `{tmp_dir}/iw-archive-view/{project_id}/{item_id}/`
3. If already extracted and not expired: reuse, reset TTL
4. Return the extraction path

#### `cleanup_expired(tmp_dir, ttl_seconds)`
- Scan `{tmp_dir}/iw-archive-view/`
- For each extracted folder: check mtime vs ttl
- Delete expired extractions
- Called by the daemon on each poll cycle (lightweight — just stat checks)

#### `list_artifacts(extraction_path) -> list[dict]`
- Walk the extracted directory
- Return list of {name, relative_path, size, type (file/dir)} for the file browser

### 3. Wire Into CLI

Update the `iw archive` command (from step 05) to call `archive_work_item()` for full Tier 1 + Tier 2 processing instead of the stub.

### 4. Tests (TDD)

**Unit tests** (`tests/unit/test_archive.py`):
- Test: Tier 1 stores design doc content in DB
- Test: Tier 1 stores report content for each step
- Test: Tier 2 creates .tar.zst file with correct contents
- Test: Tier 2 records archive_path and size in DB
- Test: cleanup deletes source folder
- Test: no-cleanup preserves source folder
- Test: idempotent — second archive call doesn't fail
- Test: extractor extracts to correct path
- Test: extractor reuses existing extraction within TTL
- Test: cleanup_expired removes old extractions, keeps fresh ones
- Test: list_artifacts returns correct file tree

Use `tmp_path` pytest fixture for all file operations (no real project repos).

**Integration tests** (`tests/integration/test_archive.py`):
- Test: full archive flow — create item with design doc in tmp, archive, verify DB content + .tar.zst
- Test: search finds archived item via FTS

## Acceptance Criteria

- [ ] `iw archive I001` stores design doc in DB and creates .tar.zst
- [ ] Dashboard can render archived design docs from DB (Tier 1)
- [ ] Extraction to tmp works within 2 seconds for typical items
- [ ] TTL cleanup removes old extractions
- [ ] `make test` passes, `make quality` passes
