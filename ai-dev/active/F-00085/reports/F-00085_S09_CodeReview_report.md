# F-00085 S09 — Code Review Report (S08 API)

## Scope Reviewed

- Design: `ai-dev/active/F-00085/F-00085_Feature_Design.md`
- Implementation report: `ai-dev/active/F-00085/reports/F-00085_S08_Api_report.md`
- Changed files reviewed:
  - `dashboard/routers/auto_merge_ui.py`
  - `dashboard/app.py`
  - `tests/dashboard/test_auto_merge_routes.py`

## What I validated

- 7 required endpoints are present and registered.
- Router wiring in `dashboard/app.py` is correct.
- Verdict validation (`pending|correct|wrong|partial`), target event type gate (`merge_auto_resolved`), notes size limit (8192 bytes), and JSON/fragment dual response path are implemented.
- Config validation rejects phase 2/3 with explicit reserved-for-future-CR message.
- Config validation re-checks `runtime_option_id` is enabled at API layer.
- Diff rendering uses `difflib.HtmlDiff` + `subprocess.run(["git", "show", ...], timeout=10, check=False, cwd=repo_root)` and avoids raising to FastAPI.
- Out-of-scope guard for S08 is respected (no templates/CSS/daemon code edited by this step).

## Findings

### 1) HIGH — No-op config writes still emit audit events

- **File:** `dashboard/routers/auto_merge_ui.py`
- **Lines:** 302-338
- **Issue:** `POST /project/{project_id}/auto-merge/config` always inserts `auto_merge_config_updated` event, even when request body matches existing config exactly (no effective change).
- **Why this matters:** Violates S09 checklist requirement “No event is emitted on a no-op POST”, and creates noisy/incorrect audit history.
- **Suggested fix:** Compute `new_payload = {"phase": body.phase, "runtime_option_id": body.runtime_option_id}` and short-circuit when `old_payload == new_payload`:
  - do not mutate `auto_merge_project_config`
  - do not emit `auto_merge_config_updated`
  - return normal success response shape (JSON or fragment) with unchanged state.

### 2) MEDIUM — Unknown project ID is not validated in config POST

- **File:** `dashboard/routers/auto_merge_ui.py`
- **Lines:** 273-338
- **Issue:** `POST /config` does not call `_get_project_or_404`. For unknown `project_id`, behavior depends on DB FK enforcement at commit (potential 500) instead of deterministic API 404.
- **Why this matters:** Diverges from router convention used by sibling endpoints and can surface DB-level errors to clients.
- **Suggested fix:** Add `_get_project_or_404(db, project_id)` at the top of `auto_merge_set_config` before any writes.

## Quality checks run

- `uv run pytest tests/dashboard/test_auto_merge_routes.py -q`
  - Functional result: **9 passed**
  - Repo gate result: command exits non-zero due to global coverage threshold (`fail-under=50`) in isolated run.
- `make lint` ✅ passed.

## Verdict

- **Result:** NEEDS_FIX
- **Mandatory fixes:** 1 (Finding #1)

```json
{
  "step": "S09",
  "agent": "code-review-impl",
  "work_item": "F-00085",
  "reviewed_agent": "api-impl",
  "verdict": "NEEDS_FIX",
  "mandatory_fix_count": 1,
  "findings": [
    {
      "severity": "HIGH",
      "file": "dashboard/routers/auto_merge_ui.py",
      "lines": "302-338",
      "description": "POST /config emits auto_merge_config_updated on no-op writes.",
      "suggested_fix": "Short-circuit when old/new payloads are equal; skip row mutation and skip event emission."
    },
    {
      "severity": "MEDIUM",
      "file": "dashboard/routers/auto_merge_ui.py",
      "lines": "273-338",
      "description": "POST /config does not validate project existence with _get_project_or_404.",
      "suggested_fix": "Call _get_project_or_404(db, project_id) at handler start for deterministic 404 semantics."
    }
  ],
  "notes": "Core API contracts are mostly met; no-op audit emission is the primary blocker."
}
```
