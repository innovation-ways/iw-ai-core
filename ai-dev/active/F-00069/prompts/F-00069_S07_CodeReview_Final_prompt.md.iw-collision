# F-00069_S07_CodeReview_Final_prompt

**Work Item**: F-00069 -- Test Execution, Coverage Gate, Reports, and Coverage Dashboard View
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01..S05

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `uv run iw item-status F-00069 --json`
- `ai-dev/active/F-00069/F-00069_Feature_Design.md`
- All implementation step reports: `F-00069_S01..S05_*_report.md`
- All per-agent code review reports: `F-00069_S03_CodeReview_report.md`, `S04_CodeReview_report.md`, `S06_CodeReview_report.md`
- All files listed in the implementation reports' `files_changed`

## Output Files

- `ai-dev/active/F-00069/reports/F-00069_S07_CodeReview_Final_report.md`

## Context

You are performing the **final cross-agent review** of ALL work for F-00069. Per-step reviews are done — your job is the cross-cutting picture: does the wired-together feature deliver every AC in the design, does it integrate cleanly, and does the full test suite stay green?

## Review Checklist

### 1. Completeness vs Design Document

- [ ] All 7 ACs (AC1–AC7) have visible code paths.
- [ ] Every "In Scope" deliverable is implemented (parallel exec, coverage gate, reports, allure targets, e2e make targets, /coverage page, nav entry).
- [ ] Every "Out of Scope" item is genuinely absent (no @smoke marker, no test-quality.yml, no security scanning targets, no migration tests added in this work item).
- [ ] Design doc's "Baseline Coverage Snapshot" section is filled in.

### 2. Cross-Agent Consistency

- [ ] S01's `CoverageView` shape matches what S02's templates iterate over (PackageRow.name, .line_pct, .badge etc. all present).
- [ ] S02's htmx URL `hx-get="/system/coverage/files/{{ pkg.name }}"` matches S01's router prefix + path.
- [ ] S05's tests exercise the integration of S01 + S02 (via dashboard test client).
- [ ] Naming is consistent: "Test Coverage" in nav, "Test Coverage" in page title, threshold called `fail_under` everywhere.

### 3. Integration Points

- [ ] `dashboard/app.py` registers the coverage router exactly once.
- [ ] Templates dependency in `coverage.py` matches the project's `get_templates` (or equivalent) — no new `Jinja2Templates(...)` instance leaks.
- [ ] Makefile's `e2e-health` invokes `scripts/e2e_health_check.py` and the script exists and is importable.
- [ ] `pyproject.toml` is internally consistent: `[dependency-groups] dev` lists pytest-xdist, `[tool.pytest.ini_options]` uses --cov flags, `[tool.coverage.run]` and `[tool.coverage.report]` are populated, `fail_under` matches the report.

### 4. Holistic Test Coverage

- [ ] Run the **full** test suite: `make test`. Zero failures.
- [ ] Run `make test-parallel`. Zero failures, no fixture-race errors.
- [ ] Coverage of the new files (`coverage_service.py`, `coverage.py` router) is itself ≥ the threshold floor.
- [ ] Manually verify (curl or browser): `/system/coverage` returns 200 and renders something.

### 5. Architecture Compliance

- [ ] No live-DB calls introduced (verify by grep).
- [ ] Coverage threshold floor in pyproject matches `S01.report.baseline_coverage.floor_percent`.
- [ ] Existing `make test`, `make test-unit`, `make test-integration`, `make check` behave exactly as before (serial, plus coverage collection).
- [ ] No new top-level dependencies in `[project] dependencies` (only dev-deps additions allowed).

### 6. Security (Cross-Cutting)

- [ ] No path traversal in `coverage_service` (the package param in router is matched against a known set, not used as a filesystem path).
- [ ] No HTML injection in templates (Jinja autoescape is on by default; spot-check string interpolation in error messages).
- [ ] `coverage.json` is read read-only; nothing writes to it from request handlers.

### 7. Dependencies & Blocks

- [ ] Design doc's `Blocks: F-00070` is still accurate; nothing in this implementation accidentally satisfies F-00070's scope (no test-quality.yml, no @smoke marker, no logging tests).

## Test Verification (NON-NEGOTIABLE)

1. `make lint` — zero errors
2. `make format-check` (or `make format`) — clean
3. `make typecheck` — zero errors
4. `make test-unit` — zero failures, threshold met
5. `make test-integration` — zero failures, threshold met
6. `make test-parallel` — zero failures (this is the new path; treat any failure as CRITICAL)

## Severity Levels

(Standard table.)

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "code-review-final-impl",
  "work_item": "F-00069",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
