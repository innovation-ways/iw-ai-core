# F-00075_S01_Backend_prompt

**Work Item**: F-00075 -- MiniMax Coding Plan usage from /coding_plan/remains (replace local SQLite estimate)
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

Your job in a Database step is to WRITE the migration FILE. The daemon
will apply it as part of the merge pipeline.

This step does **NOT** touch the database. No migrations are required.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — for the current step list, status, prompt paths, gate commands, etc., prefer `uv run iw item-status F-00075 --json`.
- `ai-dev/active/F-00075/F-00075_Feature_Design.md` -- design document (read first; sections "In Scope", "Acceptance Criteria", "Boundary Behavior", "Invariants", "Notes/Reference fixture")
- Pre-evidence:
  - `ai-dev/active/F-00075/evidences/pre/F-00075-before-fragment.html` — the wrong "before" output the user is currently seeing
- Existing source files you will modify:
  - `orch/llm_usage.py` — main file (see lines 137–175 for the current MiniMax SQLite path)
- Reference (do **not** modify in this step):
  - `dashboard/routers/usage.py` — consumer of `get_llm_usage()`
  - `dashboard/templates/fragments/llm_usage_footer.html` — template

## Output Files

- `ai-dev/active/F-00075/reports/F-00075_S01_Backend_report.md` -- step report

## Context

You are implementing the backend slice of **F-00075**. The user's dashboard footer currently shows a wrong MiniMax usage percentage (19% on 2026-04-30 while platform.minimax.io shows 0%) because `_minimax_usage()` in `orch/llm_usage.py` reads `~/.local/share/opencode/opencode.db` and divides token counts by a hard-coded limit on a Unix-epoch-aligned 5h grid that does not match MiniMax's actual billing window. The Coding Plan tier also counts **requests, not tokens** — the local computation is wrong on multiple axes.

Your job: replace that local computation with a direct call to the authoritative MiniMax endpoint, and **delete the SQLite path entirely** so it cannot reintroduce wrong numbers on a transient failure. The user explicitly directed: "I don't want the local counter for minimax, it's wrong so I don't want to keep it."

Read `CLAUDE.md` and `orch/CLAUDE.md` for project conventions. The Claude path in this same file (`_claude_usage()`, `_run_ccusage()`, `_block_start()`, `_sum_jsonl_tokens()`) is **out of scope** — do not modify it.

## Requirements

### 1. Add `_load_minimax_key() -> str | None`

Resolution order:

1. Read `os.environ.get("IW_MINIMAX_API_KEY")`. If non-empty, return it.
2. Otherwise, attempt to read `~/.local/share/opencode/auth.json` (use `Path.home() / ".local/share/opencode/auth.json"`). If the file exists and parses as JSON, return `data["minimax"]["key"]` if present and non-empty.
3. On any exception (missing file, permission error, JSON parse error, `KeyError`), return `None` — never raise.

### 2. Add `_format_reset(remains_ms: int) -> str | None`

Format milliseconds-to-reset as a short human string, mirroring the Claude path's format produced by `_claude_usage()`:

- `remains_ms <= 0` → `None`
- `remains_ms < 3_600_000` (less than 1 hour) → `"{m}m"` (e.g. `"25m"`)
- otherwise → `"{h}h {m}m"` (e.g. `"2h 43m"`, `"1h 0m"`)

This helper may also be used by the Claude path if you want to dedupe — but if you refactor Claude's existing inline formatter, the resulting Claude output must remain byte-identical for the same input. Otherwise leave Claude alone and keep `_format_reset` as a MiniMax-only helper.

### 3. Add `_minimax_usage_remote(api_key: str) -> dict[str, Any]`

Call `GET https://api.minimax.io/v1/api/openplatform/coding_plan/remains` using `httpx`:

