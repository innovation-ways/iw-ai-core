# I-00083 S05 — Final Cross-Agent Code Review

**Verdict**: `needs-fix` (1 CRITICAL + 2 HIGH unresolved from S02).

---

## Inputs reviewed

- `ai-dev/active/I-00083/I-00083_Issue_Design.md`
- `ai-dev/active/I-00083/workflow-manifest.json` (`scope.allowed_paths`)
- `ai-dev/active/I-00083/reports/I-00083_S01_Pipeline_report.md`
- `ai-dev/active/I-00083/reports/I-00083_S02_CodeReview_report.md`
- `ai-dev/active/I-00083/reports/I-00083_S03_Tests_report.md`
- `ai-dev/active/I-00083/reports/I-00083_S04_CodeReview_report.md`
- `git diff HEAD` (unstaged changes) and `git status`
- Source files: `orch/active_files.py`, `orch/daemon/batch_manager.py`,
  `tests/integration/test_branch_base_drift.py`,
  `orch/cli/item_commands.py:14,649`

---

## Independently re-verified

### Reproduction + regression test results

```
$ uv run pytest tests/integration/test_branch_base_drift.py -v --no-cov
collected 7 items

TestI00083BranchBaseDrift::test_i00083_b_worktree_does_not_inherit_a_pre_impl_test_drift PASSED
TestI00083HappyPathSoloItem::test_solo_item_emits_empty_sibling_log_and_transitions_to_executing PASSED
TestI00083SiblingScopeUnit::test_multiple_in_flight_siblings_non_overlapping_globs_sum_counts PASSED
TestI00083SiblingScopeUnit::test_sibling_with_merge_commit_contributes_zero PASSED
TestI00083SiblingScopeUnit::test_sibling_glob_matches_nothing_contributes_zero PASSED
TestI00083ChoreCommitAllowList::test_chore_commit_excludes_non_design_files PASSED
TestI00083ChoreCommitAllowList::test_chore_commit_with_only_non_design_files_skips_commit PASSED

7 passed in 5.52s
```

AC1 reproduction + AC3 happy-path + sibling-scope unit tests + chore-commit
allow-list tests all pass locally on the current worktree. ✅

### Scope check (`git status` / `git diff HEAD --stat`)

| File | Status | In `scope.allowed_paths`? |
|------|--------|---------------------------|
| `orch/active_files.py` | **modified** | ❌ **NO** — see C1 below |
| `orch/daemon/batch_manager.py` | modified | ✅ |
| `tests/integration/test_branch_base_drift.py` | new | ✅ |
| `orch/cli/item_commands.py` | untouched | ✅ (listed but not edited) |
| `executor/setup_worktree.sh` | untouched | ✅ (listed but not edited) |

Workflow scratch (untracked, not subject to scope):
`ai-dev/active/I-00083/I-00083/` (nested duplicate of design files),
`ai-dev/active/I-00083/reports/` (this and prior step reports).

No other source-tree files were touched. The branch HEAD (`5e84080e`) is
the chore-commit snapshot, and the actual fix lives in the unstaged diff.

---

## CRITICAL

### C1 — Scope deviation: `orch/active_files.py` is modified but not in `allowed_paths`

The S05 prompt is explicit:

> `git diff --stat` shows ONLY files in `scope.allowed_paths`. ANY other
> file is CRITICAL.

`workflow-manifest.json` declares:

```json
"scope": {
  "allowed_paths": [
    "orch/cli/item_commands.py",
    "orch/daemon/batch_manager.py",
    "executor/setup_worktree.sh",
    "tests/integration/test_branch_base_drift.py"
  ]
}
```

