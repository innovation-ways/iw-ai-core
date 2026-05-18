# CR-00061 S01 Backend Report

**Work Item**: CR-00061 — Flaky test quarantine workflow (P2-CR-C)
**Step**: S01 (backend-impl)
**Date**: 2026-05-18
**Status**: COMPLETE

---

## Summary

CR-00061 S01 implements the full quarantine workflow for flaky/intermittently-failing tests. All 9 deliverables completed. No regressions, no pre-existing `@pytest.mark.quarantine` usage found, no changes to existing test bodies, no migrations.

---

## Files Changed

| File | Change |
|------|--------|
| `pyproject.toml` | Added `pytest-rerunfailures>=14.0,<16` to `[dependency-groups] dev`; added `quarantine` marker; extended `addopts` from `-m 'not browser'` to `-m 'not browser and not quarantine'` |
| `uv.lock` | Regenerated (added pytest-rerunfailures v15.1) |
| `Makefile` | Added `test-quarantine` and `test-flake-detect` targets; added both to `.PHONY` |
| `scripts/flake_detect_aggregate.py` | New file (≤120 SLoC, stdlib-only, parses pytest -v logs, exits 1 on flakes, 0 otherwise) |
| `tests/unit/test_quarantine_marker_setup.py` | New RED-first guard test (5 cases — all pass post-S01) |
| `docs/IW_AI_Core_Testing_Strategy.md` | §3 new "Flaky/quarantine workflow" sub-section; §3 Markers table new `quarantine` row; §5 2 new rows; §9 row flipped to ✅ |
| `tests/CLAUDE.md` | New "Quarantine workflow" sub-section (5-rule list verbatim from design) |
| `skills/iw-ai-core-testing/SKILL.md` | New "Quarantine workflow" sub-section in §2 (same 5 rules); synced to `.claude/skills/iw-ai-core-testing/SKILL.md` |
| `ai-dev/work/TESTS_ENHANCEMENT.md` | §6 item 2.3 → DONE — CR-00061 (2026-05-18); §11 new changelog entry |

---

## RED → GREEN Evidence

All 5 tests in `tests/unit/test_quarantine_marker_setup.py` pass:

```
tests/unit/test_quarantine_marker_setup.py::test_quarantine_marker_registered PASSED
tests/unit/test_quarantine_marker_setup.py::test_addopts_deselects_quarantine PASSED
tests/unit/test_quarantine_marker_setup.py::test_pytest_rerunfailures_installed PASSED
tests/unit/test_quarantine_marker_setup.py::test_makefile_exposes_quarantine_and_flake_detect_targets PASSED
tests/unit/test_quarantine_marker_setup.py::test_flake_detect_aggregator_is_valid_python PASSED
5 passed in 0.09s
```

---

## Smoke Test: marker deselection

**Setup**: Temporarily added `@pytest.mark.quarantine(reason="smoke-test-cr-00061")` to `test_iw_help_exits_zero` (first test in `tests/unit/test_smoke.py`). Reverted before S01 completion.

### Default run (quarantine deselected)

```
uv run pytest tests/unit/test_smoke.py -v --no-cov
...
collected 6 items / 1 deselected / 5 selected
tests/unit/test_smoke.py::TestSmokeCredentialRedaction::test_get_orch_db_url_redacts_password XFAIL
tests/unit/test_smoke.py::TestSmokeCredentialRedaction::test_db_url_construction_redacts_password XFAIL
tests/unit/test_smoke.py::TestSmokePlatformBasics::test_dashboard_app_factory_creates PASSED
tests/unit/test_smoke.py::TestSmokePlatformBasics::test_root_projects_page_renders PASSED
tests/unit/test_smoke.py::TestSmokePlatformBasics::test_base_import_works PASSED
================== 3 passed, 1 deselected, 2 xfailed in 1.86s ==================
```

**Result**: The marked test (`test_iw_help_exits_zero`) was **deselected** — not collected in the default run. `collected 6 items / 1 deselected`.

