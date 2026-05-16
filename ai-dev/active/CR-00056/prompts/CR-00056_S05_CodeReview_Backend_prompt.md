# CR-00056_S05_CodeReview_Backend_prompt

**Work Item**: CR-00056 -- Surface step prompts in dashboard (Prompt column + modal viewer)
**Step Being Reviewed**: S04 (backend-impl)
**Review Step**: S05

---

## ⛔ Docker is off-limits

Standard policy.

## ⛔ Migrations: agents generate, daemon applies

Standard policy.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00056 --json`
- `ai-dev/active/CR-00056/CR-00056_CR_Design.md` — focus on `AC2`, `AC3`, and `Notes` (append-only invariant)
- `ai-dev/work/CR-00056/reports/CR-00056_S04_Backend_report.md`
- All files in S04 report's `files_changed`

## Output Files

- `ai-dev/work/CR-00056/reports/CR-00056_S05_CodeReview_report.md`

## Context

You are reviewing S04's daemon changes that snapshot prompt content into the new `StepRun` columns at launch time. Two sites: initial-run launch in `orch/daemon/batch_manager.py`, fix-cycle retry launch in `orch/daemon/fix_cycle.py`.

## Read the Design Document FIRST

- `Acceptance Criteria → AC2` (initial run snapshots prompt content)
- `Acceptance Criteria → AC3` (fix-cycle retry sets `fix_prompt_text` AND preserves base `prompt_text`)
- `Notes → append-only invariant`
- `TDD Approach → Integration tests` — the test file the design names is `tests/integration/test_daemon_prompt_snapshot.py`. Confirm it appears in S04's `files_changed`.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

NEW violations → CRITICAL with `"category": "conventions"`.

## Review Checklist

### 1. Architecture Compliance

- The snapshot is captured **at the `StepRun(...)` constructor**, not via a subsequent UPDATE. UPDATE on `step_runs` violates append-only and is a **CRITICAL** finding.
- `prompt_text` is written for **prompt-bearing** steps only, not for qv-gate StepRun rows (which have `command`/`gate` set but no prompt). If S04 wrote prompt_text for qv-gate rows, that's a HIGH finding (semantic noise; downstream UI would show meaningless content).

### 2. Code Quality

- Prompt content is captured from the in-memory `prompt` variable that was just written to disk — NOT re-read from disk redundantly. Re-reading is acceptable but suboptimal; flag as MEDIUM (suggestion).
- IO errors during the (optional) re-read or any prompt-snapshot path are caught locally (`OSError`, `UnicodeDecodeError`) and logged at WARNING, NOT propagated. Confirm: a missing prompt file must NOT crash step launch.
- For fix-cycle retries, AC3 requires `prompt_text` to also be set to the **base prompt** (for traceability). Verify the implementation does this — either by reading the WorkflowStep's prompt_file, or by copying from the first StepRun's prompt_text. Whichever it chose, the value must match the base prompt, not the fix prompt.

### 3. Project Conventions

- Logger usage matches sibling daemon modules (`logging.getLogger(__name__)`).
- Kwarg ordering on the StepRun constructor matches nearby StepRun() constructions.
- No psycopg2 imports introduced.

### 4. Security

- No SQL injection risk (the columns are parameterised through SQLAlchemy).
- Prompt content is *trusted internal data* (written by the daemon itself); no escaping needed at this layer. The dashboard layer is responsible for HTML-escaping (Jinja's autoescape) when rendering.

### 5. Testing

- A new test file `tests/integration/test_daemon_prompt_snapshot.py` exists and runs against a testcontainer (verify by inspecting imports for `testcontainers.postgres` or `pg_container` fixture from `tests/integration/conftest.py`).
- The test exercises BOTH the initial-run code path AND the fix-cycle retry code path (or at minimum one test per path).
- Tests do NOT connect to the live DB on port 5433 — grep the new test file for hard-coded `5433` or `IW_CORE_DB_PORT` references. If found, **CRITICAL** per `CLAUDE.md`.

### 5a. TDD RED Evidence (mandatory — Backend step)

1. Confirm `tdd_red_evidence` is present and shows a plausible `AssertionError` from the new test. If it shows an `ImportError`, `SyntaxError`, or fixture-collection error, that's a HIGH finding (test was broken, not RED).
2. Reason about whether the test would fail against pre-S04 code: the assertion `step_runs.prompt_text == expected_content` would fail with `None == 'expected content'` because the column was never written. This is a legitimate RED.

### 6. CLAUDE.md hard rules

- **NEVER apply uncommitted migration to live DB**: confirm S04 did not run `alembic upgrade head`. The S01 migration must still be unapplied.
- **`step_runs` append-only**: re-confirm no UPDATE on the table for these columns.

## Test Verification (NON-NEGOTIABLE)

```bash
uv run pytest tests/integration/test_daemon_prompt_snapshot.py -v
uv run pytest tests/unit/ -k "daemon" -v
```

Report results accurately.

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview",
  "work_item": "CR-00056",
  "step_reviewed": "S04",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed",
  "notes": ""
}
```
