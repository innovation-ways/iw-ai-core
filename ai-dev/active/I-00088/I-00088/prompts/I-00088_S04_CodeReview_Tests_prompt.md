# I-00088_S04_CodeReview_Tests_prompt

**Work Item**: I-00088 — Auto-merge health probe always fails — CLI-shape mismatch with step_executor.sh
**Step Being Reviewed**: S03 (Tests)
**Review Step**: S04

---

## ⛔ Docker is off-limits

Same policy as the implementation step. Testcontainer fixtures spun up by
pytest are exempt. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

No migrations. Read-only `alembic history / current / show` is OK.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00088 --json`
- `ai-dev/active/I-00088/I-00088_Issue_Design.md` — Design document
- `ai-dev/work/I-00088/reports/I-00088_S03_Tests_report.md` — S03 report
- All files in S03's `files_changed` (expected: `tests/unit/test_auto_merge_health.py`, `tests/integration/test_auto_merge_health_runtime.py`)

## Output Files

- `ai-dev/work/I-00088/reports/I-00088_S04_CodeReview_report.md`

## Context

You are reviewing the test coverage that locks in the I-00088 fix. The key
risk to guard against is: tests that pass without actually catching the
original bug.

## Read the Design Document FIRST

- `## Acceptance Criteria` AC2 (regression test exists) and AC3 (unit tests
  assert on argv shape) are the contract you are auditing.
- `## TDD Approach` names two test files: `tests/unit/test_auto_merge_health.py`
  and `tests/integration/test_auto_merge_health_runtime.py`. Both must be
  present in S03's `files_changed`. If either is missing, that is a
  **CRITICAL** finding.
- `## Test to Reproduce` shows the canonical integration test shape — the
  fake CLI on `PATH` pattern. Verify S03's implementation matches that shape.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

New violations in the changed files are CRITICAL.

## Review Checklist

### 1. Semantic Correctness Over Shape (I003 Lesson — CRITICAL CATEGORY)

For EACH test in the modified unit file:

- Does it assert on the **command list passed to subprocess.run** (the
  argv), or only on `payload["runtime_reachable"]`?
- A test that ONLY asserts `payload["runtime_reachable"] is True` after
  mocking `subprocess.run` to return `returncode=0, stdout="OK"` is the
  exact pattern that hid the original bug. Such a test is acceptable as a
  SECONDARY assertion, but EVERY mocked-subprocess test MUST also assert
  on the argv.
- Required argv assertions (per the design):
  - `argv[0] == "bash"`,
  - `argv[1].endswith("step_executor_lib.sh")` (NOT `step_executor.sh`),
  - `argv[2] == "auto_merge_resolve"`,
  - `argv[3] == resolved.cli_tool`,
  - `argv[4] == resolved.model`.
- If any test in S03's modified set lacks any of these argv assertions,
  raise a **HIGH** finding with `"category": "testing"` quoting the test
  name and the missing assertion.

For the new integration test:

- Does it write a real executable file to `tmp_path` named `opencode` (or
  `claude`) and prepend `tmp_path` to `PATH` via `monkeypatch.setenv("PATH", ...)`?
- Does the success-path test assert that the **capture file contents** include
  BOTH the resolved model name AND the probe prompt string? Capture-file
  assertions are the irrefutable proof that the runtime was actually invoked
  with the right argv via a real PATH lookup, *through the real lib-script
  dispatch*. Missing either is a HIGH finding.
- Does the test rely on the probe inheriting `PATH` from the parent process?
  (i.e. the probe's env dict reads `os.environ.get("PATH", ...)`.) If the
  probe hardcoded `PATH` to `/usr/local/bin:/usr/bin:/bin`, the test cannot
  inject a fake CLI and would either silently invoke the real `opencode`
  on disk or fail with `command not found`. Cross-check S01's implementation.

### 2. Would the test have caught the original bug?

Mentally apply the test suite to the **pre-S01** version of
`orch/daemon/auto_merge_health.py` (where the probe shells out to
`step_executor.sh --step-type ...`):

- Would at least one unit test fail? It should — the new argv assertions
  would see `argv[1].endswith("step_executor.sh")` (not `step_executor_lib.sh`)
  and `argv[2] == "--step-type"` (not `"auto_merge_resolve"`).
- Would the integration test fail? It should — pre-fix, `step_executor.sh`
  exits 2 before any runtime is invoked, so the fake `opencode` shim on
  `PATH` would not be touched, the capture file wouldn't exist (or would
  be empty), and `runtime_reachable` would be `False`.

If your mental model says EITHER test would still pass against pre-S01
code, raise a CRITICAL finding — the test isn't actually a regression
test.

### 3. Test Isolation (NON-NEGOTIABLE under pytest-randomly)

`pytest-randomly` is ON by default. Verify:

- The integration test uses `monkeypatch.setenv("PATH", ...)`, NOT raw
  `os.environ["PATH"] = ...`. Raw mutation leaks across tests; randomised
  order will eventually expose the leak.
- The integration test uses `tmp_path`, NOT a hard-coded `/tmp/...` path.
- No module-level state is mutated in a way that other tests would observe.

If any of these are violated, raise a HIGH finding.

### 4. Tests/CLAUDE.md Compliance

Read `tests/CLAUDE.md` and confirm:

- The new integration test does NOT connect to the live DB (port 5433).
- The new integration test does NOT call `importlib.reload(orch.config)`.
- The new integration test is placed under `tests/integration/`, not
  `tests/unit/` or `tests/dashboard/`. (It exercises real `subprocess.run`
  — integration territory.)

### 5. Architecture: are the assertions on the public seam?

The probe's "public" seam to the runtime is the argv it passes to
`subprocess.run`. Assertions on `run.call_args.args[0]` are correct.
Assertions that grovel into `_EXECUTOR_PATH` or any other module-private
detail are incorrect — they bind tests to implementation, not behaviour.
Flag any such grovelling as MEDIUM_FIXABLE.

### 6. Coverage of the design's named test files

The design's `## TDD Approach` names two test files by path:
- `tests/unit/test_auto_merge_health.py`
- `tests/integration/test_auto_merge_health_runtime.py`

Both MUST appear in S03's `files_changed`. Any missing entry is a
**CRITICAL** finding (per the universal "design names a test file → it
must exist" rule).

## Test Verification (NON-NEGOTIABLE)

Run only the modified / added files:

```bash
uv run pytest tests/unit/test_auto_merge_health.py tests/integration/test_auto_merge_health_runtime.py -v
```

If any test fails, that is a CRITICAL finding.

Do NOT run `make test-unit` or `make test-integration` — those are QV gates.

## Severity Levels

Standard scale. `verdict: pass` requires zero CRITICAL/HIGH/MEDIUM_FIXABLE.

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "CodeReview",
  "work_item": "I-00088",
  "step_reviewed": "S03",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "<results from the targeted run>",
  "notes": ""
}
```
