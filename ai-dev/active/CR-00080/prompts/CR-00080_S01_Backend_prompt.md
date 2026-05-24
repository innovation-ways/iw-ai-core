# CR-00080_S01_Backend_prompt

**Work Item**: CR-00080 -- Widen mutmut mutation-testing scope from `orch/daemon/` to all of `orch/`, run a second spike, and flip the mutation gate from informational to blocking
**Step**: S01
**Agent**: Backend

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY of the following commands or any command that
changes Docker container/volume/network state:

  docker kill | docker stop | docker rm | docker restart
  docker compose up | docker compose down | docker compose restart
  docker-compose up | docker-compose down | docker-compose restart
  docker volume rm | docker volume prune
  docker system prune | docker container prune | docker image prune

The orchestration database, daemon, dashboard, and any long-lived
infrastructure containers are outside your scope. Touching them can
cause multi-hour outages and data loss (see the 2026-04-22 incident in
docs/IW_AI_Core_DB_Setup.md).

Allowed exceptions:

  1. Testcontainers spun up by pytest fixtures (they self-label and
     self-destruct via Ryuk).
  2. Read-only introspection: `docker ps`, `docker inspect`, `docker logs`.
  3. Invoking `./ai-core.sh` or `make` targets — those know which
     commands are safe.

If your task seems to require a prohibited command, STOP and raise a
blocker. Do not work around this rule.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

You MUST NOT run the following alembic commands against the live
orchestration DB (port 5433) from an agent context:

```
alembic upgrade head
alembic upgrade <revision>
alembic downgrade <anything>
alembic stamp <anything>
```

