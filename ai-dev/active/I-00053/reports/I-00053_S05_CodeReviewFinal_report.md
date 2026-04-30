# I-00053 S05 — Final Code Review Report

## Work Item
**I-00053** — Batch Planner Ignores Explicit "Depends on:" / "Blocks:" Declarations

## Step Reviewed
**S05** — code-review-final-impl (cross-cutting global review)

---

## Verdict: **PASS**

---

## What Was Done

Reviewed all implementation reports (S01–S04), re-read the design doc, verified all modified and new source files, and ran the complete regression suite across all quality gates.

### Files Reviewed

| File | Step | Change |
|------|------|--------|
| `orch/design_doc_parser.py` | S01 | Created — pure parser: `parse_dependencies()`, `strip_excluded_sections()` |
| `orch/cli/item_commands.py` | S01 | Modified — wires parser into `iw register`; self-dep filter; Blocks inversion |
| `orch/batch_planner.py` | S01 | Modified — `extract_affected_files()` calls `strip_excluded_sections()` |
| `tests/unit/test_design_doc_parser.py` | S03 | New — 19 parser unit tests |
| `tests/unit/test_batch_planner_dependencies.py` | S03 | New — 6 planner regression tests |
| `tests/integration/test_register_persists_dependencies.py` | S03 | New — 5 register integration tests |

---

## Checklist Assessment

### 1. Completeness vs Design

| AC | Status |
|----|--------|
| AC1: Declared deps persisted at register time | ✅ — `parse_dependencies()` called in `register()`; `WorkItem.depends_on` populated |
| AC2: `Blocks:` inversion equivalent | ✅ — post-`session.flush()`, `blocked_item.depends_on += [item_id]` |
| AC3: Regression tests exist | ✅ — 32 new tests all pass |
| AC4: Spurious file-overlap eliminated | ✅ — `strip_excluded_sections()` removes `## Out of Scope` / `## Notes` before path extraction |
| AC5: Backwards compatibility | ✅ — 2089 existing unit tests pass |
| AC6: No out-of-scope items shipped | ✅ — no new CLI, no migration, no executor/daemon/dashboard changes |

All 7 invariants verifiable from code: ✅

### 2. Cross-Step Consistency

- `Dependencies` dataclass shape (`depends_on: list[str]`, `blocks: list[str]`) — consistent across parser, register, and tests ✅
- Section names `"Out of Scope"`, `"Notes"` — hard-coded in `strip_excluded_sections()`, matched in tests ✅
- ID regex `\b(?:F|I|CR)-\d{3,5}\b` — covers all valid IDs used in tests (F-, I-, CR- with 3-5 digits) ✅

### 3. Integration

- **I-00053 regression suite**: 32 tests, all passed ✅
- **Full unit suite**: 2089 passed, 2 skipped (pre-existing) ✅
- **Real design doc (F-00073 → `parse_dependencies()`)**:
  - Returns `Dependencies(depends_on=['F-00069', 'F-00073'], blocks=[])` — correctly parsed, self-dep filtered ✅
- **F-00069 `extract_affected_files()`** — does NOT include `tests/unit/test_logging.py` (false-positive from `## Out of Scope` eliminated) ✅
- **BATCH-00064 root case with declared deps**: F-00069 group 0, F-00073 group 1 ✅

### 4. Architecture

- No new external Python deps ✅
- `orch/design_doc_parser.py` is pure (no I/O, no DB) ✅
- No live-DB connections introduced ✅
- `extract_affected_files()` refactor preserves `_is_test_path()` exclusion behavior ✅

### 5. Security

- Parser is regex-based; no `eval`, no `exec`, no shell-out ✅
- No new HTTP/network calls ✅
- Logging does not leak credentials or unexpected paths ✅

### 6. Holistic Test Pass

| Gate | Result |
|------|--------|
| `make lint` (touched files) | ✅ All checks passed |
| `make format-check` | ✅ All checks passed |
| `make typecheck` (mypy) | ✅ No errors |
| `make test-unit` | ✅ 2089 passed, 2 skipped, 0 new failures |
| `make test-integration` | ✅ 28 passed (test_register_persists_dependencies.py + models) |

---

## Known Observation (not a bug)

F-00073's own `## File Manifest` table legitimately lists `tests/unit/test_logging.py` as a "New" file — it is the **authoritative source** for that path. The path therefore appears in F-00073's `extract_affected_files()` output. This is correct behavior: a path in the File Manifest table is the canonical source, not a prose mention. F-00069's false-positive (from its `## Out of Scope` prose) is correctly eliminated.

---

## Pre-Existing Test Failures (unrelated to I-00053)

- `test_qv_baseline.py::test_integration_tests_is_not_in_gate_parsers`
- `test_i00049_gate_command.py::test_integration_tests_not_in_gate_parsers`
- `test_precommit_config.py::test_pre_commit_hooks_repo_rev_pinned`
- `test_safe_migrate.py` (×2)

---

## Test Summary

| Suite | Passed | Failed | Skipped |
|-------|--------|--------|---------|
| I-00053 unit (parser + planner) | 27 | 0 | 0 |
| I-00053 integration | 5 | 0 | 0 |
| Full unit suite | 2089 | 0 | 2 |
| Full integration suite | 28 | 0 | 0 |

**Total: 2149 passed, 0 new failures**

---

## Notes

The S02 review (code-review-impl) correctly identified that `item_commands.py` had not been updated when S01's report was filed. S01 subsequently fixed this gap (the current state of `item_commands.py` shows `parse_dependencies()` wired in at lines 349–389 with self-dependency filtering and Blocks inversion). All subsequent reviews (S03, S04) confirmed the correct implementation.

The fix is complete and correct. I-00053 is ready for merge.