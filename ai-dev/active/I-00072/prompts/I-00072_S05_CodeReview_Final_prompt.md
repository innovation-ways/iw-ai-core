# I-00072_S05_CodeReview_Final_prompt

**Work Item**: I-00072 -- iw merge-queue retry-merge rejects items in merge_failed status
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

Allowed: testcontainers from pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` and `make` targets.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run `alembic upgrade|downgrade|stamp` against the live DB. Final review-only step.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status I-00072 --json` (canonical).
- `ai-dev/active/I-00072/I-00072_Issue_Design.md` — Design document; "Acceptance Criteria" section is the spec.
- `ai-dev/active/I-00072/I-00072_Functional.md` — Functional summary (cross-check the implementation matches the user-facing claims).
- All implementation reports: `ai-dev/active/I-00072/reports/I-00072_S0{1,3}_*_report.md`.
- All per-agent code review reports: `ai-dev/active/I-00072/reports/I-00072_S0{2,4}_CodeReview_*_report.md`.
- All files listed in S01's and S03's `files_changed`:
  - `orch/daemon/merge_queue.py`
  - `orch/cli/merge_queue_commands.py`
  - `dashboard/routers/actions.py`
  - `tests/unit/test_merge_queue_cli.py`

## Output Files

- `ai-dev/active/I-00072/reports/I-00072_S05_CodeReview_Final_report.md` — Final review report.

## Context

You are performing the **final cross-step review** of all I-00072 work. Per-step reviews (S02 over S01, S04 over S03) have already covered each step in isolation. Your job is to catch the things they could not — issues that span multiple steps, inconsistencies between the implementation and the tests, and gaps between either of them and the design's acceptance criteria.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

NEW violations on any file in S01's or S03's `files_changed` are **CRITICAL** with `"category": "conventions"`.

## Review Checklist

### 1. Acceptance Criteria — every AC has implementation + test

Walk through each AC in the design doc and confirm both halves exist:

- **AC1 (Bug is fixed):** S01 changed the CLI filter; S03 has a test that fails pre-S01 and passes post-S01. ✓ or ✗.
- **AC2 (Regression test exists):** the reproduction test from the design doc exists in `tests/unit/test_merge_queue_cli.py`. ✓ or ✗.
- **AC3 (CLI/dashboard parity):** S01 imported the constant in both surfaces; S03 has the `is`-identity parity test. Both halves present? Confirm the test uses `is`, not `==`.
- **AC4 (Legacy back-compat preserved):** S01 added the legacy-failed-with-merge-notes path to the CLI; S03 has both the acceptance test (legacy notes → accepted) AND the rejection test (non-merge notes → refused).

Any AC missing implementation OR missing tests → **CRITICAL** finding (`"category": "completeness"`, with the AC reference in the description).

### 2. The constant is single-source-of-truth in practice

```bash
grep -rn "BatchItemStatus.merge_failed\|BatchItemStatus.migration_invalid\|BatchItemStatus.migration_rolled_back\|BatchItemStatus.migration_rebase_failed" \
  orch/cli/merge_queue_commands.py dashboard/routers/actions.py
```

Both files should reference these statuses ONLY via `OPERATOR_RECOVERABLE_MERGE_STATUSES` — direct enum-member references in the retry/restart filter logic are a sign of stale local copies that S02 and S04 may have missed.

(Direct references to the enum in *other* code paths — e.g. `abandon_merge`, error messages, log strings — are fine. Focus on the retry/restart filter site.)

### 3. Forward coverage for `migration_rolled_back`

The design pulls `migration_rolled_back` into the constant proactively (no producer wired today). Verify:

- The constant lists it (`merge_queue.py`).
- S03 has a test row for it.
- The CLI's first-pass `BatchItem.status.in_(list(OPERATOR_RECOVERABLE_MERGE_STATUSES))` will accept it once a producer lands.
- The dashboard's first-pass `BatchItem.status.in_(list(OPERATOR_RECOVERABLE_MERGE_STATUSES))` will accept it once a producer lands.

Missing in any of these four → **CRITICAL** finding.

### 4. No regression in adjacent flows

The merge-queue and dashboard files contain other code paths that reference these statuses. Verify nothing else broke:

- `orch/daemon/merge_queue.py:process_merge_queue` — still produces `merge_failed` (CR-00028 contract).
- `dashboard/routers/actions.py:abandon_merge` — still flips `merge_failed`/`migration_invalid`/`migration_rebase_failed` to `failed` for cascade. Confirm this list was NOT touched (the design says it shouldn't be).
- `orch/daemon/state_machine.py` — no transition table changes.

Any unintended drift → **HIGH** or **CRITICAL** depending on impact.

### 5. The test suite verifies the integration end-to-end

Run the full suite (both unit AND integration) and confirm:

- Existing `test_merge_queue.py`, `test_merge_queue_merge_failed_status.py`, `test_merge_queue_migration_pipeline.py`, `test_merge_status_recoverable_display.py` all still pass — these are the daemon-side tests for the same code area, and a regression there is more important than a new test passing.
- The new I-00072 tests pass.
- No tests connect to the live DB on port 5433.

If integration tests fail, this is a **CRITICAL** finding.

### 6. Functional doc accuracy

Read `I-00072_Functional.md`. Cross-check claims against the implementation:

- "The terminal command now accepts every kind of recoverable merge failure that the dashboard already accepted, plus one additional category" — confirm via the constant's contents.
- "The terminal command also accepts older items that failed merge before the new status labels were introduced" — confirm via the legacy CLI path.
- "Internally it now reads its list of acceptable statuses from the same source the terminal uses" — confirm via the import in `actions.py`.

Any user-facing claim contradicted by the code → **HIGH** finding (the functional doc misleads support / operators).

### 7. Cross-cutting findings only

Per-step reviews caught per-step issues. **Do not re-file** findings already raised in S02 or S04 unless they were addressed but the fix introduces a *new* cross-cutting concern. Your job is the seam between steps — gaps, mis-translations, and integration mismatches.

## Test Verification (NON-NEGOTIABLE)

1. Run `make test-unit` — must pass.
2. Run `make test-integration` — must pass.
3. Report results accurately. If integration tests fail, that's a **CRITICAL** finding.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Missing implementation for an AC; missing test for an AC; stale local copy of the status set; functional doc contradicts implementation; integration tests fail |
| **HIGH** | Functional claim misaligned with code; adjacent flow regressed |
| **MEDIUM (fixable)** | Cross-step naming inconsistency; missing log/audit field |
| **MEDIUM (suggestion)** | Better integration test exists |
| **LOW** | Documentation polish |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00072",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "completeness|consistency|integration|testing|architecture|security",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it",
      "cross_cutting": true
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` if zero CRITICAL/HIGH/MEDIUM-fixable findings.
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM-fixable.
- `missing_requirements`: list any AC that lacks implementation OR a test. Each missing item is automatically a CRITICAL finding.
- `cross_cutting: true` on findings that span multiple steps.
