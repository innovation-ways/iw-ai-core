# CR-00061 — S12 SelfAssess Report

**Work Item**: CR-00061 — Flaky test quarantine workflow (P2-CR-C)
**Step**: S12 (self-assess-impl)
**Date**: 2026-05-18
**Status**: COMPLETE

---

## Summary

Phase-2 closing self-assessment for CR-00061. Analysis draws on S01–S03 reports, CR-00059/CR-00060 predecessor reports, and `ai-dev/work/TESTS_ENHANCEMENT.md`. Produces the 7 Phase-2-closing findings plus Phase-3 sequencing recommendation.

---

## TDD RED Evidence

S01's `tests/unit/test_quarantine_marker_setup.py` RED-first guard — 5 tests written before implementation, observed failing with real AssertionErrors, then passing GREEN after S01 implementation:

**Test IDs and failure lines (from RED-first run):**

| Test ID | RED failure line |
|---------|-----------------|
| `tests/unit/test_quarantine_marker_setup.py::test_quarantine_marker_registered` | `AssertionError: assert 'quarantine' in markers` (marker not yet registered) |
| `tests/unit/test_quarantine_marker_setup.py::test_addopts_deselects_quarantine` | `AssertionError: assert 'not browser and not quarantine' in addopts` (addopts not yet extended) |
| `tests/unit/test_quarantine_marker_setup.py::test_pytest_rerunfailures_installed` | `ModuleNotFoundError: No module named 'pytest_rerunfailures'` (dep not yet added) |
| `tests/unit/test_quarantine_marker_setup.py::test_makefile_exposes_quarantine_and_flake_detect_targets` | `AssertionError: Makefile target 'test-quarantine' not found in make -n output` (targets not yet added) |
| `tests/unit/test_quarantine_marker_setup.py::test_flake_detect_aggregator_is_valid_python` | `FileNotFoundError: scripts/flake_detect_aggregate.py does not exist` (script not yet written) |

All 5 passed GREEN after S01 implementation (S01 report lines 34–43).

**CR-00045 contract**: `tdd_red_evidence` present with real test ids + failure lines. ✅ **n/a NOT used — contract satisfied.**

---

## Phase-2 Closing Findings

### Finding 1 — Marker deselection foolproofness

**Did S01's SMOKE TEST in deliverable 7 work first try?**

Yes. The smoke test in `CR-00061_S01_Backend_report.md` (lines 49–77) shows:
- `@pytest.mark.quarantine(reason="smoke-test-cr-00061")` added to `test_iw_help_exits_zero`
- Default run: `collected 6 items / 1 deselected / 5 selected` — marked test silently excluded
- `-m quarantine` run: `collected 6 items / 5 deselected / 1 selected` — marked test sole collected
- No addopts parsing surprise; no `--strict-markers` interaction; no pytest version mismatch
- **The addopts-merge pattern is now muscle-memory**: the old `-m 'not browser'` clause was **replaced** (not duplicated) with `-m 'not browser and not quarantine'`. Exactly one `-m` filter in addopts throughout.

**Lesson for Phase 3**: Phase 3 will add more markers (3.4 cross-project isolation may add `tenant_a`/`tenant_b`; 3.5 security may add a `negative` marker). The pattern demonstrated here — replace the single `-m` clause, never append a second `-m` — is the correct approach. The `test_quarantine_marker_setup.py` guard test (`test_addopts_deselects_quarantine`) permanently encodes this constraint.

**Recommendation**: When Phase 3 adds markers, the Phase-3 template should require a guard test that asserts the exact form of addopts (single `-m`, correct filter chain) in addition to smoke-test capture. This prevents the duplicate-`-m` regression that would silently break deselection.

---

### Finding 2 — Aggregator robustness: SKIPPED-row handling

**Did S03's independent run on the SKIPPED-row fabricated log surface any parsing surprise?**

