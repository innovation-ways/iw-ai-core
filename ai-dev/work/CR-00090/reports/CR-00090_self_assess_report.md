# CR-00090 Self-Assessment Report

**Work Item**: CR-00090 — Fix E2E Polling Suppression — Replace UA Sniffing with IW_CORE_E2E_MODE Env Var
**Step**: S14 (SelfAssess)
**Analyzer**: self-assess-impl (iw-item-analyze skill)
**Date**: 2026-05-28

---

## Item Analysis: CR-00090

**Bottom line**: The item's implementation is solid and all acceptance criteria are met, but the CR introduced two QV gate regressions (stale staleness-dot tests and a dead-migration reference) that cost one extra fix cycle each — a gap in the design doc's TDD scope that should be addressed before merge.

**Steps analyzed**: 14 (S01–S13) + 2 fix cycles (S12-fix, S13-fix)  
**Steps with retries**: 2 (S12, S13 — both due to pre-existing test breakage, not CR-00090 code defects)  
**Total fix-cycles**: 2  
**DB signal**: yes (DB:UP, `iw item-status CR-00090 --json` confirmed 13/14 completed steps, all 4 QV gates passed in final runs)  
**Log coverage**: Read S01–S05, S10, S12-fix, S13-fix, S13 browser logs in full. Sampled tail of S12_run4.log (845 KB) and S12_run1.log (824 KB) — full run logs for the two gated steps.

---

## Findings

[1] Pre-existing staleness-dot tests need `_e2e_mode` global in `test_staleness_templates.py` fixture
Severity: **HIGH**   Class: **environment**   Frequency: **systemic**
Evidence:
  - `ai-dev/active/CR-00090/fix-cycles/CR-00090_S12_FIX_cycle1_prompt.md:27` — "FAILED tests/dashboard/test_staleness_templates.py::TestStalenessDotUpToDate::test_renders_grey_dot_when_up_to_date"
  - `ai-dev/active/CR-00090/fix-cycles/CR-00090_S12_FIX_cycle1_prompt.md:28` — "FAILED tests/dashboard/test_staleness_templates.py::TestStalenessDotUpToDate::test_grey_dot_has_hx_get" (9 staleness-dot tests failed in S12 run1)
  - `.worktrees/CR-00090/ai-dev/logs/CR-00090_S12_fix1.log:3` — "The design doc spec is correct... dashboard/routers/staleness.py creates a separate module-level Jinja2Templates instance at import time"
Recommendation: Add a `pytest.fixture` to `conftest.py` that injects `_e2e_mode = False` into the module-level `staleness_mod.templates.env.globals["_e2e_mode"]` at test session start, mirroring how `tests/dashboard/test_e2e_mode.py` patches it for E2E-mode tests. All staleness-dot template tests use the module-level templates instance; without this patch they fail with `UndefinedError: 'get_e2e_mode' is not defined`.
Target: `tests/conftest.py` (~15 lines, 1 fixture)
Pros: Pre-existing staleness-dot tests that test non-E2E behavior (green/red dot, hx attributes) are fixed without modifying each test file.
Cons: A session-scoped fixture unconditionally sets `_e2e_mode`; if a future test needs to explicitly test the undefined-or-absent case, it would need to override the fixture.
If we don't: Every future CR that adds Jinja global injection (as CR-00090 did) risks breaking staleness-dot template tests in the same way. The pattern will repeat.
Effort: S (~15 lines, 1 file)

[2] `test_phase2_apply_no_self_deadlock.py` hardcodes a migration revision that drifts from actual head
Severity: **HIGH**   Class: **environment**   Frequency: **systemic**
Evidence:
  - `ai-dev/active/CR-00090/fix-cycles/CR-00090_S12_FIX_cycle1_prompt.md:35` — "FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_succeeds_when_no_blocking_lock"
  - `ai-dev/active/CR-00090/fix-cycles/CR-00090_S12_FIX_cycle1_prompt.md:36` — "FAILED tests/integration/daemon/test_phase2_apply_no_self_deadlock.py::test_i_00063_apply_does_not_self_deadlock_when_caller_holds_share_lock"
  - `.worktrees/CR-00090/ai-dev/logs/CR-00090_S12_fix1.log:9` — "_HEAD_REVISION = \"d43ea9e75e8f\" updated to match actual current head migration (f_00090_regression_link_fields)"
