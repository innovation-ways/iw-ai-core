# I-00071: Scope-overlap gate over-blocks items due to backtick-wrapped paths and leading-slash test marker

**Type**: Issue
**Severity**: Medium
**Created**: 2026-05-05
**Reported By**: sergio (operator) — observed live on BATCH-00078
**Status**: Draft

---

## ⛔ Docker is off-limits

(Standard policy. Testcontainer fixtures in tests are exempt.)

## ⛔ Migrations: agents generate, daemon applies

Standard policy. **This item adds no migrations.** Existing rows in `work_items.impacted_paths` are not backfilled — they merge soon and new items go through the fixed parser.

## Description

The F-00076 cross-batch scope-overlap gate over-holds approved items because two latent bugs combine: (1) `parse_impacted_paths` keeps surrounding markdown backticks when extracting bullet-list globs, so paths land in the DB as `` `dashboard/CLAUDE.md` `` instead of `dashboard/CLAUDE.md`; (2) `scope_overlap.is_test_path` only recognises `/tests/`, `/test/`, `/__tests__/` substrings (with leading slash), so relative test paths like `tests/foo.py` are never stripped before the sibling-directory check. The combined effect is that test files participate in sibling overlap — and with backticks, every comparison is fragile.

## Project Context

Read the project's `CLAUDE.md` for architecture, conventions, and hard rules. The relevant module is `orch/daemon/scope_overlap.py` (pure helpers; no DB) and `orch/design_doc_parser.py` (pure parsing; no DB).

## Steps to Reproduce

1. Create a Feature/Incident with an `## Impacted Paths` section using bullet syntax wrapped in markdown backticks, e.g. `` - `dashboard/CLAUDE.md` ``.
2. Run `iw register {ID} ...`.
3. Inspect the row: `select impacted_paths from work_items where id = '{ID}'` — globs are stored with surrounding `` ` `` characters preserved.
4. In a batch where another item declares a different file in the **same parent directory** (e.g. `dashboard/app.py`), put both items in the same `execution_group`.
5. Approve the batch and start the daemon.

**Expected**: Both items launch in parallel because their paths are siblings only by coincidence (no functional dependency); even when they share a parent directory, the gate should at least not consider test files for sibling matching.

**Actual**: Once one item begins executing, the other is held by the F-00076 gate every poll cycle. Daemon emits `item_held_for_scope` events such as:

```
Held: I-00070 overlaps with I-00069 on `dashboard/CLAUDE.md`
Held: CR-00034 overlaps with I-00069 on `tests/dashboard/test_i00067_recent_activity_truncation.py`
```

(Live evidence captured 2026-05-05 19:34–19:48 UTC on BATCH-00078: I-00069 was running, I-00070 and CR-00034 were repeatedly parked.)

The conflict for CR-00034 is **especially wrong** — both files are tests under `tests/dashboard/`. Test paths should have been stripped before the sibling check fired (`scope_overlap.py:88-89` calls `_strip_test_globs`). They were not, because the relative path `tests/dashboard/...` does not contain `/tests/` (with leading slash), so `is_test_path` returned False.

## Root Cause Analysis

**Bug 1 — backtick wrapping persists into impacted_paths** (`orch/design_doc_parser.py:84-90`):

```python
lstripped = raw_line.lstrip()
if lstripped.startswith(("- ", "* ")):
    indent = len(raw_line) - len(lstripped)
    glob = raw_line[indent + 2 :].strip()  # skip marker "- " or "* "
    _validate_glob(glob)  # raises ValueError on invalid
```

The bullet marker is stripped, but surrounding `` ` `` characters from a markdown code-span (e.g. `` - `dashboard/CLAUDE.md` ``) are kept verbatim. `_validate_glob` does not reject backticks (they are not whitespace, not `/`, not `..`), so the wrapped string is stored as the glob.

**Bug 2 — `is_test_path` requires leading slash** (`orch/daemon/scope_overlap.py:16-32`):

```python
_TEST_PATH_MARKERS = (
    "/tests/", "/test/", "/__tests__/",
    "conftest", ".test.", ".spec.",
)

def is_test_path(glob: str) -> bool:
    return any(marker in glob for marker in _TEST_PATH_MARKERS)
```

Relative test paths (`tests/foo.py`, `test/foo.py`, `__tests__/foo.py`) do not contain `/tests/`, `/test/`, or `/__tests__/` because they have no leading slash. So `is_test_path` returns False for any test file at the repository root level. These paths reach `find_blocking_items` and trigger sibling-directory false positives via `_same_parent` (`scope_overlap.py:125-129`).

**How they combine on the wild evidence**:

- I-00069 declares `` `dashboard/app.py` ``, `` `tests/dashboard/test_live_db_guard_log_level.py` ``.
- I-00070 declares `` `dashboard/CLAUDE.md` ``, `` `dashboard/static/clipboard.js` ``, … (all backtick-wrapped).
- CR-00034 declares `` `tests/dashboard/test_i00067_recent_activity_truncation.py` ``.