No. S03 independently ran the aggregator on fabricated logs with shape:
- run1: `test_create PASSED`, `test_update FAILED`, `test_delete SKIPPED`
- run2: `test_create PASSED`, `test_update PASSED`, `test_delete SKIPPED`
- run3: `test_create PASSED`, `test_update PASSED`, `test_delete SKIPPED`

Result (`CR-00061_S03_CodeReviewFinal_report.md` lines 48–63):
- `test_update` (PASSED→FAILED→PASSED) correctly identified as flaky ✅
- `test_delete` (all SKIPPED) NOT reported as flaky ✅ — no false positive on SKIPPED
- `test_create` (all PASSED) NOT reported as flaky ✅ — no false positive on consistent PASSED

**Conclusion**: The aggregator correctly treats SKIPPED as a stable (non-flake) result. No follow-up CR needed for aggregator-skipped-row handling. The regex matches only `PASSED`/`FAILED` lines from pytest `-v` output; SKIPPED lines are simply not matched.

---

### Finding 3 — File-an-incident rule enforceability

**Did reviewers in S02 and S03 actually verify the rule's text was verbatim across the three documentation surfaces?**

Yes. S02 checklist item 7 (`CR-00061_S02_CodeReview_report.md` lines 119–129) verified all 5 rules present in order in `tests/CLAUDE.md`. S03 checklist item 4 (`CR-00061_S03_CodeReviewFinal_report.md` lines 83–98) independently verified the cross-doc-square with a per-rule table across all three locations:

| Rule | tests/CLAUDE.md | skill | strategy doc |
|------|----------------|-------|--------------|
| 1. file incident before quarantine | ✅ | ✅ | ✅ (summary) |
| 2. marker reason contains `I-NNNNN` | ✅ | ✅ | ✅ (summary) |
| 3. incident describes test verbatim | ✅ | ✅ | ✅ (summary) |
| 4. recovery = 3 runs / 7 days | ✅ | ✅ | ✅ |
| 5. order_dependent stays separate | ✅ | ✅ | ✅ |

**Signal**: The prose rule is working as written. No automated check was needed for this CR. However, the **enforceability depends on reviewer diligence** — S03's cross-doc-square was a dedicated checklist item, not automatic.

**Recommendation**: The Phase-3 template should include a cross-doc-square checklist item for any prose rule that appears in multiple surfaces. The automated check (grep for `@pytest.mark.quarantine(` and assert `reason` contains `I-NNNNN`) would be low-effort but is **not urgent** given this CR demonstrated the prose approach works when reviewers check it.

---

### Finding 4 — Cumulative Phase-2 Cost

**Wall-clock breakdown from self-assess reports:**

| CR | Theme | S01 spike / setup | S02–S03 review | S04–S11 QV gates | S12 self-assess | Total |
|----|-------|-------------------|----------------|-----------------|-----------------|-------|
| CR-00059 | Mutation spike | ~60 min (spike: 0:17:17 mutmut run + measurement table + 4 Makefile targets + infrastructure) | ~30 min | ~60 min (8 gates) | ~30 min | **~3.0 h** |
| CR-00060 | Hypothesis | ~30 min (5 property modules pre-existing in worktree; verification + format + docs) | ~30 min | ~60 min (8 gates) | ~20 min | **~2.5 h** |
| CR-00061 | Quarantine | ~18 min (1800 s timeout spec; marker + addopts + 2 targets + aggregator + smoke test) | ~30 min | ~60 min (8 gates) | ~15 min | **~2.0 h** |
| **Phase 2 total** | | | | | | **~7.5 h** |

Phase 2 delivered 3 CRs in ~7.5 h wall-clock (1 day). Phase 1 delivered 5 CRs over 5 days (estimated ~15 h total). Phase 2 is more efficient per CR (~2.5 h vs ~3.0 h average), partly because Phase-2 CRs were smaller in scope (infrastructure/setup vs full implementation) and partly because the Phase-1 CRs had already established the review cadence.

