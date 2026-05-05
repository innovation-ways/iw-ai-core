# I-00064_S05_CodeReview_Final_prompt

**Work Item**: I-00064 -- Job detail "View document" link 404s with double project_id prefix
**Review Step**: S05 (Final Review)
**Implementation Steps Reviewed**: S01..S03

---

## ⛔ Docker is off-limits

(Standard policy. Allowed exceptions: testcontainer fixtures, read-only
introspection, `./ai-core.sh` / `make` targets. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This item does not touch migrations.)

## Input Files

- `uv run iw item-status I-00064 --json` — runtime step state.
- `ai-dev/active/I-00064/I-00064_Issue_Design.md` — design.
- `ai-dev/active/I-00064/reports/I-00064_S01_Backend_report.md`
- `ai-dev/active/I-00064/reports/I-00064_S02_CodeReview_Backend_report.md`
- `ai-dev/active/I-00064/reports/I-00064_S03_Tests_report.md`
- `ai-dev/active/I-00064/reports/I-00064_S04_CodeReview_Tests_report.md`
- All files listed in any of the implementation reports' `files_changed`
  (expected: `orch/jobs/aggregator.py` and the new test file).

## Output Files

- `ai-dev/active/I-00064/reports/I-00064_S05_CodeReview_Final_report.md`

## Context

You are the **final cross-step review** for I-00064. Per-step reviews
(S02, S04) have already happened — your job is to catch issues that
span both the fix and the tests, and to confirm the bug is genuinely,
verifiably fixed end-to-end.

Read the design document for the full root-cause story.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

```bash
make lint
make format-check
```

Any NEW violations introduced by S01 or S03 → CRITICAL.

## Review Checklist

### 1. Completeness vs design document

The design's **Acceptance Criteria** are AC1, AC2, AC3:

- **AC1 — Bug fixed**: clicking "View document" on a doc_generation
  job navigates to the doc detail page (HTTP 200). Verify by tracing
  S01's change → URL the template builds → docs route lookup. The
  composite-prefix double-up is broken.
- **AC2 — Regression test exists**: at least one test in
  `tests/integration/test_i00064_doc_generation_view_document_url.py`
  fails against pre-fix code and passes now. Verify the assertions are
  semantic, not shape (S04's job, but double-check).
- **AC3 — Orphan handling unchanged**: orphan jobs (FK null, or
  ProjectDoc deleted) → `raw["doc_id"]` is `None` → template hides the
  link. No 500.

### 2. Cross-step integration

- The aggregator change (S01) and the tests (S03) reference the same
  field and convention.
- The reproduction test really exercises the lines S01 changed
  (`_build_doc_generation_raw`, `_fetch_doc_generation`,
  `_get_doc_generation`).

### 3. No other consumer regressed

Search the repo:

```bash
grep -rn 'raw\["doc_id"\]\|raw\.get("doc_id")\|raw_doc\["doc_id"\]' \
  orch/ dashboard/ tests/ | grep -v test_i00064
```

Walk every result. For each, confirm it does NOT depend on the value
being the composite for `doc_generation` rows. Notable existing
consumers:

- `dashboard/templates/pages/project/job_detail.html:85` — gates the
  "View code map" link on code_mapping rows (presence check; the link
  URL doesn't include the doc_id). Still correct.
- `dashboard/templates/pages/project/job_detail.html:124-126` — the
  fixed link itself.
- `dashboard/templates/pages/project/job_detail.html:232-234` — the
  research "View research" link. `_fetch_research` already passes the
  inner `doc.doc_id` (line 495). Still correct.
- `tests/integration/test_i00059_doc_generation_get_job.py:92` —
  asserts `row.raw.get("doc_id") is None` for orphans. Still correct
  with the fix.

If any consumer breaks, classify as CRITICAL (`category: "integration"`).

### 4. Architecture compliance

- Read `CLAUDE.md` and `orch/CLAUDE.md`.
- Aggregator stays in `orch/jobs/aggregator.py` — no leak into the
  router or template.
- Sync SQLAlchemy 2.0 idiom (`select(...).where(...)` etc.).
- No new DB query loop; existing batched query reused.

### 5. Security & data integrity

- The fix does not expose any new identifier to the user (the inner
  `doc_id` is already user-visible via the docs catalog).
- No SQL injection — uses ORM, not string-built SQL.

### 6. Test coverage holistic check

- Three tests in the new file cover (a) reproduction, (b) end-to-end
  URL resolution, (c) orphan.
- The end-to-end test exercises both the aggregator and the docs
  router — the only two layers in the bug chain. Good integration
  coverage.
- No existing test was deleted or weakened.

## Test Verification (NON-NEGOTIABLE)

Run the **full suite**:

```bash
make test-unit
make test-integration
```

Both must pass with zero failures. If either fails, this is a CRITICAL
finding.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| CRITICAL | AC not met, regression in another consumer, integration test fails |
| HIGH | Missing end-to-end coverage, design requirement not implemented |
| MEDIUM_FIXABLE | Code quality issue spanning S01+S03 |
| MEDIUM_SUGGESTION | Refactor opportunity |
| LOW | Nitpick |

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "CodeReview_Final",
  "work_item": "I-00064",
  "steps_reviewed": ["S01", "S03"],
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X unit passed, Y integration passed, 0 failed",
  "missing_requirements": [],
  "notes": ""
}
```

`verdict` is `pass` only when CRITICAL + HIGH + MEDIUM_FIXABLE = 0.
