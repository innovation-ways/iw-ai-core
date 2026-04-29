# F-00069_S03_CodeReview_Backend_prompt

**Work Item**: F-00069 -- Test Execution, Coverage Gate, Reports, and Coverage Dashboard View
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S03

---

## ⛔ Docker is off-limits

(Standard policy applies.)

## ⛔ Migrations: agents generate, daemon applies

S01 does not modify migrations. Confirm none were touched.

## Input Files

- `uv run iw item-status F-00069 --json` — runtime step state
- `ai-dev/active/F-00069/F-00069_Feature_Design.md`
- `ai-dev/active/F-00069/reports/F-00069_S01_Backend_report.md`
- All files listed in S01's `files_changed`

## Output Files

- `ai-dev/active/F-00069/reports/F-00069_S03_CodeReview_report.md`

## Context

You are reviewing S01's backend implementation: pyproject.toml + Makefile
+ .gitignore changes; new `dashboard/services/coverage_service.py`;
new `dashboard/routers/coverage.py`; `dashboard/app.py` registration;
the `scripts/e2e_health_check.py` helper; and the design doc's
"Baseline Coverage Snapshot" being filled in.

## Review Checklist

### 1. Pyproject / Coverage config

- [ ] `pytest-xdist>=3.5.0` added to `[dependency-groups] dev`.
- [ ] `[tool.pytest.ini_options] addopts` includes `--cov=orch --cov=dashboard --cov=executor` and the four report flags (term-missing, html, xml, json) all writing under `tests/output/coverage/`.
- [ ] `[tool.coverage.run]` block present with `source`, `omit` (migrations, tests, scripts, bin), and `branch = true`.
- [ ] `[tool.coverage.report] fail_under = N` present, where N matches the design's "floor = floor(baseline) - 5" formula and the S01 report's `floor_percent`.
- [ ] `addopts` has NOT been changed to include `-n auto` — that would change `make test-unit` semantics.

### 2. Makefile

- [ ] `test-parallel` target exists, uses `-n auto --dist=loadfile`.
- [ ] `test-unit`, `test-integration`, `test`, and `check` targets are unchanged in behavior (still serial).
- [ ] `allure-report` target exists with the install-check guard printing clear instructions.
- [ ] `allure-serve` target updated to use the same install-check guard.
- [ ] `e2e-health`, `e2e-logs`, `e2e-stats` targets exist and use `COMPOSE_PROJECT_NAME` correctly.
- [ ] `.PHONY` list updated to include all new targets.

### 3. Baseline measurement

- [ ] S01 report contains `baseline_coverage` JSON block with `measured_on`, `baseline_percent`, `floor_percent`.
- [ ] Design doc's "Baseline Coverage Snapshot" section is populated (placeholders replaced).
- [ ] Threshold in pyproject matches `floor_percent` from the report (sanity check).
- [ ] `make test-unit` passes with the new threshold (the report's `tests_passed` is true and the test_summary mentions the cov-fail-under being satisfied or no FAIL message).

### 4. coverage_service.py

- [ ] `load_coverage()` returns a `CoverageView` with `available=False` when file is missing — does NOT raise.
- [ ] Malformed JSON path: `available=False`, `error` populated, no exception escapes.
- [ ] Color-coding boundaries match the design (green ≥ threshold, amber [threshold-10, threshold), red < threshold-10).
- [ ] No FastAPI / SQLAlchemy / DB imports — pure stdlib + dataclasses only.
- [ ] Per-package rollup correctly groups by first path segment (orch/dashboard/executor).
- [ ] Reads `fail_under` from pyproject.toml using `tomllib`; falls back to 0 cleanly if absent.
- [ ] Type hints complete; passes `make typecheck`.
- [ ] Logging uses the standard `logging` module (no `print`).

### 5. coverage.py router

- [ ] APIRouter prefix is `/system/coverage`.
- [ ] Two routes: page and `/files/{package}` fragment.
- [ ] 404 for unknown package.
- [ ] No DB dependency — uses only `Depends(get_templates)` (or equivalent project pattern).
- [ ] Registered in `dashboard/app.py` alphabetically with other routers.
- [ ] Uses the project's templates dependency, not a fresh `Jinja2Templates(...)` instance.

### 6. e2e_health_check.py

- [ ] Parses `docker-compose.e2e.yml` correctly (handles missing `ports:` gracefully).
- [ ] Curls each service with a finite timeout (5s).
- [ ] Prints PASS/FAIL line per service with HTTP code or error.
- [ ] Exits 0 on all-pass, 1 otherwise.
- [ ] If `pyyaml` is required, it is in dev deps.

### 7. .gitignore

- [ ] `tests/output/` is excluded.
- [ ] Existing entries not deleted.

### 8. Conventions

- Read `CLAUDE.md`, `tests/CLAUDE.md`, `dashboard/CLAUDE.md`.
- Code passes `make lint`, `make format-check`, `make typecheck`.
- No live-DB connections introduced (filesystem and HTTP only).
- No new external runtime deps beyond `pytest-xdist` and possibly `pyyaml`.

## Test Verification

Run:
- `make lint`
- `make typecheck`
- `make test-unit` (verify coverage threshold gate works)

## Severity Levels

| Severity | Meaning | Action |
|---|---|---|
| CRITICAL | Threshold gate not enforced; xdist breaks fixtures; live-DB call introduced | Must fix |
| HIGH | Missing required deliverable; wrong fail_under value; broken router registration | Must fix |
| MEDIUM (fixable) | Style drift, missing edge case, unclear error message | Should fix |
| MEDIUM (suggestion) | Optional refactor | Author decides |
| LOW | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S03",
  "agent": "code-review-impl",
  "work_item": "F-00069",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
