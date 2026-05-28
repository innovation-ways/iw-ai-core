# CR-00092_S06_CodeReview_Final_prompt

**Work Item**: CR-00092 -- Column-docs baseline scrub
**Review Step**: S06 (Final Review)
**Implementation Steps Reviewed**: S01..S04

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY docker commands that change container/volume/network state. Testcontainers from pytest fixtures and read-only introspection are the only exceptions. Full policy: docs/IW_AI_Core_Agent_Constraints.md

## ⛔ Migrations: agents generate, daemon applies

This CR adds NO migration. Any file under `orch/db/migrations/versions/**` in the diff → CRITICAL.

## Input Files

- **Runtime step state** — `uv run iw item-status CR-00092 --json`.
- `ai-dev/active/CR-00092/CR-00092_CR_Design.md` — Design document (AC1–AC8 are the spine of this review).
- `ai-dev/work/CR-00092/reports/CR-00092_S01_Database_report.md`..`S04_Database_report.md` — all four wave reports.
- `ai-dev/work/CR-00092/reports/CR-00092_S05_CodeReview_report.md` — per-agent review report.
- All files in `S04`'s `files_changed` (the canonical full diff list).

## Output Files

- `ai-dev/work/CR-00092/reports/CR-00092_S06_CodeReview_Final_report.md`.

## Context

You are performing the **final cross-step review** of the four-wave column-docs scrub + gate flip. Per-agent review (S05) caught local issues; your job is the holistic check — every AC mechanically, every cross-step numeric anchor, every scope rule.

## Read the Design Document FIRST

Specifically:
- AC1–AC8 — execute each one mechanically below.
- Notes → Description sourcing rule.
- Notes → Known trade-off (gate stays folded into `make quality`, NOT promoted to canonical daemon QV gate).
- Impacted Paths — exactly six files plus implicit `ai-dev/**`.

## Pre-Review Lint & Format Gate

```bash
make lint
make format
```

Any new violation → CRITICAL with `"category": "conventions"`.

## Scope Discipline — Implicitly Allowed Paths

`ai-dev/active/CR-00092/**`, `ai-dev/archive/CR-00092/**`, `ai-dev/work/CR-00092/**` are NOT scope creep.

### Directional scope diff

```bash
git diff main...HEAD --name-only
git status -s
```

Expected (besides implicit allows): exactly the six Impacted Paths files. Anything else → CRITICAL.

## AC Execution Checklist

Execute every AC mechanically. Record exit codes and grep output verbatim in the report.

### AC1: Scanner exits clean

```bash
uv run python scripts/check_db_column_docs.py --baseline /dev/null
echo "exit=$?"
```
Expected: exit 0, no violations.

### AC2: Baseline file is gone

```bash
test ! -e orch/db/column_docs_baseline.txt && echo "absent" || echo "PRESENT"
git ls-files orch/db/column_docs_baseline.txt
```
Expected: "absent" and empty `git ls-files`.

### AC3: `make quality` is blocking (with synthetic regression)

Temporarily remove one `doc=` from any column (record which), run `make quality`, confirm exit non-zero, restore. Do NOT leave the regression in the tree.

```bash
# Save baseline state of one Column declaration.
# Remove its doc= argument.
make quality
echo "exit_with_regression=$?"   # must be non-zero
# Restore the doc= argument.
make quality
echo "exit_clean=$?"             # must be 0
git diff -- orch/db/models.py    # must be empty
```

### AC4: GH workflow no longer has `|| true`

```bash
grep -n "check-column-docs" .github/workflows/test-quality.yml
```
Expected: matching line does NOT contain `|| true`.

### AC5: `make quality` exits 0 on the unchanged tree

```bash
make quality
echo "exit=$?"
```
Expected: exit 0.

### AC6: Strategy doc + tracker updated

Read both files:
- `docs/IW_AI_Core_Testing_Strategy.md` §5: `check-column-docs` row marked blocking; references CR-00092.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §8 row 4.5.followup: Status = `✅ (CR-00092, 2026-05-28, blocking)`, Link = `CR-00092`.
- `ai-dev/work/TESTS_ENHANCEMENT.md` §11: top entry dated 2026-05-28 with CR-00092 and the 450-count.
- Header version bumped (v1.8 → v1.9).

Any missing → HIGH.

### AC7: Scope discipline

```bash
git diff main...HEAD --name-only
```
Expected list (apart from `ai-dev/active/CR-00092/**` and `ai-dev/work/CR-00092/**`):
```
.github/workflows/test-quality.yml
Makefile
ai-dev/work/TESTS_ENHANCEMENT.md
docs/IW_AI_Core_Testing_Strategy.md
orch/db/column_docs_baseline.txt   (D)
orch/db/models.py
```
ANYTHING else → CRITICAL. Specifically check that `docs/IW_AI_Core_Database_Schema.md` is NOT listed and that no `orch/db/migrations/versions/**` file is listed.

### AC8: Deliberate-break demonstration in S04 report

Read `CR-00092_S04_Database_report.md`'s "AC8 deliberate-break demonstration" section. Confirm specific column named, both invocations recorded, `git diff` empty after restore.

## Cross-step Consistency Checks (cross-agent)

1. **Wave count math**: 103 + 90 + 123 + S04.wave_scrub_count = 450 (within ±5). If sum doesn't equal 450, the live `orch/db/models.py` may have changed mid-CR or a class was mis-counted — investigate, raise HIGH if unresolved.
2. **Cumulative cross-check**: S04 report's `cumulative_scrub_count` MUST equal 450. S04's `remaining_baseline_count` MUST equal 0.
3. **Baseline-deleted flag**: S04 report's `baseline_deleted` = true AND `git ls-files orch/db/column_docs_baseline.txt` empty AND filesystem absent. All three must agree.
4. **CR-00092 ID consistency**: the CR ID appears verbatim in:
   - The strategy doc §5 update
   - The tracker §8 row 4.5.followup
   - The tracker §11 changelog entry
   - The S04 report's notes
   Any mismatch (e.g. typo `CR-00091`, `CR00092`) → HIGH.

## Re-run the test suites (NON-NEGOTIABLE)

```bash
uv run pytest tests/orch/db/test_column_docs.py -v
make test-unit
```

Plus the scanner library-form sanity check:

```bash
uv run python scripts/check_db_column_docs.py --baseline /dev/null
```

Any failure → CRITICAL.

## Comparable Prior Work

CR-00085 (the scanner-kit CR that created this baseline) and CR-00081 (the assertion-baseline scrub) are the two closest precedents. CR-00085 took ~13 steps and shipped in one session; CR-00081 scrubbed 78 entries in a single CR. This CR scrubs 450 entries in four waves — if the time/fix-cycle footprint balloons well beyond either precedent, note it in the report under `notes` (informational, not a finding).

## Review Result Contract

```json
{
  "step": "S06",
  "agent": "CodeReview_Final",
  "work_item": "CR-00092",
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
  "ac_execution": {
    "AC1_scanner_dev_null_exit_0": true,
    "AC2_baseline_file_absent": true,
    "AC3_make_quality_blocks_with_synthetic_regression": true,
    "AC4_gh_workflow_no_or_true": true,
    "AC5_make_quality_clean_exits_0": true,
    "AC6_docs_and_tracker_updated": true,
    "AC7_scope_discipline_clean": true,
    "AC8_deliberate_break_demonstrated_in_s04": true
  },
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
