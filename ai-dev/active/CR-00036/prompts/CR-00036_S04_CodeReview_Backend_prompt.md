# CR-00036_S04_CodeReview_prompt

**Work Item**: CR-00036 -- Batch-level auto_merge toggle with operator-approved manual merge
**Step Being Reviewed**: S03 (backend-impl)
**Review Step**: S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY container/volume/network management commands. Allowed: testcontainers via pytest, read-only `docker ps`/`inspect`/`logs`, `./ai-core.sh` and `make` targets. STOP and raise a blocker if you think a prohibited command is needed. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

No `alembic upgrade|downgrade|stamp` against the live DB. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- `ai-dev/active/CR-00036/CR-00036_CR_Design.md`
- `ai-dev/work/CR-00036/reports/CR-00036_S03_Backend_report.md`
- All files listed in S03's `files_changed`.

## Output Files

- `ai-dev/work/CR-00036/reports/CR-00036_S04_CodeReview_report.md`

## Context

You are reviewing the backend implementation for CR-00036: projects.toml parsing, BatchManager gate, `approve_merge` service, CLI commands, dashboard `_merge_status` update, and doc updates.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations on changed files → CRITICAL findings under `category: conventions`.

## Review Checklist

### 1. Registry parsing

- `ProjectConfig.auto_merge_default` defaults to `True`.
- Parsing pattern matches `self_assess` exactly (handles bool, non-bool, missing key).
- Warning is logged for non-bool values; default falls back to `True`.

### 2. BatchManager gate

- The gate sits at the **workflow-completion** site, not at fix-cycle paths or stall paths.
- The branch only triggers on success — failed/stalled items are unaffected.
- The `Batch` row is loaded once per call (no N+1).
- DaemonEvent emission uses `event_metadata` (Python attribute), not `metadata`.
- `process_merge_queue` is **unchanged** — its filter on `BatchItemStatus.completed` is the gate behavior.

### 3. `approve_merge` service

- Locks the `BatchItem` row with `FOR UPDATE` (or equivalent) before mutating.
- Rejects with a clear `ValueError` when status is not `awaiting_merge_approval`. Error message includes the current status.
- Commits in a single transaction.
- Emits `DaemonEvent(event_type="merge_approved_by_operator", ...)`.

### 4. CLI: `iw item approve-merge`

- Subcommand registered correctly (verify with `uv run iw item --help`).
- Project resolution mirrors sibling commands.
- JSON mode produces structured output; non-JSON produces a one-liner.
- Error path exits with non-zero (4 per design doc).

### 5. CLI: `iw batch-create --auto-merge / --no-auto-merge`

- Click flag style is `--auto-merge/--no-auto-merge`, not two separate boolean flags.
- `default=None` so absent flag falls through to project default (verify the resolution order: explicit flag → project default → built-in `True`).
- Value flows into `Batch(...)` constructor.
- JSON output and human echo both include the new field.

### 6. Dashboard `_merge_status`

- New branch returns the literal string `"awaiting_approval"` (matches the design's frontend contract).
- New branch is positioned before the recoverable-status check (otherwise `awaiting_merge_approval` items might leak into a `merge_failed` UI path if the recoverable set is ever extended).
- `_synthetic_merge_step` propagates the new status without logic change.

### 7. Doc updates

- CLI spec: synopsis line, flag table row, new section for `iw item approve-merge`.
- Daemon design: paragraph in merge-queue section accurately describes the gate.
- Daemon design: stall-monitor section explicitly exempts `awaiting_merge_approval` from the stall-fail timer (see design Notes — `awaiting_merge_approval` is a *waiting-on-human* state, not a *stuck* state).
- If the S03 report includes a `stall_audit` note, verify it matches what `grep -rn "stall\|stalled" orch/daemon/` actually shows — silent skip of the audit is a HIGH finding.

### 8. Tests (RED before GREEN)

- The test names suggest TDD was followed (one assertion per behavior; tests would fail before code change).

## Test Verification

`make test-unit` and `make test-integration` MUST pass.

## Severity Levels

| Severity | Examples |
|----------|----------|
| CRITICAL | Gate engages on failed items; `metadata` vs `event_metadata` typo crashes daemon at runtime; missing FOR UPDATE causes lost-update; `process_merge_queue` modified |
| HIGH | Missing rejection on wrong-status approve; flag default not honoring project config; CLI not registered |
| MEDIUM (fixable) | Missing tests, weak error messages, doc drift |
| MEDIUM (suggestion) | Refactor opportunity |
| LOW | Nitpick |

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "CR-00036",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
