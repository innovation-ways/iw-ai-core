# I-00120_S02_CodeReview_prompt

**Work Item**: I-00120 — Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Do not run any command that changes Docker state. Read-only `docker ps|inspect|logs`, testcontainer
fixtures, and `./ai-core.sh` / `make` targets are allowed. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No migrations in this item. Do not run `alembic upgrade|downgrade|stamp` against the live DB.

## Input Files

- Runtime step state: `uv run iw item-status I-00120 --json`.
- `ai-dev/active/I-00120/I-00120_Issue_Design.md` — design document.
- `ai-dev/work/I-00120/reports/I-00120_S01_Backend_report.md` — implementation report.
- All files listed in S01's `files_changed` (`orch/llm_usage.py`, `tests/unit/test_llm_usage.py`).

## Output Files

- `ai-dev/work/I-00120/reports/I-00120_S02_CodeReview_report.md` — review report.

## Context

Review the backend status discriminator added in S01. Read the design doc's **Status discriminator
contract** and **Root Cause Analysis** sections first.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the changed files (report only, fix nothing):
```bash
make lint
make format
```
New violations in changed files → CRITICAL findings (`category: conventions`) with file/line/code.

## Review Checklist (item-specific)

1. **Contract correctness** — `_codex_usage()` returns a `"status"` key in **every** branch, with the
   exact values `ok` / `expired` / `unauthenticated` / `error` mapped to the right triggers per the
   design doc table. The zeroed numeric shape (`block_pct: 0`, etc.) is preserved alongside the new key.
2. **Proactive expiry** — `_oauth_is_expired` treats `expires` as epoch **milliseconds**, returns
   `False` for missing/non-numeric `expires` (does NOT misclassify unknown as expired), and the
   boundary (expires == now) is handled deliberately.
3. **401 vs other errors** — a `401` maps to `expired`; any other HTTP status and any other exception
   map to `error`. Confirm `httpx.HTTPStatusError` is caught before the generic `Exception` and that
   `exc.response.status_code` is read safely.
4. **Never raises** — the function preserves the "never raises out" guarantee. No bare path can escape.
5. **No token refresh** — confirm S01 did NOT add any OAuth refresh, write-back to `auth.json`, or
   token-endpoint call (explicitly out of scope). If it did, that is a CRITICAL scope violation.
6. **No collateral changes** — Claude/MiniMax paths and the 60s cache are untouched. `get_llm_usage()`'s
   outer codex fallback carries `status: error`.
7. **TDD RED evidence** — S01's report `tdd_red_evidence` shows a plausible RED failure
   (`AssertionError`/`KeyError` from the missing `status` key), not an import/collection error. Reason
   about whether the test would actually fail against pre-change code.

## Severity Levels

CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW. `verdict: pass` only when zero
CRITICAL + HIGH + MEDIUM_FIXABLE findings.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/unit/test_llm_usage.py -k codex -v
```
Report results accurately.

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00120",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