`orch/active_files.py` is **not** on that list, yet it received a ~90-line
rewrite (the entire chore-commit narrowing — the very first of the "two
halves" the prompt asks me to verify). `orch/cli/item_commands.py` is on
the list but was not touched (it merely imports
`ensure_active_files_committed` at line 14 and calls it at line 649).

**Structural assessment**: the design doc (§"Affected Components",
§"Code Changes") names `orch/cli/item_commands.py` because that is where
`iw approve` is implemented — but the file already delegates the
chore-commit work to `orch.active_files.ensure_active_files_committed`,
so the narrowing legitimately had to land in `active_files.py`. The S01
report calls this out plainly. The change is logically inside the spirit
of the design but mechanically outside the manifest's scope list. The
S02 review missed this; S04 was test-focused and also missed it.

**Fix**: amend `workflow-manifest.json` to add
`"orch/active_files.py"` to `scope.allowed_paths`, and (optionally) add a
short note that the chore-commit logic was implemented in the delegated
helper module rather than the entry point. This is the lowest-friction
remediation. The alternative — moving the function body into
`orch/cli/item_commands.py` purely to satisfy the manifest — would be a
code-quality regression.

I'm filing this as CRITICAL because the prompt instructs me to do so for
any out-of-scope file, but the intent here is "manifest is wrong" not
"impl was sloppy" — please decide and update one or the other.

---

## HIGH (unresolved from S02; still HIGH)

### H1 — `git add` will exit 128 when an allow-listed pathspec resolves to nothing

S02 raised this and recommended pre-filtering. The S03 report
acknowledged it ("This is a real production constraint — items approved
without a Functional.md would fail today") but did not fix it. S04 then
passed the test review without re-raising it. The pre-fix code did
`git add ai-dev/active/<id>/` (full directory pathspec — tolerant of any
internal shape). The post-fix code unconditionally passes all four
pathspecs to `git add`:

```python
# orch/active_files.py:113-125
subprocess.run(
    ["git", "-C", str(root), "add", "--", *allowed_pathspecs],
    capture_output=True, text=True, check=True,
)
```

**Empirically reproduced** in a throwaway repo on this machine:

```
$ git add -- "sub/d.txt" "sub/nonexistent.txt"
fatal: pathspec 'sub/nonexistent.txt' did not match any files
exit=128
```

`check=True` means the whole `subprocess.run` raises `CalledProcessError`
and `iw approve` dies. Concrete failure modes I read into the codebase:

- An item created without `<ID>_Functional.md`. `item_commands.py:414-418`
  even has explicit "auto-detect sibling `<ID>_Functional.md`" logic,
  implying it can legitimately be absent — and `validate_approve_transition`
  imposes no presence precondition on any of the four files.
- An item whose design generator failed half-way and never wrote
  `workflow-manifest.json` or `prompts/`.
- An item with a non-conforming design filename (anything that doesn't
  match `<ID>_*_Design.md`).

The S03 test suite hides this because `_simulate_chore_commit` always
creates all four files explicitly to keep its own assertions green. The
gap is documented in the S03 report's "Issues / Observations" section
but treated as "not in scope to fix" — that's the wrong call because
this is a regression introduced by **this** issue's fix.

**Fix**: before calling `git add`, glob-resolve the four pathspecs via
`Path.glob` / `Path.is_dir` / `Path.is_file` and pass only the matching
ones. The `dirty_check` at lines 93-106 already guarantees the filtered
list is non-empty before reaching `git add`, so the call stays simple.
Add a regression test that approves an item missing `<ID>_Functional.md`
and asserts the chore commit lands the design alone without error.

### H2 — `_emit_sibling_drift_log` is not wrapped, can abort `_launch_item`

S02 raised this. Still unresolved. The spec is **WARN, not BLOCK** —
verifying that contract is one of the four bullets in this step's
checklist.

What I verified by re-reading `orch/daemon/batch_manager.py:840-917`:

- There is **no** explicit `raise`, `sys.exit`, or early-return based on
  the drift count. ✅ When `total_drift > 0`, the code emits one INFO
  line and one WARNING line and continues. ✅
- BUT the function body has no outer `try/except`. Its inner helpers
  do wrap their own failures (`_list_worktree_files` at 752-768,
  `_glob_matches_any` at 793-810), and `_resolve_worktree_base_sha`
  swallows internally (1027). However:
  - `_collect_in_flight_sibling_items` (857 → 813-838) is a raw
    SQLAlchemy session query with no try/except. Any
    `OperationalError` / `DBAPIError` / detached-mapper error
    propagates straight up.
  - The `for sibling in siblings:` loop accesses
    `sibling.merge_commit_sha` and `sibling.impacted_paths` —
    lazy-loaded ORM attributes that can raise `DetachedInstanceError`
    if the session state shifts.
  - The `logger.info` `%`-formatting renders Python lists with `repr`
    semantics; safe today but if `sibling_ids` ever contains a value
    that throws in `__repr__` (e.g., a future SQLAlchemy proxy) the
    log call itself raises.

If any of those raise, `_launch_item:594` is in the call stack
**immediately after** `_setup_worktree` returned. The worktree directory
exists on disk, the BatchItem row reflects setup-completed, but the
function unwinds before reaching `BatchItemStatus.executing` at 689 and
before launching the first step at 721. That is a hard failure mode v1
forbids.

**Fix**: wrap the entire `_emit_sibling_drift_log` body in
`try/except Exception` and `logger.warning(..., exc_info=True)`. The
function returns `None` on success; the change is one indent.

---

## MEDIUM (carryover from S02 / S04 — non-blocking but on the punch list)

| ID | Source | Recommendation |
|----|--------|----------------|
| M1 | S02 | Extend in-flight status set to also include `BatchItemStatus.completed` and `BatchItemStatus.awaiting_merge_approval` (current set silently misses the precise CR-00053 window between "gates done" and "merged"). |
| M2 | S02 | `in_flight_siblings=` rendering uses Python list `repr` → `['CR-00052', 'CR-00053']` with quotes/spaces. Design example shows `[CR-00052,CR-00053]`. The S03 tests only grep substrings so they tolerate either; the public contract should be cleaned up. |
| M3 | S02 | One-line comment near `_glob_matches_any` noting it's a v1 approximation and pointing to `pathspec` PyPI lib for the BLOCK upgrade. |
| M4 | S02 | S03 unit tests against `_emit_sibling_drift_log` were added — M4 from S02 is now resolved by `TestI00083SiblingScopeUnit`. ✅ |
| M5 | S04 | `_simulate_in_flight_impl` helper is defined but never called by any test. Delete or wire into the multi-sibling test. |
| M6 | S04 | `DaemonConfig(db_port=5433, ...)` in `_make_batch_manager` is alarming next to the project's "NEVER connect tests to live DB (port 5433)" rule. The session_factory override means it's metadata only, but a non-routable placeholder (`0` or `65535`) would make the no-connection guarantee self-evident. |

---

## Checklist (S05 prompt)

| Item | Status |
|------|--------|
| Reproduction test (AC1) passes locally | ✅ |
| Happy-path regression (AC3) passes locally | ✅ |
| `git diff --stat` shows only files in `scope.allowed_paths` | ❌ **C1** — `orch/active_files.py` is out of scope |
| Both halves of (b) + launch-time-check shipped | ✅ |
| Chore-commit allow-list is comprehensive (design + functional + manifest + prompts) | ✅ |
| Allow-list is commented with an I-00083 citation | ✅ (`orch/active_files.py:7-32`) |
| Daemon log line matches spec exactly | ✅ |
| Solo-item case: `in_flight_siblings=[] sibling_paths_without_merge=0` with no `details=` | ✅ (lines 861-866) |
| Launch-time check is WARN-only: no `raise`/`sys.exit`/early-return aborting worktree creation when count is non-zero | ⚠️ No explicit abort, but **H2** — uncaught DB exception in `_collect_in_flight_sibling_items` propagates and aborts `_launch_item` before `BatchItemStatus.executing` is set |
| Backwards compatibility: items approved before this change still work; no history rewrites; merge-path untouched | ✅ (verified: `merge_queue.py`, `migration_rebase.py`, `executor/worktree_commit.sh`, `executor/setup_worktree.sh` all untouched) |

---

## Verdict

`needs-fix`.

Three issues block this review:

1. **C1 (CRITICAL)** — Resolve the scope deviation: either add
   `orch/active_files.py` to `scope.allowed_paths` in the manifest (the
   right call, since the function lives there by existing architecture)
   or relocate the chore-commit logic into `orch/cli/item_commands.py`.
2. **H1 (HIGH, regression)** — Pre-filter the chore-commit pathspecs to
   those that exist on disk; otherwise `iw approve` fails for legitimate
   items that lack one of the four allow-listed files. This is a
   regression vs the pre-S01 behaviour and is the kind of bite that
   bricks the platform for an operator the next time they hand-craft an
   item without a `Functional.md`.
3. **H2 (HIGH)** — Wrap `_emit_sibling_drift_log` body in
   `try/except Exception → logger.warning(..., exc_info=True)`. The v1
   contract is WARN-only and a stray DB error in the new code path
   would leave a half-set-up batch item with a worktree on disk and the
   BatchItem stuck in `setting_up`.

The six MEDIUMs are queued for a follow-up but do not block this step.

## Files Reviewed (this step, full)

- `orch/active_files.py` (entire file via diff vs HEAD; the modified
  function body lines 1-104)
- `orch/daemon/batch_manager.py` (lines 580-720 launch flow + lines
  740-917 new methods; cross-checked imports and surrounding context)
- `tests/integration/test_branch_base_drift.py` (read once at S04 by
  the test reviewer; verified herein by re-running the suite)
- `ai-dev/active/I-00083/I-00083_Issue_Design.md` (decision, ACs, log
  shape, status set)
- `ai-dev/active/I-00083/workflow-manifest.json` (scope.allowed_paths)
- `ai-dev/active/I-00083/reports/I-00083_S01..S04_*.md`
- `orch/cli/item_commands.py:14, 649` (call sites)

## Files Changed (this step)

| File | Change |
|------|--------|
| `ai-dev/active/I-00083/reports/I-00083_S05_CodeReviewFinal_report.md` | New — this report |

No production or test code was modified by S05 (review-only step).
