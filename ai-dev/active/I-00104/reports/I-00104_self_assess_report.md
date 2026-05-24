# I-00104 Self-Assessment Report — S13

**Step**: S13 — `self-assess-impl`
**Work Item**: I-00104 — Batch planner false-negative overlap analysis + Max Parallel display mismatch
**Date**: 2026-05-24
**Completion Status**: **complete**

---

## 1. What Was Done

This is a self-assessment step for I-00104. It analyses the implementation quality across all prior steps (S01–S12) against five focus areas defined in the step prompt. The `iw-item-analyze` skill is not registered as a CLI command in this worktree; analysis was performed directly by reading the step reports, git diffs, and source code.

Output files produced:
- `ai-dev/active/I-00104/reports/I-00104_self_assess_report.md` (this file)
- `ai-dev/active/I-00104/reports/I-00104_self_assess_findings.json`

---

## 2. Analysis by Focus Area

### 2.1 Helper Adoption — ✅ REAL, NOT REIMPLEMENTED

The S01 fix correctly imports and calls `globs_intersect`:

```python
# orch/batch_planner.py — intra-batch loop (Phase 3)
from orch.daemon.scope_overlap import globs_intersect  # noqa: E402

files_a = list(analysis[id_a].affected_files)
files_b = list(analysis[id_b].affected_files)
overlap = globs_intersect(files_a, files_b)
```

```python
# orch/batch_planner.py — cross-batch loop (Phase 3b)
overlap = globs_intersect(list(analysis[iid].affected_files), list(active_files))
```

**Finding**: No reimplementation of `globs_intersect` logic inline. The canonical helper is imported and called correctly. Both loops now use it. `git diff origin/main` confirms zero `& set(` remaining in the affected file.

### 2.2 Class-of-Bug Grep — ✅ NO DUPLICATE IMPLEMENTATIONS FOUND

S05's final review already performed the grep. No other place in `orch/`, `dashboard/`, `executor/`, or `tests/` re-implements overlap detection via `set & set` on path strings.

The S05 finding about `tests/unit/test_batch_planner_analysis.py` call sites using literal `4` is a **pre-existing test fixture** issue, not a production code bug — see Section 2.3.

**Finding**: No follow-up Incident needed for duplicate overlap implementations. The single canonical implementation is `globs_intersect` in `orch/daemon/scope_overlap.py`, now shared by both the planner and the daemon.

### 2.3 Constant Elimination — ⚠️ ONE SURFACE, NO LIVE BUG (MEDIUM follow-up)

S05 confirmed zero remaining `, 4)` literals in **production** call sites:
- `dashboard/routers/actions.py:894-896`: `batch.max_parallel` ✅
- `orch/cli/batch_commands.py:221-223`: `batch.max_parallel` ✅

The only remaining literal `4` in call sites is in **pre-existing test fixtures**:
- `tests/unit/test_batch_planner_analysis.py` — `test_generate_plan_md_contains_batch_id` (line 220), `test_generate_drawio_valid_xml` (line 237), `test_generate_png_returns_bytes` (line 254)

These tests verify the rendering helpers in isolation (structural XML/markdown content) — they pass `4` as an arbitrary constant to exercise the rendering. The S03 regression-lock test (`test_execution_plan_md_renders_given_max_parallel`) already covers value-variation (3 and 7) and is the appropriate place for that concern.

**Assessment**: Not a live bug. The S05 recommendation to update these fixtures to use named parameters (`max_parallel=4`) is a code-hygiene improvement but does not constitute an Incident. A follow-up Change Request (MEDIUM) is appropriate — see `I-00104_self_assess_findings.json`.

### 2.4 Test-RED Honesty — ✅ GENUINE RED, PRECISE TARGETING

S03's `tdd_red_evidence` in `test_batch_planner_overlap.py` is analytically sound:

| Test | Pre-fix code path targeted | RED mechanism |
|------|---------------------------|---------------|
| `test_glob_vs_concrete_file_overlap` | `set(...) & set(...)` in Phase 3 | `{"skills/iw-ai-core-testing/**"} & {"skills/iw-ai-core-testing/SKILL.md"}` → empty → `overlap_with=[]` → `assert "B" in []` FAILS |
| `test_dir_glob_vs_dir_glob_overlap` | Same Phase 3 bug | `{"a/**"} & {"a/b/**"}` → empty → FAILS |
| `test_cross_batch_overlap_uses_globs_intersect` | Cross-batch loop `set(...) & active_files` | `{"dashboard/static/x.js"} & {"dashboard/**"}` → empty → `cross_batch_conflicts=[]` → FAILS |
| `test_execution_plan_md_renders_given_max_parallel` | **GREEN only** (not RED-able) | The helper was always correct; the bug was the caller. Correctly categorised as a regression-lock. |