Both bugs together: backticks make the strings opaque to glob/fnmatch checks; relative-tests-not-stripped means the test files participate in the parent-directory sibling check; sibling check fires on `` `tests/dashboard `` and `` `dashboard `` parents. Items get held indefinitely.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/design_doc_parser.py` | Bullet-list globs are stored with surrounding markdown code-span backticks intact |
| `orch/daemon/scope_overlap.py` | Relative test paths bypass `is_test_path`, reaching the sibling-directory check |
| F-00076 cross-batch gate | Approved items are over-held; multi-item batch parallelism collapses |
| `work_items.impacted_paths` (DB rows) | Existing rows hold backtick-wrapped strings (read-only consequence; no fix-up here) |

## Fix Plan

### Agents and Execution Order

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | `backend-impl` | Strip wrapping markdown code-span backticks in `parse_impacted_paths`; broaden `is_test_path` to recognise relative test paths (`tests/`, `test/`, `__tests__/` at any path segment, including leading) | — |
| S02 | `code-review-impl` | Per-agent review of S01 | — |
| S03 | `tests-impl` | Reproduction unit tests + regression coverage for both bugs | — |
| S04 | `code-review-impl` | Per-agent review of S03 | — |
| S05 | `code-review-final-impl` | Global cross-agent review | — |
| S06..S12 | `qv-gate` | lint, format-check, type-check, arch-check, security-sast, test-unit, test-integration | — |
| S13 | `self-assess-impl` | Self-assessment via iw-item-analyze (project has `self_assess = true`) | — |

### Database Changes

- **New tables**: None
- **Modified tables**: None
- **Migration notes**: No migration. Existing `work_items.impacted_paths` rows with backticks are left as-is — they will reach `merged` soon and new items go through the fixed parser.

### Code Changes

- **Files to modify**:
  - `orch/design_doc_parser.py` — strip surrounding markdown code-span backticks (`` ` `` … `` ` ``) before validating globs in both bullet-list and fenced-code-block branches.
  - `orch/daemon/scope_overlap.py` — extend `_TEST_PATH_MARKERS` (or replace the substring check with a smarter check) so relative test paths starting with `tests/`, `test/`, or `__tests__/` are correctly classified.
  - `orch/batch_planner.py` — keep `_is_test_path` in sync with `scope_overlap.is_test_path` (both modules carry an identical `_TEST_PATH_MARKERS` constant with the same bug; the docstring of `scope_overlap.is_test_path` already states "Mirror orch/batch_planner.py:_is_test_path semantics").
- **Nature of change**: Defensive normalization in the parser; broader test-path recognition in the gate helpers. All pure-function changes — no DB, no I/O.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00071_Issue_Design.md` | Design | This document |
| `I-00071_Functional.md` | Design | Human-facing summary (Why / What Changed / How It Behaves / Out of Scope) |
| `workflow-manifest.json` | Manifest | Step definitions for orchestrator |
| `prompts/I-00071_S01_Backend_prompt.md` | Prompt | S01 fix implementation |
| `prompts/I-00071_S02_CodeReview_Backend_prompt.md` | Prompt | Per-agent review of S01 |
| `prompts/I-00071_S03_Tests_prompt.md` | Prompt | Reproduction + regression tests |
| `prompts/I-00071_S04_CodeReview_Tests_prompt.md` | Prompt | Per-agent review of S03 |
| `prompts/I-00071_S05_CodeReview_Final_prompt.md` | Prompt | Global cross-agent review |
| `prompts/I-00071_S13_SelfAssess_prompt.md` | Prompt | Self-assessment |

Reports are created during execution in `ai-dev/active/I-00071/reports/`.

## Test to Reproduce

**Test-file location** — Both reproduction tests are pure-Python helpers with no FastAPI / template dependency, so they go under `tests/unit/`.

```python
# tests/unit/test_design_doc_parser.py — added test
def test_parse_impacted_paths_strips_markdown_code_span_backticks():
    """I-00071 RED: bullet items wrapped in markdown backticks must not retain them."""
    content = """## Impacted Paths

- `dashboard/CLAUDE.md`
- `dashboard/static/clipboard.js`
- `tests/dashboard/test_i00071.py`
"""
    result = parse_impacted_paths(content)
    assert result.found is True
    assert result.paths == [
        "dashboard/CLAUDE.md",
        "dashboard/static/clipboard.js",
        "tests/dashboard/test_i00071.py",
    ], "globs must be stored without surrounding backticks"
```

