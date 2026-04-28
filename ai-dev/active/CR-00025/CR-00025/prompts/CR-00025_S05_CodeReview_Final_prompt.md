# CR-00025 S05 — Final cross-layer code review

**Work Item**: CR-00025 — Implement missing evidence-ingestion pipeline (CR-00020 follow-up) and backfill archived items
**Step**: S05
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Same constraints as S01.

## Input Files

- `uv run iw item-status CR-00025 --json`
- `ai-dev/active/CR-00025/CR-00025_CR_Design.md`
- All prior step reports under `ai-dev/active/CR-00025/reports/`:
  - `CR-00025_S01_Backend_report.md`
  - `CR-00025_S02_CodeReview_Backend_report.md`
  - `CR-00025_S03_Tests_report.md`
  - `CR-00025_S04_CodeReview_Tests_report.md`
- All files changed in S01 and S03 (concatenate the `files_changed`
  arrays from both reports and review every file).

## Output Files

- `ai-dev/active/CR-00025/reports/CR-00025_S05_CodeReview_Final_report.md`

## Context

This is the final cross-layer review before QV gates. You are the last
human-style review checkpoint. Two prior reviewers (S02, S04) have
already approved their slices; your job is to verify the **whole** is
coherent, all ACs are covered end-to-end, and there are no integration
gaps between the helper, the CLI hooks, and the tests.

The historical lesson from CR-00020: a final review missed that the
ingestion hooks were never written, and the qv-browser step also missed
it. Be paranoid about the whole pipeline working end-to-end.

## Cross-Layer Review Checklist

### 1. AC1–AC8 traceability

For each AC in the design doc, identify:
- The implementation file/lines that satisfy it.
- The test file/function that asserts it.
- Note any AC without both implementation AND a test as a CRITICAL
  finding.

AC6, AC7, AC8 are about the backfill script (S12) — they will not yet
be implemented at this point in the pipeline. Note them in your report
but do **not** fail this review on their absence; mark them as "to be
verified in S12". Verify only AC1–AC5.

### 2. Transaction integrity (CRITICAL)

Trace the `approve` command end-to-end:
- `with get_session() as session:` opens a transaction.
- Status flip happens.
- `ingest_phase_from_disk(...)` runs against the same session.
- If it raises, the context manager rolls back. Confirm by reading
  `orch/db/session.py`'s implementation.
- If it succeeds, the implicit commit at the end of the `with` block
  persists both the status flip and the ingested rows atomically.

Same trace for `step_done` with browser_verification.

### 3. Archive survival (AC5)

The whole point of the CR. Verify by reading the regression test in
`tests/integration/test_evidences_lifecycle.py`:
- It exercises the **real** archiver, not a stub.
- It deletes the active dir via `cleanup=True`.
- It asserts `_list_evidences` (the real dashboard helper) returns DB
  rows after cleanup.
- It asserts byte-identical content via SHA256 or equivalent.

### 4. No agent-facing surface change

- `iw approve` and `iw step-done` CLIs are byte-identical from an
  agent's perspective (no new flags, no changed argument order, no
  changed exit codes for the success path).
- The qv-browser skill prompts and `validate_browser_evidence_present`
  still work as before for their existing purpose.

### 5. Documentation consistency

- `docs/IW_AI_Core_Database_Schema.md` and `CLAUDE.md` Quick Navigation
  are synced.
- The design doc's "File Manifest" matches the actual changed files.

### 6. No regressions

- Existing `tests/integration/test_work_item_evidence.py` still passes
  — the model-level CRUD/UNIQUE/FK tests must not break.
- Dashboard reads (`_list_evidences`, `item_evidence_file`) are
  unchanged at the source level.

### 7. Style and conventions

- Sync SQLAlchemy 2.0 style maintained.
- psycopg v3 driver assumed.
- No new external deps.
- Imports placed at top of files (no scattered local imports unless
  they break a circular dep — flag any local imports that look avoidable).

## Test Verification (NON-NEGOTIABLE)

Run the full test pre-gate suite locally:
1. `make format-check`
2. `make lint`
3. `make typecheck`
4. `make test-unit`
5. `make test-integration`

All five must be green before you mark verdict=pass. If any fail, list
the failure in your findings with severity CRITICAL or HIGH.

## Severity Levels

| Severity | Meaning | Action |
|----------|---------|--------|
| **CRITICAL** | AC1–AC5 not satisfied end-to-end, broken transaction | Must fix |
| **HIGH** | Missing test, integration gap, doc drift | Must fix |
| **MEDIUM (fixable)** | Code quality issue | Should fix |
| **MEDIUM (suggestion)** | Better pattern | Optional |
| **LOW** | Nitpick | Informational |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "CR-00025",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "ac_traceability": {
    "AC1": {"impl": "<file:line>", "test": "<file::function>"},
    "AC2": {"impl": "<file:line>", "test": "<file::function>"},
    "AC3": {"impl": "<file:line>", "test": "<file::function>"},
    "AC4": {"impl": "<file:line>", "test": "<file::function>"},
    "AC5": {"impl": "<file:line>", "test": "<file::function>"},
    "AC6": {"status": "deferred to S12"},
    "AC7": {"status": "deferred to S12"},
    "AC8": {"status": "deferred to S12"}
  },
  "tests_passed": true,
  "test_summary": "X unit + Y integration passed, 0 failed",
  "notes": ""
}
```
