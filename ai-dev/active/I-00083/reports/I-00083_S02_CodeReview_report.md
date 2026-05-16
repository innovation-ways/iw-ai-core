# I-00083 S02 — Per-Agent Code Review of S01 (Pipeline)

**Verdict**: `needs-fix` (2 HIGH findings).

## Scope Reviewed

S01 changes:

- `orch/active_files.py` — chore-commit allow-list (I-00083 requirement 1).
- `orch/daemon/batch_manager.py` — launch-time sibling-scope drift log
  (I-00083 requirement 2).
- `tests/integration/test_branch_base_drift.py` — AC1 RED→GREEN reproduction.

Cross-checked against:

- `ai-dev/active/I-00083/I-00083_Issue_Design.md` (Fix Plan, AC1/AC2/AC3, log
  line spec, status-set spec).
- `ai-dev/active/I-00083/reports/I-00083_S01_Pipeline_report.md` (claims).
- `orch/db/models.py` (`WorkItem.merge_commit_sha`, `BatchItemStatus`,
  `WorkItemStatus`, `WorkItem.impacted_paths`).
- `orch/cli/item_commands.py::validate_approve_transition` (no precondition
  on the 4 chore-commit files).

---

## CRITICAL findings

None.

- **Backwards compatibility**: no historical commit rewrites; the
  narrowed chore commit only applies to items approved after this lands.
  Items mid-flight are unaffected. ✓
- **Single-item happy path**: solo case emits
  `worktree create: item=<X> base=<sha> in_flight_siblings=[] sibling_paths_without_merge=0`
  and no other behavioural change. ✓
- **Merge-path untouched**: `git diff main` shows no changes to
  `orch/daemon/merge_queue.py`, `orch/daemon/migration_rebase.py`,
  `executor/worktree_commit.sh`, or `executor/setup_worktree.sh`. The
  `_emit_sibling_drift_log` hook lives in `_launch_item`, before the
  compose phase, and is never called from the merge path. ✓

---

## HIGH findings

### H1. `git add` aborts when an allow-listed pathspec is absent

`orch/active_files.py:113-125` runs:

```python
subprocess.run(
    ["git", "-C", str(root), "add", "--", *allowed_pathspecs],
    capture_output=True, text=True, check=True,
)
```

with `allowed_pathspecs` containing **all four** entries unconditionally:

```python
_CHORE_COMMIT_PATHSPECS = [
    "{active_dir}/{item_id}_*_Design.md",
    "{active_dir}/{item_id}_Functional.md",
    "{active_dir}/workflow-manifest.json",
    "{active_dir}/prompts/",
]
```

I empirically confirmed (in a throwaway repo) that `git add -- <pathspec>`
exits **128** with `fatal: pathspec '...' did not match any files` when the
pathspec resolves to nothing — and the error happens for the run **as a
whole**, even if other pathspecs in the same invocation matched files.

Concretely this breaks `iw approve` in legitimate cases:

- An item created without `<ID>_Functional.md` (`validate_approve_transition`
  only checks `WorkItemStatus`, never the presence of the four files;
  `item_commands.py:414-418` even has explicit "auto-detect sibling
  `<ID>_Functional.md`" logic, implying it can legitimately be absent).
- An item where the design file hasn't been renamed to the
  `<ID>_*_Design.md` convention yet.
- An item missing `workflow-manifest.json` because the design generator
  failed half-way.

The previous (pre-S01) code passed `ai-dev/active/<id>/` as a directory
pathspec and was tolerant of any internal state. The narrowing is correct
in intent (it's the fix's whole point), but the implementation is
**stricter than the previous behaviour and can now hard-fail `iw approve`
where it used to succeed**. That's a regression I haven't seen tested.

**Fix**: glob-resolve the four pathspecs in Python first (via
`Path.glob` / `Path.is_dir` / `Path.is_file`), keep only those that match,
and pass that filtered list to `git add` (still narrowed, never the whole
active dir). The `dirty_check` at lines 93-106 already guarantees the
filtered list is non-empty before reaching `git add`, so the call site
stays simple.

Alternative: per-pathspec loop with `check=False`, treating exit 128 as
"no match, skip" — but that's noisier and less explicit than pre-filtering.

### H2. WARN-only contract not guaranteed at the method boundary

The spec for the launch-time check is **WARN, not BLOCK** (Issue_Design
§"Fix Plan" / "Implementation options — DECIDED", and the S02 checklist
HIGH item). The internal helpers `_list_worktree_files` and
`_glob_matches_any` each wrap their work in `try/except Exception:` and
log at DEBUG on failure (`batch_manager.py:752-768`, `789-810`), but
`_emit_sibling_drift_log` itself does **not** wrap its body:

- `_resolve_worktree_base_sha` (line 854) — `try/except Exception: pass`
  internal, OK.
- `_collect_in_flight_sibling_items` (line 857) — **no try/except**, a
  raw SQLAlchemy session query. Any transient DB error (`OperationalError`,
  `DBAPIError`, mapper misconfiguration, …) propagates straight up.
- The `for sibling in siblings:` loop accesses
  `sibling.merge_commit_sha` and `sibling.impacted_paths` — lazy-loaded
  ORM attributes that can raise `DetachedInstanceError` /
  `ObjectDeletedError` if the session state changes underneath.

If any of those raise, `_emit_sibling_drift_log` propagates the
exception up to `_launch_item:594`, which has no surrounding try/except
for this call. The worktree is *already created* by then
(`_setup_worktree` returned at line 569), so the failure leaves a
half-set-up batch item with a real worktree on disk while the launch
unwinds. That's exactly the "BLOCK" failure mode v1 forbids.

**Fix**: wrap the entire `_emit_sibling_drift_log` body in
`try/except Exception` and log at WARN (`exc_info=True`). The contract
is "WARN, not BLOCK" — a defensive outer guard is the cheap way to make
that contract honest. The function already returns `None` on success, so
the change is mechanical.

---

## MEDIUM findings

### M1. Sibling status set is narrower than the un-merged set it claims to cover

`_collect_in_flight_sibling_items` (`batch_manager.py:813-838`) uses:

```python
in_flight_statuses = (
    BatchItemStatus.setting_up,
    BatchItemStatus.executing,
    BatchItemStatus.merging,
)
```

The Issue_Design (§"Code Changes") says "approved / executing / merging".
That's a `WorkItemStatus` × `BatchItemStatus` confusion in the spec; the
principled translation is **any sibling with `merge_commit_sha IS NULL`
whose work has reached disk**. That set should also include
`BatchItemStatus.completed` and `BatchItemStatus.awaiting_merge_approval`
— both states have a branch with un-merged code (and may have written
out-of-scope test files that have *already* been merged to `main` by a
previous sibling, which is exactly the CR-00053 scenario the design doc
calls out).

Skipping them means a real drift source can sit silently in a sibling
that's between "finished gates" and "in the merge queue" — the
WARN we promised the operator never fires.

**Fix**: extend the tuple to:

```python
in_flight_statuses = (
    BatchItemStatus.setting_up,
    BatchItemStatus.executing,
    BatchItemStatus.completed,
    BatchItemStatus.awaiting_merge_approval,
    BatchItemStatus.merging,
)
```

Skipping `pending` is correct (nothing written yet); skipping the
terminal statuses (`merged`, `failed`, `stalled`, …) is correct too.

### M2. `in_flight_siblings=` rendering uses Python list `repr`

`batch_manager.py:898` formats with `%s` over `sibling_ids: list[str]`,
which gives `in_flight_siblings=['CR-00052', 'CR-00053']` — quotes plus a
space after each comma. The Issue_Design example shows
`in_flight_siblings=[<sib1>,...]` (bare IDs, no quotes, no spaces) and
the AC1 test (`test_branch_base_drift.py:319-320`) docstring also writes
`in_flight_siblings=[<A>]` bare. The test only greps for substrings, so
it tolerates either format — but the contract in the prompt's "Log line
shape" item is exact.

**Fix**: build the list-shaped segments by hand, e.g.:

```python
sibling_segment = "[" + ",".join(sibling_ids) + "]"
warn_segment = "[" + ",".join(sid for sid, cnt in details if cnt > 0) + "]"
```

then pass them as `%s` to keep the format string non-interpolated. Same
treatment for the `details=` segment (already does this) and the WARNING
line at 902-909.

### M3. Glob matching is approximative — flag in code

`_glob_matches_any` tries `PurePath.match()` then `fnmatch.fnmatch()`.
Neither implements full gitignore / git-pathspec semantics: `PurePath.match`
ignores `**` (treats it as a single segment in pre-3.13 pathlib),
`fnmatch` treats `*` as crossing `/` boundaries. For the v1 WARN-only
behaviour this is acceptable, but the docstring already notes it. Worth
a single inline comment near `_CHORE_COMMIT_PATHSPECS` / the call site
linking to a follow-up to use `pathspec` (the PyPI lib) when this
graduates to BLOCK behaviour.

### M4. No unit tests for the new helpers in S01

S01 added three new private methods (`_list_worktree_files`,
`_glob_matches_any`, `_collect_in_flight_sibling_items`) plus the
orchestrating `_emit_sibling_drift_log`. The only test is the AC1
end-to-end reproduction. The Issue_Design (§"TDD Approach") explicitly
calls out unit tests for "list in-flight sibling items at this SHA" and
"compute path-set to exclude from chore commit".

S03's prompt is the right place for these (and the prompt names them
already), but the S01 report's "Tests" section claims only AC1 — flag
here so S04 doesn't miss the unit coverage gap when reviewing S03.

