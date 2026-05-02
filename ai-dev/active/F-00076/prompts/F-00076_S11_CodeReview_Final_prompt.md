# F-00076_S11_CodeReview_Final_prompt

**Work Item**: F-00076 -- Cross-batch file-conflict gate
**Step**: S11
**Agent**: code-review-final-impl

---

## Input Files

- `ai-dev/active/F-00076/F-00076_Feature_Design.md`
- ALL prior step reports under `ai-dev/active/F-00076/reports/`
- Full git diff of the worktree branch vs `main`

## Review Scope

This is the global cross-agent review. Verify integration correctness across S01–S10.

1. **Contract chain**:
   - S01 column shape matches what S03 writes and S04 reads.
   - S03's `parse_impacted_paths` output matches what S04's gate consumes.
   - S04's `_emit_event` payload (keys: `candidate_item_id`, `blocking_item_id`, `conflicting_globs`) matches what S07's frontend reads.
   - `merge_info["conflict_files"]` shape consistent: array of strings, never null.

2. **Design-doc adherence**:
   - All six ACs covered by at least one integration test.
   - All eight Invariants are enforced by code (not just docstrings).
   - Out-of-scope items are NOT shipped (e.g., no pre-merge trial-merge, no global parallelism cap).

3. **Architecture**:
   - `scope_overlap.py` is a pure helper module (no DB / no logger import beyond standard) — daemon imports it cleanly.
   - Templates updated identically (active + master copies).
   - Manifest `scope.allowed_paths` mirrors `WorkItem.impacted_paths` for F-00076 itself.

4. **Risk surface**:
   - The daemon launch loop's complexity hasn't grown unsafely (gate is one new branch).
   - In-flight scope query is bounded (project_id filter, status filter).
   - No new long-held DB locks.
   - `pathspec` import is fail-fast at module load — daemon won't silently skip the gate.

5. **Test pass status**:
   - Re-run `make check` (full quality + tests).
   - Record results in the report.

## Severity Levels

- **CRITICAL**: cross-step contract broken, production risk, data loss possible.
- **HIGH**: missing test for an Invariant, security issue.
- **MEDIUM**: integration friction, doc drift, observability gap.
- **LOW**: nit.

## Output

`ai-dev/active/F-00076/reports/F-00076_S11_CodeReview_Final_report.md` containing:

- One-line verdict (PASS / NEEDS_FIXES).
- Findings grouped by severity, each with file:line and recommended fix.
- Coverage matrix: AC1..AC6 → test file, Invariant1..8 → code-or-test reference.
- Output of `make check`.

## Subagent Result Contract

```json
{
  "step": "S11",
  "agent": "code-review-final-impl",
  "work_item": "F-00076",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["ai-dev/active/F-00076/reports/F-00076_S11_CodeReview_Final_report.md"],
  "verdict": "PASS|NEEDS_FIXES",
  "findings_count": {"critical": 0, "high": 0, "medium": 0, "low": 0},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed",
  "blockers": [],
  "notes": ""
}
```
