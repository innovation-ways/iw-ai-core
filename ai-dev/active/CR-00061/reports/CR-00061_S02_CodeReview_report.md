# CR-00061 S02 Code Review Report

**Work Item**: CR-00061 — Flaky test quarantine workflow (P2-CR-C)
**Step**: S02 (code-review-impl)
**Reviewed Agent**: backend-impl (S01)
**Date**: 2026-05-18
**Verdict**: **PASS**

---

## Summary

S01 implemented the full quarantine workflow correctly. All 11 review checklist items pass. The five CRITICAL risks identified in the S02 prompt were all mitigated: `addopts` uses exactly one `-m 'not browser and not quarantine'` filter (no duplicate), `test-quarantine` uses `--reruns 1` (not `--reruns 3`), smoke-test marker was fully reverted, aggregator is stdlib-only, and the 5-rule list is verbatim in both `tests/CLAUDE.md` and the skill.

---

## Pre-Review Lint Gate

| Check | Result |
|-------|--------|
| `make lint` | ✅ All checks passed (ruff + templates + check_templates.py) |
| `make format-check` | ✅ 760 files already formatted |

No new lint or format violations introduced by S01.

---

## Per-Checklist Findings

### 1. Dependency + marker registration ✅ PASS

- `pytest-rerunfailures>=14.0,<16` present in `[dependency-groups] dev` (`pyproject.toml:100`)
- `import pytest_rerunfailures` succeeds (version 15.1)
- `pytest --markers` lists `quarantine` with description matching design prose: key phrases present ("intermittently failing", "excluded from the merge gate", "tracked via an Incident", "Recovery signal: passes consistently in `make test-quarantine` for >=3 consecutive runs")

**Finding**: None. AC1 fully satisfied.

### 2. addopts mutation correctness ✅ PASS

```python
# addopts before:
"-m 'not browser' --strict-markers"
# addopts after:
"-m 'not browser and not quarantine' --strict-markers"
```

- Contains `not browser and not quarantine` exactly **once** ✅
- Does NOT contain a separate `-m 'not browser'` clause (old filter replaced, not appended) ✅
- Contains `--strict-markers` ✅
- Exactly one `-m ` substring (count = 1) ✅

**Finding**: None. AC2 fully satisfied. No duplicate `-m` risk.

### 3. Makefile recipes — exact form ✅ PASS

`make -n test-quarantine` output:
```
uv run pytest tests/ -m quarantine --reruns 1 --reruns-delay 1 -v --no-cov
```

- `--reruns 1` (not `--reruns 3`) ✅ — design intent: surface flakes, don't mask them
- `--reruns-delay 1` ✅
- `-v` present ✅ (per-test line emission for aggregator regex)

`make -n test-flake-detect` output:
- Loops `pytest` 3× into `tests/output/flake-detect-{1,2,3}.log` ✅
- Invokes `scripts/flake_detect_aggregate.py` with all three log paths ✅
- Uses `-v` (not `-q`) ✅ — required for aggregator regex matching
- Both targets in `.PHONY` line ✅

**Finding**: None. AC3 fully satisfied.

### 4. Aggregator script — purity + behaviour ✅ PASS

- 89 SLoC (≤120 limit) ✅
- Imports: `re`, `sys`, `collections.defaultdict`, `pathlib.Path` — all stdlib ✅
- `ast.parse()` succeeds (valid Python) ✅
- No third-party imports (`pytest`, `requests`, `httpx`) ✅

**Behaviour test — fabricated flake (pass-fail-pass):**
```
Flake detection over 3 runs of the full suite
Found 1 flaky test(s):
  tests/unit/test_fake.py::test_a
    run 1: PASSED
    run 2: FAILED
    run 3: PASSED
exit=1 ✅
```

**Behaviour test — all agreeing logs:**
```
No flakes detected.
exit=0 ✅
```

**Finding**: None. AC4 fully satisfied.

### 5. Smoke-test captures in S01 report ✅ PASS

Two sub-sections present in `CR-00061_S01_Backend_report.md`:

- **Smoke test: marker deselection** — contains `collected 6 items / 1 deselected / 5 selected` (default run) and `collected 6 items / 5 deselected / 1 selected` (`-m quarantine` run). Marker deselection confirmed in both directions ✅
- **Smoke test: aggregator behaviour** — contains fabricated flake (exit 1) AND all-passing logs (exit 0) ✅

**Finding**: None. AC5 fully satisfied.

### 6. Smoke-test marker REVERTED ✅ PASS

