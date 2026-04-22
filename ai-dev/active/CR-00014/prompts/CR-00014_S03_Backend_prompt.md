# CR-00014_S03_Backend_prompt

**Work Item**: CR-00014 — Orchestration DB instance-identity fingerprint
**Step**: S03
**Agent**: backend-impl

---

## Input Files

- `ai-dev/active/CR-00014/CR-00014_CR_Design.md` — Design document (Desired Behavior, AC1–AC4)
- `ai-dev/active/CR-00014/reports/CR-00014_S01_Database_report.md` and `..._S02_CodeReview_report.md`
- `orch/daemon/main.py` — contains the startup health check where the identity check must plug in
- `orch/config.py` — env-var loader pattern
- `orch/cli/` — existing CLI command groups (pick the right module or add a new one — `orch/cli/db_commands.py` if new)
- `orch/db/models.py` — has the new `IwCoreInstance` model from S01
- `orch/db/session.py` — `SessionLocal` for session access
- `ai-core.sh` — contains `cmd_status` to extend
- `.env.example` — add `IW_CORE_EXPECTED_INSTANCE_ID` documentation
- `CLAUDE.md`, `orch/CLAUDE.md`

## Output Files

- `ai-dev/active/CR-00014/reports/CR-00014_S03_Backend_report.md` — step report
- `orch/db/identity.py` — new module
- `orch/daemon/main.py` — call `verify_instance_identity()` during startup health check
- `orch/cli/db_commands.py` — new CLI group (or add to existing `item_commands.py`-style module — match project convention)
- `orch/cli/__init__.py` — register new command group if needed
- `ai-core.sh` — extend `cmd_status`; optional fail-on-mismatch in `cmd_start`
- `.env.example` — document new var

## Context

You're wiring identity verification into every process that talks to the orchestration DB, except the dashboard (S05 handles that). Read the design doc first — in particular "Desired Behavior" and AC1 through AC4.

## Requirements

### 1. `orch/db/identity.py` — the verification module

Public API (minimum):

```python
class InstanceMismatchError(RuntimeError): ...
class InstanceRowMissingError(RuntimeError): ...

@dataclass(frozen=True)
class IdentityStatus:
    expected: uuid.UUID | None   # from env, None in bootstrap mode
    actual: uuid.UUID | None     # from DB, None if row missing
    mode: Literal["match", "mismatch", "bootstrap", "missing"]
    message: str                 # human-readable summary

def get_live_instance_id(session: Session) -> uuid.UUID | None:
    """Return the instance_id from iw_core_instance, or None if the row is missing."""

def get_expected_instance_id() -> uuid.UUID | None:
    """Parse IW_CORE_EXPECTED_INSTANCE_ID env var. Return None if unset/empty."""
    # Trim whitespace, treat empty string as unset.
    # Case-insensitive UUID parse (uuid.UUID(...) handles this by default).
    # Raise ValueError on malformed non-empty value.

def check_identity(session: Session) -> IdentityStatus:
    """Pure function: read both values, classify, return status. Does not raise."""

def verify_instance_identity(session: Session) -> IdentityStatus:
    """Enforce. Raises InstanceMismatchError on mismatch, InstanceRowMissingError on missing row when env is set. Returns IdentityStatus on match or bootstrap."""
```

Module must be importable without touching the DB (no module-level queries).

Error messages must name both UUIDs and include a one-line remediation hint. Example:

```
DB instance-identity MISMATCH.
  Expected: 7f3a9b2e-1234-4abc-8def-0123456789ab   (from IW_CORE_EXPECTED_INSTANCE_ID)
  Actual  : 9a2c1d4e-5678-4abc-8def-0123456789ab   (from iw_core_instance.instance_id)
Remediation: restore the correct DB, or update IW_CORE_EXPECTED_INSTANCE_ID in .env AFTER verifying the live DB is the one you intend.
```

Bootstrap notice (log at INFO, once):

```
IW_CORE_EXPECTED_INSTANCE_ID is unset. Live DB identity is 9a2c1d4e-5678-4abc-8def-0123456789ab.
Add this line to .env to enable strict identity verification:
  IW_CORE_EXPECTED_INSTANCE_ID=9a2c1d4e-5678-4abc-8def-0123456789ab
```

### 2. Daemon startup wiring

In `orch/daemon/main.py`, extend the startup health-check phase (currently logs "Database connection verified"):

