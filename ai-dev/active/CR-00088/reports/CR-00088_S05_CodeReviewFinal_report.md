# CR-00088 S05 — Final Code Review Report

**Reviewer**: code-review-final-impl
**Work Item**: CR-00088 — Auto-merge — partial-allowlist semantics in Phase 1 dry-run
**Steps Reviewed**: S01 (backend-impl), S02 (backend-impl), S03 (tests-impl)
**Result**: **PASS** — zero CRITICAL, zero HIGH, zero MEDIUM_FIXABLE findings

---

## Pre-Review Gates

| Gate | Result | Notes |
|------|--------|-------|
| `make lint` | ✅ All checks passed | ruff + templates |
| `make format-check` | ✅ All checks passed | 903 files formatted, 0 violations |

> **S04 carryover**: S04 reported 2 format violations in `tests/integration/test_auto_merge_partial_allowlist.py` (the duplicate `# 6. Phase-1 invariant` dead-code block + string literal formatting). Both were fixed during this review: (1) `uv run ruff format` normalised the string literals; (2) the duplicate `post_hash` assertion block (identical to the `# 5` block above it) was deleted as dead code. The test file now has exactly one worktree-hash assertion.

---

## Scope Verification

`git diff --name-only main` (modified) + untracked new files (confirmed via `git status --porcelain`):

| File | Status | In Manifest? |
|------|--------|-------------|
| `orch/daemon/auto_merge.py` | modified ✅ | ✅ |
| `orch/daemon/merge_queue.py` | modified ✅ | ✅ |
| `tests/unit/test_auto_merge_classifier.py` | modified ✅ | ✅ |
| `tests/integration/test_auto_merge_phase1.py` | modified ✅ | ✅ |
| `tests/integration/test_auto_merge_partial_allowlist.py` | **new (untracked) ✅** | ✅ |
| `docs/research/R-00076-llm-automated-merge-resolution.md` | modified ✅ | ✅ |
| `ai-dev/active/AUTO_MERGE_RESOLUTION.md` | modified ✅ | ✅ |
| `tests/unit/test_auto_merge_invoke.py` | **absent ✅** | forbidden |

Scope is clean. No file outside the manifest's `allowed_paths` and `ai-dev/active/CR-00088/**` + `ai-dev/work/CR-00088/**`.

---

## AC × Test Cross-Walk

| AC | Test(s) | File:line |
|----|---------|-----------|
| AC1 (partition correctness) | `test_partial_allowlist_returns_partition` | `tests/unit/test_auto_merge_classifier.py:519` |
| AC2 (all-deferred skip) | `test_all_deferred_keeps_skip_reason` + `test_cr88_deferred_files_skipped_event` | `tests/unit/test_auto_merge_classifier.py:547` + `tests/integration/test_auto_merge_phase1.py:1241` |
| AC3 (refuse-list wins) | `test_refuselist_wins_over_partial_allowlist` | `tests/unit/test_auto_merge_classifier.py:574` |
| AC4 (Phase-1 non-mutation) | `test_cr00084_shape_partitions_event_metadata` (worktree-hash assert) + `test_invariant3_phase1_never_modifies_worktree` | `tests/integration/test_auto_merge_partial_allowlist.py:~243` + `tests/integration/test_auto_merge_phase1.py:825` |
| AC5 (CR-00084 shape end-to-end) | `test_cr00084_shape_partitions_event_metadata` | `tests/integration/test_auto_merge_partial_allowlist.py:99` |
| AC6 (FAILED event has deferred_files on LLM abstain/error) | `test_cr88_deferred_files_failed_event` | `tests/integration/test_auto_merge_phase1.py:1145` |

All ACs have at least one test. No empty rows.

---

## AC Walk-Through

### AC1: Partial-allowlist partitions correctly

**Statement**: Given 3 conflict files (1 allowlisted, 2 not) + no refuse-list, `classify_conflicts()` returns `eligible_files=(allowlisted)`, `deferred_files=(the-2-non-allowlisted)`, `skipped_reason=None`.

