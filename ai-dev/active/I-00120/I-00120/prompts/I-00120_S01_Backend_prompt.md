# I-00120_S01_Backend_prompt

**Work Item**: I-00120 — Codex usage chips silently show 0% when the opencode OAuth token is expired or invalid
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute any command that changes Docker container/volume/network state
(`docker kill|stop|rm|restart`, `docker compose up|down|restart`, `docker volume rm|prune`,
`docker system|container|image prune`). Read-only introspection (`docker ps|inspect|logs`),
testcontainer fixtures spun up by pytest, and `./ai-core.sh` / `make` targets are allowed.
If your task seems to require a prohibited command, STOP and raise a blocker.
Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This step adds no migrations. Do not run any `alembic upgrade|downgrade|stamp` against the live DB.

## Input Files

- Runtime step state: `uv run iw item-status I-00120 --json` (authoritative; the manifest is a design-time snapshot).
- `ai-dev/active/I-00120/I-00120_Issue_Design.md` — design document (read the **Root Cause Analysis** and **Status discriminator contract** sections in full).
- `orch/llm_usage.py` — the file you will modify.

## Output Files

- `ai-dev/work/I-00120/reports/I-00120_S01_Backend_report.md` — step report.

## Context

You are implementing the backend half of **I-00120**. The Codex usage path in `orch/llm_usage.py`
collapses every failure mode (auth missing, 401 token-expired, network/decode error) into a single
undifferentiated zeroed dict, so the dashboard cannot distinguish "0% genuine usage" from "auth broken".

Your job: add a **`status` discriminator** to the Codex usage dict. **Do NOT implement token refresh** —
detection only. This is explicitly out of scope.

Read the design document first, then `CLAUDE.md` and `orch/CLAUDE.md` for conventions.

## Requirements

### 1. Add a `status` field to every Codex usage dict

`_codex_usage()` must always return a dict containing a `"status"` key with exactly one of these
string values, per the **Status discriminator contract** table in the design doc:

| status | Trigger |
|--------|---------|
| `ok` | `_codex_usage_remote()` returned successfully |
| `expired` | the stored `expires` epoch-ms is at/before now (proactive), OR the endpoint returns HTTP `401` |
| `unauthenticated` | `_load_openai_oauth()` returns `None` (no file / no valid OAuth entry) |
| `error` | any other failure (non-401 HTTP error, network error, JSON decode, schema drift) |

Suggested approach (match existing module style — keep it minimal and readable):
- Define small status constants (e.g. `_CODEX_STATUS_OK = "ok"`, etc.).
- Replace the module-level `_CODEX_ZERO` usage with a helper `_codex_zero(status: str) -> dict[str, Any]`
  that returns the existing zeroed shape **plus** `"status": status`. Keep the zeroed shape otherwise
  identical (`block_pct: 0, week_pct: 0, block_reset: None, week_reset: None, plan_type: None`).
- `_codex_usage_remote()`'s success return dict must include `"status": _CODEX_STATUS_OK`.

### 2. Proactive expiry check

Add a helper `_oauth_is_expired(entry: dict[str, Any]) -> bool` that reads the `expires` field
(epoch **milliseconds**) from the OAuth entry and returns `True` when it is a number at/before the
current time. Use the module's existing `datetime`/`UTC` import for the clock
(`datetime.now(UTC).timestamp() * 1000`). When `expires` is missing or not a number, return `False`
(do NOT treat unknown as expired — let the remote call decide).

In `_codex_usage()`, after loading the entry and before calling the remote endpoint, if
`_oauth_is_expired(entry)` is `True`, log a WARNING and return `_codex_zero(_CODEX_STATUS_EXPIRED)`
without making the doomed network call.

### 3. Distinguish 401 from other remote failures

In `_codex_usage()`, wrap the `_codex_usage_remote(...)` call so that:
- `httpx.HTTPStatusError` with `exc.response.status_code == 401` → log WARNING, return `_codex_zero(_CODEX_STATUS_EXPIRED)`.
- any other `httpx.HTTPStatusError` → log via `logger.exception(...)`, return `_codex_zero(_CODEX_STATUS_ERROR)`.
- any other `Exception` → log via `logger.exception(...)`, return `_codex_zero(_CODEX_STATUS_ERROR)`.

The function must still **never raise** (preserve the existing guarantee).

### 4. Keep the auth-missing branch as `unauthenticated`

When `_load_openai_oauth()` returns `None`, keep the existing WARNING log and return
`_codex_zero(_CODEX_STATUS_UNAUTHENTICATED)`.

### 5. Update `get_llm_usage()`'s outer fallback

The outer `except` for codex in `get_llm_usage()` currently does `codex = dict(_CODEX_ZERO)`.
Update it to produce a dict carrying `"status": _CODEX_STATUS_ERROR` (e.g. `codex = _codex_zero(_CODEX_STATUS_ERROR)`).

### Do NOT

- Do NOT implement OAuth token refresh, write back to `auth.json`, or call any OAuth token endpoint.
- Do NOT change the Claude or MiniMax code paths.
- Do NOT change the 60s cache behaviour.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. Match the existing defensive style in `orch/llm_usage.py`
(typed dicts, `from __future__ import annotations`, `logger.warning` vs `logger.exception`). Sync
SQLAlchemy is irrelevant here — this is a pure service function.

## TDD Requirement

Follow TDD (RED → GREEN → REFACTOR). The dedicated `tests-impl` step (S05) owns the full test
authoring, but for your own RED evidence add/extend at least one targeted unit test in
`tests/unit/test_llm_usage.py` proving an expired token yields `status == "expired"`, run it RED
first (targeted run only: `uv run pytest tests/unit/test_llm_usage.py -k codex -v`), capture the
failure line, then implement to GREEN. Confirm the RED failure is an `AssertionError`/`KeyError`
from missing behaviour, not an import/collection error.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `complete`, run in order and fix issues in files you touched:
1. `make format`
2. `make typecheck`
3. `make lint`

Full-suite / aggregate-gate success (`make quality` / `make check` / `make test-unit` /
`make test-integration`) is **NOT** this step's responsibility and MUST NOT be used as a
completion gate — those are owned by the downstream `tests-impl` (S05) and `qv-gate` steps
(S08..S15). (Canonical Verification Placement Rule — `skills/iw-workflow/SKILL.md`; CR-00092 / I-00117.)

## Test Verification (NON-NEGOTIABLE)

Run ONLY targeted tests for your change:
```bash
uv run pytest tests/unit/test_llm_usage.py -k codex -v
```
Do NOT run `make test-unit` / `make test-integration` — those are downstream QV gates.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00120",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["orch/llm_usage.py", "tests/unit/test_llm_usage.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/unit/test_llm_usage.py::test_codex_usage_expired_token_reports_expired_status — KeyError: 'status' // captured RED run",
  "blockers": [],
  "notes": ""
}
```
