# F-00073_S02_CodeReview_prompt

**Work Item**: F-00073 -- Smoke Gate + Active Test CI + Logging Tests
**Step Being Reviewed**: S01
**Review Step**: S02

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `uv run iw item-status F-00073 --json`
- `ai-dev/active/F-00073/F-00073_Feature_Design.md`
- `ai-dev/active/F-00073/reports/F-00073_S01_Backend_report.md`
- `pyproject.toml`, `Makefile`
- `.github/workflows/test-quality.yml`
- `tests/unit/test_logging.py`
- All test files modified (smoke marker additions)

## Output Files

- `ai-dev/active/F-00073/reports/F-00073_S02_CodeReview_report.md`

## Review Checklist

### 1. Smoke marker

- [ ] `smoke` registered in `[tool.pytest.ini_options] markers`.
- [ ] Existing `integration` marker preserved.
- [ ] `pytest --strict-markers -m smoke` does not warn about unknown markers.

### 2. Smoke set quality

- [ ] At least 10 tests collected under `pytest -m smoke --collect-only`.
- [ ] Each smoke test runs in <5s wallclock (verify by reading S01 report's `smoke_test_inventory.wallclock_ms`).
- [ ] Total smoke wallclock <60s.
- [ ] Each test on the design's smoke list has a corresponding marked test (cross-reference S01 report).
- [ ] Markers are additive — existing markers preserved.
- [ ] No smoke test depends on a live network connection or external API.

### 3. Make target

- [ ] `make smoke` exists.
- [ ] Uses `--strict-markers` (catches typos).
- [ ] Doesn't collect coverage (speed > measurement) — `--no-cov` or equivalent.
- [ ] `.PHONY` updated.

### 4. Logging tests

- [ ] `tests/unit/test_logging.py` exists.
- [ ] Asserts on EXISTING behavior (no test that pretends a non-existent helper exists).
- [ ] Credential-leak check is real — passes against current code OR raises a blocker if a leak was found.
- [ ] If a leak was found, S01 report's `logging_test_findings` lists it and `completion_status` is `blocked`.

### 5. CI workflow

- [ ] File at `.github/workflows/test-quality.yml`.
- [ ] Triggers: PR + push to main.
- [ ] Permissions: `contents: read` only.
- [ ] Four jobs: lint-typecheck, unit, integration, smoke.
- [ ] Coverage XML artefact uploaded with `if: always()`.
- [ ] All `uses:` pinned to 40-char SHAs with `# vN.N.N` comments.
- [ ] Postgres service container major matches `docker-compose.bootstrap.yml`.
- [ ] Smoke + integration jobs both have the Postgres service.
- [ ] No Codecov upload (skipped per design).
- [ ] `IW_CORE_DB_PORT: "5433"` matches production port for tests that introspect it.

### 6. Dependency on F-00069

- [ ] Workflow's unit job runs `make test-unit` which consumes F-00069's threshold.
- [ ] No accidental override of F-00069's coverage config.
- [ ] `make smoke` doesn't conflict with F-00069's xdist parallelism (the smoke target is serial — if it inherits xdist via addopts, override with `-n 0` or `-p no:xdist`).

### 7. Conventions

- Read `CLAUDE.md`, `tests/CLAUDE.md`, `compliance-scan.yml` patterns.

## Test Verification

- `make lint`, `make typecheck`, `make test-unit`, `make smoke`, `make test-integration`.

## Severity Levels

| Severity | Meaning |
|---|---|
| CRITICAL | Action versions not pinned; permissions overly broad; credential leak ignored; smoke marker shadows production code |
| HIGH | Missing required smoke test; missing CI job; logging test bypassed |
| MEDIUM (fixable) | Smoke wallclock approaching 60s ceiling; missing artefact upload; missing strict-markers |
| MEDIUM (suggestion) | Reorganise smoke tests for clarity |
| LOW | Comment style |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "F-00073",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "",
  "notes": ""
}
```
