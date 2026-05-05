# I-00064_S02_CodeReview_Backend_prompt

**Work Item**: I-00064 -- Job detail "View document" link 404s with double project_id prefix
**Step Being Reviewed**: S01 (backend-impl)
**Review Step**: S02

---

## ⛔ Docker is off-limits

(Standard policy. Allowed exceptions: testcontainer fixtures, read-only
introspection, `./ai-core.sh` / `make` targets. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.)

## ⛔ Migrations: agents generate, daemon applies

(Standard policy. This item does not touch migrations.)

## Input Files

- `uv run iw item-status I-00064 --json` — runtime step state.
- `ai-dev/active/I-00064/I-00064_Issue_Design.md` — design document.
- `ai-dev/active/I-00064/reports/I-00064_S01_Backend_report.md` — S01 report.
- All files listed in the S01 report's `files_changed` (expected: `orch/jobs/aggregator.py`).

## Output Files

- `ai-dev/active/I-00064/reports/I-00064_S02_CodeReview_Backend_report.md`

## Context

Review the implementation work done in S01 by `backend-impl`. The bug
(I-00064) is described in the design doc — read it first.

The fix is small and surgical. Your job is to confirm it is correct,
minimal, and does not introduce regressions in adjacent code paths.

## Pre-Review Lint & Format Gate (NON-NEGOTIABLE)

Run on the files listed in the S01 report's `files_changed`:

```bash
make lint
make format-check
```

Any NEW violations introduced by S01 → CRITICAL finding with
`"category": "conventions"`.

## Review Checklist

### 1. Correctness of the fix

- Does `_build_doc_generation_raw` now expose the **inner**
  `ProjectDoc.doc_id` as `raw["doc_id"]` (not the composite FK)?
- Does the orphan case (`job.doc_id is None` OR doc row missing) result
  in `raw["doc_id"] is None` so the template hides the link?
- Is `_fetch_doc_generation` reusing the same batched `ProjectDoc` query
  it already issues for titles (no new query loop, no N+1)?
- Is `_get_doc_generation` reusing its existing `self._session.get(
  ProjectDoc, job.doc_id)` lookup (single query, not duplicated)?

### 2. Convention comment in `_fetch_code_mapping`

- Does the comment explicitly call out that this `doc_id` is the
  composite FK and MUST NOT be used to build a `/docs/{id}` URL?
- Was the value itself left unchanged (the comment is the only edit
  there)?

### 3. No other consumers regressed

- Search for `raw\["doc_id"\]`, `raw\.get\("doc_id"\)`, and
  `raw_doc\["doc_id"\]` usages in:
  - `dashboard/templates/`
  - `orch/`
  - `tests/`
- Confirm none of them rely on the **composite** form for
  `doc_generation` rows. The only known consumer of the composite was
  the `_get_doc_generation` self-lookup, which the fix removes.
- The existing assertion at
  `tests/integration/test_i00059_doc_generation_get_job.py:92`
  (`row.raw.get("doc_id") is None` for orphans) MUST still hold.

### 4. Type hints & SQLAlchemy idioms

- New parameter `inner_doc_id: str | None = None` is annotated and
  matches project conventions.
- Batch query uses `select(ProjectDoc).where(ProjectDoc.id.in_(doc_ids))`
  — no string concatenation, no `.execute(text(...))`.

### 5. No scope creep

- ONLY `orch/jobs/aggregator.py` was modified. No edits to:
  - `orch/db/models.py`
  - `orch/doc_service.py`
  - `dashboard/routers/docs.py`
  - `dashboard/templates/pages/project/job_detail.html`

## Test Verification (NON-NEGOTIABLE)

Run `make test-unit` (and `make test-integration` if S03 has not yet
run; otherwise the runtime suite is what counts). Report results.

## Severity Levels

| Severity | Meaning |
|----------|---------|
| CRITICAL | Bug not actually fixed, regression introduced, or a security/data issue |
| HIGH | Convention/lint/format new violation; missing orphan handling |
| MEDIUM_FIXABLE | Code quality issue (e.g., duplicate query, unused param) |
| MEDIUM_SUGGESTION | Style improvement |
| LOW | Nitpick |

## Review Result Contract

```json
{
  "step": "S02",
  "agent": "CodeReview",
  "work_item": "I-00064",
  "step_reviewed": "S01",
  "verdict": "pass|fail",
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "notes": ""
}
```

`verdict` is `pass` only when CRITICAL + HIGH + MEDIUM_FIXABLE = 0.