```bash
git diff tests/unit/test_smoke.py  # empty output ✅
git diff origin/main..HEAD | grep -E "^\+.*@pytest\.mark\.quarantine"  # NONE FOUND ✅
```

The temporary `@pytest.mark.quarantine(reason="smoke-test-cr-00061")` was fully reverted. No stray quarantine markers in any test file.

**Finding**: None. CRITICAL risk #3 fully mitigated.

### 7. tests/CLAUDE.md 5-rule list verbatim ✅ PASS

All 5 rules present in order, matching design wording:

1. "Before adding `@pytest.mark.quarantine`, run `/iw-new-incident`..." ✅
2. "The marker MUST carry a `reason` string of the form `"I-NNNNN: <one-liner — suspected cause + when added>"`" ✅
3. "The Incident's `Description` field must name the test(s) verbatim..." ✅
4. "To remove the marker: run `make test-quarantine` for 3 consecutive runs (or 7 calendar days, whichever is more)..." ✅
5. "The existing `@pytest.mark.order_dependent` is a narrower flavour of `quarantine`..." ✅

**Finding**: None. Rule list is verbatim, not paraphrased.

### 8. Strategy doc / skill consistency ✅ PASS

- `docs/IW_AI_Core_Testing_Strategy.md` §3: "Flaky/quarantine workflow" sub-section present ✅
- §5: 2 new rows present (quarantine deselection + flake detector on-demand) ✅
- §9: row "Flaky/quarantine workflow" flipped to ✅ with CR-00061, 2026-05-18 ✅
- `skills/iw-ai-core-testing/SKILL.md`: "Quarantine workflow" sub-section present with same 5 rules ✅
- `diff skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md` → empty ✅

**Finding**: None. AC6 fully satisfied.

### 9. Plan + changelog ✅ PASS

- `ai-dev/work/TESTS_ENHANCEMENT.md` §6 item 2.3: `DONE — CR-00061 (2026-05-18)` ✅
- §11 dated entry (2026-05-18) includes: marker registration; addopts change; 3 targets (test-quarantine, test-flake-detect, aggregator); file-an-incident rule; order_dependent reconciliation ✅

**Finding**: None. AC7 fully satisfied.

### 10. Scope-creep audit ✅ PASS

**CR-00061 files changed (staged/modified in worktree):**
- `pyproject.toml` ✅
- `uv.lock` ✅
- `Makefile` ✅
- `scripts/flake_detect_aggregate.py` ✅
- `tests/unit/test_quarantine_marker_setup.py` ✅
- `docs/IW_AI_Core_Testing_Strategy.md` ✅
- `tests/CLAUDE.md` ✅
- `skills/iw-ai-core-testing/SKILL.md` + `.claude/skills/iw-ai-core-testing/SKILL.md` ✅
- `ai-dev/work/TESTS_ENHANCEMENT.md` ✅

These are exactly the "Impacted Paths" from the design.

**Forbidden paths — NOT touched by CR-00061:**
- `orch/`, `dashboard/`, `executor/` — only modified by CR-00060 (merge commit), not by CR-00061's S01 ✅
- No GH workflow changes ✅
- No Alembic migrations ✅
- No test-body changes (only the new guard test `test_quarantine_marker_setup.py`) ✅

**Finding**: None. Scope is clean and exactly matches design.

### 11. RED-first contract integrity ✅ PASS

`tests/unit/test_quarantine_marker_setup.py` is in `files_changed` ✅

The file contains 5 RED-first guard tests:
1. `test_quarantine_marker_registered` — asserts `quarantine:` in markers ✅
2. `test_addopts_deselects_quarantine` — asserts `not browser and not quarantine` in addopts, exactly one `-m`, `--strict-markers` present ✅
3. `test_pytest_rerunfailures_installed` — `importlib.import_module("pytest_rerunfailures")` ✅
4. `test_makefile_exposes_quarantine_and_flake_detect_targets` — `make -n test-quarantine` and `make -n test-flake-detect` both parse ✅
5. `test_flake_detect_aggregator_is_valid_python` — `ast.parse()` + stdlib-only assertion ✅

All 5 tests pass (GREEN evidence in S01 report). The tests use real assertions with real error messages, not `"n/a"`.

**Finding**: None. RED-first contract fully satisfied.

---

## addopts Before/After Diff

```
BEFORE (pyproject.toml addopts):
  "-m 'not browser' --strict-markers"

AFTER (pyproject.toml addopts):
  "-m 'not browser and not quarantine' --strict-markers"
```

The `-m 'not browser'` clause was **replaced** (not duplicated) with the combined `-m 'not browser and not quarantine'` filter. Exactly one `-m ` present. `--strict-markers` preserved.

