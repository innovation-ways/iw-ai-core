# I-00105_S10_CodeReview_prompt

**Work Item**: I-00105 — Workflow step fails when its agent runtime overflows the model context window
**Step**: S10
**Agent**: code-review-impl
**Step Being Reviewed**: S09 (tests-impl — reproduction + regression tests)

---

## ⛔ Docker / Migrations

Standard policy — read-only review. Do not run container-mutating commands; do
not apply migrations.

## Input Files

- **Runtime step state** — `uv run iw item-status I-00105 --json`.
- `ai-dev/work/I-00105/I-00105_Issue_Design.md` — design doc (§Test to Reproduce, AC3, §TDD Approach).
- `ai-dev/work/I-00105/reports/I-00105_S09_Tests_report.md` — S09 report.
- Every test file in S09's `files_changed`.

## Output Files

- `ai-dev/work/I-00105/reports/I-00105_S10_CodeReview_report.md` — review report.

## Review Checklist

Verify and record a finding (with severity) for each:

1. **Reproduction test** — `test_i_00105_context_pct_accounts_for_output_reservation` exists and would genuinely FAIL against the pre-fix raw-window meter (reason through it: if the meter still divided by the full window, the assertion `pct >= 100.0` would fail). It is not vacuous.
2. **Semantic correctness, not shape** — every test asserts specific expected values (`pct >= 100.0`, `spill_file.read_text() == original`, the backfilled `131072`), never just `is not None` / `isinstance` / non-empty. This is the I003 lesson — a shape-only test that passes without the fix is a CRITICAL finding.
3. **Coverage** — the effective-budget meter (large/small/NULL `max_output`, buffer effect), the migration backfill, the executor cap helper, and the context-overflow-detection helper are all covered (AC3, AC4), matching the design's §TDD Approach.
4. **Placement** — pure-computation tests in `tests/unit/`, testcontainer-DB tests in `tests/integration/`, `client`-fixture tests in `tests/dashboard/` (`tests/CLAUDE.md` rules). Order-independent (`pytest-randomly`).
5. **Assertion scanner** — the S09 report shows `make test-assertions` green; no new no-assert / tautology / mock-only / bare-`pytest.raises` violations.
6. **Scope** — `git diff` confined to `scope.allowed_paths` (tests only).

Severities: CRITICAL (shape-only test / reproduction test cannot fail / scope breach), HIGH (coverage gap), MEDIUM (placement / weak assertion), LOW (nit). A CRITICAL or HIGH finding means the step does not pass review.

## Subagent Result Contract

```json
{
  "step": "S10",
  "agent": "code-review-impl",
  "work_item": "I-00105",
  "step_reviewed": "S09",
  "completion_status": "complete",
  "verdict": "pass|fail",
  "findings": [{"severity": "CRITICAL|HIGH|MEDIUM|LOW", "file": "", "detail": ""}],
  "notes": ""
}
```

## Lifecycle Commands

Start: `uv run iw step-start I-00105 --step S10`
On completion: write the report, then
`uv run iw step-done I-00105 --step S10 --report ai-dev/work/I-00105/reports/I-00105_S10_CodeReview_report.md`
You MUST call `step-done` (with `--report`) before exiting.
