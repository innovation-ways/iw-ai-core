# F-00073: Smoke Gate + Active Test CI + Logging Tests

**Type**: Feature
**Priority**: High
**Created**: 2026-04-29
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainers in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

This feature does NOT modify migrations.

## Description

Add a `@smoke` pytest marker for ~10 lightweight critical-path tests
that prove the system is alive in under a minute, expose them as
`make smoke`, and stand up an active GitHub Actions workflow
(`test-quality.yml`) that runs lint + typecheck + unit + integration +
smoke on every PR — consuming the coverage gate established by F-00069.
Add explicit logging tests under `tests/unit/test_logging.py` to guard
the observability hooks. Together these make broken-on-main impossible
without the daemon noticing.

## Project Context

Read `CLAUDE.md`, `tests/CLAUDE.md`, and `dashboard/CLAUDE.md`.

Existing CI workflows:
- `codeql.yml` — SAST
- `compliance-scan.yml` — gitleaks + OSS compliance
- `scorecard.yml` — OpenSSF Scorecard
- `release-please.yml` — release automation

NONE of these run the unit/integration/quality test suite. This feature
adds that coverage.

## Scope

### In Scope

1. **`@smoke` pytest marker registration**
   - Add `smoke: marks tests as fast critical-path smoke tests` to
     `[tool.pytest.ini_options] markers` in `pyproject.toml`.
   - The marker MUST be additive — preserve the existing `integration`
     marker.

