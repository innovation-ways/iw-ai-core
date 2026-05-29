# I-00121_S03_Tests_prompt

**Work Item**: I-00121 — Allure reports & summaries missing for make-based test categories
**Step**: S03
**Agent**: Tests

---

## ⛔ Docker is off-limits

You MUST NOT run any command that changes Docker state. The ONLY allowed Docker usage is
testcontainer fixtures spun up by pytest (they self-label and self-destruct via Ryuk).
Read-only `docker ps|inspect|logs` and `make` targets are fine. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds no migration. Do not run `alembic upgrade|downgrade|stamp` against the live DB.
Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `uv run iw item-status I-00121 --json` (authoritative step state).
- `ai-dev/active/I-00121/I-00121_Issue_Design.md` — Design (read **Test to Reproduce** + **TDD Approach**).
- `ai-dev/active/I-00121/reports/I-00121_S01_Backend_report.md` — S01 report (the helper name + signature it created).
- `orch/test_runner.py` — the code under test.
- `tests/CLAUDE.md` and `skills/iw-ai-core-testing/SKILL.md` — **MUST read before writing tests.**

## Output Files

- `ai-dev/active/I-00121/reports/I-00121_S03_Tests_report.md` — Step report.
- `tests/unit/test_test_runner_allure_env.py` — unit tests for the command-rewrite helper.
- `tests/integration/test_test_runner_report_persistence.py` — integration test for report-dir persistence.

## Context

Write the reproduction + regression tests for I-00121. The fix lives in `orch/test_runner.py`
(S01). Read the design's **Test to Reproduce** and **TDD Approach** sections — they name both
test files and the assertions.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For THIS item that means: do not merely assert that the rewritten command "changed" or that
`PYTEST_ADDOPTS` appears *somewhere* — assert the **run-scoped `--alluredir` value** is the one
that reaches pytest (e.g. `--alluredir=allure-results-42`, matching the run id), and that the
pytest-direct branch does **not** gain a second `--alluredir`. For persistence, assert the
exact NULL-vs-set outcome of `run.allure_report_dir`, not just that the run finished.

## Requirements

### 1. Reproduction + unit tests — `tests/unit/test_test_runner_allure_env.py`

Test the pure helper `_build_run_command` (created in S01; confirm its exact name/signature
from the S01 report). Cover:

- **`make` command** → result contains `PYTEST_ADDOPTS=` with `--alluredir=<run-scoped rel>`
  AND still exports `ALLURE_RESULTS=<run-scoped rel>`. This is the **reproduction test**
  (fails pre-fix: no `PYTEST_ADDOPTS` for make commands).
- **pytest-direct command** (`… --alluredir=allure-results`) → the inline `--alluredir` is
  rewritten to the run-scoped dir and there is **no** `PYTEST_ADDOPTS` (no duplicate flag).
- **append-safety** — when the helper is designed to preserve an existing `PYTEST_ADDOPTS`,
  assert the produced command references/keeps it (e.g. contains `$PYTEST_ADDOPTS` or merges
  the existing value) rather than dropping it.
- **passthrough** — a command with neither `--alluredir` nor `make ` (or `allure_results=None`)
  is returned unchanged.

These are pure-function tests → `tests/unit/` (no DB, no FastAPI).

### 2. Regression integration test — `tests/integration/test_test_runner_report_persistence.py`

Assert the dangling-pointer fix end-to-end through `launch_test_run`, WITHOUT running a real
test subprocess or real `allure generate`:

- Use the testcontainer `db_session` fixture (see `tests/CLAUDE.md` / existing integration
  tests for the pattern). Seed a `Project` with a minimal `test_config` and a `TestRun` row.
- **Monkeypatch `subprocess.Popen`** (the one used in `orch.test_runner`) so no real command
  runs — have it create the run-scoped `allure-results` dir (to simulate a category that DID
  emit results) for the "report generated" case, and create nothing for the "no results" case;
  return a fake process object whose `wait()` returns exit code 0 and with a settable `pid`.
- **Monkeypatch `orch.test_runner._generate_allure_report`** to return `True` (and write a
  fake `index.html` into the report dir) for the "generated" case, and to be asserted
  *not called* for the "no results" case.
- Assert:
  - **Generated case**: after `launch_test_run(run.id)`, `run.allure_report_dir` is set to the
    expected category report path AND `run.summary` reflects the parsed stats (monkeypatch
    `parse_allure_summary` to return a known dict, then assert that exact dict / its totals).
  - **No-results case**: `run.allure_report_dir` is **NULL** (the dangling pointer is gone) and
    `_generate_allure_report` was not invoked.

Follow all testcontainer rules in `tests/CLAUDE.md` (psycopg URL replacement, FTS DDL after
`create_all`, never the live DB on 5433, never `importlib.reload(orch.config)`).

### 3. Every assertion must be able to fail

Each assertion must be one that would fail if the production line it guards regressed (the
mutation-test question). No assertions that merely restate a mock.

## TDD note

The reproduction unit test (`make` → `PYTEST_ADDOPTS`) was introduced in S01 as the RED test;
expand it here into the full matrix. Do NOT perform a manual runtime revert / `git stash` to
"prove RED" — RED was demonstrated at design time and in S01.

## Test Verification (NON-NEGOTIABLE — targeted only)

Run ONLY the two files you created:

```bash
uv run pytest tests/unit/test_test_runner_allure_env.py tests/integration/test_test_runner_report_persistence.py -v
```

Do **NOT** run `make test-unit` or `make test-integration` — full-suite execution is owned by
the downstream QV gates (S10/S11). Running them here routinely blows the step's timeout budget
(I-00073/S03 post-mortem).

Run `make format`, `make typecheck`, `make lint` on your new files before reporting.

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "Tests",
  "work_item": "I-00121",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "tests/unit/test_test_runner_allure_env.py",
    "tests/integration/test_test_runner_report_persistence.py"
  ],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "tdd_red_evidence": "n/a — tests-impl coverage step (tests authored after the S01 fix exists)",
  "blockers": [],
  "notes": ""
}
```
