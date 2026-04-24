# CR-00020_S06_CodeReview_prompt

**Work Item**: CR-00020 -- Store work item evidences as BLOBs in the database
**Step Being Reviewed**: S05 (api-impl)
**Review Step**: S06

---

## ⛔ Docker is off-limits
See `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies
See `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/CR-00020/CR-00020_CR_Design.md` — Design (ACs 5 + 7 are primary focus)
- `ai-dev/active/CR-00020/reports/CR-00020_S05_API_report.md`
- `dashboard/routers/items.py` — after S05 edits
- `dashboard/templates/fragments/item_evidences.html` — verify shape compatibility

## Output Files

- `ai-dev/active/CR-00020/reports/CR-00020_S06_CodeReview_report.md`

## Review Checklist

### 1. DB-first semantics (AC5)

- `_list_evidences` queries `work_item_evidences` first. For an item whose FS dir was deleted, the query still returns rows.
- `item_evidence_file` returns DB bytes when the row exists. No FS read is attempted when DB has the row.

### 2. FS fallback scope (AC7)

- Fallback applies to post-phase only, gated on an active worktree (`bi.worktree_info["path"]`), AND only when DB has no post rows (for `_list_evidences`) or the specific file is missing (for `item_evidence_file`).
- Pre-phase has NO fallback — once approved, DB is canonical. Flag as HIGH if pre-FS-fallback remains.

### 3. Path traversal guard

- The existing guard in `item_evidence_file` is preserved on the FS fallback branch.
- Resolves symlinks via `.resolve()` and verifies the resolved path is under `evidences/`.

### 4. Response correctness

- `Response(content=row.content, media_type=row.content_type)` — not JSON, not stringified. Content-Type is taken from the DB row, NOT re-guessed.
- FS fallback does re-guess via `mimetypes.guess_type` (acceptable — no DB row to source from).

### 5. Template contract

- Open `dashboard/templates/fragments/item_evidences.html`. Verify every field referenced by the template is still populated by `_list_evidences` return values.
- If the template uses `evidence.abs_path`, confirm the new code populates it (even with a sentinel / empty string) or the template gets an update in S05. If neither, flag MEDIUM_FIXABLE.

### 6. Deduplication in FS fallback

- If both DB and FS have a post-phase filename, the function returns only one entry. The code should dedupe by filename, preferring the DB row.

### 7. Error handling

- 404 when neither DB nor FS has the evidence (existing behavior preserved).
- 403 on path-traversal attempt (existing behavior preserved on FS fallback).

### 8. No dead code / imports

- `mimetypes` is still imported (used in FS fallback MIME detection).
- Path / Response / HTTPException imports are present; unused imports from the prior FS-only code are removed.

### 9. Test verification

- `make test-unit`, `make test-integration`, `make lint`, `make format`, `make typecheck` all pass.
- Existing `dashboard/` tests that touched `_list_evidences` still compile (even if the mock shape needs updating — S07 handles the full rewrite).

## Severity Items to flag

- CRITICAL: pre-phase FS fallback present → AC5 still breaks after archive
- CRITICAL: content-type inferred from filename when a DB row exists (wrong for upload with non-obvious extension)
- HIGH: FS fallback triggered for merged items (no worktree check)
- HIGH: path-traversal guard removed from FS branch
- MEDIUM_FIXABLE: template-field mismatch that causes a Jinja `UndefinedError`

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview",
  "work_item": "CR-00020",
  "step_reviewed": "S05",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