### Quarantine run (only marked test)

```
uv run pytest tests/unit/test_smoke.py -m quarantine -v --no-cov
...
collected 6 items / 5 deselected / 1 selected
tests/unit/test_smoke.py::TestSmokePlatformBasics::test_iw_help_exits_zero PASSED
======================= 1 passed, 5 deselected in 0.17s ========================
```

**Result**: The marked test was **the only test collected** under `-m quarantine`. Marker deselection confirmed working in both directions.

---

## Smoke Test: aggregator behaviour

### Fabricated flake (one test flips across runs)

```bash
uv run python scripts/flake_detect_aggregate.py /tmp/run1.log /tmp/run2.log /tmp/run3.log
```

Where run1=pass, run2=fail, run3=pass:

```
Flake detection over 3 runs of the full suite

Found 1 flaky test(s):
  tests/unit/test_fake.py::test_a
    run 1: PASSED
    run 2: FAILED
    run 3: PASSED

Recommendation: file an incident, add `@pytest.mark.quarantine(reason="I-NNNNN: ...")`
exit=1
```

**Result**: Exit 1 — flake correctly identified with per-run outcomes.

### Agreeing logs (all pass)

```bash
uv run python scripts/flake_detect_aggregate.py run1.log run2.log run3.log  # all identical
```

```
Flake detection over 3 runs of the full suite

No flakes detected.
exit=0
```

**Result**: Exit 0 — no false positives on clean logs.

---

## Pre-existing `@pytest.mark.quarantine` audit

```bash
grep -rn "@pytest.mark.quarantine" tests/ scripts/ orch/ dashboard/ executor/
```

**Result**: NONE FOUND. Zero pre-existing usage — the marker name was available and the addopts deselection will not silently break any existing workflow.

---

## Pre-flight Checks

| Check | Result |
|-------|--------|
| `make format` | ✅ All files formatted |
| `make typecheck` | ✅ mypy clean (255 source files) |
| `make lint` | ✅ ruff + templates + check_templates.py all pass |

---

## Verification Summary

- [x] `uv run pytest tests/unit/test_quarantine_marker_setup.py -v` → 5/5 pass
- [x] `make -n test-quarantine` and `make -n test-flake-detect` → both parse
- [x] `pytest --markers | grep quarantine` → lists new marker with correct prose
- [x] Smoke test 1: marker deselection confirmed (deselected in default run, selected under `-m quarantine`)
- [x] Smoke test 2: aggregator correctly reports flake (exit 1) and clean logs (exit 0)
- [x] `git diff tests/unit/test_smoke.py` → empty (smoke-test marker reverted)
- [x] Skill sync: `diff skills/iw-ai-core-testing/SKILL.md .claude/skills/iw-ai-core-testing/SKILL.md` → empty
- [x] `addopts` contains exactly one `-m` filter (`-m 'not browser and not quarantine'`)
- [x] `pytest-rerunfailures` importable: version 15.1
- [x] `scripts/flake_detect_aggregate.py` ≤120 SLoC, stdlib-only (no pytest/requests/httpx imports)
- [x] 5 existing `order_dependent` quarantines untouched (CR-00048/55 tracking preserved)

---

## Notes

Phase-2 closes with this CR. All three Phase-2 items are now DONE:
- 2.1: Mutation testing (CR-00059, 2026-05-18) ✅
- 2.2: Hypothesis property-based tests (CR-00060, 2026-05-18) ✅
- 2.3: Flaky/quarantine workflow (CR-00061, 2026-05-18) ✅

The `quarantine` marker and `order_dependent` marker coexist: both excluded from the merge gate, new entries default to `quarantine`, pre-existing `order_dependent` entries (from CR-00048/55) are not migrated.

The file-an-incident rule is the load-bearing part of this CR. Without it, quarantine is just a marker — with it, the quarantine backlog becomes queryable via Incident IDs and bounded by the Incident state machine.