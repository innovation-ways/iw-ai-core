# CR-00072_S02_CodeReview_prompt

**Work Item**: CR-00072 — Contract / No-5xx Route Sweep + schemathesis Fuzzing
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state (`docker kill|stop|rm|restart`, `docker compose up|down|restart`,
`docker volume rm|prune`, `docker system prune`, …). Allowed: testcontainers via
pytest fixtures; read-only `docker ps|inspect|logs`; `./ai-core.sh` and `make`
targets. If your task seems to require a prohibited command, STOP and raise a
blocker. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

CR-00072 adds no migration. If you find a migration file in the changeset, that
is a **CRITICAL** scope violation. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## Input Files

- **Runtime step state** — prefer `uv run iw item-status CR-00072 --json`.
- `ai-dev/work/CR-00072/CR-00072_CR_Design.md` — design document.
- `ai-dev/work/CR-00072/reports/CR-00072_S01_Backend_report.md` — S01 report.
- All files listed in the S01 report's `files_changed`.

## Output Files

- `ai-dev/work/CR-00072/reports/CR-00072_S02_CodeReview_report.md` — review report.

## Context

You are reviewing the S01 implementation of CR-00072 — a test-infrastructure CR
that adds a no-5xx route-contract sweep and a nightly schemathesis fuzz module.
Read the design document first (especially the Acceptance Criteria and TDD
Approach sections), then the S01 report, then every changed file.

## Read the Design Document FIRST

Read `## Acceptance Criteria` (AC1–AC6) and `## TDD Approach` in full. Every AC
is a mandatory check. Note the two test files the design names by path
(`tests/dashboard/test_route_contract_sweep.py`,
`tests/dashboard/test_schemathesis_contract.py`) — both MUST appear in S01's
`files_changed`; a missing one is **CRITICAL**.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run `make lint` and `make format-check` on the changed files. Fix nothing — only
report. Any NEW violation (not on `main` before S01) is a **CRITICAL** finding
with `category: conventions`, the file/line, and the exact code+message. Also run
`make test-assertions` — a new assertion-scanner violation in either new test
file is **CRITICAL**. If a command is unavailable, STOP and raise a blocker.

## Review Checklist

### 1. Scope discipline (CRITICAL category)

- **No production code touched.** The only files changed must be within
  `scope.allowed_paths`: the two new test files, possibly `tests/dashboard/conftest.py`
  and `tests/fixtures/**`, `.github/workflows/contract-fuzz.yml`, `pyproject.toml`,
  `uv.lock`, `Makefile`, `docs/IW_AI_Core_Testing_Strategy.md`,
  `skills/iw-ai-core-testing/**`, `.claude/skills/iw-ai-core-testing/**`,
  `ai-dev/work/TESTS_ENHANCEMENT.md`. Any edit to `orch/`, `dashboard/`,
  `executor/`, `scripts/` is a **CRITICAL** scope violation — including a
  "fix" for a 5xx the sweep found (those must be allowlisted, not fixed; see AC5).
- **No deliberate-break injection left behind.** S01's TDD demonstration
  registers throwaway, deliberately-5xx routes on the *test* app (it never edits
  production code), then removes them. Confirm via
  `git diff origin/main -- dashboard/ orch/` that it is **empty**, and that no
  throwaway `/__cr72_selfcheck__`-style route remains in the committed test
  files. Any production-code edit, or a residual throwaway route, is
  **CRITICAL**.

### 2. AC1 — route sweep correctness

- The sweep enumerates `app.routes` and exercises every GET/HEAD route minus a
  documented skip set.
- The `TestClient` is constructed with **`raise_server_exceptions=False`** — if
  it is `True`, the sweep cannot observe a 500 and AC1 is not met → **CRITICAL**.
- Each case asserts `response.status_code < 500`. The assertion is real and would
  fail on a regression (it is not `assert response is not None` or similar).
- The sweep is parametrized one case per route; failures name the route.
- The skip set is a documented constant with a per-entry rationale; SSE/streaming
  routes are skipped (a sweep that GETs an SSE route hangs).
- `UNRESOLVED` path-param routes are asserted against an explicit expected set,
  not silently dropped.

### 3. AC3 — schemathesis module + marker exclusion

- `schemathesis` is in `[dependency-groups] dev`, pinned to a real current major;
  `uv.lock` is regenerated and consistent.
- The module is marked `contract_fuzz`; the marker is registered in
  `pyproject.toml` `[tool.pytest.ini_options].markers`.