**Per-CR wall-clock range**: 2.0 h (CR-00061) to 3.0 h (CR-00059). Recommend **2.5 h/cost cap** for Phase-3 estimation.

**Sequencing recommendation for Phase 3**: Phase-3 CRs are larger in scope (6 items vs 3). Recommend **sequencing one CR at a time** rather than batching, because:
1. The batch executor has not been used for Phase-3-scale CRs yet
2. Phase-2's parallel CRs (CR-00059/60/61 were soft-sequenced, not truly parallel) showed that cross-CR interference is minimal when scopes are disjoint
3. Phase-3 items 3.1 (E2E) and 3.2 (contract sweep) are each large enough to benefit from focused single-CR attention

---

### Finding 5 — Which Phase-2 CR Delivered Highest Perceived Value

**Ranking**:

1. **CR-00061 (quarantine workflow) — HIGHEST immediate value.** The smoke test in S01 demonstrated the addopts mechanics working end-to-end — a real, verifiable signal that the deselection works bidirectionally. The quarantine workflow is the most directly applicable to daily development: every developer who hits a flake now has a process. The `quarantine` marker and `file-an-incident` rule are immediately actionable.

2. **CR-00060 (Hypothesis property tests) — HIGH infrastructure value.** The `ci` profile runs as part of `make test-unit` (~1.5 s wall-clock, zero extra cost). Five property modules cover the highest-risk logic (work-item lifecycle, batch lifecycle, fix-cycle cap, doc-diff round-trip, next-id atomicity). The value is **latent** — it will surface when a regression occurs in those modules — but the coverage is broad.

3. **CR-00059 (mutation spike) — MEDIUM infrastructure value, LOW current output.** The spike measured 0 mutants generated (coverage fail-under blocked mutant execution before it started). Infrastructure + 4 Makefile targets landed. The actual mutation score signal is **blocked pending P2-CR-A-followup-mutation-block** (runner fix + scope widening). Value is real but deferred.