**Evidence**: `git diff main -- orch/daemon/auto_merge.py` shows the partition loop at step 6:
```python
eligible_files: list[str] = []
deferred_files: list[str] = []
for rel_path in conflict_files:
    if any(fnmatch.fnmatchcase(rel_path, pat) for pat in config.allowlist_patterns):
        eligible_files.append(rel_path)
    else:
        deferred_files.append(rel_path)
```
`test_partial_allowlist_returns_partition` (line 519) asserts exact tuple equality:
```python
assert result.eligible_files == ("docs/foo.md",)
assert result.deferred_files == ("Makefile",)
assert result.skipped_reason is None
```

**Verdict**: PASS

---

### AC2: All-deferred still emits existing skip event

**Statement**: All conflicted files outside allowlist → `skipped_reason="not_allowlisted"` + `deferred_files` populated + `EVENT_AUTO_RESOLUTION_SKIPPED` emitted.

**Evidence**:
- `git diff main -- orch/daemon/auto_merge.py` shows the empty-eligible branch (step 6) sets `skipped_reason="not_allowlisted"` and `deferred_files=tuple(deferred_files)`.
- `git diff main -- orch/daemon/merge_queue.py` shows `emit_skipped_event` dict now includes `"deferred_files": list(_classification.deferred_files)` (line ~519).
- `test_all_deferred_keeps_skip_reason` (line 547) asserts:
  ```python
  assert result.eligible_files == ()
  assert result.deferred_files == ("Makefile", "pyproject.toml")
  assert result.skipped_reason == "not_allowlisted"
  ```
- `test_cr88_deferred_files_skipped_event` (line 1241) calls `attempt_resolution()` with `phase=0` and asserts the SKIPPED event's `event_metadata["deferred_files"]` equals the input.

**Verdict**: PASS

---

### AC3: Refuse-list wins over partial allowlist

**Statement**: Refuse-list aborts before the partition step — `deferred_files=()` in the refuse-list outcome.

**Evidence**:
- `git diff main -- orch/daemon/auto_merge.py` confirms step 1 (refuse-list check, ~line 397) returns BEFORE step 6 (partition, ~line 489). No changes were made to step 1.
- `test_refuselist_wins_over_partial_allowlist` (line 574) uses 3 files including one allowlisted and one refuse-listed:
  ```python
  assert result.skipped_reason == "refuse_list"
  assert result.refuse_files == ("orch/db/migrations/versions/abc.py",)
  assert result.eligible_files == ()
  assert result.deferred_files == ()
  ```

**Verdict**: PASS

---

### AC4: Phase-1 dry-run never mutates worktree

**Statement**: With `phase=1`, `attempt_resolution()` completes without touching the worktree's working tree.

**Evidence**:
- `git diff main -- orch/daemon/auto_merge.py` confirms the `PHASE_TESTS_ONLY` guard (`if config.phase >= PHASE_TESTS_ONLY: raise ValueError`) is untouched at ~line 887.
- `test_cr00084_shape_partitions_event_metadata` in `test_auto_merge_partial_allowlist.py` computes `pre_hash = _hash_worktree_tree(tmp_path)` before calling `attempt_resolution()` and asserts `post_hash == pre_hash` (single assertion block after the format fix).
- `test_invariant3_phase1_never_modifies_worktree` in `test_auto_merge_phase1.py` is a pre-existing test that verifies the same invariant with a different conflict shape.

**Verdict**: PASS

---

### AC5: Integration test reproducing CR-00084 shape

**Statement**: An integration test with the exact CR-00084 conflict shape (Makefile, docs/architecture/foo.md, pyproject.toml) asserts correct event metadata partition and Phase-1 invariant.

**Evidence**:
- `tests/integration/test_auto_merge_partial_allowlist.py` exists as an untracked new file (confirmed via `git status`).
- `test_cr00084_shape_partitions_event_metadata` (line 99) creates a worktree with the 3 conflict files, runs `classify_conflicts()` then `attempt_resolution()` through a testcontainer DB session.
- Key assertions:
  ```python
  assert classify_result.eligible_files == ("docs/architecture/foo.md",)
  assert classify_result.deferred_files == ("Makefile", "pyproject.toml")
  assert attempted.event_metadata["allowlisted_files"] == ["docs/architecture/foo.md"]
  assert attempted.event_metadata["deferred_files"] == ["Makefile", "pyproject.toml"]
  assert "Makefile" not in proposed   # LLM not called for deferred
  assert "pyproject.toml" not in proposed
  assert resolved.event_metadata["deferred_files"] == ["Makefile", "pyproject.toml"]
  assert post_hash == pre_hash       # Phase-1 non-mutation
  assert result.success is False and result.phase == PHASE_DRY_RUN
  ```