- After DB connectivity is confirmed, open a short-lived session and call `verify_instance_identity(session)`.
- On `IdentityStatus.mode == "match"`: log INFO `Database identity verified (<short-uuid>)`.
- On `"bootstrap"`: log the bootstrap notice once (use a flag on the daemon instance to ensure one-shot across a single process's lifetime — a restart emits it again, that's fine).
- On `"mismatch"` or `"missing"` with env set: log a boxed ERROR block (the multi-line message from §1), then **raise** out of startup. The existing startup-error path should cause the daemon to exit with a non-zero code. If no such path exists, use `sys.exit(2)` with a final log line.
- Do NOT enter the main polling loop on mismatch/missing.

### 3. `iw db-identity` CLI

Add a new click command group. Two subcommands:

- `iw db-identity show` — connects, prints the live UUID, the expected UUID (or `unset`), and the mode. Always exits 0 (read-only diagnostic).
- `iw db-identity check` — connects, runs `verify_instance_identity`. Exit codes: `0` on match or bootstrap; `2` on mismatch; `3` on missing row with env set; `1` on connection failure. Prints the same error block as the daemon on failures.

Register the command group in `orch/cli/__init__.py` (or wherever groups are wired — match existing pattern).

### 4. `ai-core.sh` — `cmd_status` line

Extend `cmd_status` to add a "DB identity" line between the "PostgreSQL: accepting connections" line and the Daemon block.

- Run `uv run iw db-identity check` (capture exit code + stdout).
- Exit 0 → `print_ok "DB identity: PASS ($(short-uuid))"` where short-uuid is the first 8 chars of the actual UUID (parsed from stdout).
- Exit 2 → `print_err "DB identity: FAIL (expected=… actual=…)"`, plus the full error block indented by 6 spaces.
- Exit 3 → `print_err "DB identity: row missing from iw_core_instance"`.
- Exit 1 → `print_err "DB identity: could not connect"` (DB was already flagged unreachable above, so this becomes a secondary symptom).
- Exit 0 with mode=bootstrap → `print_warn "DB identity: UNVERIFIED (bootstrap mode — add IW_CORE_EXPECTED_INSTANCE_ID to .env)"`.

Do NOT make `cmd_status` itself fail (return non-zero) on identity mismatch — `status` should always complete so a user can see the full picture. But `cmd_start` SHOULD fail-fast on identity mismatch (daemon startup will catch it, but early failure in the script is clearer). Add `uv run iw db-identity check` as the first command after `cmd_db start` and before `alembic upgrade head` in `cmd_start`; propagate non-zero exit with a clear error.

### 5. `.env.example`

Add a documented section:

```
# -----------------------------------------------------------------------------
# DB instance-identity fingerprint (CR-00014)
# -----------------------------------------------------------------------------
# The orchestration DB seeds a UUID into iw_core_instance on first migration.
# Set this to that UUID so every process verifies it's talking to the right
# DB. To find the current value:  uv run iw db-identity show
# Leaving this unset puts the system in bootstrap mode (warns instead of
# refusing). Do NOT commit a populated value from production.
IW_CORE_EXPECTED_INSTANCE_ID=
```

Do NOT populate `.env` itself — that's user-owned.

## Project Conventions

- Follow `orch/CLAUDE.md` CLI conventions: click groups, `iw` entry point, session access via `orch.cli.utils` helpers if they exist.
- Error message style: multi-line boxed ERROR with `====` delimiters is fine; match what daemon already uses if there's a convention.
- Logging: use `logging.getLogger(__name__)` — don't `print()` inside `identity.py`. The daemon log-formatter adds timestamps/level.
- Do NOT swallow exceptions at the module boundary. Let `InstanceMismatchError` / `InstanceRowMissingError` propagate.

## TDD Requirement

Red–Green–Refactor. Unit tests go in S07 (a dedicated tests step), but you SHOULD write smoke coverage as you build so your code isn't completely untested when it reaches review. Minimum smoke tests: `get_expected_instance_id` with env set/unset/malformed, `check_identity` mode classification. Do not duplicate what S07 will do formally.

## Test Verification (NON-NEGOTIABLE)

1. `make test-unit` — pass.
2. `make lint` — pass.
3. `uv run iw db-identity show` against the live DB returns a UUID and exits 0.
4. `uv run iw db-identity check` against the live DB exits 0 (bootstrap mode, since we haven't set the env var yet in this CR; that's the expected behavior at this point in the rollout).
5. Manually test daemon startup once: start the daemon locally, verify it logs the bootstrap notice once, enters main loop. Stop it.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "CR-00014",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["..."],
  "tests_passed": true,
  "test_summary": "...",
  "blockers": [],
  "notes": ""
}
```

## Lifecycle commands

```bash
uv run iw step-start CR-00014 --step S03
# implement ...
uv run iw step-done CR-00014 --step S03 --report ai-dev/active/CR-00014/reports/CR-00014_S03_Backend_report.md
```
