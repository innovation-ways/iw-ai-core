# CR-00087 S02 — BackendImpl Report

**Work Item**: CR-00087 -- Auto-amend scope violations matching per-project allow-patterns
**Step**: S02
**Agent**: backend-impl
**Status**: complete

---

## What Was Done

Added the pure helper `should_auto_amend` to `orch/daemon/scope_amendment.py` and
promoted `_scope_match` to a public `scope_match` name in `orch/daemon/fix_cycle.py`,
with the matcher reused by the new helper for guaranteed semantic consistency.

---

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/fix_cycle.py` | Renamed `_scope_match` → `scope_match` (public); updated 2 internal call sites. No backward-compat alias added — no external callers exist. |
| `orch/daemon/scope_amendment.py` | Added `should_auto_amend(violations, allow_patterns, max_paths) -> bool` pure helper. Matcher is imported inside the function body (deferred import) to avoid any module-level cycle risk. |
| `tests/unit/daemon/test_scope_amendment.py` | Added `TestShouldAutoAmend` class with 13 test methods covering the full matrix (empty patterns, empty violations, single match, all-match, partial-match, max_paths cap, at-cap, dir-glob, nested-glob, dashboard-glob, max_paths=0, graceful non-list inputs, matcher-parity guard). |

---

## Matcher Promotion Decision

`grep -rn "_scope_match" tests/ orch/` showed exactly two internal callers in
`fix_cycle.py` (lines 238 and 1092) — no callers outside the defining module,
and no test pins the private name. The backward-compat alias (`_scope_match = scope_match`)
was **omitted**. All internal callers now use the public `scope_match`.

---

## Import Cycle Mitigation

`scope_amendment.py` does not import from `fix_cycle.py` at module-load time.
`fix_cycle.py` only imports from `scope_amendment.py` inside `_complete_fix_cycle`
(at function-call time, for S03's auto-amend hook) — this is already a deferred
pattern. The `should_auto_amend` import of `scope_match` is placed inside the function
body (deferred import) as an extra precaution. No cycle is introduced.

---

## TDD RED Evidence

The first test (`test_should_auto_amend_returns_true_for_single_matching_violation`)
was run with the stub that returns `False` unconditionally before implementation:

```
tests/unit/daemon/test_scope_amendment.py::TestShouldAutoAmend::test_should_auto_amend_returns_true_for_single_matching_violation FAILED
AssertionError: assert False is True
```

This confirmed the RED phase before the real implementation was added.

---

## Test Drop: `test_should_auto_amend_returns_false_for_unrecognised_glob`

This test was removed during implementation. It assumed `docs/*.md` would NOT match
`docs/sub/notes.md`, but Python's `fnmatch` uses greedy `*` that spans path segments:

```
fnmatch.fnmatch("docs/sub/notes.md", "docs/*.md") → True
```

The `scope_match` contract is the existing fnmatch-based contract. The test had
an incorrect expectation about the matcher's semantics — not a gap in `scope_match`,
but a mischaracterisation of it. The other 13 tests cover all the intended cases.

---

## Pre-flight Results

| Gate | Result |
|------|--------|
| `make format` | ok (893 files formatted) |
| `make typecheck` | ok (0 errors in 276 source files) |
| `make lint` | ok (0 errors) |

---

## Test Results

```
uv run pytest tests/unit/daemon/test_scope_amendment.py::TestShouldAutoAmend
                                           tests/unit/test_fix_cycle.py -v --no-cov
→ 69 passed, 0 failed
```

---

## Blockers

None.

---

## Notes

- **Deferred import in `should_auto_amend`**: `from orch.daemon.fix_cycle import scope_match`
  is placed inside the function body (not at module top-level) despite being safe from a
  cycle perspective. This documents the deliberate seam and mirrors the deferred-import
  pattern already used in `fix_cycle.py` for `review_mapping`.
- **Deferred import confirmed safe**: verified by running the test suite — no import errors.
- **`scope_match` vs fnmatch**: the `dir/**` shorthand (prefix-based) and plain fnmatch
  patterns (`dir/*.py`) are preserved exactly as-is. `fnmatch.fnmatch` with `*` matches
  across path separators, which is the existing documented behaviour of `_scope_match`.