- All assertions are exact-value checks (not shape/membership-only).

**Verdict**: PASS

---

### AC6: FAILED event surfaces deferred subset on LLM abstain/error

**Statement**: `EVENT_AUTO_RESOLUTION_FAILED.event_metadata["deferred_files"]` contains the deferred subset when LLM abstains or errors for all eligible files.

**Evidence**:
- `git diff main -- orch/daemon/auto_merge.py` shows `EVENT_AUTO_RESOLUTION_FAILED` metadata dict (~line 1034) now includes `"deferred_files": list(deferred_files or [])`.
- `test_cr88_deferred_files_failed_event` (line 1145) stubs `fake_llm.abstain_for.add("docs/foo.md")`, passes `eligible_files=["docs/foo.md"]` and `deferred_files=["Makefile","pyproject.toml"]`, then asserts:
  ```python
  assert meta["deferred_files"] == deferred_files          # exact match
  assert meta["abstained_files"] == eligible_files        # AC6 co-assertion
  ```

**Verdict**: PASS

---

## Cross-Step Partition Invariants

| Invariant | Check | Evidence | Verdict |
|-----------|-------|----------|---------|
| Refuse-list precedence (step 1 < step 6) | Code review of `git diff main -- orch/daemon/auto_merge.py` | Step 1 return (~line 397) is before step 6 partition (~line 489); no changes to step 1 | ✅ |
| Order preservation (single linear pass) | Code review of partition loop | `for rel_path in conflict_files: ... append()` — one pass, append preserves iteration order | ✅ |
| Phase-1 non-mutation (`attempt_resolution` aborts before worktree write) | `PHASE_TESTS_ONLY` guard at ~line 887 | `if config.phase >= PHASE_TESTS_ONLY: raise ValueError` — unchanged | ✅ |
| Backward compat for `ClassificationResult` | `deferred_files: tuple[str, ...] = ()` trailing default | Field is last in dataclass with default `()`; all 7 existing constructors in `classify_conflicts` remain positional | ✅ |
| Backward compat for event metadata | `conflict_files` and `eligible_files` keys preserved | ATTEMPTED event keeps `"conflict_files": eligible_files`; no key removals | ✅ |
| FAILED event carries `deferred_files` | Read dict literal in `git diff main` at ~line 1034 | `"deferred_files": list(deferred_files or [])` present in FAILED metadata dict | ✅ |
| Tests use `event.event_metadata` (not `event.metadata`) | `grep -n "\.metadata\[" tests/integration/test_auto_merge_partial_allowlist.py tests/integration/test_auto_merge_phase1.py` | Zero matches — all tests use `.event_metadata` | ✅ |

`partition_invariants_verified: true`

---

## Test Coverage Cross-Check

```bash
uv run pytest \
  tests/unit/test_auto_merge_classifier.py \
  tests/integration/test_auto_merge_phase1.py \
  tests/integration/test_auto_merge_partial_allowlist.py \
  -v
```

**Result: 47 passed, 0 failed** (1 pre-existing PytestAssertRewriteWarning, unrelated to CR-00088)

| Suite | Count | New CR-00088 tests |
|-------|-------|---------------------|
| `test_auto_merge_classifier.py` | 22 | 4 new: `test_partial_allowlist_returns_partition`, `test_all_deferred_keeps_skip_reason`, `test_refuselist_wins_over_partial_allowlist`, `test_deferred_files_default_empty` |
| `test_auto_merge_phase1.py` | 24 | 5 new: `test_cr88_deferred_files_attempted_event`, `test_cr88_deferred_files_resolved_event`, `test_cr88_deferred_files_failed_event`, `test_cr88_deferred_files_default_empty`, `test_cr88_deferred_files_skipped_event` |
| `test_auto_merge_partial_allowlist.py` | 1 | 1 new: `test_cr00084_shape_partitions_event_metadata` |