This step does not touch migrations at all. If you find yourself reaching for
alembic, STOP — you are out of scope.

Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00080 --json` (canonical, do NOT trust the design-time manifest snapshot).
- `ai-dev/active/CR-00080/CR-00080_CR_Design.md` -- Design document
- `pyproject.toml` -- contains the `[tool.mutmut]` block (lines 248-257 at design time)
- `Makefile` -- contains the `mutation-check` / `mutation-audit` / `mutation-results` / `mutation-show` targets
- `tests/unit/test_mutmut_setup.py` -- RED-first guard test from CR-00059
- `ai-dev/active/CR-00059/` (if still present) -- prior spike measurements (peer evidence; the directory may have been archived to `ai-dev/archive/CR-00059/`)
- `ai-dev/work/TESTS_ENHANCEMENT.md` -- tracker (read-only in this step; updated in S03)

## Output Files

- `pyproject.toml` -- widened `paths_to_mutate` + runner cov-fail-under override + rewritten comment block
- `Makefile` -- updated `mutation-audit` loop iterating `orch/**/*.py` + cov-fail-under override on the inner pytest invocation
- `tests/unit/test_mutmut_setup.py` -- assertion extended for the new `"orch/"` scope
- `ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt` -- second-spike measurements (total wall-clock, mutants generated / killed / surviving, mutation score, per-module breakdown)
- `ai-dev/work/CR-00080/reports/CR-00080_S01_Backend_report.md` -- Step report

## Context

You are implementing part of **Widen mutmut mutation-testing scope from `orch/daemon/` to all of `orch/`, run a second spike, and flip the mutation gate from informational to blocking**.

Read the design document first (especially Current Behavior, Desired Behavior, AC1, and the Notes section explaining the cost-of-spike risk). Then read `CLAUDE.md` for project-specific patterns and conventions.

The CR-00059 spike measured 0:17:17 wall-clock on `orch/daemon/` but generated **0 mutants** because every module-level mutmut invocation hit `FAIL Required test coverage of 50.0% not reached` from pytest before any mutant could execute. Your first job is to fix that interaction, then widen the scope, then re-spike.

## Requirements

### 1. Fix the pytest cov-fail-under interaction

The current `Makefile` `mutation-check` and `mutation-audit` recipes invoke `uv run pytest tests/unit/daemon/ tests/integration/daemon/ -x --tb=no -q` as the mutmut runner. pytest reads `[tool.coverage.report] fail_under` (or equivalent) from `pyproject.toml` and fails the test session when total coverage drops below the floor. During mutation testing this fails the runner on the first mutant before the assertion check runs.

Fix this in one of two ways (pick one and document your choice in the step report):

- **Option A (preferred)**: pass `--cov-fail-under=0` on the inner pytest invocation inside the mutmut runner string (in `pyproject.toml` `[tool.mutmut].runner` AND in the `Makefile` recipes that build their own runner string).
- **Option B**: add a mutmut-specific `pyproject.toml` override (e.g., set `addopts` for the mutmut runner context only). This is fragile if mutmut spawns a fresh interpreter — verify it actually applies before relying on it.

Verify the fix BEFORE the wider widen: run `make mutation-check MODULE=orch/daemon/main.py` (one small module from the existing scope). Confirm that mutmut now reports a non-zero mutant count and that pytest no longer dies with the cov-fail-under error.

### 2. Widen `paths_to_mutate` from `orch/daemon/` to `orch/`

Edit `pyproject.toml` lines 248-257:
- `paths_to_mutate = "orch/"` (was `"orch/daemon/"`)
- Rewrite the comment block above `[tool.mutmut]`: replace the `(currently scoped to orch/daemon/; expand in follow-up CR P2-CR-A-followup-mutation-block)` text with a CR-00080 reference and the new wall-clock / score numbers (write these AFTER the spike runs in Requirement 4).

Edit `Makefile` `mutation-audit` recipe:
- Change `$(find orch/daemon/ -name "*.py" …)` to `$(find orch/ -name "*.py" -not -name "__init__.py" -not -path "*/__pycache__/*" -not -path "*/migrations/*" | sort)`. **Exclude `orch/db/migrations/`** explicitly — there is no useful mutation testing on alembic revision files (they are atomically committed schema state).
- Update the runner string inside the audit loop to include the cov-fail-under override.

### 3. Extend the RED-first guard test

Edit `tests/unit/test_mutmut_setup.py` so the assertion accepts the new `"orch/"` value.

**TDD RED-first**: change the assertion FIRST (before touching `pyproject.toml`), run targeted (`uv run pytest tests/unit/test_mutmut_setup.py -v`), CONFIRM the failure is `AssertionError: assert 'orch/daemon/' == 'orch/'` (or equivalent), capture that line for `tdd_red_evidence` in your result contract. THEN apply the `pyproject.toml` widening to make it GREEN, re-run the targeted test, confirm pass.

### 4. Run the second spike on the widened scope

Run `make mutation-audit` end-to-end on the widened scope.

**Do NOT pre-prime with `make test-unit` or `make test-integration`.** Those duplicate QV gates S10/S11 (wasted budget) and do not populate `.mutmut-cache` — `.mutmut-cache` is mutmut-owned, built by `mutmut run` itself, not by pytest. The first spike on a fresh worktree is always cold by design. Persistent `.mutmut-cache` across runs ("cache-warm-from-`main`") is a future optimisation for the nightly workflow (out of scope for this CR).

The wall-clock budget for this step is **3600 seconds**. If `mutation-audit` is still running at the 60-minute mark, capture whatever partial output exists and pivot to reporting `completion_status: partial` with the partial measurements. S02's AC3 viability guard handles thin data — if `M < 20%` OR `(killed + survived) < 30`, S02 deliberately refuses to wire the gate and reports `blocked`, so a partial spike does not silently produce a meaningless threshold.

Write the measurement file at `ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt` with this structure:

```
CR-00080 second mutmut spike — widened scope (orch/)
Date: <YYYY-MM-DD>
Commit: <git rev-parse HEAD>
Runner: <exact runner string from pyproject.toml>
Cache: cold (fresh worktree; .mutmut-cache built during this run)

Wall-clock total: HH:MM:SS
Mutants generated: <N>
Mutants killed:    <N> (<pct>%)
Mutants survived:  <N> (<pct>%)
Mutants timeout:   <N>
Mutants skipped:   <N>
Mutation score:    <N>%  (killed / (killed + survived))
Viability inputs:  M=<score>%, K=(killed + survived)=<N>

