# I-00077_S02_CodeReview_report — Doc-generation jobs abort on missing editorial guide

## Step

S02 — code-review-impl

## Work Item

I-00077 — Doc-generation jobs abort on missing editorial guide and the failure is invisible on the Docs page

## Step Reviewed

S01 (backend-impl)

---

## What Was Reviewed

Review of S01's implementation of Fix #1 (`_effective_guide` `_default` fallback) and Fix #2 (skill "Job lifecycle" wording).

## Files Changed

| File | Change |
|------|--------|
| `orch/doc_service.py` | `_effective_guide` now falls back to `get_type_guide("_default")` when no instance or doc_type guide exists; guard added to prevent redundant query when `doc_type == "_default"` |
| `skills/iw-doc-generator/SKILL.md` | Added "Note on null editorial snapshots" paragraph in Job lifecycle step 1 |
| `skills/iw-doc-system/SKILL.md` | Added identical "Note on null editorial snapshots" paragraph in Job lifecycle step 1 |
| `tests/unit/test_doc_type_guide_service.py` | Added `TestEffectiveGuide` class with 4 tests |

---

## Pre-Review Quality Gates

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ✅ All files already formatted |
| `make typecheck` | ✅ Success: no issues found in 240 source files |

---

## Review Checklist

### Fix #1 Correctness

- ✅ Resolution order is exactly: instance guide → `get_type_guide(doc_type)` → `get_type_guide("_default")` → `None`
- ✅ The `doc_type == "_default"` guard prevents a redundant extra lookup and avoids any potential infinite-loop concern
- ✅ `create_doc_job` is unchanged — it already calls `_effective_guide(...)` and stores the result in `guide_snapshot`
- ✅ `section_guides_snapshot` behaviour is unchanged (remains `None` for docs with no section guides — this is correct, not a bug to fix)
- ✅ No behaviour change for docs that already have an instance guide or a `doc_type`-specific guide
- ✅ Design doc's AC1 is satisfied

### Fix #2 Correctness

- ✅ Both `skills/iw-doc-generator/SKILL.md` AND `skills/iw-doc-system/SKILL.md` were edited, identically
- ✅ New wording explicitly states that `null` / empty `section_guides_snapshot` and `guide_snapshot` are **normal and expected**, not a reason to abort
- ✅ Wording instructs the agent to **proceed using the static `references/…-guidelines.md`** bundled with the skill
- ✅ Wording instructs to only close with `--error` when `iw doc-job-status <job-id> --json` itself exits non-zero, or when generation genuinely cannot proceed — **never** merely because the editorial snapshot was empty
- ✅ Pre-existing "if non-zero exit, close immediately" guidance is fully retained (unchanged)
- ✅ Markdown style matches surrounding sections
- ✅ Design doc's AC2 is satisfied

### Conventions / Quality / Security

- ✅ No hardcoded values (ports, URLs, credentials)
- ✅ No scope creep — dashboard layer (Fix #3) is not touched; that's S03
- ✅ `CLAUDE.md` conventions respected throughout
- ✅ No security issues introduced

### Testing

- ✅ `tests/unit/test_doc_type_guide_service.py` covers the three-level resolution order (4 new tests in `TestEffectiveGuide`):
  - `test_effective_guide_falls_back_to_default_when_no_specific_guide` — reproduction test (RED → GREEN)
  - `test_effective_guide_returns_instance_guide_when_present` — regression: instance takes priority
  - `test_effective_guide_returns_doc_type_guide_when_no_instance_guide` — regression: type guide used when no instance
  - `test_effective_guide_returns_none_when_no_guide_exists` — degenerate: no guide at all returns `None`
- ✅ Test assertions are semantic (checking `guide_md` content), not bare substring checks
- ✅ Design doc's AC4 is satisfied (regression test exists)

---

## Test Verification

```
uv run pytest tests/unit/test_doc_type_guide_service.py -v --no-cov
======================== 8 passed, 1 warning in 0.08s =========================
```

All 8 tests pass (4 pre-existing + 4 new). The reproduction test `test_effective_guide_falls_back_to_default_when_no_specific_guide` went RED on first run and GREEN after the fix, as reported by S01.

---

## Acceptance Criteria Status

| AC | Description | Status |
|----|-------------|--------|
| AC1 | `guide_snapshot` equals `_default` guide when no instance/type guide exists | ✅ Satisfied |
| AC2 | Skill text explicitly says null snapshot is normal — proceed using static guidelines | ✅ Satisfied |
| AC4 | Reproducing tests exist and pass | ✅ Satisfied |

---

## Notes

- Fix #3 (surfacing failed jobs on the Docs catalogue page) is **out of scope** for S01 — correctly handled by S03 (frontend-impl)
- Skill propagation to IW-AI-DEV and InnoForge repositories is a manual post-merge operator step, not a workflow step
- No migrations were needed — the `_default` row already existed

---

## Findings

None. Zero CRITICAL/HIGH/MEDIUM_FIXABLE findings.

---

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "I-00077",
  "step_reviewed": "S01",
  "verdict": "pass",
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "8 passed, 0 failed",
  "notes": "Fix #1 (_effective_guide fallback) and Fix #2 (skill wording) both implemented correctly and all quality gates pass. No issues found."
}
```