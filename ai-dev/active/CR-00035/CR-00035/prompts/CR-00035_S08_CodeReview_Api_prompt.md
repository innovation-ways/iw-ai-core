# CR-00035_S08_CodeReview_Api_prompt

**Work Item**: CR-00035 -- Doc-generation job observability + execution report + dispatch fix
**Step Being Reviewed**: S07 (api-impl)
**Review Step**: S08

---

## ⛔ Docker is off-limits

Standard policy. Testcontainers exempt. No lifecycle commands. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00035 --json`.
- `ai-dev/active/CR-00035/CR-00035_CR_Design.md` (esp. AC8).
- `ai-dev/active/CR-00035/reports/CR-00035_S07_Api_report.md`.
- All files in S07's `files_changed`.

## Output Files

- `ai-dev/active/CR-00035/reports/CR-00035_S08_CodeReview_report.md`

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```
Any new violation in S07's changed files = **CRITICAL**.

## Review Checklist

### Routes & registration

- Three new endpoints exist at the paths in AC8 / the design doc.
- Route declaration order does NOT shadow the existing `GET /jobs/{job_type}/{job_id}` catch-all in `jobs_ui.py`. Confirm by reading the registered router and tracing FastAPI's match order.
- The existing detail route still resolves and now passes `log_file_exists` into the template context.

### Path resolution

- `_resolve_doc_job_log_path` accepts both `DOC-NNNNN` and the internal UUID and resolves to the correct row.
- Log filename uses `job.id` (UUID), never `public_id`.
- Resolved path is verified to be inside `Project.repo_root` after `.resolve()` (path-traversal guard).
- 404 is raised with explanatory body when project is missing, job is missing, or `repo_root` is empty.

### `/log/tail`

- Default `n=200`, hard cap 1000. Verify the cap.
- ANSI strip imported from `orch/utils/log_capture.py` (do NOT re-implement inline).
- Per-line cap of 8 KB, with a `…` truncation suffix.
- Empty file → 200 with empty `lines`. Missing file → 404. Both behaviours under tests.
- Response shape matches the design doc.

### `/log/stream` (SSE)

- Content-Type: `text/event-stream; charset=utf-8`.
- Initial 50-line backfill is sent before tailing.
- 15-second heartbeat (`event:ping`).
- Terminal-status detection re-opens a fresh, short-lived session every ~2s — does NOT hold a session open for the stream's lifetime. **This is the single most likely defect.**
- Client disconnect terminates the generator (file descriptor closes).
- `event:status\ndata:terminal\n\n` sent before close.

### `/log/raw`

- ANSI is NOT stripped on raw download.
- `Content-Disposition: attachment; filename="doc_job_<id>.log"`.
- File missing → 404.
- Streamed (not loaded entirely in memory) for large files.

### Cross-cutting

- No `agent-browser`, no `chromium.launch()`, no `npx playwright install` referenced.
- No mock-DB or live-DB usage in any test stubs.
- Type hints on the helper.
- Imports organised per ruff conventions.

## Test Verification

```bash
make test-unit
make test-integration
```

Report results accurately.

## Severity Levels

Standard.

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "CodeReview",
  "work_item": "CR-00035",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