---

## Smoke-Test Capture Summary

**Smoke test 1 — Marker deselection:**  
S01 temporarily added `@pytest.mark.quarantine(reason="smoke-test-cr-00061")` to `test_iw_help_exits_zero` in `tests/unit/test_smoke.py`, then reverted. In the default run, pytest output was `collected 6 items / 1 deselected / 5 selected` — the marked test was silently excluded from collection. Under `-m quarantine`, the same test was the sole collected item (`collected 6 items / 5 deselected / 1 selected`). This confirms the `addopts` deselection works bidirectionally.

**Smoke test 2 — Aggregator behaviour:**  
S01 ran the aggregator against fabricated logs: run1=pass, run2=fail, run3=pass → reported `test_a` as flaky with per-run outcomes and exited 1. Against all-agreeing logs (run1=run2=run3=pass) → exited 0 with "No flakes detected." Both behaviours match the design spec.

---

## Aggregator Independent Re-Verification

I ran the aggregator independently against my own fabricated logs:

```
# pass-fail-pass across 3 runs
$ uv run python scripts/flake_detect_aggregate.py run1.log run2.log run3.log
Flake detection over 3 runs of the full suite
Found 1 flaky test(s):
  tests/unit/test_fake.py::test_a
    run 1: PASSED
    run 2: FAILED
    run 3: PASSED
exit=1 ✅

# all agreeing logs
$ uv run python scripts/flake_detect_aggregate.py run1.log run2.log run3.log
No flakes detected.
exit=0 ✅
```

Both behaviours match the design spec. The aggregator is a pure stdlib script with no third-party dependencies.

---

## Scope Diff

| File | Status | Notes |
|------|--------|-------|
| `pyproject.toml` | PASS | quarantine marker + addopts + pytest-rerunfailures dep |
| `uv.lock` | PASS | regenerated with pytest-rerunfailures 15.1 |
| `Makefile` | PASS | test-quarantine + test-flake-detect targets + .PHONY |
| `scripts/flake_detect_aggregate.py` | PASS | 89 SLoC, stdlib-only, exits 0/1 per spec |
| `tests/unit/test_quarantine_marker_setup.py` | PASS | 5 RED-first guard tests, all pass |
| `docs/IW_AI_Core_Testing_Strategy.md` | PASS | §3 sub-section + §5 rows + §9 flipped |
| `tests/CLAUDE.md` | PASS | 5-rule quarantine workflow verbatim |
| `skills/iw-ai-core-testing/SKILL.md` | PASS | 5-rule quarantine workflow verbatim |
| `.claude/skills/iw-ai-core-testing/SKILL.md` | PASS | byte-identical sync |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | PASS | §6 item 2.3 DONE + §11 changelog |
| `orch/` | PASS | no changes (CR-00060 merge commit only) |
| `dashboard/` | PASS | no changes (CR-00060 merge commit only) |
| `executor/` | PASS | no changes |
| `.github/` workflows | PASS | no changes |
| Alembic migrations | PASS | none |
| Test bodies | PASS | only new guard test, no body modifications |

---

## Notes

- Phase 2 closes with this CR. All three Phase-2 items (2.1 mutation spike CR-00059, 2.2 Hypothesis CR-00060, 2.3 quarantine CR-00061) are DONE.
- The `quarantine` marker and `order_dependent` marker coexist per design: both excluded from merge gate, pre-existing `order_dependent` entries (CR-00048/55) untouched.
- The file-an-incident rule is the load-bearing part of this CR — the 5-rule verbatim text in `tests/CLAUDE.md` and the skill is what makes it enforceable.
- The `--reruns 1` choice in `test-quarantine` is intentional and correct per the design notes: it surfaces flakes rather than masking them with retries.

---

## Verdict

**PASS** — S01 implementation is correct, complete, and compliant with the design. No mandatory fixes required.

```json
{
  "step": "S02",
  "agent": "code-review-impl",
  "work_item": "CR-00061",
  "reviewed_agent": "backend-impl",
  "verdict": "PASS",
  "mandatory_fix_count": 0,
  "findings": [],
  "notes": "All 11 review checklist items pass. addopts merge is exact (single -m filter). test-quarantine uses --reruns 1 (not 3). smoke-test marker fully reverted. aggregator is stdlib-only 89-line pure Python script. 5-rule list verbatim in tests/CLAUDE.md and skill. Skill synced byte-identically. §6 item 2.3 = DONE. §11 changelog complete. Scope is clean — exactly Impacted Paths from design, no production code, no migrations, no GH workflows. Phase 2 closes."
}
```