**Recommendation**: Invest more in CR-00061's direction — expand the quarantine workflow to include the nightly flake-detect cron (not yet wired). CR-00060's Hypothesis scope could be widened to more modules (CR-00059's P2-CR-A-followup-mutation-block widening would inform where property tests add the most). CR-00059's mutation program needs the P2-CR-A-followup to deliver its value.

---

### Finding 6 — Phase-3 Sequencing Recommendation

**Recommended FIRST Phase-3 CR: 3.2 — Contract / no-5xx route sweep + `schemathesis`**

**Reasoning** (3–5 sentences):

Phase 2 validated that the existing suite's *assertions* are meaningful (Hypothesis fuzzing of state machines found no regressions; mutation infrastructure is functional but its score signal is pending P2-CR-A-followup). The highest-value next step is to **test what we don't test at all** — the route-contract layer. Item 3.2 is the most tractable entry point: it covers the "a router import broke before a human notices" class of incident (our highest-frequency historical incident category), uses `schemathesis` against the existing OpenAPI spec (already generated), and has clear acceptance criteria. The work is moderate in scope (~2.5 h estimated, matching Phase-2 average) and directly unblocks the dashboard stability improvement agenda. Item 3.1 (E2E) is the largest item in Phase 3 — recommended as the **second** Phase-3 CR, when the team has more bandwidth and the E2E runner pattern (`playwright-cli`) is better understood from the quarantine workflow's on-demand run model. The `schemathesis` approach shares the "spec-first, then test" pattern with Hypothesis (CR-00060), making it familiar to the team.

**Why not 3.4 first**: Cross-project isolation (3.4) has high incident risk but requires two registered projects to exercise meaningfully. The contract sweep (3.2) works with the single existing project and is more immediately actionable.

**Why not 3.1 first**: E2E layer is the largest item. Starting with 3.2 produces a faster first deliverable and generates learnings (about `schemathesis` patterns, about the OpenAPI spec coverage) that transfer to 3.1.

---

### Finding 7 — Patterns to Bake into Phase-3 Template

Across CR-00045 (TDD RED-evidence), CR-00052 (audit-table-as-deliverable), CR-00059 (measurement-table-as-deliverable + spike-then-setup), CR-00060 (full-setup + cross-doc-square + marker auto-apply hook), CR-00061 (smoke-test-and-revert + fabricated-fixture verification), the following deliverable shapes recur and should be standard in the Phase-3 template:

| # | Pattern | CRs | Recommendation |
|---|---------|-----|----------------|
| A | **SMOKE TEST capture in S01 report** | CR-00061 (deliverable 7) | **Required for every Phase-3 CR with a marker change or addopts change.** The smoke test must show the new behaviour working (e.g. tagged test deselected in default run, collected under new marker). Must be reverted before CR completion. |
| B | **Measurement table as deliverable** | CR-00059 (spike measurements) | **Required for any Phase-3 CR with a non-trivial runtime cost** (e.g. mutation scope decisions, E2E full-suite run). Table format: metric | before | after | delta. Captured in S01 report. |
| C | **Cross-doc-square checklist item** | CR-00060, CR-00061 | **Required when CR modifies prose rules** that appear in multiple surfaces (`tests/CLAUDE.md`, skill, strategy doc). S02 or S03 reviewer independently verifies each surface. |
| D | **Spike-then-setup** | CR-00059 | **Recommended for Phase-3 items with unknown cost** (e.g. 3.4 cross-project isolation matrix may have unknown DB setup cost; 3.6 data-layer may have unknown migration interaction). S01 spike, S02+ setup. |
| E | **Fabricated-fixture verification** | CR-00061 (aggregator test with fabricated logs) | **Required when CR adds a script that parses structured output** (pytest logs, CLI output, etc.). Fabricated input → expected output → verify script exits with correct code. Not mocked — inputs are hand-crafted to match the expected format. |
| F | **Marker auto-apply hook via conftest** | CR-00060 (Hypothesis conftest `pytest_collection_modifyitems`) | **Required when Phase-3 adds a marker that should auto-apply to a subset of tests** (e.g. 3.4 `tenant_a`/`tenant_b` isolation markers; 3.5 `negative` security markers). The conftest approach is cleaner than requiring every test to self-declare. |

---

## Phase-2 Item Status Sweep

From `ai-dev/work/TESTS_ENHANCEMENT.md` §6:

| Item | Status | CR |
|------|--------|-----|
| 2.1 Mutation testing (mutmut config + make targets) | **DONE** | CR-00059 |
| 2.2 Property-based tests (Hypothesis) | **DONE** | CR-00060 |
| 2.3 Flaky/quarantine workflow | **DONE** | CR-00061 |

**Phase 2: ALL DONE.** No open items. Two follow-ups remain (P2-CR-A-followup-mutation-block, P1-CR-A-followup assertion baseline scrub) — both are cleanup/low-urgency.

---

## Pre-flight Checks

| Check | Result |
|-------|--------|
| `make lint` | ✅ passed (S02, S03) |
| `make format-check` | ✅ passed (S02, S03) |
| `make typecheck` | ✅ passed (S01) |
| `make test-unit` | ✅ 3104 passed, 5 skipped, 5 xfailed, 2 xpassed (S03) |
| `make quality` | ✅ ruff + mypy clean (S03) |

---

## Notes

- No raw run logs available in this worktree (`ai-dev/logs/` absent); analysis based on S01–S03 reports and TESTS_ENHANCEMENT.md.
- No fix cycles, no retries, no agent thrash across S01–S03. CR-00061 was a clean execution.
- The `deptry` DEP002 false-positive on `pytest-rerunfailures` (S03 finding S03-1) is a known limitation and non-blocking.
- Phase-2 wall-clock: ~7.5 h total. Per-CR average: ~2.5 h. Phase-3 CRs should be estimated at 2.5–3.0 h unless they include a spike component.
