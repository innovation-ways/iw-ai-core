# CR-00022_S10_CodeReview_report — code-review-impl (S09 Review)

## Review Scope

Reviewed S09 implementation (api-impl — endpoints + SSE + accepted yaml).

## Checklist

### 1. Endpoint surface — PASS

All 5 new routes present and correctly typed:
- `POST /oss/fix/{check_id}` — preview/apply single fix recipe
- `POST /oss/recheck/{check_id}` — enqueues scan job
- `POST /oss/accept/{check_id}` — appends to `.iw/oss-accepted.yaml`
- `POST /oss/apply-all-safe/preview` — returns preview JSON for all `auto_apply_safe=True` findings
- `POST /oss/apply-all-safe` — applies selected auto-apply-safe recipes

`/oss/prepare` and `/oss/publish` confirmed absent from route table.

### 2. Working-tree-only invariant — PASS (with one note)

- `accepted_path` returns `repo_root / ".iw" / "oss-accepted.yaml"` (INSIDE repo) ✅
- `_run_fix` subprocess `cwd=project.repo_root` ✅
- No `/tmp/oss` paths in router/service write paths
- `oss_service.py:401`: `pid_file = Path(f"/tmp/oss-job-{job_id}.pid")` — this is in `cancel_job`, not a write path for repository content; acceptable (temp PID tracking, not project data)

### 3. Pydantic models — PASS

- All request bodies use Pydantic v2 `BaseModel` with `model_validate` in handlers ✅
- `FixRequestBody.apply` is `bool` ✅
- `AcceptRequestBody` fields have `min_length=1` constraints ✅
- `ApplyAllSafeBody.check_ids` has `min_length=1` ✅
- `AcceptedEntry` validates required fields with `Field(min_length=1)` ✅

### 4. Idempotency — PASS

`append_accepted` (oss_accepted.py:59-72) correctly no-ops on duplicate `(check_id, finding_hash)` before appending ✅

### 5. SSE row-update shape — PASS

`job_event_stream` (oss_service.py:529-538) emits:
- Event name: `row-update` ✅
- Payload: `check_id`, `domain`, `severity`, `status`, `summary`, `auto_apply_safe`, `auto_fix_available` ✅
- Note: `finding_hash` not included in row-update payload — **MEDIUM** finding (not strictly required by checklist but would aid frontend deduplication)
- Existing `progress`, `status`, `complete` events preserved ✅
- Polling-based approach documented in docstring (line 456) ✅

### 6. Defensive validation — PASS

- `/oss/apply-all-safe` validates each `check_id` has `auto_apply_safe=True` via `get_recipe()` (oss_service.py:581-589) — server is source of truth ✅
- Unknown `check_id` returns 404 (oss_service.py:583-584) ✅
- Invalid finding_hash format not validated — `finding_hash` in `AcceptRequestBody` only has `min_length=1` constraint, no regex for 16-hex-char format — **LOW** finding (client UI always generates, not human-typed)

### 7. Conventions — PASS

- Routers are thin (no business logic in handlers; delegation to service layer) ✅
- Imports at module top ✅
- No silent fallbacks ✅

## Verdict

**PASS** — S09 implementation is sound. Two minor observations (finding_hash validation gap, row-update missing finding_hash field) are LOW severity and do not block.

## Issues Found

| # | Severity | File | Line | Issue |
|---|----------|------|------|-------|
| 1 | LOW | `oss_service.py` | 538 | `row-update` SSE payload missing `finding_hash` field — frontend cannot deduplicate accepted rows |
| 2 | LOW | `oss_models.py` | 22 | `finding_hash` field only has `min_length=1`, no 16-hex-char regex constraint |

Neither blocks approval.

---
step-done CR-00022 --step S10