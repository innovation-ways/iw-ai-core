# I-00083 S14 — Self-Assessment

**Verdict**: `pass` (with one observation).

This step audits whether I-00083's *own* run exhibited the cross-item
drift pattern this CR was designed to eliminate, and confirms whether
the new launch-time log line was emitted for this CR's worktree-create
event. A copy of this report is also written to
`ai-dev/work/I-00083/reports/I-00083_S14_SelfAssess_report.md` for the
post-merge analyzer.

---

## Focus 1 — Did this CR's own run need any carry-over fixes?

**Result: No carry-over fixes.**

The branch's working-tree diff vs `main` is exactly the spec'd surface:

```
orch/active_files.py          |  92 ++++++++++++++++++++-
orch/daemon/batch_manager.py  | 186 +++++++++++++++++++++++++++++++++++++++++++
tests/integration/test_branch_base_drift.py | (new file, AC1+AC2+AC3 + chore-commit + sibling-scope unit tests)
```

Two fix cycles ran during execution (S06 and S07), and both are scoped
to **this CR's own newly-authored test file** — not cross-item
carry-overs:

| Cycle | Gate | Failure | Carry-over class? |
|-------|------|---------|-------------------|
| S06 (lint) | `make lint` | `PT018` — compound assertion in `test_branch_base_drift.py:665` | No — own-file ruff fix |
| S07 (assertions) | `make test-assertions` | tautology baseline violation in `test_branch_base_drift.py:587` | No — own-file assertion strengthening |

For comparison, CR-00053's three concrete carry-over fixes were:

- **5 entries appended to `tests/assertion_free_baseline.txt`** (CR-00052 carry-over)
- **1-line `BatchStatus.executing` → `BatchStatus.completed`** in
  `tests/integration/test_dashboard_actions.py` (CR-00052 carry-over)
- **`_HEAD_REVISION` constant** alignment (CR-00052 carry-over)

This CR's diff touches **none** of those files or symbols:

- `tests/assertion_free_baseline.txt` — unchanged.
- `tests/integration/test_dashboard_actions.py` — unchanged.
- No `_HEAD_REVISION` reference added or modified.

The three `BatchStatus.executing` occurrences in
`tests/integration/test_branch_base_drift.py` (lines 225, 350, 467) are
the test's own `Batch` factory setting the *batch* status to
`executing` for the in-flight sibling simulation, not a flip of the
CR-00053 kind.

**Why the run was clean.** The fix is the *structural* fix for this
exact pattern, but the run happened to be clean for an orthogonal
reason too: no concurrently-merging item in BATCH-00104's window wrote
into the impl files I-00083 touches (`orch/active_files.py`,
`orch/daemon/batch_manager.py`). Compare CR-00053, where CR-00052 was
mid-flight and had already squash-landed tests targeting CR-00053's
files. So this run is **consistent with** the fix's promise but is not
a strong end-to-end validation of it; the design's documented "bite"
(the CR-00053 hand-rescue) remains the validating case study.

## Focus 2 — Was the daemon log line emitted on every worktree-create event, including this CR's?

**Result: Not for this CR's own worktree-create event** — by design.

Grep over `logs/daemon.log` filtered to I-00083 returns zero matches
for `worktree create:`, `sibling_paths_without_merge`, or
`in_flight_siblings`:

```
$ grep -E 'worktree create:|sibling_paths_without_merge|in_flight_siblings' logs/daemon.log | grep I-00083
(no output)
```

This is **expected** for any self-modifying daemon change:

- I-00083's worktree was created at 2026-05-16 ~05:13 by the daemon
  process running pre-fix `main` code. At that moment, the new
  `_emit_sibling_drift_log` method does not yet exist in the running
  daemon — it only exists in this worktree's working tree.
- The first emission of the log line will occur on the next worktree
  the daemon creates **after** I-00083 is squash-merged to `main` and
  the daemon is restarted (or its in-process `BatchManager` reloads).
- The S03 unit tests (`TestI00083HappyPathSoloItem`,
  `TestI00083SiblingScopeUnit`) prove the emission shape; the live log
  evidence has to wait for post-merge daemon reload.

This is the same self-bootstrap caveat any daemon-side fix has (see
e.g. CR-00021 pre-merge migration rebase — also could not run on its
own initial merge).

## Focus 3 — Backwards-compat sanity: were any tests modified that were authored under the old chore-commit shape?

**Result: No.**

`git status -s` shows the test surface as:

```
?? tests/integration/test_branch_base_drift.py
```

