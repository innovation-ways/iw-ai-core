# I-00062_S04_CodeReview_Backend_prompt

**Work Item**: I-00062 -- Agent subprocess inherits orch DB env vars, allowing migrations to leak to port 5433
**Step Being Reviewed**: S03 (Backend)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT change Docker container/volume/network state. Read-only
introspection allowed. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade/downgrade/stamp` against the live orch
DB. **Do NOT run bare `make`.** `alembic history/current/show` is allowed.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- For runtime step state, prefer `uv run iw item-status I-00062 --json`.
- `ai-dev/active/I-00062/I-00062_Issue_Design.md` — design document
- `ai-dev/active/I-00062/reports/I-00062_S03_Backend_report.md` — S03 report
- All files listed in S03's `files_changed`:
  - `orch/daemon/worktree_compose.py`
  - `orch/daemon/batch_manager.py`
  - `orch/config.py`

## Output Files

- `ai-dev/active/I-00062/reports/I-00062_S04_CodeReview_report.md` — review report

## Context

S03 implemented the three-layer defense-in-depth: (1) strip orch DB vars
from the inherited env in `_agent_subprocess_env`, (2) inject per-worktree
DB vars in `_launch_step` when a compose stack is up, (3) fail-fast in
`orch/config.py` when an agent context resolves to the orch port.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files in S03's `files_changed`:

```bash
make lint
make format
```

NEW violations on changed files → **CRITICAL** with `"category":
"conventions"`. Tool unavailable → STOP and raise a blocker.

## Review Checklist (I-00062-specific)

### 1. `_agent_subprocess_env` — snapshot + strip block

- BEFORE the strip, the daemon's `IW_CORE_DB_HOST/PORT/NAME/USER/PASSWORD`
  values are snapshotted into `IW_CORE_ORCH_DB_*` via `setdefault`
  (so an existing `IW_CORE_ORCH_DB_*` value from `extra` / `browser_env`
  is NOT overwritten).
- AFTER the snapshot, the five `IW_CORE_DB_HOST/PORT/NAME/USER/PASSWORD`
  keys are popped from the copied env.
- `IW_CORE_ORCH_DB_*` keys are NOT popped (legitimate operator path
  for `iw step-done` etc).
- Snapshot+strip happen BEFORE `IW_CORE_AGENT_CONTEXT=true` is set and
  BEFORE the `extra` merge, so callers passing `extra={...}` still win
  for `IW_CORE_DB_*` (compose-stack injection, browser_env e2e).
- The function still returns `dict[str, str]` and the existing call
  sites (browser env merge, plain agent launch) continue to compile.
- **Verify**: with no `IW_CORE_ORCH_DB_*` in the inherited env, after
  `_agent_subprocess_env()` returns, `IW_CORE_ORCH_DB_PORT` IS set (from
  snapshot) and `IW_CORE_DB_PORT` is NOT set. The Layer 3 guard relies
  on this invariant — if the snapshot is absent or `setdefault`
  semantics are wrong, the guard goes vacuous for legacy worktrees.

### 2. `_launch_step` — injection block

- The injection branch runs ONLY when `worktree_compose_path` is set.
- All five DB vars (host/port/name/user/password) are injected from
  `worktree_info`, not from the daemon's env or hardcoded.
- The runtime check refuses to launch when any of the five values is
  missing, with a clear `RuntimeError` referencing I-00062 and the batch
  item id.
- The `bv_env` (browser-verification env) merge happens BEFORE the
  injection block — verify by reading the surrounding code, not just
  trusting the report.
- `IW_CORE_PER_WORKTREE_DB="true"` marker is still set.

### 3. `worktree_info` assembly — credentials passthrough

- Around line 660–670, all four new fields (`worktree_db_host`,
  `worktree_db_name`, `worktree_db_user`, `worktree_db_password`) are
  passed from `BatchItem` columns into `worktree_info`.
- They are mapped to non-empty strings (`or ""` fallback) so the
  injection block's truthiness check works correctly.
- Failure / no-compose branches set all four to `None` on `BatchItem`.

### 4. `worktree_compose.py` — `UpResult` extension

- `UpResult` has a new `discovered_db_credentials: dict[str, str]` field.
- `up()` populates it from the rendered compose / `worktree-env.toml`.
- Empty dict (not `None`) when DB stack absent — never raises.
- Existing callers of `discovered_ports` are untouched.
- No psycopg2 references introduced.

### 5. `orch/config.py` — fail-fast guard

- Helper `_check_agent_context_does_not_resolve_to_orch_port` exists.
- Triggers iff `IW_CORE_AGENT_CONTEXT == "true"` AND
  `IW_CORE_ORCH_DB_PORT` is set AND `port == IW_CORE_ORCH_DB_PORT`.
  (After Layer 1's snapshot, `IW_CORE_ORCH_DB_PORT` is always set in
  agent contexts launched via `_agent_subprocess_env`, so the guard
  fires for both compose and legacy regressions.)
- `RuntimeError` message references I-00062 verbatim (the runbook
  string in the design doc).
- Called from `get_db_url()` only. **Verify it is NOT called from
  `get_orch_db_url()`** — that path is the legitimate operator channel
  for orch DB writes.
- Operator context (no `IW_CORE_AGENT_CONTEXT`) is unaffected.
- No new bypass env var introduced.

### 6. Architecture & layer boundaries

- No new dependencies on dashboard or RAG modules from daemon files.
- No imports of psycopg2 anywhere.
- `load_dotenv` is NOT changed to `override=True` globally (would
  affect daemon and dashboard processes — explicitly forbidden by the
  design doc).

### 7. Security

- No credentials logged anywhere. The `RuntimeError` in `_launch_step`
  reports booleans (presence flags), never the actual passwords.
- The `RuntimeError` in `orch/config.py` does not include the resolved
  port number outside the runbook string (acceptable — port number is
  not a secret).
- No new SQL strings, no string formatting in queries.

### 8. NO live-DB writes

S03 must NOT have run `make` (bare), `make install`, `make db-migrate`,
or any alembic upgrade/downgrade/stamp against 5433. Check the report's
`notes` and any reproduced log output. Violation → **CRITICAL** with
`"category": "architecture"`.

### 9. Test impact

S03 should NOT add permanent tests — that's S05's job. Scratch tests
under `tests/_scratch/` should be absent from the diff. If present →
**MEDIUM_FIXABLE**.

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` and `make test-integration`. Confirm no regressions
unrelated to I-00062. Pre-existing failures (if any) must be flagged but
not classified as new findings.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Strip incomplete, injection missing, fail-fast in wrong place, live-DB write attempted |
| **HIGH** | bv_env merge ordering broken, AC6 regression risk, credentials leaked in error message |
| **MEDIUM (fixable)** | Convention drift, scratch tests left in tree, missing fail-loud branch |
| **MEDIUM (suggestion)** | Better error message, additional cross-check |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "I-00062",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict: pass` requires zero CRITICAL/HIGH/MEDIUM (fixable) findings.
