# CR-00014_S04_CodeReview_prompt

**Work Item**: CR-00014 — Orchestration DB instance-identity fingerprint
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## Input Files

- `ai-dev/active/CR-00014/CR-00014_CR_Design.md`
- `ai-dev/active/CR-00014/reports/CR-00014_S03_Backend_report.md`
- All files listed in the S03 report's `files_changed`
- `orch/CLAUDE.md`, project `CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00014/reports/CR-00014_S04_CodeReview_report.md`

## Context

Review the identity module, daemon wiring, CLI, and `ai-core.sh` changes from S03. This is the layer that decides "go vs. no-go" for every orchestration process, so the review bar is high on fail-fast semantics and error clarity.

## Review Checklist

### 1. `orch/db/identity.py`

- Module is importable without touching the DB (no module-level queries, no connection at import time).
- `get_expected_instance_id()`:
  - Returns `None` for unset, empty string, whitespace-only.
  - Trims whitespace from the env value before parsing.
  - Raises `ValueError` with a clear message on malformed non-empty value (malformed env var is a config bug, not an "unset").
  - Case handling via `uuid.UUID(...)` (tolerant).
- `get_live_instance_id(session)`:
  - Returns `None` when row is missing (not raises).
  - Uses an explicit `SELECT instance_id FROM iw_core_instance LIMIT 1` or the ORM `session.query(IwCoreInstance).one_or_none()` — either is fine; prefer ORM for consistency with the rest of the codebase.
- `check_identity(session)` is pure: doesn't raise, returns an `IdentityStatus` dataclass for all four modes (`match`, `mismatch`, `bootstrap`, `missing`).
- `verify_instance_identity(session)` raises exactly the two error types the design calls for; does NOT swallow exceptions; does NOT retry.
- Error messages include BOTH UUIDs and a remediation hint (multi-line, delimited). Check against the design doc's example block.

### 2. Daemon startup wiring (`orch/daemon/main.py`)

- Identity verification happens AFTER DB connectivity is confirmed (reusing the existing session or opening a short-lived one — either OK).
- On mismatch or missing (with env set): the daemon **does not enter the main loop**. Verify this is a raised exception, not a `return` from a helper (a bare return would let startup continue in the parent frame).
- On bootstrap: one-shot INFO logging. Verify it's actually one-shot (a flag on the daemon instance or a module-level `_warned` guard) — acceptable patterns.
- On match: single INFO line `Database identity verified (<short-uuid>)`.
- No partial-start path: specifically, the projects.toml loader, the poll loop, and any signal handlers must not be set up before identity verification passes.

### 3. `iw db-identity` CLI

- Command group registered with the `iw` entry point (test locally: `uv run iw --help` shows `db-identity`).
- `show` exits 0 in all DB-reachable cases.
- `check` exit codes match the prompt spec exactly: `0` match/bootstrap, `2` mismatch, `3` missing-row, `1` connection failure. Any other exit code is a bug.
- CLI does NOT print Python tracebacks on expected failure modes — prints the formatted error block only.
- CLI output parseable enough that `ai-core.sh` can extract the short UUID without brittle regex hell.

### 4. `ai-core.sh` changes

- `cmd_status` runs the check but does NOT fail the overall status command on mismatch — `status` must always complete. (Design doc requires this explicitly.)
- Output uses existing `print_ok`/`print_err`/`print_warn` helpers; colours consistent.
- Short-UUID extraction works when the actual UUID starts with digits (don't assume alphabet).
- `cmd_start` propagates non-zero identity-check exit: if identity check fails after DB is up, the script aborts before daemon/dashboard start (the daemon would catch it anyway, but early is clearer).
- `set -uo pipefail` compatibility: no unguarded variable expansions on identity output.

### 5. `.env.example`

- Section added, commented, shows the exact command to find the value (`iw db-identity show`).
- Warning against committing a populated value.
- No accidental value written into `.env` itself (user-owned).

### 6. Regression surface

- No behavior change for developers who have NOT yet set the env var (bootstrap mode) — they still get a working daemon, dashboard, and status command, just with a one-shot notice.
- Existing startup health-check behavior preserved on the happy path (connection verification still happens).

## Severity Grading

CRITICAL / HIGH / MEDIUM / LOW — standard.

Fix-in-place allowed. Re-run `make test-unit` + `make lint` after fixes.

## Subagent Result Contract

Same pattern as S02.

## Lifecycle commands

```bash
uv run iw step-start CR-00014 --step S04
# ... review + apply fixes ...
uv run iw step-done CR-00014 --step S04 --report ai-dev/active/CR-00014/reports/CR-00014_S04_CodeReview_report.md
```
