# I-00068_S02_CodeReview_Backend_prompt

**Work Item**: I-00068 -- Recent Activity batch link from "archived" event routes to /item/ instead of /batch/
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy.

## Input Files

- `uv run iw item-status I-00068 --json` — runtime step state
- `ai-dev/active/I-00068/I-00068_Issue_Design.md` — Design document
- `ai-dev/active/I-00068/reports/I-00068_S01_Backend_report.md` — S01 implementation report
- All files listed in S01 `files_changed`
- Reference: `orch/cli/batch_commands.py:392`, `orch/daemon/batch_manager.py` (correct emitters)

## Output Files

- `ai-dev/active/I-00068/reports/I-00068_S02_CodeReview_Backend_report.md`

## Pre-Review Lint & Format Gate

```bash
make lint
make format
```

Report new violations as CRITICAL findings.

## Review Checklist

### 1. Architecture Compliance

- The fix is contained to `orch/archive/batch_archiver.py` — no leakage into other emitters.
- The new parameter has a sensible default (`None`) so any external caller (if one exists) is not broken.
- The change does NOT introduce UPDATE or DELETE on `daemon_events` (append-only contract).

### 2. Correctness

- Every call to `_emit(...)` inside `batch_archiver.py` passes `entity_type="batch"`. Run `grep -n "_emit(" orch/archive/batch_archiver.py` and confirm.
- The `DaemonEvent(...)` constructor receives the new parameter. Verify by reading the body of `_emit`.
- `entity_type` is propagated by name (kwarg), not by position — matches SQLAlchemy ORM convention.

### 3. Type hints

- `entity_type: str | None = None` annotation present on both the function signature and (if helpful) at the call sites.

### 4. No unintended changes

- No edits to `orch/daemon/batch_manager.py`, `orch/cli/batch_commands.py`, or other emitters (out of scope).
- No new imports beyond what is needed.
- Existing event metadata (`event_metadata=metadata or {}`) is preserved.

### 5. Project conventions

- Follows `orch/CLAUDE.md` (especially `event_metadata` Python name, append-only `daemon_events`).
- Read `CLAUDE.md` for any other rules.

### 6. Security / Safety

- No string interpolation that could lead to SQL injection (the ORM constructor handles this correctly).
- `entity_type` value `"batch"` is a literal string — no untrusted input.

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` and `make test-integration`. All must pass.

## Severity Levels

CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.

## Review Result Contract

Same JSON shape as I-00067_S02. `verdict: "pass"` requires zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.