- Headers: `Authorization: Bearer {api_key}`, `Accept: application/json`.
- If `os.environ.get("IW_MINIMAX_GROUP_ID")` is set and non-empty, append `?GroupId={value}` to the URL. Otherwise the URL has no query string.
- Use `httpx.get(...)` (synchronous) with `timeout=10.0`. Do not use the async client — the rest of `orch/llm_usage.py` is synchronous.
- Call `resp.raise_for_status()`.
- Parse `data = resp.json()`.
- If `data["base_resp"]["status_code"] != 0`, raise `RuntimeError(data["base_resp"]["status_msg"])`.
- Find the row in `data["model_remains"]` where `model_name == "MiniMax-M*"`. If absent, raise `LookupError("MiniMax-M* row not present")`.
- If `row["current_interval_total_count"] == 0`, raise `ValueError("MiniMax-M* total quota is 0")`.
- Compute `used = row["current_interval_total_count"] - row["current_interval_usage_count"]` (the API's `usage_count` is **remaining**, not used — confirmed in design doc Notes section).
- Compute `pct = min(100, round(used / row["current_interval_total_count"] * 100))`.
- Compute `reset = _format_reset(row["remains_time"])`.

Return:

```python
{
    "block_pct": pct,
    "block_reset": reset,
    "used": used,
    "total": row["current_interval_total_count"],
}
```

This function is allowed to raise. Its caller `_minimax_usage()` is responsible for catching.

### 4. Rewrite `_minimax_usage() -> dict[str, Any]`

The new orchestrator function:

1. Call `_load_minimax_key()`. If `None`, log a single `logger.warning("MiniMax API key not configured; usage bar will show 0%")` and return `{"block_pct": 0, "block_reset": None}`. **Do not** read the SQLite database. **Do not** fall back to a local computation.
2. Otherwise call `_minimax_usage_remote(key)` inside a `try`. On success return the dict (it already has the right keys).
3. On any exception (`httpx.HTTPError`, `httpx.RequestError`, `RuntimeError`, `LookupError`, `ValueError`, `KeyError`, `json.JSONDecodeError`, generic `Exception`), call `logger.exception("MiniMax usage fetch failed")` and return `{"block_pct": 0, "block_reset": None}`.

Logging severity rule (matches AC3):
- Missing API key → `logger.warning` (operator action, not an exception condition).
- Any runtime failure path → `logger.exception` (preserves traceback for diagnosis).

### 4a. Align the outer wrapper in `get_llm_usage()`

`get_llm_usage()` currently wraps `_minimax_usage()` with its own `try/except` that on failure falls back to `{"block_pct": 0}` (single-key). After your change `_minimax_usage()` is contracted to never raise, so the outer fallback is dead code in practice — but if it ever fires (e.g. truly catastrophic error), the dict shape must still match the new contract `{"block_pct": 0, "block_reset": None}` so `dashboard/routers/usage.py` does not silently lose the `block_reset` key.

Update the outer `except` branch in `get_llm_usage()` accordingly:

```python
try:
    minimax = _minimax_usage()
except Exception:
    logger.exception("MiniMax usage fetch failed")
    minimax = {"block_pct": 0, "block_reset": None}
```

Do **not** modify the equivalent Claude wrapper.

### 5. Delete the SQLite code path

Remove from `orch/llm_usage.py`:

- `import sqlite3` (top of file).
- `_OPENCODE_DB = Path.home() / ".local/share/opencode/opencode.db"`.
- `_FIVE_H_MS = 5 * 3600 * 1000`.
- `_MINIMAX_5H_LIMIT: int = int(os.environ.get("IW_MINIMAX_5H_LIMIT", "3860000"))`.
- The entire body of the previous `_minimax_usage()` (the SQLite query, bucket math, etc.).

After your change, `grep -nE 'sqlite3|_OPENCODE_DB|_FIVE_H_MS|_MINIMAX_5H_LIMIT|IW_MINIMAX_5H_LIMIT' orch/llm_usage.py` must return zero matches. Confirm this before reporting completion.

If `Path` was only used by `_OPENCODE_DB`, you may also remove the `from pathlib import Path` import — but **only** if it is genuinely unused after your changes. Verify with grep first.

### 6. Update the module docstring

The current docstring at the top of `orch/llm_usage.py` describes the MiniMax computation as "current 5h bucket tokens / highest ever 5h bucket". Replace that line and the surrounding paragraphs with an accurate description of the new behavior:

- MiniMax 5h: live call to `https://api.minimax.io/v1/api/openplatform/coding_plan/remains`, reading the `MiniMax-M*` row only. Counts requests, not tokens.
- Mention that the API key is resolved from `IW_MINIMAX_API_KEY` env var first, then from `~/.local/share/opencode/auth.json`.
- Mention the optional `IW_MINIMAX_GROUP_ID` escape hatch.
- Note that on missing key or any failure the bar reports `block_pct=0, block_reset=None` and the failure is logged.

Keep the Claude paragraphs in the docstring intact.

### 7. `.env.example` update (only if the file exists)

If `.env.example` exists at the repository root, add the new entries near any other `IW_CLAUDE_*` lines:

```
# Optional: MiniMax Coding Plan API key. If unset, falls back to ~/.local/share/opencode/auth.json.
# IW_MINIMAX_API_KEY=

# Optional: GroupId query param for the /coding_plan/remains endpoint. Most accounts don't need this.
# IW_MINIMAX_GROUP_ID=
```

If `.env.example` does not exist, skip this — do not create it.

## Project Conventions

Read the project's `CLAUDE.md` and `orch/CLAUDE.md` for:

- Architecture patterns and layer boundaries.
- Coding conventions and naming rules.
- Technology stack: psycopg v3, SQLAlchemy 2.0 sync, Click, httpx already a dep.
- The 60s in-process cache (`_CACHE_TTL`, `_cache`, `_cache_lock`) **must be reused**, not duplicated.

Match existing code style in `orch/llm_usage.py` — module-level constants, type-hinted module-level functions, `from __future__ import annotations`, `logger = logging.getLogger(__name__)` already present.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Write the failing tests in `tests/unit/test_llm_usage.py` first. (S07 will add more comprehensive coverage; this step's tests should at least cover the happy-path remote call, the missing-key path, and one failure path.) The tests must fail before the implementation is written.
2. **GREEN**: Implement the minimum code to make those tests pass.
3. **REFACTOR**: Clean up while keeping tests green.

Mocking guidance: this code calls module-level `httpx.get(...)`, so the simplest approach is `monkeypatch.setattr("httpx.get", fake_get)` — `httpx.MockTransport` only attaches to `httpx.Client`/`httpx.AsyncClient` instances and is not a fit here. `respx` is **not** currently in `pyproject.toml`; do not add it as a dependency for this work item. Do not perform real network calls in tests.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

Before reporting `completion_status: complete`:

1. `make format` — auto-fix formatting drift, re-stage if changed.
2. `make typecheck` — zero errors involving files you touched.
3. `make lint` — zero errors.

Populate the `preflight` block in your result contract.

## Test Verification (NON-NEGOTIABLE)

After implementation:

1. `make test-unit` must pass.
2. `make lint` and `make typecheck` must pass.
3. Do **NOT** report `tests_passed: true` unless all unit tests pass with zero failures.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "F-00075",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/llm_usage.py",
    "tests/unit/test_llm_usage.py"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
