# I-00122_S03_Tests_prompt

**Work Item**: I-00122 — db-start guard against empty-DB displacement
**Step**: S03
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

You MUST NOT change Docker state. Your test must **never** invoke the real
`docker` binary. Instead it places a **stub `docker` executable** first on `PATH`
that records its arguments to a log file and exits 0. This is the whole point of
the harness: it lets you assert what `ai-core.sh` *would* have run without
running it. Do NOT run `./ai-core.sh db start` against the live DB.

## Input Files

- `uv run iw item-status I-00122 --json` — runtime step state.
- `ai-dev/active/I-00122/I-00122_Issue_Design.md` — design (read **Test to
  Reproduce** + **TDD Approach**).
- `ai-dev/active/I-00122/reports/I-00122_S01_Backend_report.md` — S01 report
  (note the chosen prod container name / subcommand).
- `ai-core.sh` — the script under test.
- `tests/CLAUDE.md` and `tests/conftest.py` — test conventions.

## Output Files

- `ai-dev/active/I-00122/reports/I-00122_S03_Tests_report.md`.
- New test file: `tests/unit/test_db_start_guard.py`.

## Context

The bug: with a production identity pinned and the DB down, `ai-core.sh db start`
ran the bootstrap compose and created an empty DB on the production port. The fix
makes it refuse. Your job is to lock this behaviour with a reproduction test plus
regression tests.

This is a pure shell-behaviour test — **no FastAPI, template, or DB dependency** —
so it lives under `tests/unit/` (a `tests/integration/`/`tests/dashboard/`
placement would needlessly pull in the testcontainer fixtures). It must be fast
and hermetic.

## Requirements

### 1. Test harness (fixture)

Build a helper/fixture that runs `ai-core.sh db start` in a controlled
environment:

- Create a temp dir with a **stub `docker`** script (executable) that appends its
  full argument list to `$DOCKER_CALL_LOG` and exits 0. Prepend that dir to
  `PATH` for the subprocess.
- Provide a minimal `.env`/environment so `ai-core.sh` loads cleanly. Set
  `IW_CORE_DB_PORT` to a **closed** port (pick a high port nothing listens on) so
  the script's `db_ready` probe reports the DB as **down**. If `db_ready` proves
  hard to force via a closed port alone, prefer that approach over editing the
  script; document any difficulty in your report rather than weakening the test.
- Run via `subprocess.run(["bash", "ai-core.sh", "db", "start"], ...)` from the
  repo root, capturing returncode, stdout, stderr, and the docker call log.

### 2. Reproduction test (the bug)

`test_i00122_db_start_refuses_bootstrap_when_instance_pinned`:
- **Arrange**: `IW_CORE_EXPECTED_INSTANCE_ID` set to a non-empty UUID; DB down.
- **Act**: run `db start`.
- **Assert (semantic — see warning below)**:
  - returncode **!= 0**;
  - the docker call log contains **no** `compose`+`up` invocation and no
    `up -d db` (assert the specific absence, not just "log is short");
  - stderr communicates that the production DB is down / refused to bootstrap
    (assert a specific expected substring the S01 message uses, not merely that
    stderr is non-empty).

### 3. Regression tests

- `test_db_start_bootstraps_on_fresh_dev_machine_when_no_identity_pinned`:
  `IW_CORE_EXPECTED_INSTANCE_ID` **unset**; DB down → returncode 0 path attempted
  and the docker call log **does** contain a `compose ... up -d db` invocation
  (the dev path is preserved). The stub returns 0 so the script proceeds.
- `test_db_start_is_noop_when_db_already_up`: force `db_ready` true (e.g. point
  `IW_CORE_DB_PORT` at a listener you open in the test, or stub the readiness
  probe) → the script returns 0 and the docker call log shows **no** container
  creation/`up` call at all.

If forcing `db_ready` true is impractical without a real listener, open a throwaway
local TCP socket on the chosen port within the test (standard library only) — do
**not** start a real database.

> **Probe semantics — make `db_ready` control fully deterministic.** `db_ready()`
> in `ai-core.sh` prefers `pg_isready` when it is on `PATH` and only falls back to
> `nc -z` otherwise. `pg_isready` performs a real PostgreSQL protocol handshake, so
> a bare TCP-socket listener does **not** make it report "ready" — the noop test
> would then be host-dependent (passes where only `nc` exists, fails where
> `pg_isready` is installed). The robust, hermetic approach is to **stub the probe
> binary too**: drop a stub `pg_isready` (and a stub `nc`) into the same on-`PATH`
> bin dir you already use for the `docker` stub, and control its exit code per test
> (exit 0 ⇒ DB up; non-zero ⇒ DB down). Prefer this over relying on a real port's
> open/closed state. Document the chosen mechanism in your report.

### CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

I002's tests checked API response SHAPE (key exists, is a list, is non-empty) and passed.
But the bug was NOT fixed. Tests must verify SPECIFIC VALUES:

- BAD: `assert "permissions" in data` (shape only)
- GOOD: `assert "brands:manage" in permissions` (semantic — verifies specific expected value)
- GOOD: `assert "*" not in permissions` (semantic — verifies unwanted value is absent)

For this item that means: assert the **specific absence** of a `compose`/`up -d db`
call in the refuse case (not just "exit != 0"), and assert the **specific
presence** of that call in the dev-machine case. Exit code alone is insufficient —
the displacement is defined by whether the bootstrap container is created.

## Test Verification (NON-NEGOTIABLE)

Run **only** your new file:

```bash
uv run pytest tests/unit/test_db_start_guard.py -v
```

Do **NOT** run `make test-unit` / `make test-integration` — those are downstream
QV gates with their own budgets. Do not report `tests_passed: true` unless all
your tests pass. Do not perform a manual `git checkout`/`git stash` RED-revert of
`ai-core.sh` — the bug was already proven at design time; just confirm your tests
pass against the fixed script.

## Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00122",
  "completion_status": "complete",
  "files_changed": ["tests/unit/test_db_start_guard.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "3 passed, 0 failed",
  "tdd_red_evidence": "n/a — fix already implemented in S01; tests assert post-fix behaviour and specific compose-call presence/absence",
  "blockers": [],
  "notes": "Document how db_ready up/down was forced."
}
```