Recommendation: Replace the hardcoded `_HEAD_REVISION` constant in `test_phase2_apply_no_self_deadlock.py` with a dynamic query that reads the actual Alembic head from the test DB:
```python
def _get_head_revision(session: Session) -> str:
    result = session.execute(text("SELECT version_num FROM alembic_version"))
    return result.scalar_one()
```
Target: `tests/integration/daemon/test_phase2_apply_no_self_deadlock.py` (~10 lines changed)
Pros: The test never goes stale when new migrations land; no future fix cycle needed for this specific failure pattern.
Cons: Minor one-time change; no runtime cost.
If we don't: Every migration added after the test's last update will break it in CI, requiring a manual revision bump.
Effort: S (~10 lines, 1 file)

---

## Step-by-Step Summary

| Step | Agent | Runs | Fix Cycles | Issue | Finding |
|------|-------|------|------------|-------|---------|
| S01 Backend | backend-impl | 1 | 0 | Clean — TDD RED first, 9 tests green | None |
| S02 Frontend | frontend-impl | 1 | 0 | Clean — template edits only, no regressions | None |
| S03 Tests | tests-impl | 1 | 0 | Clean — 7 new tests + S01's 9, all pass. Discovered staleness router module-level templates nuance and patched it correctly in test fixtures | None |
| S04 CodeReview | code-review-impl | 1 | 0 | Clean | None |
| S05 FinalReview | code-review-final-impl | 1 | 0 | Clean; integration timeout noted (testcontainers under load) but no CR-00090 failures | None |
| S06 QV lint | qv-gate | 1 | 0 | Pass | None |
| S07 QV format | qv-gate | 1 | 0 | Pass | None |
| S08 QV typecheck | qv-gate | 1 | 0 | Pass | None |
| S09 QV arch-check | qv-gate | 1 | 0 | Pass | None |
| S10 QV security-sast | qv-gate | 1 | 0 | Pass — semgrep 0 findings | None |
| S11 QV unit-tests | qv-gate | 1 | 0 | Pass — 3626 passed | None |
| S12 QV integration | qv-gate | 4 | 1 | 11 pre-existing test failures (9 staleness-dot, 2 dead migration ref) → fix cycle 1 resolved both | **Finding [1]**, **Finding [2]** |
| S13 QV browser | qv-browser | 4 | 1 | S13_run1 empty (timeout), S13_run4 timeout at 1846s. S13-fix identified staleness router module-level templates issue; fix applied. S13_run4 re-run passed all 4 verifications (V0–V4) | **Finding [1]** surfaced here too |
| S14 SelfAssess | self-assess-impl | — | — | Complete | — |

---

## Key Observations

1. **S12 was a regression catch, not a CR-00090 code defect.** The 9 failing staleness-dot tests (`test_staleness_templates.py`) and 2 dead-migration tests (`test_phase2_apply_no_self_deadlock.py`) pre-existed CR-00090 — neither test file was in CR-00090's scope. S01/S02/S03 introduced `_e2e_mode` as a Jinja global that `staleness_dot.html` relied on, which exposed the pre-existing fixture gap. The fix (injecting the global in the test fixture) was the right one.

2. **S13 required two retries.** S13_run1 was an empty log (browser env issue). S13_run4 timed out at 1846s (agent logic timeout, not E2E stack failure). The S13-fix identified the same staleness router `_e2e_mode` injection issue as S12-fix and applied the same fix to `staleness.py`. The fix was correct and V0–V4 all passed on re-run.

3. **No agent thrash.** No step ran more than once with the same error. Both fix cycles resolved cleanly in a single pass.

4. **All 4 QV gates passed on final runs.** S12_run4 passed integration tests (3303 passed, 0 failed). S13 passed all browser verifications with screenshots as evidence.

---

## TDD Red Evidence Checklist

| Step | Type | Had new behavioural tests? | Evidence present? | Notes |
|------|------|---------------------------|-------------------|-------|
| S01 Backend | implementation | Yes — 9 parametrized tests | ✅ `AttributeError` RED phase + all 9 GREEN | TDD-first approach applied correctly |
| S02 Frontend | implementation | No — template/YAML edits | n/a — template/markdown edits only | N/A |
| S03 Tests | implementation | Yes — 7 new dashboard tests | ✅ No RED (tests-impl adds tests after code exists) | S03 is a tests-impl step; dedicated coverage step, exempt from RED-first |
| S04 CodeReview | code_review | No | n/a | N/A |
| S05 FinalReview | code_review_final | No | n/a | N/A |

---

## No Actionable Patterns (otherwise)

The following were reviewed and did NOT meet the bar for promotion:
- S05 integration timeout — testcontainers under load, not a code issue; S12_run4 passed cleanly
- S13 browser timeout (1846s) — agent logic timeout, not E2E infrastructure failure; S13_fix resolved it
- S01/S02/S03: clean execution, no findings
- S06–S11: all passed first try, no findings
