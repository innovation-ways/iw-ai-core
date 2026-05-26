# CR-00088 S04 — Code Review Report

## Step Summary

**Reviewer**: code-review-impl  
**Work Item**: CR-00088 — Auto-merge — partial-allowlist semantics in Phase 1 dry-run  
**Steps Reviewed**: S01 (backend-impl), S02 (backend-impl), S03 (tests-impl)  
**Result**: **PASS with one MEDIUM_FIXABLE finding**

---

## Pre-Review Gates

| Gate | Result |
|------|--------|
| `make lint` | ✅ All checks passed |
| `make format-check` | ❌ **1 file needs reformatting** (see finding #1) |

---

## Scope Verification

`git diff --name-only main` against the design manifest:

| File | Expected | Present |
|------|----------|---------|
| `orch/daemon/auto_merge.py` | ✅ | ✅ |
| `orch/daemon/merge_queue.py` | ✅ | ✅ |
| `tests/unit/test_auto_merge_classifier.py` | ✅ | ✅ |
| `tests/integration/test_auto_merge_phase1.py` | ✅ | ✅ |
| `tests/integration/test_auto_merge_partial_allowlist.py` | ✅ (new) | ✅ |
| `docs/research/R-00076-llm-automated-merge-resolution.md` | ✅ | ✅ |
| `ai-dev/active/AUTO_MERGE_RESOLUTION.md` | ✅ | ✅ |
| `tests/unit/test_auto_merge_invoke.py` | ❌ FORBIDDEN | ❌ not in diff ✅ |
| Any other files | ❌ | ❌ None found |

**Scope: CLEAN.**

---

## Findings

### Finding #1 — MEDIUM_FIXABLE (conventions, format)

**File**: `tests/integration/test_auto_merge_partial_allowlist.py`  
**Lines**: 240–241, 246–247 (duplicate assertion block)

**Description**: `make format-check` reports this file needs reformatting. Two adjacent `post_hash` assertions (both labeled "# 5" and "# 6. Phase-1 invariant: worktree untouched") are identical and represent a copy-paste duplication. Ruff wants to join the two string literals into one `f"-style` format string on a single line.

```python
# Lines 240-247 (current):
    # 5. Phase-1 invariant: worktree untouched
    post_hash = _hash_worktree_tree(tmp_path)
    assert post_hash == pre_hash, (
        "Phase 1 dry-run must not mutate the worktree. "
        f"Pre-hash={pre_hash}, post-hash={post_hash}"
    )

    # 6. Phase-1 invariant: worktree untouched
    post_hash = _hash_worktree_tree(tmp_path)
    assert post_hash == pre_hash, (
        "Phase 1 dry-run must not mutate the worktree. "
        f"Pre-hash={pre_hash}, post-hash={post_hash}"
    )
```

The second block (comment "# 6.") is dead code — `_hash_worktree_tree` is deterministic, `pre_hash` is already set, and no code path between the two blocks could mutate the worktree in Phase 1. The duplicate should simply be removed.

**Fix**: Delete the "# 6. Phase-1 invariant" block entirely. The single "# 5." assertion (now the only one) is sufficient and already has a unique error message.

---

## S01 — Partition Logic Review (`classify_conflicts`)

| Checklist Item | Status |
|----------------|--------|
| `ClassificationResult.deferred_files: tuple[str, ...] = ()` — trailing default | ✅ Field is at line 266, last in the field list, has default `()` |
| Single linear pass partition (one `for rel_path` loop) | ✅ Lines 493–499: `for rel_path in conflict_files` — no double-pass |
| Order preservation (both tuples reflect input ordering) | ✅ Both lists use `append()` in iteration order; final `tuple()` preserves it |
| Empty-eligible branch keeps `skipped_reason="not_allowlisted"` | ✅ Lines 501–512: `if not eligible_files: ... skipped_reason="not_allowlisted"` |
| Non-empty eligible branch returns `skipped_reason=None` | ✅ Lines 521–534: `skipped_reason=None` |
| Refuse-list precedence unchanged | ✅ Step 1 (lines 397–413) runs before step 6; no changes |
| Docstring step 6 updated | ✅ Lines 382–388 describe the partition |
| 4 new RED-first tests | ✅ `test_partial_allowlist_returns_partition`, `test_all_deferred_keeps_skip_reason`, `test_refuselist_wins_over_partial_allowlist`, `test_deferred_files_default_empty` |
| `test_non_allowlisted_file` tightened | ✅ Now asserts `result.deferred_files == ("dashboard/static/foo.js",)` |

**S01 Verdict: PASS.**

---

## S02 — Event Metadata Thread-Through Review

| Checklist Item | Status |
|----------------|--------|
| `attempt_resolution()` accepts `deferred_files: list[str] \| None = None` | ✅ Line 873: trailing kwarg with default `None` |
| `EVENT_AUTO_RESOLUTION_ATTEMPTED` metadata has `allowlisted_files` + `deferred_files` | ✅ Lines 966–967: both keys present |
| `conflict_files` (back-compat) preserved in ATTEMPTED | ✅ Line 963: `"conflict_files": eligible_files` |
| `EVENT_AUTO_RESOLVED` metadata has `deferred_files` | ✅ Line 1060 |
| Human-readable message mentions deferred count when non-zero | ✅ Lines 1071–1076: `"...; N file(s) deferred (non-allowlisted) for operator"` |
| `EVENT_AUTO_RESOLUTION_FAILED` metadata has `deferred_files` | ✅ Line 1037 |
| `EVENT_AUTO_RESOLUTION_SKIPPED` (Phase 0 path) in `attempt_resolution()` has `deferred_files` | ✅ Line 910 |
| `merge_queue.py` passes `deferred_files=list(_classification.deferred_files)` to `attempt_resolution()` | ✅ Line ~556 |
| `merge_queue.py` `emit_skipped_event` dict includes `deferred_files` | ✅ Line ~517 |
| 4 new RED integration tests in `test_auto_merge_phase1.py` | ✅ `test_cr88_deferred_files_attempted_event`, `test_cr88_deferred_files_resolved_event`, `test_cr88_deferred_files_failed_event`, `test_cr88_deferred_files_default_empty` |
| Tests use `event.event_metadata[...]` (not `event.metadata[...]`) | ✅ All tests read `.event_metadata` |
| No new tests in `tests/unit/test_auto_merge_invoke.py` | ✅ Confirmed — file is not in diff |
| No new event types | ✅ `EVENT_AUTO_*` constants unchanged |
| `PHASE_TESTS_ONLY` guard still raises `ValueError` | ✅ Line 887–888 unchanged |
| `test_cr88_deferred_files_skipped_event` in phase-0 path | ✅ Tests the skipped event from within `attempt_resolution()` when `phase=0` |

**S02 Verdict: PASS.**

---

## S03 — Integration Test + Docs Review

| Checklist Item | Status |
|----------------|--------|
| `tests/integration/test_auto_merge_partial_allowlist.py` exists as new file | ✅ New file present |
| Test reproduces CR-00084 shape (3 files, 1 allowlisted, 2 deferred) | ✅ `docs/architecture/foo.md`, `Makefile`, `pyproject.toml` |
| Uses `AutoMergeConfig.defaults()` (production config, not a test override) | ✅ Line 107: `config = AutoMergeConfig.defaults()` |
| LLM stubbed (`FakeLLM` from `auto_merge_fixtures`) | ✅ `fake_llm` fixture injected; no real subprocess |
| Worktree-non-mutation assertion (`_hash_worktree_tree` pre/post) | ✅ Lines 130, 239–243: `pre_hash` / `post_hash` + assert |
| Phase-1 invariant: `result.success is False`, `result.phase == PHASE_DRY_RUN` | ✅ Lines 148–149 |
| Real testcontainer Postgres (`db_session` fixture) | ✅ `db_session: Session` parameter |
| `docs/research/R-00076-*.md` — partial-allowlist subsection | ✅ §5.1.1 "Partial-allowlist semantics (CR-00088)" present |
| `ai-dev/active/AUTO_MERGE_RESOLUTION.md` — tracker entry | ✅ Line 306: v1.8 changelog entry |
| Assertions are strong (exact list equality, not membership checks) | ✅ `== ["docs/architecture/foo.md"]` (exact), `== ["Makefile", "pyproject.toml"]` (exact) |
| `event_metadata` used (not `metadata`) | ✅ `attempted.event_metadata["allowlisted_files"]`, etc. |

**S03 Verdict: PASS (minus the format finding carried from the new test file).**

---

## Architecture Compliance

| Check | Status |
|-------|--------|
| No new event types registered | ✅ `EVENT_AUTO_*` block unchanged |
| No `from executor.*` imports added | ✅ No new executor imports |
| No new fields on `LLMCallResult` or `AutoMergeResult` | ✅ Both dataclasses untouched |
| `event_metadata` (Python name, not SQL `metadata`) used in all tests | ✅ All assertions use `.event_metadata` |
| `phase` config untouched | ✅ No changes to phase ladder or config |
| `executor/auto_merge.toml` untouched | ✅ Not in diff |
| `executor/worktree_commit.sh` untouched | ✅ Not in diff |

---

## Backwards Compatibility

| Check | Status |
|-------|--------|
| `ClassificationResult(...)` without `deferred_files` still works | ✅ Default `= ()` on field |
| Existing tests that construct `ClassificationResult` without `deferred_files` | ✅ `test_all_files_allowlisted`, `test_one_file_refuse_listed`, etc. pass without change |
| Dashboard event views unaffected (additive JSON keys) | ✅ New keys are additive |
| All-allowlisted case byte-identical to today | ✅ S01 report diff confirms `test_all_files_allowlisted` unchanged |
| `event.event_metadata` (not `event.metadata`) used throughout | ✅ All tests and code use the Python attribute name |

---

## Security

| Check | Status |
|-------|--------|
| No user-controlled string flows into subprocess/shell/filesystem | ✅ `fnmatch.fnmatchcase` is pure pattern matching |
| No new prompt content sent to LLM | ✅ `build_resolution_prompt` unchanged; only `eligible_files` reach it |
| No glob expansion against filesystem | ✅ `fnmatchcase` operates on the rel_path string, not the filesystem |

---

## Test Verification

```bash
$ uv run pytest tests/unit/test_auto_merge_classifier.py \
    tests/integration/test_auto_merge_phase1.py \
    tests/integration/test_auto_merge_partial_allowlist.py -v
```

**Result: 47 passed, 0 failed, 1 warning (pre-existing fixture reimport, unrelated to CR-00088)**

All CR-00088-specific tests confirmed passing:
- `test_partial_allowlist_returns_partition` ✅
- `test_all_deferred_keeps_skip_reason` ✅
- `test_refuselist_wins_over_partial_allowlist` ✅
- `test_deferred_files_default_empty` ✅
- `test_cr88_deferred_files_attempted_event` ✅
- `test_cr88_deferred_files_resolved_event` ✅
- `test_cr88_deferred_files_failed_event` ✅
- `test_cr88_deferred_files_default_empty` ✅
- `test_cr88_deferred_files_skipped_event` ✅
- `test_cr00084_shape_partitions_event_metadata` ✅

---

## Cross-Step: Partition Invariants

| Invariant | Verified |
|-----------|----------|
| Refuse-list precedence (step 1 before step 6) | ✅ Confirmed by `test_refuselist_wins_over_partial_allowlist` + code review |
| Order preservation (single-pass loop, `append()` in iteration order) | ✅ Confirmed by `test_partial_allowlist_returns_partition` + code review |
| Phase-1 worktree non-mutation (`_hash_worktree_tree` pre == post) | ✅ Verified by `test_cr00084_shape_partitions_event_metadata` (line 243) + `test_invariant3_phase1_never_modifies_worktree` (already existed) |

**partition_invariants_verified: true**

---

## Summary

The implementation is sound. S01 correctly partitions the allowlist check, S02 correctly threads `deferred_files` through every daemon event metadata path (including the FAILED event required by AC6), and S03's end-to-end integration test validates the CR-00084 shape with strong assertions and no real LLM calls. The only issue is a minor format violation in the new test file that `make format-check` catches — the second duplicate worktree-hash assertion block should be removed.

---

## Review Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "CR-00088",
  "steps_reviewed": ["S01", "S02", "S03"],
  "verdict": "pass",
  "findings": [
    {
      "severity": "MEDIUM_FIXABLE",
      "category": "conventions",
      "file": "tests/integration/test_auto_merge_partial_allowlist.py",
      "line": 244,
      "description": "make format-check reports 2 format violations. The second 'post_hash' assert block (comment '# 6. Phase-1 invariant: worktree untouched') is identical to the first and is dead code — no mutation can occur between the two calls. Delete it. Ruff wants the remaining single assertion to have its string on one line.",
      "suggestion": "Delete lines 244-247 (the duplicate '# 6. Phase-1 invariant' block). Keep only the '# 5.' assertion."
    }
  ],
  "mandatory_fix_count": 1,
  "tests_passed": true,
  "test_summary": "47 passed, 0 failed",
  "partition_invariants_verified": true,
  "scope_violations": [],
  "notes": "The format finding is the only issue. All five ACs (AC1-AC5) are verified by the test suite. AC6 (FAILED event has deferred_files) is verified in test_cr88_deferred_files_failed_event. The design doc says tests/integration/test_auto_merge_partial_allowlist.py is a NEW file; it is present and correct. All three S01/S02/S03 TDD RED chains are documented in their respective reports."
}
```