# CR-00056_S04_Backend_prompt

**Work Item**: CR-00056 -- Surface step prompts in dashboard (Prompt column + modal viewer)
**Step**: S04
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

Standard policy. Read-only docker introspection only; testcontainers are exempt.

## ⛔ Migrations: agents generate, daemon applies

The migration from S01 is in your worktree but unapplied to the live DB. Do NOT run `alembic upgrade` against the live DB. Tests that need the new columns use testcontainers (where `Base.metadata.create_all()` produces the columns from the ORM model regardless of migration state).

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00056 --json`
- `ai-dev/active/CR-00056/CR-00056_CR_Design.md` — Design document (`Acceptance Criteria → AC2, AC3`)
- `ai-dev/work/CR-00056/reports/CR-00056_S01_Database_report.md` — S01 report (so you know which columns now exist)
- `orch/daemon/batch_manager.py` — read around lines 1238, 1311, 1388-1407, 1497 (StepRun creation sites + prompt-file write site)
- `orch/daemon/fix_cycle.py` — read around lines 649, 711, 1859-1920, 2335 (fix prompt generation + retry StepRun creation)

## Output Files

- `ai-dev/work/CR-00056/reports/CR-00056_S04_Backend_report.md` — Step report

## Context

S01 added `StepRun.prompt_text` and `StepRun.fix_prompt_text`. Your job is to populate them at step launch time — both for initial runs (in `orch/daemon/batch_manager.py`) and for fix-cycle retries (in `orch/daemon/fix_cycle.py`).

The daemon already writes prompt files to disk just before creating the StepRun row, so the prompt **string** is in memory at the right moment. The change is small: pass that string into the `StepRun(...)` constructor.

Read the design document's `Desired Behavior` and `AC2 / AC3` first. Then read `CLAUDE.md` and `orch/CLAUDE.md`.

## Requirements

### 1. Snapshot prompt content at initial-run launch (`orch/daemon/batch_manager.py`)

Locate the prompt-file write site around line 1388:

```python
prompt_file = (...)
prompt_file.parent.mkdir(parents=True, exist_ok=True)
write_agent_prompt(prompt_file, prompt)
```

The `prompt` variable here is the in-memory string content. Capture it (or read it back from disk with `prompt_file.read_text()` — implementer's choice, but reading from the variable already in hand is preferred — fewer IO calls, no encoding round-trip).

Find the three `StepRun(...)` constructions in this file (lines ~1238, 1311, 1497). For the one(s) that correspond to the initial launch of an implementation step (where `prompt_file` / `prompt` is set in the same code path), pass `prompt_text=prompt` as a keyword argument.

For the StepRun constructions that happen for steps without a per-step prompt (e.g., qv-gate rows where `gate`/`command` is set and there is no prompt file), leave `prompt_text` unset — it defaults to NULL.

**Determine empirically** which of the three StepRun() sites are reached for prompt-bearing steps vs gate steps; comment on your finding in the report. Do NOT blindly add `prompt_text=` to all three — that may write the wrong prompt for gate steps.

### 2. Snapshot fix-cycle prompt content (`orch/daemon/fix_cycle.py`)

Locate the fix-prompt write site around line 1917:

```python
prompt_file = prompt_dir / f"{item_id}_{step_id}_FIX_cycle{cycle_number}_prompt.md"
prompt_file.write_text(prompt)
```

The `prompt` variable holds the fix-prompt string. Then around line 2335 a new `StepRun(...)` is created for the retry attempt. Pass `fix_prompt_text=<the fix prompt string>` into that constructor.

Additionally, set `prompt_text` on the retry StepRun to **the base prompt content** for backwards-traceability (per AC3: "StepRun.prompt_text remains the base prompt for that step"). The base prompt content is most easily obtained by:

- Reading `step.prompt_file` from disk (the WorkflowStep row carries the path), OR
- Querying the *first* StepRun for this step (`run_number=1`) and copying its `prompt_text`.

Pick whichever is simpler given the surrounding code. Document the choice in the report.

If either read fails (worktree gone, file missing), set the column to NULL and continue — do NOT raise. Step launch must not break on prompt-snapshot IO errors. Log a warning via the existing daemon logger.

### 3. Handle missing prompt files gracefully

For both step types: if `prompt_file` is None, or the file does not exist, or read fails for any reason, the corresponding column stays NULL. Wrap the read in a narrow try/except (catch `OSError`, `UnicodeDecodeError`), log the exception, set the column to None, and continue. **Do not propagate the exception.**

### 4. Preserve append-only invariant

`step_runs` is append-only. Set both columns **only at row creation** (in the `StepRun(...)` constructor call). Never write an UPDATE statement against `step_runs` to set these columns later. If your design requires an UPDATE, you've taken a wrong turn — raise a blocker.

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md` for daemon patterns, logging, error handling. Match the style of nearby `StepRun(...)` constructions for kwarg ordering. The daemon's logger is project-standard (`logging.getLogger(__name__)`).

## TDD Requirement

This is a behaviour-implementing Backend step. Follow RED → GREEN → REFACTOR.

1. **RED**: First write `tests/integration/test_daemon_prompt_snapshot.py` (or extend an existing daemon test file if one already exists with similar fixtures) with a test that:
   - Sets up a WorkflowStep + prompt file with known content.
   - Invokes the relevant daemon launch function (the one you'll modify) against a testcontainer DB.
   - Asserts `step_runs.prompt_text == expected_content`.
   - Run it targeted: `uv run pytest tests/integration/test_daemon_prompt_snapshot.py -v` — confirm it fails with `AssertionError` (the column is NULL because no code populates it yet).
   - Capture the failing assertion line for `tdd_red_evidence`.
2. **GREEN**: Implement the minimal change in `batch_manager.py` (and `fix_cycle.py`) to make the test pass.
3. **REFACTOR**: Tidy the helper if you extracted one (e.g., a small `_snapshot_prompt(path: Path | None) -> str | None` helper used by both sites is reasonable but optional — three lines of inline code is fine too).

The full S11 (tests-impl) step adds the rest of the integration tests; you only need ONE behavioural test here to satisfy RED.

## Pre-flight Quality Gates (NON-NEGOTIABLE) — CR-00023

```bash
make format
make typecheck
make lint
```

Populate `preflight` in the result contract.

## Test Verification (NON-NEGOTIABLE)

Run only the targeted tests:

```bash
uv run pytest tests/integration/test_daemon_prompt_snapshot.py -v
uv run pytest tests/unit/ -k "daemon or batch_manager or fix_cycle" -v
```

Do NOT run `make test-integration` (S19 QV gate owns the full suite).

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "backend-impl",
  "work_item": "CR-00056",
  "completion_status": "complete",
  "files_changed": [
    "orch/daemon/batch_manager.py",
    "orch/daemon/fix_cycle.py",
    "tests/integration/test_daemon_prompt_snapshot.py"
  ],
  "preflight": {
    "format": "ok|fixed",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/integration/test_daemon_prompt_snapshot.py::test_initial_run_snapshots_prompt — AssertionError: assert None == 'expected prompt'  // captured RED run",
  "blockers": [],
  "notes": "Snapshotted prompt at <site>; chose <approach> for base prompt on fix-cycle retries; IO errors swallowed and logged."
}
```