All new tests pass. No `xfail`, `skipif`, or quarantine.

---

## Documentation Sanity

- **`docs/research/R-00076-llm-automated-merge-resolution.md`**: §5.1.1 "Partial-allowlist semantics (CR-00088)" present at line 223. Accurately describes partition semantics, `deferred_files`, `allowlisted_files` alias, refuse-list precedence, and Phase-1 invariant.
- **`ai-dev/active/AUTO_MERGE_RESOLUTION.md`**: v1.8 changelog entry at line 306 with correct date (2026-05-25), CR number (CR-00088), and one-line summary of changes.

---

## Functional Doc Sanity

Re-reading `CR-00088_Functional.md`: the plain-English description matches what shipped exactly:
- Three-bucket classification (refused, eligible, deferred) ✅
- Refuse-list still wins outright ✅
- Partial-allowlist case invokes LLM for eligible subset ✅
- All-deferred case preserves `not_allowlisted` skip with explicit deferred list ✅
- Phase stays at dry-run, worktree never modified ✅
- Operator sees two lists in daemon event metadata ✅

No behavioural deviation from the design.

---

## Summary of Changes Fixed During This Review

S04 identified one MEDIUM_FIXABLE finding (format convention in `test_auto_merge_partial_allowlist.py`). Both sub-issues were resolved before finalising this report:

1. **String literal formatting**: `uv run ruff format tests/integration/test_auto_merge_partial_allowlist.py` — normalises the two adjacent string literals in the worktree-hash assertion from `"... "...` to `f"..."`.
2. **Duplicate dead-code block**: Deleted the `# 6. Phase-1 invariant` block (identical to `# 5` above it — no code between them could mutate the worktree in Phase 1).

---

## Review Result Contract

```json
{
  "step": "S05",
  "agent": "code-review-final-impl",
  "work_item": "CR-00088",
  "implementation_steps": ["S01", "S02", "S03"],
  "verdict": "pass",
  "ac_verdicts": [
    {"ac": "AC1", "verdict": "PASS", "evidence": "git diff main -- orch/daemon/auto_merge.py (partition loop step 6) + test_partial_allowlist_returns_partition at tests/unit/test_auto_merge_classifier.py:519"},
    {"ac": "AC2", "verdict": "PASS", "evidence": "test_all_deferred_keeps_skip_reason at tests/unit/test_auto_merge_classifier.py:547 + test_cr88_deferred_files_skipped_event at tests/integration/test_auto_merge_phase1.py:1241 + merge_queue.py emit_skipped_event diff"},
    {"ac": "AC3", "verdict": "PASS", "evidence": "test_refuselist_wins_over_partial_allowlist at tests/unit/test_auto_merge_classifier.py:574; step 1 return confirmed before step 6 partition in git diff"},
    {"ac": "AC4", "verdict": "PASS", "evidence": "PHASE_TESTS_ONLY guard at ~line 887 untouched; test_cr00084_shape_partitions_event_metadata worktree-hash assertion + test_invariant3_phase1_never_modifies_worktree"},
    {"ac": "AC5", "verdict": "PASS", "evidence": "test_cr00084_shape_partitions_event_metadata in tests/integration/test_auto_merge_partial_allowlist.py:99 — 6 exact-value assertions including Phase-1 worktree hash and event metadata"},
    {"ac": "AC6", "verdict": "PASS", "evidence": "git diff main -- orch/daemon/auto_merge.py (FAILED metadata dict ~line 1034 has deferred_files) + test_cr88_deferred_files_failed_event at tests/integration/test_auto_merge_phase1.py:1145"}
  ],
  "partition_invariants_verified": true,
  "findings": [],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "47 passed, 0 failed",
  "scope_violations": [],
  "notes": "S04's one MEDIUM_FIXABLE finding (format in test_auto_merge_partial_allowlist.py) was resolved during this review: (1) uv run ruff format normalised the string literals; (2) duplicate '# 6. Phase-1 invariant' post_hash block was deleted as dead code. All pre-review gates now green. All 6 ACs have PASS verdicts with concrete test and code evidence."
}
```
