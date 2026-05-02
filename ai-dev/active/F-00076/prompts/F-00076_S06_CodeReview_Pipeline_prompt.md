# F-00076_S06_CodeReview_Pipeline_prompt

**Work Item**: F-00076 -- Cross-batch file-conflict gate
**Step**: S06
**Agent**: code-review-impl
**Reviewing**: S04 (pipeline-impl)

---

## Input Files

- `ai-dev/active/F-00076/F-00076_Feature_Design.md`
- `ai-dev/active/F-00076/reports/F-00076_S04_Pipeline_report.md`
- All files listed in S04's `files_changed`

## Review Scope

1. **`scope_overlap.py` correctness**:
   - `is_test_path` matches every `_TEST_PATH_MARKERS` pattern AND the `**/tests/**`/`**/__tests__/**` shorthand.
   - `globs_intersect` produces correct results for the documented cases (exact match, `dir/**`, mixed test+prod, both empty, `["**"]`, no overlap).
   - Returns from candidate's side, deduped, order preserved.
   - Docstring documents the probe-based approximation honestly.
   - `pathspec` import is at module-load — fail-fast if missing.

2. **Launch-time gate in `batch_manager._process_batch`**:
   - Gate runs AFTER pending check and BEFORE `executing_count` increment, so held items don't consume parallelism slots.
   - Skips Research items (`WorkItemType.research`) — bypass logic correct per AC2.
   - Filters in-flight by `BatchItem.status IN {setting_up, executing, merging}` AND `project_id == self.project_id` AND `WorkItem.type != Research`.
   - Newly launched items in the same poll cycle are appended to `in_flight_scopes` so a second item with overlapping globs holds.
   - `_emit_event` payload contains `candidate_item_id`, `blocking_item_id`, `conflicting_globs` — exactly per design.
   - Held item produces ONE event per blocking_id per cycle (not coalesced — Invariant in design).
   - `_collect_in_flight_scopes` is hoisted ABOVE the launch loop (one query per `_process_batch`), not per-item.
   - `db.commit()` after event emission so the dashboard sees the held state immediately.

3. **`merge_info["conflict_files"]` wiring**:
   - `executor/worktree_commit.sh` emits exactly one `[worktree_commit] CONFLICT_FILES <json>` line after the rebase block.
   - JSON is a JSON array of strings — verified by parsing in `merge_queue` regex.
   - `merge_queue._perform_merge` writes `conflict_files: list[str]` always (empty array if marker absent) per Invariant 6.
   - The `except MergeError` path also captures conflict_files when stdout has the marker.
   - `stdout`/`stdout_truncated` keys preserved — no regression on existing `merge_info` shape.

4. **Conventions**: `orch/CLAUDE.md`, `executor/CLAUDE.md`. Bash with `set -euo pipefail`. No docker / alembic in executor.

5. **Tests**:
   - Cover AC1 (held), AC2 (Research bypass), AC5 (conflict_files captured).
   - Cover the same-poll-cycle case (two items with mutually overlapping globs).
   - Cover the resume case (held item launches after blocker reaches `merged`).
   - Use real testcontainer per `tests/CLAUDE.md`.

## Severity Levels

(Same as S02.)

## Output

`ai-dev/active/F-00076/reports/F-00076_S06_CodeReview_Pipeline_report.md`. Re-run `make test-unit` and `make test-integration`.

## Subagent Result Contract

(Same shape as S02.)
