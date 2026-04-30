# I-00053_S05_CodeReview_Final_prompt

**Work Item**: I-00053 -- Batch Planner Ignores Explicit "Depends on:" / "Blocks:" Declarations
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S03

---

## ⛔ Docker is off-limits / ⛔ Migrations: agents generate, daemon applies

(Standard policies.)

## Input Files

- `ai-dev/active/I-00053/I-00053_Issue_Design.md`
- All reports under `ai-dev/active/I-00053/reports/`
- All files modified by S01: `orch/design_doc_parser.py`, `orch/cli/item_commands.py`, `orch/batch_planner.py`
- All files added by S03: `tests/unit/test_design_doc_parser.py`, `tests/unit/test_batch_planner_dependencies.py`, `tests/integration/test_register_persists_dependencies.py`

## Output Files

- `ai-dev/active/I-00053/reports/I-00053_S05_CodeReview_Final_report.md`

## Review Checklist

### 1. Completeness vs Design

- [ ] All 6 ACs (AC1–AC6) implemented.
- [ ] All 7 invariants verifiable from the code.
- [ ] No "Out of Scope" items leaked in:
  - No new `iw deps refresh` / `iw deps show` CLI.
  - No Markdown-section parsing beyond the three the design names.
  - No changes to executor / daemon / dashboard / workflow runtime.
  - No new alembic migration.

### 2. Cross-step consistency

- [ ] `Dependencies` dataclass shape used by S01's register code matches what S03's tests assert.
- [ ] Section names hard-coded in S01's `strip_excluded_sections()` ("Out of Scope", "Notes") are the exact strings S03's tests use.
- [ ] ID regex used by parser covers the IDs used in S03's tests (F-, I-, CR- with 3-5 digits).

### 3. Integration

- [ ] Run the FULL regression suite of THE BUG: `uv run pytest tests/unit/test_design_doc_parser.py tests/unit/test_batch_planner_dependencies.py tests/integration/test_register_persists_dependencies.py -v` — all pass.
- [ ] Run `make test` — pre-existing tests still green (confirm by reading reports).
- [ ] Verify: parse a real design doc (e.g. `ai-dev/active/F-00073/F-00073_Feature_Design.md`) through `parse_dependencies()` — confirm it returns `Dependencies(depends_on=["F-00069"], blocks=[])`. This is the BATCH-00064 root case.
- [ ] Verify: `extract_affected_files()` on `ai-dev/active/F-00069/F-00069_Feature_Design.md` does NOT include `tests/unit/test_logging.py` (the spurious match that caused BATCH-00064).

### 4. Architecture

- [ ] No new external Python deps in `[project] dependencies`.
- [ ] `orch/design_doc_parser.py` has no I/O — pure functions.
- [ ] No live-DB connections introduced.
- [ ] `extract_affected_files()` refactor preserves the existing test-path exclusion behavior.

### 5. Security

- [ ] Parser is regex-based; no eval, no exec, no shell-out.
- [ ] No new HTTP/network calls.
- [ ] Logging does not leak credentials or paths beyond what's already logged at register time.

### 6. Holistic test pass

1. `make lint`
2. `make format-check`
3. `make typecheck`
4. `make test-unit`
5. `make test-integration`

If any fail, that's CRITICAL. The fix is incomplete.

## Severity Levels

| Severity | Meaning |
|---|---|
| CRITICAL | Live-DB connection introduced; full suite fails; out-of-scope item shipped; pre-existing test broken |
| HIGH | AC not fully implemented; invariant violated; cross-step naming mismatch causes test bypass |
| MEDIUM (fixable) | Missing log message; subtle parser edge case |
| MEDIUM (suggestion) | Refactor opportunity; could DRY a helper |
| LOW | Style |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "I-00053",
  "steps_reviewed": ["S01", "S02", "S03", "S04"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```
