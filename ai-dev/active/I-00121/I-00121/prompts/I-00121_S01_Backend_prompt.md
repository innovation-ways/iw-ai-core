# I-00121_S01_Backend_prompt

**Work Item**: I-00121 — Allure reports & summaries missing for make-based test categories
**Step**: S01
**Agent**: Backend

---

## ⛔ Docker is off-limits

You MUST NOT run any command that changes Docker container/volume/network state
(`docker kill|stop|rm|restart`, `docker compose up|down|restart`, `docker volume rm|prune`,
`docker system|container|image prune`). Allowed: testcontainer fixtures spun up by pytest,
read-only `docker ps|inspect|logs`, and `./ai-core.sh` / `make` targets. If your task seems
to require a prohibited command, STOP and raise a blocker. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds **no** migration — do not create, modify, or apply one. You MUST NOT run
`alembic upgrade|downgrade|stamp` against the live DB. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- **Runtime step state** — prefer `uv run iw item-status I-00121 --json` (the manifest is a design-time snapshot).
- `ai-dev/active/I-00121/I-00121_Issue_Design.md` — Design document (read it first — especially Root Cause Analysis, Fix strategy, and Notes).
- `orch/test_runner.py` — the file you will modify.

## Output Files

- `ai-dev/active/I-00121/reports/I-00121_S01_Backend_report.md` — Step report.

## Context

You are fixing the root cause of **I-00121**: `make`-based test categories never emit Allure
results, so they produce no HTML report and a NULL `summary` on the dashboard Results tab.
Read the design document's **Root Cause Analysis** and **Fix strategy (approved)** sections in
full before editing. Read `CLAUDE.md` and `orch/CLAUDE.md` for conventions.

This is a **backend logic** change confined to `orch/test_runner.py`. The dashboard rendering
side was already fixed separately (commit eefcd837) — do NOT touch dashboard files.

## Requirements

### 1. Extract the command-rewrite into a pure, testable helper

The Allure redirect logic currently lives inline in `launch_test_run` (around
`orch/test_runner.py:86-92`):

```python
command = run.command
if allure_results:
    results_rel = Path(allure_results).relative_to(execution_dir)
    if "--alluredir" in command:
        command = re.sub(r"--alluredir[=\s]\S+", f"--alluredir={results_rel}", command)
    elif "make " in command:
        command = f"ALLURE_RESULTS={results_rel} {command}"
```

Extract this into a **module-level pure function** so it can be unit-tested without a
subprocess or DB:

```python
def _build_run_command(command: str, allure_results: str | None, execution_dir: str) -> str:
    ...
```

It must take the raw command, the (absolute) run-scoped allure-results dir, and the
execution dir, and return the rewritten command string. `launch_test_run` then calls this
helper instead of inlining the logic. Preserve existing behaviour for the two existing
branches exactly.

### 2. Inject `PYTEST_ADDOPTS` for `make` commands (PRIMARY FIX)

In the `make ` branch of the helper, in **addition** to the existing
`ALLURE_RESULTS=<results_rel>` prefix, export `PYTEST_ADDOPTS` so that pytest invoked inside
*any* `make` target writes Allure results into the run-scoped dir:

```python
elif "make " in command:
    command = (
        f"ALLURE_RESULTS={results_rel} "
        f"PYTEST_ADDOPTS='--alluredir={results_rel} {{existing}}' "
        f"{command}"
    )
```

Requirements for this injection:

- The run-scoped relative results dir (`results_rel`) MUST appear inside the `--alluredir`
  value passed via `PYTEST_ADDOPTS`.
- **Append-safe**: if `PYTEST_ADDOPTS` is already set in the environment, your value must be
  prepended/merged, not clobbered (e.g. reference `$PYTEST_ADDOPTS` inside the quoted value
  so an existing value is preserved). An unset `$PYTEST_ADDOPTS` must expand to empty
  harmlessly under `sh -c` (the command runs with `shell=True`).
- Quote the value so the space between `--alluredir=...` and any existing addopts does not
  break shell tokenisation.