2. **~10 smoke tests** — distributed under `tests/unit/` and
   `tests/integration/` using existing test files where possible (don't
   create a new top-level smoke directory; mark existing tests when a
   suitable one exists, write new ones only when no existing test
   covers the path):

   The smoke set, finalised in the planning conversation 2026-04-29:
   - **Dashboard cold start** — FastAPI app factory creates without error.
   - **`/healthz/identity`** — returns 200 (or 503 in bootstrap mode) with the expected JSON shape.
   - **Project list** — GET `/projects` (or the actual project list URL — verify) returns 200 with at least the registered projects in the response.
   - **Queue / History list** — GET the project queue page; renders 200 with no template errors.
   - **Batch creation** — `iw batch-create` against a fixture work item creates a row in DB with status=pending.
   - **Daemon SIGHUP** — sending SIGHUP to the daemon process triggers a project-registry reload (mock the signal at the unit level; do not actually fork the daemon).
   - **`iw db-identity check`** — succeeds against the testcontainer with a matching `IW_CORE_EXPECTED_INSTANCE_ID`.
   - **CLI `iw --help`** — exits 0 and prints something sensible.
   - **Models import** — `from orch.db.models import Base` works without raising.
   - **Coverage view-model** — `dashboard.services.coverage_service.load_coverage()` returns an empty-state view when file missing (this also smoke-checks F-00069's deliverable).

   Each smoke test runs in <2s typical. The combined suite target: <30s wallclock.

   Tests are marked with `@pytest.mark.smoke` (in addition to any other marker they already carry — e.g. `@pytest.mark.integration`).

3. **`make smoke` target**
   - Runs `uv run pytest -m smoke -v`.
   - No coverage collection on this target (smoke is for speed, not measurement).
   - `.PHONY` updated.

4. **`tests/unit/test_logging.py`**
   - Asserts the project's logging is configured at INFO level by default
     in dashboard and daemon entrypoints.
   - Asserts `logging.getLogger("orch")` and `logging.getLogger("dashboard")`
     have parents that propagate to the root configuration.
   - Asserts that credentials in DB URLs are redacted by any logging that
     touches the URL (verify by inspecting the relevant code paths in
     `orch/config.py` / `orch/db/session.py` and writing a test that runs
     the redaction function over a URL containing a password and asserts
     the password substring is absent from the redacted output).
   - If no redaction helper exists today, the test should ASSERT that
     credentials in `IW_CORE_DB_PASSWORD` do not appear in the rendered
     `repr()` of `engine.url` or in the formatted log of the engine creation.
     If they DO leak, the test fails — exposing a real observability bug
     for follow-up.

5. **`.github/workflows/test-quality.yml`**
   - Triggers: `pull_request` to main, `push` to main.
   - Permissions: `contents: read`.
   - One job (or split as makes sense):
     - **lint-typecheck**: runs `make lint`, `make format-check`, `make typecheck`.
     - **unit**: runs `make test-unit` (which under F-00069 collects coverage and enforces the `--cov-fail-under` threshold).
     - **integration**: runs `make test-integration` against a Postgres service container (matching production major version per `docker-compose.bootstrap.yml`).
     - **smoke**: runs `make smoke` — fast critical-path gate; runs in parallel with integration.
   - Coverage XML artefact uploaded as a workflow artefact (no Codecov upload — explicitly skipped per user decision 2026-04-29).
   - All `uses:` pinned to 40-char SHAs with `# vN.N.N` trailing comments per `compliance-scan.yml` convention.
   - `set -euo pipefail` in run-step shells.

6. **Smoke regression guard test** — add to existing
   `tests/unit/test_make_targets.py` from F-00069 (or create if absent):
   - Asserts `make smoke` target exists in Makefile.
   - Asserts `[tool.pytest.ini_options] markers` includes `smoke`.
   - Asserts `.github/workflows/test-quality.yml` exists.
   - Asserts the workflow runs `make test-unit`, `make test-integration`,
     `make smoke`.

### Out of Scope

- Codecov / external coverage upload (explicitly skipped per user decision 2026-04-29).
- Parallel test execution (`pytest-xdist` lives in F-00069 — already shipped when this feature runs).
- Coverage threshold enforcement (set up in F-00069).
- Pre-commit hooks (F-00070).
- Security scanning (F-00071).
- Migration roundtrip test or schema-validation workflow (F-00072).
- Performance/load testing.
- Mutation testing.
- New observability infrastructure (the logging tests assert what already exists; they do not add metrics, traces, or new sinks).

## Implementation Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | backend-impl | pyproject markers, ~10 smoke tests (mark or write), make smoke target, tests/unit/test_logging.py, test-quality.yml workflow | — |
| S02 | code-review-impl | Review S01 (markers + smoke tests + workflow + logging tests) | — |
| S03 | tests-impl | Smoke regression guard (extend tests/unit/test_make_targets.py from F-00069 or create) | — |
| S04 | code-review-impl | Review S03 | — |
| S05 | code-review-final-impl | Cross-cutting global review | — |
| S06–S11 | qv-gate | lint, format, typecheck, unit-tests, integration-tests, smoke | — |

No frontend / browser verification.

### Database Changes

None.

### API Changes

None.

### Frontend Changes

None.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `ai-dev/active/F-00073/F-00073_Feature_Design.md` | Design | This document |
| `ai-dev/active/F-00073/workflow-manifest.json` | Manifest | Step definitions |
| `ai-dev/active/F-00073/prompts/F-00073_S01_Backend_prompt.md` | Prompt | S01 implementation |
| `ai-dev/active/F-00073/prompts/F-00073_S02_CodeReview_prompt.md` | Prompt | Review of S01 |
| `ai-dev/active/F-00073/prompts/F-00073_S03_Tests_prompt.md` | Prompt | Smoke regression guard |
| `ai-dev/active/F-00073/prompts/F-00073_S04_CodeReview_Tests_prompt.md` | Prompt | Review of S03 |
| `ai-dev/active/F-00073/prompts/F-00073_S05_CodeReview_Final_prompt.md` | Prompt | Final review |
| `pyproject.toml` | Modified | Add `smoke` to markers list |
| `Makefile` | Modified | Add `make smoke` target |
| `tests/unit/test_logging.py` | New | Logging configuration + credential-redaction tests |
| `tests/**` (various) | Modified | Add `@pytest.mark.smoke` to ~10 critical-path tests |
| `.github/workflows/test-quality.yml` | New | Active CI for lint/typecheck/unit/integration/smoke |
| `tests/unit/test_make_targets.py` | Modified | Smoke regression guard additions |

## Acceptance Criteria

### AC1: Smoke target works locally

```
Given the developer has run `uv sync`
When `make smoke` is invoked
Then the suite runs in under 60 seconds wallclock on a typical workstation
And exits 0 on a healthy checkout
And exits non-zero with a clear pytest summary if any smoke test fails
```

### AC2: Smoke covers the planned critical paths

```
Given F-00073 is merged
When the developer runs `pytest -m smoke --collect-only -q`
Then at least 10 tests are collected
And the set covers: dashboard cold start, /healthz, project list, queue render,
    batch creation, daemon SIGHUP, db-identity check, CLI --help,
    models import, coverage view-model
```

### AC3: CI workflow runs on PRs

```
Given a PR is opened against main
When the test-quality.yml workflow triggers
Then lint, typecheck, unit, integration, and smoke jobs all run
And coverage XML is uploaded as a workflow artefact
And the PR is blocked if any job fails
And action `uses:` are all pinned to 40-char SHAs
```

### AC4: Logging tests pass and assert real behavior

```
Given the existing logging configuration
When `pytest tests/unit/test_logging.py` runs
Then the tests pass against the current code
And if a future change strips credential redaction from a log path,
    test_logging fails immediately with a message identifying the path
```

### AC5: Smoke regression guard catches deletions

```
Given a developer accidentally removes `make smoke` or the smoke marker
When `make test-unit` runs
Then tests/unit/test_make_targets.py fails with a clear message
```

### AC6: No regressions

```
Given F-00073 is merged
When `make check` runs (full quality + tests)
Then all pre-existing tests still pass
And the new tests pass
And total CI wallclock for test-quality.yml is under 10 minutes
```

## Boundary Behavior

| Scenario | Input/State | Expected Behavior |
|----------|-------------|-------------------|
| `make smoke` run with no smoke tests collected | All markers stripped | pytest exits with "no tests ran" — Makefile target treats this as failure (use `--strict-markers` or `-rN` to surface it) |
| Smoke test depends on testcontainer | Integration-marked smoke test | Must spin up testcontainer; if Docker missing, test FAILS rather than skips silently (matches the live-DB-guard ethos) |
| CI run on a fork PR | No write secrets | Workflow runs in read-only mode; no artefact upload failure |
| One smoke test exceeds 5s | Slowness drift | pytest doesn't time out, but flag in S01 report; consider whether the test still belongs in smoke |
| Logging test detects credential leak | Real bug uncovered | Test FAILS — do NOT bypass; raise a blocker so the leak is fixed before this feature lands |
| Coverage threshold from F-00069 not in pyproject | Dependency not yet merged | Smoke job in CI still works (no coverage on smoke); unit job will fail to find threshold — make sure design doc's `Depends on: F-00069` is honored by the batch executor |

## Invariants

1. The `smoke` marker is registered in `pyproject.toml` so `pytest --strict-markers` doesn't fail.
2. Every smoke test runs in < 5 seconds wallclock; the full smoke set in < 60 seconds.
3. CI workflow `permissions:` is `contents: read` only.
4. All `uses:` in `test-quality.yml` are pinned to 40-char SHAs.
5. The unit job in CI consumes the coverage threshold from F-00069's `pyproject.toml` — DO NOT shadow or override it.
6. `make smoke` does NOT collect coverage (speed > measurement).
7. Logging tests assert against EXISTING behavior; if a logging test fails on first run, the failure is a real bug to fix (raise blocker), not a test bug to weaken.
8. Smoke tests use the same testcontainer fixtures as integration tests when DB is needed; no new live-DB connections.

## Dependencies

- **Depends on**: F-00069 (provides `make test-parallel`, the coverage threshold floor in `pyproject.toml`, and the coverage_service whose empty-state path is one of the smoke tests). The batch executor MUST run F-00069 before F-00073.
- **Blocks**: None

## TDD Approach

- **Smoke tests** — write each one RED first by deliberately breaking the system path it covers (e.g. comment out the project list route handler), confirm the test fails clearly, then revert.
- **Logging tests** — write RED by stubbing out the redaction logic, confirm test fails, restore.
- **Smoke regression guard** — strip `make smoke` from Makefile, confirm guard fails, restore.

## Notes

- Some of the tests on the smoke list may already exist in the repo; the right move is to ADD `@pytest.mark.smoke` to them rather than duplicate. S01's report MUST list which smoke tests reused existing tests vs were new.
- The CI workflow runs `make test-integration` which requires Postgres — use a service container at the version matching `docker-compose.bootstrap.yml` (introspect at S01 time; likely `postgres:16` or whatever production runs).
- This feature explicitly skips Codecov per user decision 2026-04-29; coverage XML is uploaded only as a workflow artefact, not as a PR comment. If we later want PR comments, that's a future CR.
- Total batch picture once all 5 features land:
  - F-00069 → coverage gate + dashboard + parallel exec (foundation)
  - F-00070 → pre-commit hardening (independent)
  - F-00071 → security scanning (independent)
  - F-00072 → migration safety + schema validation (independent)
  - F-00073 → smoke gate + test CI (this) — depends on F-00069
- The batch executor will run F-00069/70/71/72 in wave 1 and F-00073 in wave 2.