- A single **new** file. No edits to any pre-existing test.
- The new file's `_simulate_chore_commit` helper is explicitly authored
  against the new (narrow) allow-list: it always creates all four
  allow-listed pathspecs (`<ID>_Functional.md`, `<ID>_*_Design.md`,
  `workflow-manifest.json`, `prompts/`) so that `git add -- …` does not
  fail. The S03 report (line 117-124) and the S05 H1 finding both flag
  this as a real production constraint (an item missing
  `<ID>_Functional.md` would now hard-fail `iw approve` because of
  `git add` exit 128).

The H1 production-side regression is documented in S05 but was **not
fixed in this CR** (the prompt does not authorise it, and no fix
cycle landed it). The test file is authored under the new contract,
and that constraint is therefore latent. **Recommendation**: file a
follow-up incident to pre-filter the chore-commit pathspecs in
`orch/active_files.py:ensure_active_files_committed` (S02 H1 / S05 H1
both recommend `Path.glob` pre-filter). Not blocking S14.

The S05 final review also flagged a CRITICAL **C1** scope deviation
(`orch/active_files.py` not in `workflow-manifest.json::scope.allowed_paths`).
That manifest was not updated; the file remains modified outside the
declared scope at the time of S14. The remediation S05 prefers is
"amend the manifest", which is a one-line operator action; flagged
again here so it is visible in the analyzer.

## Focus 4 — Cross-CR pattern vs CR-00053's three concrete carry-over fixes

**Result: Pattern not observed in this run.** (See Focus 1.)

| CR-00053 carry-over | Touched in I-00083? | Evidence |
|---------------------|--------------------|----------|
| `tests/assertion_free_baseline.txt` (+5 entries) | No | Not in `git diff --stat`. Assertion-scanner S07 PASS on `2434+` tests across baseline-untouched. |
| `tests/integration/test_dashboard_actions.py` (BatchStatus.executing → completed) | No | File untouched. |
| `_HEAD_REVISION` constant alignment | No | No reference added/modified. |

The design-doc Notes section is therefore the **only** validating
record of the bite this CR fixes. The CR-00053 manual rescue is
referenced by the I-00083 design (§Root Cause Analysis,
§Implementation options) and the structural fix lands here. The
post-merge expectation is that **future** in-flight overlap windows
similar to CR-00052 → CR-00053 will surface a non-zero
`sibling_paths_without_merge` in the daemon log instead of producing a
silent half-state worktree.

---

## Files Changed (this step)

| File | Change |
|------|--------|
| `ai-dev/active/I-00083/reports/I-00083_S14_SelfAssess_report.md` | New — this report |
| `ai-dev/active/I-00083/reports/I-00083_S14_SelfAssess_findings.json` | New — structured findings |
| `ai-dev/work/I-00083/reports/I-00083_S14_SelfAssess_report.md` | Mirror copy for the post-merge analyzer |
| `ai-dev/work/I-00083/reports/I-00083_S14_SelfAssess_findings.json` | Mirror copy for the post-merge analyzer |

No production or test code was modified by S14 (assessment-only step).

## Issues / Observations

1. **S05 CRITICAL (C1)** — `orch/active_files.py` is modified but is not
   listed in `workflow-manifest.json::scope.allowed_paths` ({"orch/cli/item_commands.py",
   "orch/daemon/batch_manager.py", "executor/setup_worktree.sh",
   "tests/integration/test_branch_base_drift.py"}). S05's recommended
   fix is "add `orch/active_files.py` to allowed_paths". Not addressed
   pre-S14. Operator should resolve at merge time.
2. **S05 HIGH (H1)** — `git add -- <pathspec>` exits 128 when a
   pathspec resolves to nothing. The narrow allow-list passes all four
   pathspecs unconditionally and will hard-fail `iw approve` for any
   item missing one of them. Recommend a follow-up incident to
   pre-filter the pathspecs via `Path.glob`.
3. **S05 HIGH (H2)** — `_emit_sibling_drift_log` body has no outer
   `try/except`. A transient DB error in `_collect_in_flight_sibling_items`
   would propagate up to `_launch_item` *after* the worktree exists on
   disk but before `BatchItemStatus.executing` is set, contradicting
   the v1 "WARN, not BLOCK" contract. Recommend a one-indent fix:
   wrap the body in `try/except Exception` and `logger.warning(..., exc_info=True)`.
4. **First emission deferred** — the new log line cannot be verified in
   `logs/daemon.log` until the daemon restarts post-merge. Operator
   should grep `logs/daemon.log` for `worktree create:` after the next
   item launches.

## Verdict

```
pass
```

This CR's own run did not exhibit the cross-item drift pattern; the
two fix cycles required were own-file lint/assertion polish, not
carry-over fixes; no pre-existing tests were modified under the old
chore-commit shape; and the new daemon log line will start emitting on
the next worktree created after this CR merges (with daemon reload).
S05's outstanding C1/H1/H2 are flagged for the post-merge analyzer
rather than being addressed inside S14's review-only scope.
