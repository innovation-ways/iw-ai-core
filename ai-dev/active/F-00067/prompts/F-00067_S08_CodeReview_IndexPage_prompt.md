# F-00067_S08_CodeReview_IndexPage_prompt

**Work Item**: F-00067 — Documentation Visual Design Overhaul
**Step Being Reviewed**: S07 (Backend — index page generation)
**Review Step**: S08

---

## ⛔ Docker is off-limits

Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

---

## Input Files

- `ai-dev/active/F-00067/F-00067_Feature_Design.md` — Design doc (AC5, Invariants)
- `ai-dev/active/F-00067/reports/F-00067_S07_Backend_IndexPage_report.md`
- `orch/rag/index_gen.py`
- `orch/rag/job.py`
- All test files listed in S07 report

## Output Files

- `ai-dev/active/F-00067/reports/F-00067_S08_CodeReview_IndexPage_report.md`

---

## Review Checklist

### 1. Error isolation
- Verify `generate_index_page()` is wrapped in try/except in `job.py`. A failure must never fail the `CodeIndexJob`. Missing this is CRITICAL.

### 2. Session management
- Verify `index_gen.py` uses only the passed-in `session` — never creates a new session. Violation is HIGH.

### 3. DocService usage
- Verify `create_doc()` vs `update_doc()` logic correctly handles both first-time creation and re-generation.
- Verify `doc_type=DocType.architecture`, `tier=DocTier.fully_automated` as specified.

### 4. Content quality
- Verify generated Markdown has section headers for all doc types.
- Verify empty sections degrade gracefully (note text, not empty table with no rows).
- Verify the `[!NOTE]` callout at the top is present.
- Verify `<!-- generated: {date} -->` comment is included.

### 5. First-sentence extraction
- Verify the description extraction handles `None` content gracefully.
- Verify it strips Markdown headers (lines starting with `#`) before extracting.

### 6. Test coverage
- Verify unit tests cover: normal case, empty project, update (not just create).
- Verify integration test creates a real DB record.

## Test Verification

Run `make test-unit` and report results.

## Review Result Contract

```json
{
  "step": "S08",
  "agent": "CodeReview",
  "work_item": "F-00067",
  "step_reviewed": "S07",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```
