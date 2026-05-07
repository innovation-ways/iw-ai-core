# F-00080_S02_CodeReview_prompt

**Work Item**: F-00080 — First-Time User Onboarding & Contextual Help (Dashboard OSS-readiness)
**Step Being Reviewed**: S01 (api-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

Standard policies. See template boilerplate.

## Input Files

- `uv run iw item-status F-00080 --json`
- `ai-dev/active/F-00080/F-00080_Feature_Design.md`
- `ai-dev/work/F-00080/reports/F-00080_S01_api_report.md`
- All files listed in S01's `files_changed`

## Output Files

- `ai-dev/work/F-00080/reports/F-00080_S02_CodeReview_report.md`

## Context

Review S01 (api-impl): the new `dashboard/routers/help.py`, its registration in `dashboard/app.py`, and the bare unit tests that S01 wrote.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on S01's `files_changed`:

```bash
make lint
make format
```

Any NEW violations on this branch (not present on `main`) → CRITICAL finding.

## Review Checklist

### 1. Architecture compliance
- Is the router thin (no DB, no `orch/` calls)?
- Is `templates/_partials/help/<slug>.html` looked up via Jinja loader (not raw filesystem)?
- Is the slug regex `^[a-z][a-z0-9_-]{0,31}$` applied?
- Is the empty-allow-list edge case handled (warning at startup, no crash)?
- Is the `help` module imported as `help as help_router` to avoid shadowing the builtin?

### 2. Code quality
- Are all functions type-hinted?
- Is the slug allow-list cached at module import time (no per-request re-read)?
- Is the response always `HTMLResponse` (not `JSONResponse` masquerading)?
- Is the FastAPI dependency injection pattern (e.g. `templates`) consistent with other dashboard routers?

### 3. Project conventions
- Match `dashboard/CLAUDE.md` patterns.
- No emojis.
- No business logic.

### 4. Security
- Path-traversal blocked by regex (verified via tests).
- Slug never used in `os.path.join` against user-supplied input.
- No PII or secrets logged.
- The regex is anchored on both ends and rejects: uppercase, leading digit, `..`, `/`, spaces, query-string-as-slug.

### 5. Testing
- All 5 RED-phase tests from S01's prompt are present and pass.
- Tests use `monkeypatch` to set the allow-list rather than depending on real fragment files (fragments don't exist yet).

## Test Verification

Run `make test-unit` (or at least `pytest tests/dashboard/test_help_router.py -q`).

## Severity Levels

Standard scale (CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW).

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "F-00080",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "5 passed, 0 failed",
  "notes": ""
}
```

`verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM_FIXABLE.