### M5. TDD RED evidence: captured but thin

The S01 report quotes the RED failure (`AssertionError: Expected INFO
log line ...`). That's enough to confirm RED was real (the test exercises
the code path the fix targets). MEDIUM, not HIGH, because the evidence
exists in the report.

---

## LOW / nits

- `_emit_sibling_drift_log` imports `fnmatch` and `PurePath` *inside*
  `_glob_matches_any` (lines 782-783). Lift to module-level for
  consistency with the rest of the module.
- Module-level `_CHORE_COMMIT_PATHSPECS` is fine, but the template-string
  approach (`"{active_dir}/{item_id}_..."`) means the literal allow-list
  isn't grep-able by an operator scanning for `_Design.md`. A short
  literal example in the comment block (above lines 8-32) would help.
- `_resolve_worktree_base_sha` runs `git merge-base HEAD main` — at
  worktree-create time `HEAD == main`'s tip, so `merge-base` returns
  the tip. That's correct, but a one-liner comment about why we don't
  use `git rev-parse HEAD` here would save the next reader the dive.

---

## Spec-by-spec checklist

| Item | Status |
|------|--------|
| CRITICAL: backwards compatibility preserved | ✅ |
| CRITICAL: single-item happy path unchanged | ✅ |
| CRITICAL: merge path untouched | ✅ |
| HIGH: chore allow-list explicit, commented, cites I-00083 | ✅ (comment block in `active_files.py:8-32`) |
| HIGH: allow-list contents = `<ID>_*_Design.md`, `<ID>_Functional.md`, `workflow-manifest.json`, `prompts/**` | ✅ (`prompts/` directory pathspec is equivalent to `prompts/**`) |
| HIGH: launch-time sibling check in `batch_manager.py` | ✅ (call site at line 594; helpers at 744-917) |
| HIGH: emits one INFO line per worktree-create | ✅ (single `logger.info` per code path) |
| HIGH: solo case `in_flight_siblings=[] sibling_paths_without_merge=0`, no `details=` | ✅ (lines 861-866) |
| HIGH: N=0 with siblings — `details=` omitted | ✅ (lines 911-917) |
| HIGH: WARN, not BLOCK | ⚠️ See **H2** — uncaught DB exception in `_emit_sibling_drift_log` can propagate and abort `_launch_item`. |
| HIGH: existing git helpers used; no ad-hoc subprocess | ✅ (the module-wide pattern is direct `subprocess.run(["git", ...])`; the new code is consistent with `_resolve_worktree_base_sha` at line 1015) |
| MEDIUM: TDD RED evidence | ✅ (S01 report lines 56-60) |
| MEDIUM: S03 plan looks weak? | ⚠️ See **M4** — S03 prompt names the unit tests; flag if S04 sees them missing. |

---

## Verdict

`needs-fix`.

Two HIGH issues to address in a follow-up fix cycle before the per-agent
review can pass:

1. **H1** — Make `ensure_active_files_committed` tolerate absent
   allow-list pathspecs (pre-filter or per-spec loop). Otherwise
   `iw approve` regresses for items missing `<ID>_Functional.md` /
   `workflow-manifest.json` / etc.
2. **H2** — Wrap `_emit_sibling_drift_log` in `try/except Exception` so
   a transient DB error can't block worktree creation. The v1 contract
   is WARN-only.

The four MEDIUMs (status set, list rendering, glob approximation,
unit-test coverage in S03) are not blocking for S02 but should be
queued. M1 in particular should be picked up before merge; M2 affects
operator log readability; M3/M4 are documentation/coverage hygiene.

## Files Reviewed

- `orch/active_files.py` (full diff vs `main`)
- `orch/daemon/batch_manager.py` (full diff vs `main`)
- `tests/integration/test_branch_base_drift.py` (full)
- Cross-references: `orch/db/models.py:106-203, 525-540, 620-630`,
  `orch/cli/item_commands.py:127-153, 640-660`,
  `orch/daemon/batch_manager.py:540-595, 1015-1029`.
