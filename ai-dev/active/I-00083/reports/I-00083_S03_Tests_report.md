# I-00083 S03 Tests Report

## What Was Done

Extended `tests/integration/test_branch_base_drift.py` (created by S01 with the AC1
RED→GREEN reproduction) with the AC3 regression test, three sibling-scope-check
unit tests, and two chore-commit allow-list coverage tests. Added module-level
helpers so all suites share a single fake-repo / chore-commit / in-flight-impl
fixture pattern. S01's AC1 test body was **not modified** — it still passes
unchanged.

### New helpers (module-level)
- `_simulate_chore_commit(repo, item_id, extra_active_files=None)` — drops a
  realistic `ai-dev/active/<id>/` tree (design / functional / manifest /
  prompts), optionally plants extra non-allow-listed files, then invokes the
  production `orch.active_files.ensure_active_files_committed`. Returns the
  HEAD sha (or the prior HEAD when nothing allow-listed is dirty).
- `_simulate_in_flight_impl(repo, item_id, touches)` — lands a follow-up
  commit that mimics a sibling's tests/fixtures arriving via someone else's
  prior squash merge.
- `_commit_contains(repo, sha, rel_path)` — `git ls-tree -r --name-only <sha>`
  membership check used by the chore-commit assertions.

### New test classes
1. **`TestI00083HappyPathSoloItem`** (AC3) — solo-item run with no in-flight
   siblings. Asserts exactly **one** drift log line shaped
   `in_flight_siblings=[] sibling_paths_without_merge=0`, no `WARNING` records
   from `orch.daemon.batch_manager`, and behavioural equivalence: `BatchItem`
   reaches `executing`, `worktree_info["path"]` round-trips, `started_at` is
   stamped.
2. **`TestI00083SiblingScopeUnit`** — exercises
   `BatchManager._emit_sibling_drift_log` directly:
   - **Multiple in-flight siblings, non-overlapping globs**: A1 and A2 each
     match exactly 1 file → log asserts `sibling_paths_without_merge=2`,
     `details` contains both `A1:1` and `A2:1`.
   - **Sibling with merge_commit_sha set**: drift count is 0 even though the
     sibling's path is present in B's worktree; sibling id still appears in
     `in_flight_siblings`; no WARNING.
   - **Sibling whose glob matches nothing**: drift count is 0; sibling id
     still surfaced; no WARNING.
3. **`TestI00083ChoreCommitAllowList`** — exercises
   `ensure_active_files_committed` end-to-end against a fake repo seeded with
   `notes.txt`, a JSON fixture, and a fake PNG under `ai-dev/active/<ID>/`:
   - **Excludes non-design files**: allow-listed files are present in the
     chore-commit tree; `notes.txt`, `tests/fixtures/sample.json`, and
     `evidences/screenshot.png` are **not** present in the tree but **do**
     remain on disk (untracked, to travel with the squash merge).
   - **Skips empty allow-list chore commit**: when only non-design files are
     dirty, HEAD does not advance — no half-shape chore commit lands.

### Semantic-correctness rigour (I003 lesson)
Every assertion targets a meaningful production behaviour, not a shape-only
substring:
- `sibling_paths_without_merge=2` (exact numeric count) and `A1:1`/`A2:1`
  (per-sibling breakdown) — not "the key appears".
- `not _commit_contains(repo, sha, ".../notes.txt")` — actual git tree
  membership, not a stub.
- Post-call DB state (`status`, `worktree_info`, `started_at`) — not just
  "the call returned".

## Files Changed

| File | Change |
|------|--------|
| `tests/integration/test_branch_base_drift.py` | Added 3 module-level helpers + 3 new test classes (6 new tests). S01's AC1 test body preserved verbatim. |

## Test Results

```bash
$ uv run pytest tests/integration/test_branch_base_drift.py -v --no-cov
collected 7 items

TestI00083BranchBaseDrift::test_i00083_b_worktree_does_not_inherit_a_pre_impl_test_drift PASSED
TestI00083HappyPathSoloItem::test_solo_item_emits_empty_sibling_log_and_transitions_to_executing PASSED
TestI00083SiblingScopeUnit::test_multiple_in_flight_siblings_non_overlapping_globs_sum_counts PASSED
TestI00083SiblingScopeUnit::test_sibling_with_merge_commit_contributes_zero PASSED
TestI00083SiblingScopeUnit::test_sibling_glob_matches_nothing_contributes_zero PASSED
TestI00083ChoreCommitAllowList::test_chore_commit_excludes_non_design_files PASSED
TestI00083ChoreCommitAllowList::test_chore_commit_with_only_non_design_files_skips_commit PASSED

============================== 7 passed in 4.11s ===============================
```

**AC1 (S01)**: still green — body untouched.
**AC3 (S03)**: green.
**Sibling-scope unit coverage**: green across the three branches.
**Chore-commit allow-list coverage**: green; notes.txt / fixtures / evidences
proven excluded from the chore commit.

## Quality Gates

- `uv run ruff format tests/integration/test_branch_base_drift.py` — 1 file
  left unchanged.
- `uv run ruff check tests/integration/test_branch_base_drift.py` — All
  checks passed.
- `uv run mypy tests/integration/test_branch_base_drift.py` — Success: no
  issues found in 1 source file.

## TDD

S01 captured the RED → GREEN evidence for AC1 (see S01 report). S03 adds
regression and coverage tests against the already-implemented fix; all new
tests are green at HEAD. RED evidence is not applicable for S03 because the
production code under test was already in place when S03 ran (no missing
production change for these new tests to drive). The new tests would fail
if the production behaviour regressed in any of these ways:

- `_emit_sibling_drift_log` stopped emitting the empty-siblings line on solo
  items → AC3 fails.
- The per-sibling detail-string format (`<id>:<count>`) drifted → unit tests
  fail.
- `merge_commit_sha`-shielding was removed → "merged sibling contributes
  zero" fails.
- The allow-list narrowed too far or too wide → chore-commit assertions fail.

## Issues / Observations

- The production allow-list passes each pathspec literally to `git add --`.
  Git fails if any pathspec matches nothing; in particular,
  `<item_id>_Functional.md` must always exist alongside `<item_id>_*_Design.md`
  for the chore commit to succeed. The `_simulate_chore_commit` helper
  therefore always creates both. This is a real production constraint — items
  approved without a Functional.md would fail today. Not in scope for I-00083
  to fix, but worth flagging.
- All new tests use the project's testcontainer-backed `db_session` /
  `test_project` fixtures (no live-DB writes, no mocked DB).
- No changes outside the test file.