Per-module breakdown:
orch/<module>.py    generated=<N> killed=<N> survived=<N> score=<pct>%
...
```

If you only have partial data (timeout at 3600s), include `[PARTIAL — terminated at <wall-clock> while processing orch/<module>.py]` at the top.

### 5. Update the pyproject.toml comment block

After the spike completes, finalise the comment block above `[tool.mutmut]` to cite this CR (`CR-00080`) and the spike numbers (or "[PARTIAL — see evidence file]" if partial).

## Project Conventions

Read the project's `CLAUDE.md` for:

- Architecture patterns and layer boundaries
- Coding conventions and naming rules
- Build and run commands (`make` targets, `uv run` patterns)
- Test organization and fixtures

Follow all rules defined there exactly. When in doubt, match existing code in the repository.

## TDD Requirement

Follow TDD (Red-Green-Refactor):

1. **RED**: Change `tests/unit/test_mutmut_setup.py` first to assert the new `"orch/"` scope. Run `uv run pytest tests/unit/test_mutmut_setup.py -v` and **confirm the failure is `AssertionError`** (not `ImportError`, not `SyntaxError`, not a fixture error). Capture the failing line for `tdd_red_evidence`.
2. **GREEN**: Apply the `pyproject.toml` widening + the cov-fail-under fix.
3. **REFACTOR**: Trim the Makefile audit loop / runner-string duplication where reasonable; do NOT refactor anything outside the mutation-target recipes.

Do not skip the RED phase.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Before reporting `completion_status: complete`, you MUST run these in order and fix any issues they report:

1. **`make format`** — auto-fixes formatting drift on touched files (`pyproject.toml`, `Makefile`, `tests/unit/test_mutmut_setup.py`).
2. **`make typecheck`** — must report zero errors involving the files you touched. (Errors elsewhere are pre-existing — note in your report but do not ignore your own.)
3. **`make lint`** — must report zero errors.

If a tool isn't available in your worktree, STOP and raise a blocker — do not silently skip.

## Test Verification (NON-NEGOTIABLE)

Run only the test files you touched. **DO NOT** run the full unit or integration suites — those are S10/S11 QV gates.

```bash
uv run pytest tests/unit/test_mutmut_setup.py -v
```

That is sufficient. Do NOT run `make test-unit` or `make test-integration` — they are dedicated QV gates downstream with their own (longer) budgets.

The spike itself (`make mutation-audit`) is the integration evidence — it lives under `evidences/pre/`, not as a recurring test.

## Subagent Result Contract

When your work is complete, report results in this JSON structure:

```json
{
  "step": "S01",
  "agent": "Backend",
  "work_item": "CR-00080",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "pyproject.toml",
    "Makefile",
    "tests/unit/test_mutmut_setup.py",
    "ai-dev/active/CR-00080/evidences/pre/cr-00080-spike-measurements.txt"
  ],
  "preflight": {
    "format": "ok|fixed|skipped:<reason>",
    "typecheck": "ok|skipped:<reason>",
    "lint": "ok|skipped:<reason>"
  },
  "tests_passed": true,
  "test_summary": "1 passed, 0 failed (test_mutmut_setup.py)",
  "tdd_red_evidence": "tests/unit/test_mutmut_setup.py::test_paths_to_mutate_is_orch — AssertionError: assert 'orch/daemon/' == 'orch/'  // captured RED run before widening pyproject.toml",
  "blockers": [],
  "notes": "Spike completed in <HH:MM:SS> wall-clock; <N> mutants generated; mutation score <pct>%. Chose Option A (--cov-fail-under=0 in runner string). See evidence file for full per-module breakdown."
}
```

- `completion_status: partial` is acceptable if the spike timed out at 3600s — record the partial wall-clock + the count of mutants generated so far in `notes` and ensure the evidence file carries the `[PARTIAL — terminated at <wall-clock>]` prefix. S02 will apply the viability guard against whatever `M` / `K` you produce; if your data is too thin, S02 reports `blocked` and the gate is not wired (this is the design's intentional safety rail, not a failure of S01).
- `blockers`: list anything that prevents either (a) fixing the cov-fail-under bug, (b) widening to `orch/`, or (c) writing the evidence file.
