# CR-00022_S10_CodeReview_prompt

**Work Item**: CR-00022
**Step Being Reviewed**: S09 (api-impl — endpoints + SSE + accepted yaml)
**Review Step**: S10
**Agent**: code-review-impl

---

## ⛔ Docker / Migrations off-limits

Standard rules.

## Input Files

- Design + S09 report
- `dashboard/routers/oss.py`, `dashboard/routers/oss_models.py`
- `dashboard/services/oss_accepted.py`, `dashboard/services/oss_service.py`

## Output Files

- `ai-dev/active/CR-00022/reports/CR-00022_S10_CodeReview_report.md`

## Review Checklist

### 1. Endpoint surface — HIGH

- New routes exist: `/oss/fix/{check_id}`, `/oss/recheck/{check_id}`, `/oss/accept/{check_id}`, `/oss/apply-all-safe/preview`, `/oss/apply-all-safe`?
- Removed: `/oss/prepare`, `/oss/publish` no longer in `app.routes`?
- Path params, body schemas, response types match the design?
- Error responses follow project pattern (FastAPI `HTTPException` with status + detail)?

### 2. Working-tree-only invariant — CRITICAL

For every new endpoint and service method:
- No git mutation calls.
- `accepted_path` returns `repo_root / ".iw" / "oss-accepted.yaml"` — writes go INSIDE the repo only.
- `_run_fix`'s subprocess `cwd=project.repo_root` (NOT `worktree_path`).
- No `tempfile`/`/tmp` paths.

Grep:
```bash
grep -rn "git \|worktree\|/tmp/oss\|prep-" dashboard/routers/oss.py dashboard/services/oss_accepted.py dashboard/services/oss_service.py
```

### 3. Pydantic models

- Request bodies are Pydantic v2 (`BaseModel` with `model_validate`)?
- All string fields constrained (`min_length=1`)?
- `AcceptedEntry` validates required fields?

### 4. Idempotency

- `append_accepted` correctly no-ops on duplicate `(check_id, finding_hash)`?
- Manual test: call accept twice, verify file content stable.

### 5. SSE row-update shape

- Event named `row-update`?
- JSON payload includes `check_id`, `domain`, `severity`, `status`, `summary`, `auto_apply_safe`, `auto_fix_available`, `finding_hash`?
- Stream still emits the existing `progress`, `status`, `complete` events for compatibility?
- LISTEN/NOTIFY vs polling decision documented + tradeoffs noted?

### 6. Defensive validation

- `/oss/apply-all-safe` server-validates that every `check_id` in the body has `auto_apply_safe=True` registered? (UI may be compromised; server is the source of truth.)
- Unknown `check_id` returns 404, not 500?
- Invalid `finding_hash` format (not 16 hex chars) returns 422?

### 7. Conventions

- Routers thin (no business logic in handlers)?
- Imports at module top?
- No silent fallbacks?

## Output Report

Findings list, severity, file:line, verdict. End with `iw step-done` / `iw step-fail`.
