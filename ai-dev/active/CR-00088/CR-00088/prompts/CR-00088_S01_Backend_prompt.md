# CR-00088_S01_Backend_prompt

**Work Item**: CR-00088 -- Auto-merge — partial-allowlist semantics in Phase 1 dry-run
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network state. Allowed: testcontainers in pytest fixtures, read-only `docker ps/inspect/logs`, `./ai-core.sh` and `make` targets. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This step adds NO migration. Do not run alembic commands.

## Input Files

- **Runtime step state**: `uv run iw item-status CR-00088 --json` is authoritative for current step list and prompt paths.
- `ai-dev/active/CR-00088/CR-00088_CR_Design.md` — design (read first; AC1–AC3 are this step's success bar).
- `orch/daemon/auto_merge.py` — file to modify (the `classify_conflicts` function ~line 367 and the `ClassificationResult` dataclass ~line 257).
- `tests/unit/test_auto_merge_classifier.py` — file to modify (RED-first additions).
- `docs/research/R-00076-llm-automated-merge-resolution.md` §5 — for context on the phase ladder.

## Output Files

- `ai-dev/work/CR-00088/reports/CR-00088_S01_Backend_report.md` — Step report.

## Context

You are implementing **Step 1 of 14** of CR-00088. The scope is narrow: change the allowlist gate inside `classify_conflicts()` from all-or-nothing to partition semantics, and add the corresponding `deferred_files` field to `ClassificationResult`. Event-emission integration is S02's job; do NOT touch `attempt_resolution()` or `merge_queue.py` in this step. Read CLAUDE.md (root + `orch/CLAUDE.md`) before editing.

## Requirements

### 1. Extend `ClassificationResult` (orch/daemon/auto_merge.py ~line 257)

Add a new field with a default so all existing constructors stay valid:

```python
@dataclass(frozen=True)
class ClassificationResult:
    """Result of classify_conflicts() — which files are eligible, and why not."""

    eligible_files: tuple[str, ...]
    refuse_files: tuple[str, ...]
    oversized_files: tuple[str, ...]
    oversized_hunks: tuple[str, ...]
    binary_files: tuple[str, ...]
    skipped_reason: str | None
    deferred_files: tuple[str, ...] = ()
```

Note the trailing default — every existing call site that constructs `ClassificationResult` (there are ~6 inside `classify_conflicts`) keeps working without modification.

### 2. Change the allowlist check (orch/daemon/auto_merge.py step 6, ~line 484)

Replace the current all-or-nothing logic:

```python
# 6. Allowlist check
not_allowlisted = [
    rel_path
    for rel_path in conflict_files
    if not any(fnmatch.fnmatchcase(rel_path, pat) for pat in config.allowlist_patterns)
]
if not_allowlisted:
    logger.info("classify_conflicts: not_allowlisted: %s", not_allowlisted)
    return ClassificationResult(
        eligible_files=(),
        refuse_files=(),
        oversized_files=(),
        oversized_hunks=(),
        binary_files=(),
        skipped_reason="not_allowlisted",
    )
```

with partition semantics. Preserve input order on both sides (use a single pass; do NOT re-sort):

```python
# 6. Allowlist partition
eligible_files: list[str] = []
deferred_files: list[str] = []
for rel_path in conflict_files:
    if any(fnmatch.fnmatchcase(rel_path, pat) for pat in config.allowlist_patterns):
        eligible_files.append(rel_path)
    else:
        deferred_files.append(rel_path)

if not eligible_files:
    # Every file is deferred — preserve today's skip behaviour, now with explicit deferred list
    logger.info("classify_conflicts: not_allowlisted (all deferred): %s", deferred_files)
    return ClassificationResult(
        eligible_files=(),
        refuse_files=(),
        oversized_files=(),
        oversized_hunks=(),
        binary_files=(),
        skipped_reason="not_allowlisted",
        deferred_files=tuple(deferred_files),
    )

if deferred_files:
    logger.info(
        "classify_conflicts: partial allowlist — eligible=%s deferred=%s",
        eligible_files,
        deferred_files,
    )
```

Then update the existing "all pass" return at the bottom of the function to include `deferred_files=tuple(deferred_files)`:

```python
# 7. At least one file is eligible (partial OR full allowlist match)
logger.info(
    "classify_conflicts: %d eligible, %d deferred",
    len(eligible_files),
    len(deferred_files),
)
return ClassificationResult(
    eligible_files=tuple(eligible_files),
    refuse_files=(),
    oversized_files=(),
    oversized_hunks=(),
    binary_files=(),
    skipped_reason=None,
    deferred_files=tuple(deferred_files),
)
```

### 3. Update docstring on `classify_conflicts()` (orch/daemon/auto_merge.py ~line 367)

Replace step 6 in the docstring and add a new step describing the partition. The new comment block should read:

```
6. Allowlist partition:
   - eligible_files = files matching allowlist_patterns
   - deferred_files = files matching NEITHER refuse-list (already returned above) NOR allowlist
   - If eligible_files is empty, return skipped_reason="not_allowlisted" with the deferred list populated.
   - Otherwise return skipped_reason=None with both lists populated (the LLM will only be invoked for eligible_files).
```

### 4. RED-first tests in tests/unit/test_auto_merge_classifier.py

Before changing `classify_conflicts()`, add the following tests and confirm they FAIL against current code. Record the RED output in the step report under "TDD RED evidence". Then run them GREEN after the code change.

Test names and assertions:

- **`test_partial_allowlist_returns_partition`** — Create 2 fixture conflict files, e.g. `docs/foo.md` and `Makefile`. Config: `allowlist=["**/*.md"]`, `refuselist=[]`. Assert: `result.eligible_files == ("docs/foo.md",)`, `result.deferred_files == ("Makefile",)`, `result.skipped_reason is None`.
- **`test_all_deferred_keeps_skip_reason`** — Files: `Makefile`, `pyproject.toml`. Config: `allowlist=["**/*.md"]`, `refuselist=[]`. Assert: `result.eligible_files == ()`, `result.deferred_files == ("Makefile", "pyproject.toml")`, `result.skipped_reason == "not_allowlisted"`.
- **`test_refuselist_wins_over_partial_allowlist`** — Files: `docs/foo.md`, `orch/db/migrations/versions/abc.py`, `Makefile`. Config: `allowlist=["**/*.md"]`, `refuselist=["orch/db/migrations/versions/*.py"]`. Assert: `result.skipped_reason == "refuse_list"`, `result.refuse_files == ("orch/db/migrations/versions/abc.py",)`, `result.eligible_files == ()`, `result.deferred_files == ()`. (No partition occurred — refuse-list short-circuited above.)
- **`test_deferred_files_default_empty`** — Construct a `ClassificationResult` without passing `deferred_files`. Assert `result.deferred_files == ()`. Guards the dataclass default against accidental removal.

Use the existing `_make_config(...)` helper at the top of `test_auto_merge_classifier.py` for config construction. Use the existing `tmp_path: Path` fixture pattern for file creation (mirror `test_all_files_allowlisted` ~line 46).

Asserting on tuple ordering (not set membership) is intentional — `classify_conflicts` MUST preserve input order so the dashboard renders files in a predictable sequence.

### 5. Update any existing tests broken by the partition change

`tests/unit/test_auto_merge_classifier.py::test_non_allowlisted_file` (~line 258) currently asserts `skipped_reason="not_allowlisted"` with empty `eligible_files`. After the change, that test's specific input (a single non-allowlisted JS file) STILL ends in `skipped_reason="not_allowlisted"` because no file matches the allowlist — but `deferred_files` is now populated. Update the assertions to also check `result.deferred_files == ("dashboard/static/foo.js",)`.

Audit every test in `test_auto_merge_classifier.py` for similar drift. Do NOT loosen any assertion; if a test no longer reflects current behaviour, tighten it to the new partition.

### 6. Do NOT touch in this step

- `attempt_resolution()` (S02's job — event metadata changes).
- `orch/daemon/merge_queue.py` (S02's job — event metadata thread-through).
- `executor/auto_merge.toml` (no config change in this CR).
- `executor/worktree_commit.sh` (no bash-script change in this CR).
- `docs/research/R-00076-*.md` / `ai-dev/active/AUTO_MERGE_RESOLUTION.md` (S03's job after tests confirm partition semantics).
- Any production behaviour outside `classify_conflicts` and its unit tests.

## TDD Approach

RED-GREEN-REFACTOR. RED evidence (the four new tests failing against unmodified `classify_conflicts`) must be captured verbatim in the step report under a "TDD RED evidence" subsection and surfaced in the result-contract JSON via `tdd_red_evidence`. The expected failure mode for the three behavioural tests is `AssertionError` (wrong field values); for `test_deferred_files_default_empty` the failure mode is `TypeError: __init__() got an unexpected keyword argument 'deferred_files'` (until the dataclass field is added).

## Acceptance Criteria for this step

1. `ClassificationResult.deferred_files: tuple[str, ...]` exists with default `()`.
2. `classify_conflicts` partitions: at least one eligible file ⇒ `skipped_reason is None` and `deferred_files` reflects the remainder.
3. No eligible files ⇒ `skipped_reason == "not_allowlisted"` and `deferred_files` is the full input.
4. Refuse-list precedence unchanged.
5. All four new RED tests pass. All previously-green tests in `test_auto_merge_classifier.py` still pass (some assertions tightened for new behaviour).
6. `make lint && make test-assertions && make typecheck` all green at the end of the step. Run targeted tests only: `uv run pytest tests/unit/test_auto_merge_classifier.py -v`. Do NOT run `make test-unit` (full-suite execution is owned by the QV gate S10).

## Hard rules

- Allowed paths: `orch/daemon/auto_merge.py`, `tests/unit/test_auto_merge_classifier.py`, `ai-dev/work/CR-00088/reports/**`. Nothing else.
- Do NOT modify event-emission code (S02's job).
- Do NOT modify `merge_queue.py` (S02's job).
- Do NOT add new fixture files outside `tmp_path` (the test pattern uses on-the-fly file creation).
- Preserve input order in eligible/deferred tuples.

## Result Contract

Emit the standard `iw step-done` result contract JSON with:
- `tdd_red_evidence`: a short string describing the RED state of the four new tests (test names + the failure mode line).
- `files_changed`: exact list (relative paths).
- `tests_added`: the four new test names.
- `tests_updated`: any assertion-tightening you made in existing tests.
