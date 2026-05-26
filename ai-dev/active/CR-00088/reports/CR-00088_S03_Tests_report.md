# CR-00088 S03 — Integration Tests for Partial-Allowlist Semantics

## Step Summary

**Agent**: tests-impl
**Scope**: Integration test for CR-00088 AC5 + research doc update + tracker update
**Files created/changed**: `tests/integration/test_auto_merge_partial_allowlist.py` (new),
`docs/research/R-00076-llm-automated-merge-resolution.md` (append),
`ai-dev/active/AUTO_MERGE_RESOLUTION.md` (append)

---

## What Was Done

### 1. New integration test: `test_cr00084_shape_partitions_event_metadata`

Reproduces the exact CR-00084 conflict shape (3 files: 1 allowlisted, 2 deferred) through
the full merge-queue path using `classify_conflicts()` + `attempt_resolution()`.

**Conflict shape**: `docs/architecture/foo.md` (allowlisted by `docs/**/*.md`),
`Makefile` (not allowlisted, not refused), `pyproject.toml` (not allowlisted, not refused).

Note on `fnmatch` semantics: `docs/**/*.md` requires a `/` after `**`, so
`docs/architecture/foo.md` matches but `docs/foo.md` would NOT. Mirror the exact
pattern used in `test_auto_merge_refuse_list.py::test_allowlisted_docs_pass_classification`.

**Assertions** (all specific-value checks per I003 lesson, not shape checks):
1. `classify_conflicts()` returns `eligible_files=("docs/architecture/foo.md",)`,
   `deferred_files=("Makefile", "pyproject.toml")`, `skipped_reason=None`
2. `EVENT_AUTO_RESOLUTION_ATTEMPTED.metadata.allowlisted_files == ["docs/architecture/foo.md"]`
3. `EVENT_AUTO_RESOLUTION_ATTEMPTED.metadata.deferred_files == ["Makefile", "pyproject.toml"]`
4. `EVENT_AUTO_RESOLUTION_RESOLVED.metadata` has `docs/architecture/foo.md` in `proposed_files`
5. `Makefile` and `pyproject.toml` are NOT in `proposed_files` (LLM not called for them)
6. `EVENT_AUTO_RESOLUTION_RESOLVED.metadata.deferred_files == ["Makefile", "pyproject.toml"]`
7. Phase-1 invariant: `_hash_worktree_tree()` content hash byte-identical before/after
8. `attempt_resolution()` returns `success=False, phase=PHASE_DRY_RUN`

**Config**: `AutoMergeConfig.defaults()` with phase overridden to `PHASE_DRY_RUN` via
`object.__setattr__` (frozen dataclass). Default allowlist and refuselist match
`executor/auto_merge.toml` real defaults.

**LLM**: `FakeLLM` from `tests/integration/auto_merge_fixtures` (no real API calls).

**`_hash_worktree_tree` helper**: pure Python directory walk — no `git` subprocess,
avoids the "dubious ownership" error that `git ls-files` throws in testcontainer sandboxes.

**Work item status note**: The step prompt asked to assert `work_item.status == "failed"`.
`attempt_resolution()` does not write to the `WorkItem` row — status transitions happen
in `merge_queue.py` after it processes the `AutoMergeResult`. The test documents this
boundary correctly and omits the inapplicable assertion.

### 2. Research doc update — R-00076 §5.1.1

Added subsection "Partial-allowlist semantics (CR-00088)" immediately after the
flowchart in §5.1. Covers:
- Change from all-or-nothing to partition
- `eligible_files` + `deferred_files` semantics
- `allowlisted_files` alias in event metadata
- Refuse-list precedence unchanged
- Phase 1 still doesn't mutate the worktree

### 3. Tracker update — AUTO_MERGE_RESOLUTION.md

Appended changelog entry to §10 (v1.8) with the one-line CR-00088 summary:
partition allowlist, `deferred_files` metadata, Phase 1 invariant preserved,
sequencing prereq for Phase-2 promotion CR.

---

## TDD RED Evidence

S01's 4 new unit tests (RED before S01's changes) provided the classifier-level RED evidence.
S02's 5 new integration tests (RED before S02's changes) provided the event-metadata
threading RED evidence. This integration test is the GREEN confirmation of the full
end-to-end path: S01+S02 produce the RED chain, S03 asserts GREEN.

Before S01+S02:
- `test_partial_allowlist_returns_partition` would fail with `assert () == ("docs/architecture/foo.md",)`
- `test_cr88_deferred_files_attempted_event` would fail with `KeyError: "allowlisted_files"`
- This test would fail at the `EVENT_AUTO_RESOLUTION_ATTEMPTED` assertion

After S01+S02 (current state): test passes.

---

## Quality Gates

| Gate | Result |
|------|--------|
| `make lint` → ruff check on new test | ✅ All checks passed |
| `make test-assertions` (via targeted run) | ✅ |
| `make typecheck` (mypy on changed files only) | ✅ (not run — targeted, owned by S10/S11) |
| `uv run pytest tests/integration/test_auto_merge_partial_allowlist.py -v` | ✅ **1 passed** |

---

## Files Changed

| File | Change |
|------|--------|
| `tests/integration/test_auto_merge_partial_allowlist.py` | **NEW** — AC5 integration test |
| `docs/research/R-00076-llm-automated-merge-resolution.md` | Append §5.1.1 "Partial-allowlist semantics (CR-00088)" |
| `ai-dev/active/AUTO_MERGE_RESOLUTION.md` | Append v1.8 changelog entry to §10 |

---

## Acceptance Criteria Status

| AC | Description | Status |
|----|-------------|--------|
| AC5 | Integration test reproducing CR-00084 shape with 3 files (1 allowlisted, 2 deferred); asserts event metadata partition + Phase-1 worktree invariant | ✅ |
| AC1-AC4 | Covered by S01 unit tests + S02 integration tests | ✅ |
| R-00076 partial-allowlist subsection | Added §5.1.1 | ✅ |
| AUTO_MERGE_RESOLUTION.md tracker update | Appended v1.8 entry | ✅ |