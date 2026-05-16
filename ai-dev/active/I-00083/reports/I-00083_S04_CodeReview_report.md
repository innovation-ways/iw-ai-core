# I-00083 S04 CodeReview (Tests) Report

**Verdict: PASS** — `tests/integration/test_branch_base_drift.py` meets every
critical and high-priority criterion in the S04 checklist. Two MEDIUM
observations are filed below as non-blocking polish items.

## Inputs Reviewed

- `ai-dev/active/I-00083/I-00083_Issue_Design.md`
- `ai-dev/active/I-00083/reports/I-00083_S03_Tests_report.md`
- `tests/integration/test_branch_base_drift.py`
- Production code under test:
  - `orch/active_files.py` (current allow-list shape)
  - `orch/daemon/batch_manager.py::_emit_sibling_drift_log`,
    `_collect_in_flight_sibling_items`, `_launch_item`
  - `main:orch/active_files.py` (pre-fix shape, fetched for RED reasoning)

## CRITICAL — all PASS

### Reproduction test would fail pre-fix

Validated by reading pre-fix (`main`) code and walking each new test through
that shape:

| Test class | Pre-fix behaviour | Failing assertion |
|---|---|---|
| `TestI00083BranchBaseDrift` | `_emit_sibling_drift_log` did not exist; `_launch_item` did not call any drift hook → no log line emitted | `assert drift_log_lines` (line 403) |
| `TestI00083HappyPathSoloItem` | Same — no log line emitted on solo launches either | `assert len(drift_lines) == 1` (line 515) |
| `TestI00083SiblingScopeUnit` (×3) | Method `_emit_sibling_drift_log` absent on `BatchManager` | `AttributeError` at the call (line 578) |
| `TestI00083ChoreCommitAllowList::test_chore_commit_excludes_non_design_files` | Pre-fix `ensure_active_files_committed` did `git add ai-dev/active/<id>/` (full dir), committing `notes.txt`, fixtures, and evidences | `assert not _commit_contains(... "notes.txt")` (line 799) |
| `TestI00083ChoreCommitAllowList::test_chore_commit_with_only_non_design_files_skips_commit` | Full-dir add would land `scratch.txt` + `logs/run.log`, advancing HEAD | `assert head_sha == first_sha` (line 846) |

None of the 7 tests would pass against the pre-S01 chore-commit / missing-drift-log
behaviour. All are genuine regression tests.

### Semantic assertions only

No `len(...) > 0` or `"key" in dict` shape-only checks. Every assertion targets
a meaningful production behaviour:

- Exact numeric counts: `"sibling_paths_without_merge=2"`, `"=0"`,
  per-sibling `"A1:1"`, `"A2:1"`.
- Literal log shapes: `"in_flight_siblings=[]"`,
  `f"item={b_id}"`.
- DB state round-tripping: `b_batch_item.status == BatchItemStatus.executing`,
  `worktree_info["path"] == str(fake_repo)`, `started_at is not None`.
- Git tree membership via `git ls-tree -r --name-only` — actual tree
  inspection, not a stub.
- Negative-WARN assertions: `warn_records == []` (strong) on the no-drift
  branches.

## HIGH — all PASS

### AC coverage

- **AC1** (no inheritance / drift detection): `TestI00083BranchBaseDrift::test_i00083_b_worktree_does_not_inherit_a_pre_impl_test_drift` (S01 author, S03 kept verbatim — confirmed unchanged).
- **AC2** (test exists): `tests/integration/test_branch_base_drift.py` is the test file named by AC2; collection + run confirmed by S03 report (`7 passed in 4.11s`).
- **AC3** (happy path preserved): `TestI00083HappyPathSoloItem::test_solo_item_emits_empty_sibling_log_and_transitions_to_executing` exercises the solo-item flow and pins both the log shape AND the behavioural equivalence (`status`, `worktree_info`, `started_at`).

### No live DB usage

- All DB access flows through the `db_session` and `test_project` testcontainer-backed fixtures (`tests/conftest.py`).
- `_make_batch_manager` builds a `BatchManager` with a `session_factory` that **yields the test session**; the daemon code path never opens a new engine.
- Filesystem state uses `tmp_path` (e.g., `tmp_path / "repo"`, `tmp_path / "worktrees"`, `tmp_path / "daemon.log"`).
- No `5433`-port connection is opened (the `db_port=5433` value in `DaemonConfig` is metadata only — never dereferenced because `session_factory` injects the testcontainer session; see LOW-1 below).