- Do **NOT** add `PYTEST_ADDOPTS` for the `--alluredir` (pytest-direct) branch — that branch
  already rewrites `--alluredir` inline, and a second `--alluredir` from `PYTEST_ADDOPTS`
  would duplicate the flag. Only the `make` branch gets `PYTEST_ADDOPTS`.

> Why this works: pytest reads `PYTEST_ADDOPTS` from the environment automatically and the
> `allure-pytest` plugin is already a project dependency (the `unit`/`all` categories use
> `--alluredir` today). So every `make` target's pytest call will now emit Allure results
> into the run-scoped dir, the `Path(allure_results).is_dir()` guard becomes true, and
> `_generate_allure_report` + `parse_allure_summary` run as they already do for `unit`/`all`.

### 3. Persist `allure_report_dir` only after report generation (SECONDARY FIX)

Currently `run.allure_report_dir` is assigned unconditionally at
`orch/test_runner.py:70-71`, *before* the run executes — leaving a dangling pointer when no
report is ever generated. Change this so `run.allure_report_dir` is set **only after**
`_generate_allure_report` returns success.

- Keep computing the report path locally (it is still passed into `_generate_allure_report`).
- Move the `run.allure_report_dir = <report path>` assignment into the post-run block (around
  `test_runner.py:180-185`), gated on `_generate_allure_report` succeeding. `parse_allure_summary`
  / `run.summary` assignment stays as-is (still only set when stats parse).
- `run.allure_results_dir` may remain assigned where it is (it is the working dir during the
  run); the dangling-pointer fix is specifically about `allure_report_dir`.
- Note `_generate_allure_report` currently returns a `bool` — use its return value to decide
  whether to persist `allure_report_dir`.

### 4. Confirm quality runs are unaffected

Quality runs (`run_type == "quality"`) are already skipped for report generation
(`test_runner.py:180` guard). After your change their `allure_report_dir` will be NULL instead
of a dangling path. Grep `dashboard/routers/quality.py` and confirm it does NOT depend on
`allure_report_dir` being set for quality runs. Note the result in your report. If it DOES
depend on it, STOP and raise a blocker (do not expand scope into quality rendering).

## Project Conventions

Read `CLAUDE.md` and `orch/CLAUDE.md`. Match the existing style in `orch/test_runner.py`
(type hints, `Path` usage, logging). Keep the change minimal and confined to
`orch/test_runner.py`.

## TDD Requirement (RED → GREEN → REFACTOR)

1. **RED**: Before implementing, write a failing unit test for `_build_run_command` asserting
   the `make` branch injects `PYTEST_ADDOPTS` with the run-scoped `--alluredir`. Run it
   targeted (`uv run pytest tests/unit/test_test_runner_allure_env.py -v`) and confirm it fails
   for the right reason (the helper does not yet inject `PYTEST_ADDOPTS` — an `AssertionError`,
   not an `ImportError`/collection error). Capture the RED line.
   - The exhaustive test suite is owned by S03 (`tests-impl`); you only need the one or two
     RED tests that drive your implementation here.
2. **GREEN**: Implement requirements 1–3 minimally.
3. **REFACTOR**: Tidy while keeping the test green.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `complete`, run and fix: `make format`, then `make typecheck` (zero errors in
files you touched), then `make lint` (zero errors). Record each in the `preflight` object.

## Test Verification (NON-NEGOTIABLE)

Run only your targeted tests — e.g.
`uv run pytest tests/unit/test_test_runner_allure_env.py tests/unit -k test_runner -v`.
**Do NOT** run `make test-unit` / `make test-integration` — those are downstream QV gates.

> **Verification Placement Rule**: a full suite / aggregate gate passing is never a completion
> gate for this implementation step. Implement, run your targeted tests, and report.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "I-00121",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["orch/test_runner.py", "tests/unit/test_test_runner_allure_env.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "tests/unit/test_test_runner_allure_env.py::test_make_command_injects_pytest_addopts_alluredir — AssertionError: 'PYTEST_ADDOPTS=' not in cmd  // captured RED run",
  "blockers": [],
  "notes": "Confirmed dashboard/routers/quality.py does/does not depend on allure_report_dir for quality runs: <state result>"
}
```