- `addopts` excludes `contract_fuzz` (`-m 'not browser and not quarantine and not contract_fuzz'`),
  `--strict-markers` and all other flags intact.
- Verify the exclusion actually works:
  `uv run pytest tests/dashboard/test_schemathesis_contract.py --collect-only -q`
  must collect **zero** tests. If it collects them, the nightly fuzzer would run
  in the blocking suite → **HIGH**.
- schemathesis is restricted to the JSON API operations (those whose OpenAPI
  response declares an `application/json` media type — keep-alive API,
  runtime-overrides, JSON job endpoints) — it does not fuzz HTML/htmx routes.

### 4. AC4 — nightly workflow

- `.github/workflows/contract-fuzz.yml` triggers on `schedule` + `workflow_dispatch`
  only — **never** `push` / `pull_request` (that would run the slow fuzzer on
  every PR) → **HIGH** if it does.
- The job runs `make test-contract-fuzz` and is non-failing during burn-in
  (`continue-on-error: true`).
- The environment setup is coherent with `test-quality.yml`'s integration job
  (the testcontainer fixtures need Docker / Python / uv available).

### 5. AC5 — genuine 5xx handled correctly

- If S01's report lists `EXPECTED_5XX` entries, each must have a
  `TODO(file-incident)` placeholder and a one-line rationale, and the
  corresponding case must be `xfail`-ed — not deleted, not skipped silently.
  Each must also be surfaced as operator follow-up in the S01 report (so the
  operator files the Incident on `main` post-merge). S01 must NOT have run
  `/iw-new-incident` or created an incident package inside the worktree — an
  `ai-dev/active/I-NNNNN/**` path in the changeset is a **CRITICAL** scope
  violation. An allowlisted route with no placeholder, no rationale, or not
  listed for the operator is **HIGH**.
- The sweep exits 0 on current `main` (S01's `test_summary` should show passes +
  xfails, 0 unexpected failures).

### 6. AC6 — docs / skill / plan

- `docs/IW_AI_Core_Testing_Strategy.md` describes the contract layer (§3/§5/§9).
- `skills/iw-ai-core-testing/SKILL.md` notes the layer + how to extend it.
- `.claude/skills/iw-ai-core-testing/SKILL.md` is **byte-identical** to the
  master (`diff` them — a mismatch means `iw sync-skills --force` was not run →
  **HIGH**).
- `ai-dev/work/TESTS_ENHANCEMENT.md`: item 3.2 → DONE (CR-00072); a §11
  changelog entry exists; counts in the changelog match the S01 report.

### 7. Test quality & isolation

- Both new tests use the testcontainer `db_session` — never the live DB.
- Tests are order-independent (`pytest-randomly` is on by default). Seeding
  happens per-test/per-fixture; no reliance on another test's state.
- Assertions are behavioural and strong — re-read `skills/iw-ai-core-testing/SKILL.md`'s
  red-flag checklist and apply it.

## TDD RED Evidence

S01 is a test-infrastructure step. Confirm `tdd_red_evidence` records the
**deliberate-break demonstration** for both new tests (a route case failing on a
throwaway 5xx route registered on the test app; schemathesis reporting a 5xx on a
throwaway JSON route) — this is the "every test must be able to fail" proof. If
`tdd_red_evidence` is missing or just says `n/a` with no demonstration, raise a
**HIGH** finding: a route sweep that cannot be shown to fail is worthless.

## Test Verification (NON-NEGOTIABLE)

Run the project's unit test command to confirm no regressions, plus the two new
files:

```bash
uv run pytest tests/dashboard/test_route_contract_sweep.py -v --no-cov
uv run pytest tests/dashboard/test_schemathesis_contract.py -m contract_fuzz -v --no-cov
```

Report results accurately in the contract.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| **CRITICAL** | Breaks functionality, scope violation, residual injection, security issue |
| **HIGH** | Significant bug, missing AC, fuzzer would run in the blocking suite |
| **MEDIUM (fixable)** | Code-quality / convention issue, weak assertion |
| **MEDIUM (suggestion)** | Better pattern available |
| **LOW** | Nitpick |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "CR-00072",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [
    {
      "severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION|LOW",
      "category": "architecture|code_quality|conventions|security|testing",
      "file": "path/to/file.py",
      "line": 42,
      "description": "What the issue is",
      "suggestion": "How to fix it"
    }
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

- `verdict`: `pass` only if zero CRITICAL/HIGH and zero MEDIUM (fixable).
- `mandatory_fix_count`: CRITICAL + HIGH + MEDIUM (fixable).