### Two-item simulation exercises the in-flight overlap

- AC1 test: item A has `merge_commit_sha=None` AND `BatchItem.status=executing`, then B's `_launch_item` is invoked while A is still active. `_collect_in_flight_sibling_items` (line 813) joins `WorkItem ⨝ BatchItem` filtered by `BatchItem.status in {setting_up, executing, merging}` and `WorkItem.id != current_item_id` — A is captured as a sibling, producing the genuine overlap window the design doc describes.
- Unit-suite `test_multiple_in_flight_siblings_non_overlapping_globs_sum_counts`: two concurrent siblings both `executing` with no merge SHA → both surface as in-flight. Real overlap, not sequential runs.
- Unit-suite `test_sibling_with_merge_commit_contributes_zero`: status `merging` + `merge_commit_sha` set captures the precise transient window the design doc calls out (the CR-00053 bite).

## MEDIUM

### MED-1 — Test naming follows convention

Method names use `test_i00083_*` for the AC1 reproducer and descriptive
behavioural names elsewhere (`test_solo_item_emits_empty_sibling_log_and_transitions_to_executing`,
`test_multiple_in_flight_siblings_non_overlapping_globs_sum_counts`, …).
Class-level naming follows `TestI00083<Scenario>`. Acceptable — the descriptive
method names read more clearly than a forced `test_i00083_` prefix on every
case, while the class name still anchors the issue id.

### MED-2 — `_simulate_in_flight_impl` is defined but never called

`_simulate_in_flight_impl` (lines 144–167) is documented as a reusable helper
for "land impl-style edits on `main` to mimic a sibling's tests/fixtures", but
no test in the file invokes it — the AC1 test uses `_add_file_and_commit`
inline and the unit suite does the same. The helper is dead code.

**Recommendation (non-blocking):** either delete the helper, or refactor at
least one test (e.g., `test_multiple_in_flight_siblings_*`) to consume it so
the documented "fake A's pending impl arriving via someone else's prior squash
merge" idiom has at least one reference user. Filing this as MEDIUM, not HIGH,
because nothing the design doc promised actually requires this helper to be
called — the underlying behaviour is exercised either way.

## LOW

### LOW-1 — `db_port=5433` in `DaemonConfig` test fixture

`_make_batch_manager` constructs a `DaemonConfig` with
`db_port=5433` and `db_url="postgresql+psycopg://test:test@localhost:5433/test"`.
These values are metadata only because the BatchManager uses the
`session_factory` override and never opens a new engine — verified by reading
`_launch_item` end-to-end. There is no live-DB risk, but the value reads as
alarming next to the project's "NEVER connect tests to live DB (port 5433)"
rule. A non-routable placeholder port (e.g., `0` or `65535`) would make the
no-connection guarantee self-evident at the call site. Non-blocking.

## Helper reusability / documentation (MEDIUM checklist item)

- `_make_fake_repo`, `_add_file_and_commit`, `_simulate_chore_commit`, and
  `_commit_contains` are all module-level, have docstrings, and are reused
  across the four test classes.
- `_simulate_chore_commit` documents the production constraint that every
  allow-listed pathspec must match at least one file (else `git add --` exits
  non-zero) and unconditionally creates the design/functional/manifest/prompt
  files for that reason. Reasonable documentation of a non-obvious gotcha.
- `_make_batch_manager`'s `session_factory` is correctly wired as a
  `contextmanager`-decorated generator that yields the testcontainer session.

## Files Changed (this step)

| File | Change |
|------|--------|
| `ai-dev/active/I-00083/reports/I-00083_S04_CodeReview_report.md` | New — this report |

No production or test code was modified during S04 (review-only step).

## Verdict

**`pass`**.

The S03 test additions reproduce the I-00083 bug under realistic in-flight
overlap, pin both the no-drift and drift code paths, exercise the chore-commit
allow-list end-to-end against a fake repo, and assert on semantically
meaningful production behaviour (numeric drift counts, per-sibling detail
strings, git tree membership, DB state). The two MEDIUM observations are
polish items that do not gate merge.
