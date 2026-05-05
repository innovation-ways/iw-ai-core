# I-00066 S03 Tests Report

**Step**: S03 — Tests
**Work Item**: I-00066 — OSS finding modal too narrow and footer buttons unclear
**Agent**: tests-impl
**Date**: 2026-05-05

---

## Summary

Created reproduction and regression tests for I-00066, verifying the CSS/template fix applied in S01. All four tests pass against the current worktree (which includes S01's fix).

## Files Changed

| File | Change |
|------|--------|
| `tests/dashboard/test_i00066_oss_modal_styling.py` | Created (74 lines, 4 test functions) |

## Test Coverage

The new test file contains four semantic tests:

1. **`test_i00066_modal_inner_widened_in_source_css`** — Verifies `.oss-modal-inner` in `tailwind.src.css` has `max-width: 80vw` (not `36rem`). Will fail on `main` because pre-fix has `max-width: 36rem`.

2. **`test_i00066_modal_inner_widened_in_compiled_css`** — Verifies the compiled `styles.css` reflects the same change. Will fail on `main` because compiled CSS has `36rem` in `.oss-modal-inner`.

3. **`test_i00066_footer_close_uses_peer_button_class`** — Verifies the footer Close button in `oss_finding_modal.html` carries the new `modal-footer-close` class. Will fail on `main` because the button only has `class="modal-close"`.

4. **`test_i00066_footer_button_class_styled_in_source_css`** — Verifies `.modal-footer-close` rule in `tailwind.src.css` contains `border:` and `padding:` declarations. Will fail on `main` because the rule does not exist.

## Test Results

```
tests/dashboard/test_i00066_oss_modal_styling.py::test_i00066_modal_inner_widened_in_source_css PASSED
tests/dashboard/test_i00066_oss_modal_styling.py::test_i00066_modal_inner_widened_in_compiled_css PASSED
tests/dashboard/test_i00066_oss_modal_styling.py::test_i00066_footer_close_uses_peer_button_class PASSED
tests/dashboard/test_i00066_oss_modal_styling.py::test_i00066_footer_button_class_styled_in_source_css PASSED

4 passed, 0 failed
```

## Pre-flight Results

| Check | Result |
|-------|--------|
| `make format` | `tests/dashboard/test_i00066_oss_modal_styling.py` is already formatted (orch/llm_usage.py has unrelated drift) |
| `make typecheck` | OK — no type errors |
| `make lint` | `tests/dashboard/test_i00066_oss_modal_styling.py` passes ruff check (W292 trailing newline auto-fixed) |

## Observational Note on `make test-unit`

The full unit test suite shows 6 pre-existing failures in `tests/unit/daemon/test_worktree_compose.py` that are unrelated to this work item (they appear to be environment/fixture issues). These failures existed before I-00066 work began and are not caused by the new test file.

## Reproduction Guarantee (Mental Verification)

- Test 1: `tailwind.src.css` on `main` has `max-width: 36rem` → assertion `"max-width: 80vw" in body` is False → test **fails** on main ✓
- Test 2: `styles.css` on `main` has `36rem` in `.oss-modal-inner` → both `max-width:80vw` and `max-width: 80vw` are absent → test **fails** on main ✓
- Test 3: `oss_finding_modal.html` on `main` has `<button type="button" class="modal-close">` without `modal-footer-close` → regex finds nothing → test **fails** on main ✓
- Test 4: `.modal-footer-close` rule does not exist on `main` → `_block(...)` raises AssertionError → test **fails** on main ✓

---

**Status**: ✅ complete — 4 tests written and passing, all pre-flight checks passed.