```python
# tests/unit/daemon/test_scope_overlap.py — added test
def test_is_test_path_recognises_relative_test_paths():
    """I-00071 RED: relative paths starting with tests/, test/, or __tests__/ must
    be recognised as test paths, not just paths containing /tests/ etc."""
    assert is_test_path("tests/dashboard/test_x.py") is True
    assert is_test_path("test/foo.py") is True
    assert is_test_path("__tests__/bar.py") is True
    # Already-covered cases remain True
    assert is_test_path("src/tests/foo.py") is True
```

Both tests FAIL on `main` and PASS after the fix.

## Acceptance Criteria

### AC1: Bug is fixed (parser strips backticks)

```
Given a design doc with `## Impacted Paths` bullets wrapped in markdown backticks
When `iw register` is called
Then `WorkItem.impacted_paths` contains the bare globs with no surrounding backticks
```

### AC2: Bug is fixed (gate strips relative test paths)

```
Given two batch items in the same execution_group whose only shared parent
directory is `tests/dashboard/` and whose impacted_paths are both test files
When the daemon advances the batch
Then `find_blocking_items` returns no overlap and both items launch
```

### AC3: Regression tests exist and verify semantic correctness

```
Given the fix is applied
When `make test-unit` runs
Then `test_parse_impacted_paths_strips_markdown_code_span_backticks` and
`test_is_test_path_recognises_relative_test_paths` both pass, and the assertions
verify the SPECIFIC EXPECTED VALUES — not just that the result is non-empty.
```

## Regression Prevention

1. **Parser normalises markdown code-span fences** — surrounding `` ` `` characters are stripped before validation. New tests cover both bullet and fenced-code-block branches and assert the bare glob (semantic check, not shape).
2. **Test-path recognition is anchored to path segments, not raw substrings** — extend `_TEST_PATH_MARKERS` (or use a segment-aware predicate) to cover relative `tests/`, `test/`, `__tests__/` prefixes. New tests cover relative, nested, conftest, and `*.test.*` / `*.spec.*` cases.
3. **Wider scope-overlap parametrization** — add an integration-style scope-overlap regression that mirrors the BATCH-00078 setup: two items in the same group, both with backtick-wrapped declarations, one writing `dashboard/app.py`, the other writing `dashboard/CLAUDE.md`. The fixed gate must not hold the second item.

## Dependencies

- **Depends on**: None
- **Blocks**: None

## Impacted Paths

- orch/design_doc_parser.py
- orch/daemon/scope_overlap.py
- orch/batch_planner.py
- tests/unit/test_design_doc_parser.py
- tests/unit/daemon/test_scope_overlap.py
- tests/unit/test_batch_planner_dependencies.py

## TDD Approach

- **Reproducing tests** (RED before fix, GREEN after):
  - `tests/unit/test_design_doc_parser.py::test_parse_impacted_paths_strips_markdown_code_span_backticks`
  - `tests/unit/daemon/test_scope_overlap.py::test_is_test_path_recognises_relative_test_paths`
- **Unit tests**:
  - Parser: backtick-wrapped paths in bullet lists, in fenced code blocks, with mixed wrapping (some bullets wrapped, some not), with double-backtick code spans (`` `` `foo` `` ``) — degrade gracefully.
  - Parser: bare paths still work unchanged (no regression).
  - Scope helper: relative `tests/`, `test/`, `__tests__/` recognised at any anchor; non-test paths still classified as non-test (`testscript.sh`, `test_data.json`, `src/test_utils.py`).
  - Scope helper: `globs_intersect` and `find_blocking_items` no longer report sibling overlaps when both candidate and in-flight paths are test files (covers BATCH-00078 CR-00034 + I-00069 case).
  - Parity helper: a single parametrized test in `tests/unit/test_batch_planner_dependencies.py` asserts `batch_planner._is_test_path` and `scope_overlap.is_test_path` agree on every fixture — guards against future divergence between the two mirrored predicates.
- **Integration tests**: None new required — the existing `tests/integration/test_f_00076_gate_performance.py` and `tests/integration/daemon/test_batch_manager_scope_gate.py` will pass unchanged (no behaviour change for non-test, non-backtick paths).

**Assertion scoping** — All new tests assert the exact expected glob values (e.g. `assert result.paths == ["dashboard/CLAUDE.md", ...]`) rather than just `assert result.paths` (truthy) or `len(...) > 0`. Test-path recognition asserts `is_test_path(x) is True` (specific Boolean), not just truthy.

## Notes

- The user explicitly chose **not** to backfill existing rows. Items currently in flight (CR-00034, I-00070) will merge soon, after which the new parser handles every future item correctly.
- The bug surfaced only because BATCH-00078 happened to put items with overlapping parent directories in the same group; if the design-time `batch_planner` had separated them, the bug would have stayed dormant. The fix prevents future incidents of this class.
- Severity is **Medium** — the gate fails-safe (items wait, they do not corrupt state). However, multi-item batches with shared parent directories collapse to serial execution, which is a real throughput regression.
