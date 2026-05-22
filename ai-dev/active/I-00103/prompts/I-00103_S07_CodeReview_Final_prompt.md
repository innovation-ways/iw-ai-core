# I00103_S07_CodeReview_Final_prompt

**Work Item**: I-00103 -- `merge_auto_resolution_failed` event drops per-file error string
**Review Step**: S07 (Final Review)
**Implementation Steps Reviewed**: S01..S06

---

## ⛔ Docker is off-limits

Standard policy. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## ⛔ Migrations: agents generate, daemon applies

No migration in this item. Full policy: docs/IW_AI_Core_Agent_Constraints.md.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00103 --json`.
- `ai-dev/active/I-00103/I-00103_Issue_Design.md` -- Design document.
- `ai-dev/active/I-00103/I-00103_Functional.md` -- Functional summary.
- All step reports: `ai-dev/active/I-00103/reports/I-00103_S01_Backend_report.md`, `_S02_CodeReview_report.md`, `_S03_Frontend_report.md`, `_S04_CodeReview_report.md`, `_S05_Tests_report.md`, `_S06_CodeReview_report.md`.
- All files listed in any implementation report's `files_changed` (expected union: `orch/daemon/auto_merge.py`, `dashboard/templates/fragments/auto_merge_event_detail.html`, possibly `dashboard/static/styles.css`, `tests/integration/test_auto_merge_failed_event_metadata.py`, `tests/dashboard/test_auto_merge_event_detail_per_file_errors.py`).

## Output Files

- `ai-dev/active/I-00103/reports/I-00103_S07_CodeReview_Final_report.md` -- Final review report.

## Context

You are performing the final cross-agent review of all implementation work for **I-00103**. Per-agent reviews (S02, S04, S06) have already been done; your job is to catch cross-cutting issues they could not.

## Read the Design Document FIRST

- `## Acceptance Criteria` — AC1..AC5. EVERY criterion must be covered end-to-end by the combined work of S01 + S03 + S05.
- `## TDD Approach` — list every test file the design names. Cross-check against the union of all `files_changed`. ANY missing test file is a **CRITICAL** finding.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format
```

If either reports NEW violations in any of the changed files, classify each as a **CRITICAL** finding.

## Review Checklist

### 1. Completeness vs Design Document

- All 5 acceptance criteria covered: AC1 (backend payload), AC2 (regression test exists), AC3 (modal renders when present), AC4 (modal hides when absent), AC5 (500-char truncation cap).
- All 7 tests from §TDD Approach exist: 4 integration + 3 dashboard.
- No TODO / FIXME / placeholder comments in any changed file.

### 2. Cross-agent contract consistency

This is the most important check for I-00103 — three agents touched three layers, and the field name + dict shape must be identical across all three.

- **Field name**: S01 persists `metadata["per_file_errors"]`. S03 reads `event.metadata.per_file_errors`. S05 asserts on `event.event_metadata["per_file_errors"]`. Verify these names match exactly. Any case-mismatch, plural-vs-singular drift, or different key (e.g. `errors_per_file`) across the three is a **CRITICAL** finding.

- **Dict shape**: S01 emits `{file_path, error, cli_tool, model}`. S03 reads `entry.file_path` / `entry.error` / `entry.cli_tool` / `entry.model`. S05 asserts the same keys. Any drift (e.g. `path` vs `file_path`, `runtime` vs `cli_tool`) is a **CRITICAL** finding.

- **Class name**: S03 uses `auto-merge-modal__per-file-errors` (or whichever class S03's report records). S05's dashboard test asserts on the exact same class. Drift here would silently make the test false-positive against unrelated HTML. Cross-check the literal string.

### 3. Integration test coverage

- The cross-layer integration is implicitly tested by AC3 (dashboard test seeds an event with the new field and asserts it renders). Verify the seeded event metadata in S05's dashboard test matches what S01 would actually produce. If S05's seed uses keys/values that don't match S01's emission shape, AC3 passes on a fiction — flag as HIGH.

### 4. Backward-compat coverage

- AC4 requires the modal to render historical events (events without `per_file_errors`) without exception. Verify S05's `test_event_detail_hides_per_file_errors_section_when_absent` and `_when_empty_list` tests exist and cover both shapes (missing key + empty list).

### 5. Architecture compliance

- S01's change is contained to `orch/daemon/auto_merge.py` lines 961-981. Anything outside that block is scope creep.
- S03's change is contained to `dashboard/templates/fragments/auto_merge_event_detail.html` (and optionally `dashboard/static/styles.css`). Any other file touched is scope creep.
- S05 only adds test files. Any production-code edit by S05 is a CRITICAL finding.

### 6. Security (cross-cutting)

- The `error` strings are free-form text from external subprocesses; they may contain stderr that includes paths, command lines, or partial credentials. Verify:
  - Persisted strings are capped at 500 chars (S01) — caps stderr propagation.
  - Template uses `{{ entry.error }}` without `| safe` — autoescape protects against XSS.
  - No `error` string is logged to anywhere new (it's already in `logs/daemon.log` via `logger.warning`).

### 7. Test files appear in `files_changed`

Cross-check the design doc's §File Manifest test rows against the union of all `files_changed` arrays. Missing entries are CRITICAL.

### 8. No format/style regressions

`make format` and `make lint` must report clean on all changed files. The S02 / S04 / S06 reviews already checked their respective steps; you re-run holistically to catch any combined drift.

## Test Verification (NON-NEGOTIABLE)

Run **targeted** tests only. The full `make test-unit` / `make test-integration` / `make test-frontend` suites are owned by the S13 / S14 / S15 QV gates that run immediately after this step — re-running them here duplicates that work and risks a step timeout (the integration suite alone is budgeted at 1800 s for S15, and this step has no extended timeout). Run the two new test files plus the existing auto-merge regression coverage:

```bash
uv run pytest tests/integration/test_auto_merge_failed_event_metadata.py -v 2>&1 | tail -30
uv run pytest tests/dashboard/test_auto_merge_event_detail_per_file_errors.py -v 2>&1 | tail -30
uv run pytest tests/integration/test_auto_merge_phase1.py tests/dashboard/test_auto_merge_routes.py -v 2>&1 | tail -40
```

If any of these fail, report as a CRITICAL finding. Full-suite green/red is established authoritatively by the S13 / S14 / S15 QV gates.

## Severity Levels

(Standard table — CRITICAL / HIGH / MEDIUM_FIXABLE / MEDIUM_SUGGESTION / LOW.)

## Review Result Contract

```json
{
  "step": "S07",
  "agent": "CodeReview_Final",
  "work_item": "I-00103",
  "steps_reviewed": ["S01", "S02", "S03", "S04", "S05", "S06"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, Z dashboard passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

- `verdict`: `pass` iff zero CRITICAL + HIGH + MEDIUM_FIXABLE findings.
- `missing_requirements`: List any AC1..AC5 with no corresponding implementation. Each missing requirement is automatically a CRITICAL finding.
- `cross_cutting: true` on any finding spanning multiple agents' work — this is especially relevant for the field-name / dict-shape consistency checks above.