The `test_strictly_disjoint_paths_no_overlap` (AC4) is a negative case — passes both before and after fix. Correctly excluded from RED evidence.

The tests target the exact code S01 changed (Phase 3 loop and Phase 3b loop in `analyze_dependencies`), not incidental side effects. The RED evidence is genuine, not boilerplate.

### 2.5 Fix Cycle Cost — ✅ MINIMAL OVERHEAD, WELL-EXPLAINED

Fix cycles encountered:

| Gate | Cycles | Cause | Assessment |
|------|--------|-------|------------|
| S06 (lint) | 3 | Pre-existing lint errors in unrelated test files (`tests/e2e/test_journey_htmx_fragments.py`) | Out-of-scope to I-00104; addressed by linting pre-existing files on main |
| S09 (unit tests) | 5 (one recorded) | Pre-existing test `TestI00105EffectiveContextPct` failing with `None == 0.0` — unrelated to I-00104 | Out-of-scope to I-00104; `test_batch_planner_overlap.py` and `test_batch_plan_max_parallel.py` all green |
| S12 (browser) | 1 | E2E DB (port 5489) had different batches than orch DB (port 5433) — required fixture creation | Productive: E2E fixture seeding was added as part of the verification |

No fix cycles were caused by a misread of `globs_intersect`'s return type or argument shape. The S01 implementation correctly converted `affected_files` (a list) to a list, passed it to `globs_intersect`, and interpreted the list-return value as truthy (non-empty list = overlap).

**Workflow improvement observation**: The `_is_test_path` function in `orch/daemon/scope_overlap.py` has a comment "Mirror `orch/batch_planner.py:_is_test_path` semantics" — but S01's fix did not need to call `_is_test_path`. The planner's overlap detection does not apply block/allow policies (that's the daemon's `find_blocking_items`). Adding a docstring example to `globs_intersect` would prevent future agents from misinterpreting its return type (it returns a list of matching globs from `a`, not a boolean). This is a minor documentation improvement — see `I-00104_self_assess_findings.json`.

---

## 3. Summary Verdict

| Focus Area | Result | Notes |
|-----------|--------|-------|
| Helper adoption | ✅ PASS | Real import + call; no reimplementation |
| Class-of-bug grep | ✅ PASS | Zero duplicate implementations; S05 already confirmed |
| Constant elimination | ⚠️ PARTIAL | No live bug; one MEDIUM follow-up for test fixture hygiene |
| Test-RED honesty | ✅ PASS | Genuine RED lines targeting exact changed code |
| Fix cycle cost | ✅ PASS | All failures were out-of-scope pre-existing issues |

**Overall**: Implementation quality is high. The fix correctly adopted the canonical helper, targeted the exact buggy code paths, and has genuine test coverage with honest RED evidence. The only area for improvement is test fixture hygiene (MEDIUM follow-up) and documentation of `globs_intersect` return semantics (minor).

---

## 4. Files Changed

| File | Purpose |
|------|---------|
| `ai-dev/active/I-00104/reports/I-00104_self_assess_report.md` | This report |
| `ai-dev/active/I-00104/reports/I-00104_self_assess_findings.json` | Structured findings (2 follow-ups) |

---

## 5. Preflight Quality Gates

- **format**: skipped (analysis step — no code changes)
- **typecheck**: skipped (analysis step — no code changes)
- **lint**: skipped (analysis step — no code changes)
- **tests**: skipped (analysis step — no code changes)

---

## 6. Notes

- The `iw-item-analyze` skill is not registered as a CLI subcommand in this worktree. Analysis performed by direct source reading.
- S12's fix cycle (E2E DB vs. orch DB mismatch) was productive: it led to the `e2e_fixtures/` directory being added with programmatic fixture seeding.
- Browser verification (S12) confirmed all three acceptance criteria (overlap detection, warnings, max_parallel consistency) end-to-end in a real browser session.