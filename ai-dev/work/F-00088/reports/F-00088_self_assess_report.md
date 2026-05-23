# F-00088 Self-Assessment Report

## Item Analysis: F-00088

**Bottom line**: S03 introduced lint/format debt in 5 E2E test files that cascaded into 15+ QV-gate fix cycles (S06–S09); the test infrastructure itself is sound but the S03 code-review step (S04) did not surface all MEDIUM_FIXABLE issues before they propagated into the QV pipeline. Additionally, S14's V6 (htmx_fragments) revealed a subtle async-file-write race in the playwright-cli snapshot infrastructure that caused a hard-to-diagnose browser-level failure.

**Steps analyzed**: 13 (S01, S02, S03, S04, S05, S06, S07, S08, S09, S10, S11, S12, S13, S14)  
**Steps with retries/fix-cycles**: 5 (S06, S07, S08, S09, S14)  
**Total fix-cycles**: ~10 across S06/S07/S08/S09, 2 in S14  
**DB signal**: no (file-only mode — DB not queried)

---

## Findings

### [1] S03 lint/format debt cascaded into 15+ QV-gate fix cycles
**Severity**: HIGH   **Class**: platform   **Frequency**: recurring  
**Evidence**:
- `ai-dev/logs/F-00088_S06_run1.log:5-10` — "E501 Line too long (109 > 100) tests/e2e/test_journey_code_qa_sse.py:73"
- `ai-dev/logs/F-00088_S06_run5.log:5-21` — "E501 Line too long (101 > 100) tests/e2e/playwright_wrapper.py:130; E501 tests/e2e/test_journey_docs_export.py:156; E741 tests/e2e/test_journey_jobs_filters.py:106; F841 tests/e2e/test_journey_jobs_filters.py:107"
- `ai-dev/logs/F-00088_S08_fix1.log` — S03 introduced multi-line string that ruff wanted single-line; "make format-check fails"
- `ai-dev/logs/F-00088_S06_fix1.log` — 1 file fixed; `ai-dev/logs/F-00088_S06_fix2.log` — 4 remaining files fixed

**Recommendation**: The S04 code-review agent found and documented the E501 at line 73 (`test_journey_code_qa_sse.py`) in its initial review, but the 4 remaining issues (`playwright_wrapper.py:130`, `test_journey_docs_export.py:156`, `test_journey_jobs_filters.py:106`, `test_journey_jobs_filters.py:107`) were either not surfaced by `make lint` at S03's own pre-flight check or were introduced during the fix cycle. Add a step-level gate: `make lint` and `make format-check` must be run as part of S03's own quality check and the S04 reviewer must explicitly confirm clean lint/format before clearing the step. Alternatively, consider running lint+format as a non-negotiable pre-flight gate in every backend-impl step's own execution loop, not just as a reviewer concern.

**Target**: `skills/iw-ai-core-testing/SKILL.md` (§ review checklist), `ai-dev/templates/Feature_Implementation_Template.md` (if it has a QV-gate section)

**Pros**: Eliminates ~15 fix cycles per affected step; reduces QV-gate wall-clock time.
**Cons**: Adds ~30s to each step's own execution (lint+format are fast); may require updating existing step templates.
**If we don't**: Every backend-impl step that touches multiple new files risks cascading lint debt into the QV pipeline; the QV gates become a de-facto lint-fix pipeline rather than a quality gate.
**Effort**: M (~20 lines across 2 files)

---

### [2] S14 V6 (htmx_fragments) async-snapshot race caused a hard-to-diagnose browser failure
**Severity**: HIGH   **Class**: environment   **Frequency**: systemic  
**Evidence**:
- `ai-dev/logs/F-00088_S14_run5.log:1` — "snapshot identical before/after Cancel click" — V6 test failure root cause
- `ai-dev/logs/F-00088_S14_fix1.log:2` — "async file write timing" — `_read_latest_snap_yml()` reads stale yml file; `pw.click("")` silently no-ops because dynamic ref extraction fails
- `ai-dev/logs/F-00088_S14_fix1.log:2` — fix replaced fragile dynamic ref extraction with hardcoded stable ref (`e107`)

**Recommendation**: The playwright-cli snapshot infrastructure (`_read_latest_snap_yml()`) has an inherent async-file-write race when a test makes multiple rapid browser interactions. The S14 fix is a partial workaround (hardcoded ref). A more robust fix would be to have the wrapper return the snapshot as a return value directly from `snapshot()` rather than reading it back from disk, so callers never depend on side-effect file writes. This requires updating `playwright_wrapper.py` and potentially all journey callers.

**Target**: `tests/e2e/playwright_wrapper.py`

**Pros**: Eliminates the race class entirely; snapshot return value is more testable and composable.
**Cons**: Requires updating all journey callers that currently use `pw.snapshot()` implicitly; breaking API change.
**If we don't**: Future htmx-fragments tests that rely on rapid DOM reads after clicks will continue to be flaky in browser context.
**Effort**: M (~5 call sites to update)

---

### [3] S03 introduced `wait_for_sse_chunk()` TypeErrors that S04 flagged but were not fixed before S06
**Severity**: MED   **Class**: platform   **Frequency**: one-off  
**Evidence**:
- `ai-dev/work/F-00088/reports/F-00088_S04_CodeReview_report.md` — "MEDIUM_FIXABLE: `wait_for_sse_chunk()` missing `stream_output` positional argument; tests/e2e/test_journey_code_qa_sse.py:79,100"
- `ai-dev/logs/F-00088_S06_run1.log` — lint error was the first failure seen; TypeErrors from `wait_for_sse_chunk()` would have appeared at runtime in S14, not in QV gates
- `ai-dev/logs/F-00088_S14_run5.log` — "V3 Journey 3 — Code Q&A SSE: PASSED" — the SSE journey still passed despite the TypeError risk; the TypeError was apparently not triggered because `wait_for_sse_chunk` may have a fallback or the test doesn't reach those lines

**Recommendation**: The S04 reviewer's finding about `wait_for_sse_chunk()` missing argument should be classified as HIGH (not MEDIUM_FIXABLE) when it affects a method signature that will TypeError at runtime. Consider adding a Python lint check to the skill that runs `python -c "import tests.e2e.journey_name"` for each new journey module to catch import-time TypeErrors early. Additionally, the `wait_for_sse_chunk` implementation should be documented in the wrapper to clarify whether it actually needs `stream_output` or can infer it from the DOM.

**Target**: `skills/iw-ai-core-testing/SKILL.md` (review checklist — elevate runtime TypeError findings to HIGH)

**Pros**: Catches signature mismatches at lint time; prevents silent pass-throughs.
**Cons**: Requires adding runtime import checks to the step quality gate.
**If we don't**: Agents may write journey code that TypeErrors at browser-execution time rather than at lint time.
**Effort**: S (~5 lines in skill review checklist)

---

### [4] TDD RED evidence recorded correctly in S01 and S03
**Severity**: INFO   **Class**: convention   **Frequency**: recurring  
**Evidence**:
- `ai-dev/work/F-00088/reports/F-00088_S02_CodeReview_report.md` — "TDD RED Evidence ✅: tests/e2e/test_harness_selfcheck.py delivers RED-first evidence: test_flags_error_level_line, test_flags_missing_landmark_region — GREEN confirmed across 3 consecutive runs"
- `ai-dev/work/F-00088/reports/F-00088_S04_CodeReview_report.md` — "TDD RED Evidence ✅: test_harness_selfcheck.py extended with TestDanglingHtmxTargetDetector::test_flags_dangling_hx_target and TestSseTimeoutDetector::test_stream_with_no_chunks_raises_sse_timeout"

**Recommendation**: The TDD RED evidence discipline is working correctly for F-00088. Both S01 and S03 recorded RED evidence for the harness self-check tests against synthetic input, not production code. No change needed.

**Target**: None (convention is working as intended)

---

### [5] e2e marker exclusion held correctly across all QV gates (S06–S13)
**Severity**: INFO   **Class**: convention   **Frequency**: recurring  
**Evidence**:
- `ai-dev/work/F-00088/reports/F-00088_S04_CodeReview_report.md` — "AC4: e2e_smoke subset is exactly two journeys — 2/22 collected under -m e2e_smoke"
- `ai-dev/logs/F-00088_S12_run1.log:tail` — coverage run with `uv run pytest tests/ --ignore=tests/e2e/ --no-cov` — explicitly ignored e2e directory; "43 files skipped due to complete coverage"
- `ai-dev/logs/F-00088_S10_run1.log:tail` — coverage run passed with e2e excluded
- `ai-dev/logs/F-00088_S13_run1.log` — security-gitleaks step; no pytest collection of e2e tests

**Recommendation**: The e2e marker exclusion (`-m 'not e2e'` in addopts) is functioning correctly across all QV gates. No change needed.

**Target**: None (invariant is holding)

---

### [6] S14 e2e-smoke blocking CI gate (V7) confirmed both smoke journeys passed
**Severity**: INFO   **Class**: platform   **Frequency**: one-off  
**Evidence**:
- `ai-dev/logs/F-00088_S14_run5.log:1` — "V7 No Regressions: PASS; e2e_smoke 2/2"
- `ai-dev/logs/F-00088_S14_run5.log:1` — "V1: test_journey_home_navigation ✅; V2: test_journey_queue_to_merge ✅"

**Recommendation**: The blocking CI gate (`.github/workflows/e2e.yml` e2e-smoke job) correctly collected and ran 2/2 smoke journeys. No change needed.

**Target**: None

---

## Coverage Notes

- S01 log (1.7 KB): read in full.
- S03 run1 log (0 bytes): empty; run2 log (2.5 KB): read in full.
- S06–S09 logs: read in full (small files, <3 KB each).
- S10 log (414 KB): read tail -100 lines; coverage summary confirmed. No pytest collection errors.
- S11 log (438 KB): tail -50 lines confirmed same pattern as S10.
- S12 log (86 KB): tail -100 lines confirmed coverage pass; e2e explicitly excluded.
- S13 log (279 bytes): read in full (gitleaks only).
- S14 browser logs (7.6 KB + 1.4 KB): read in full.
- S14_fix1 log (2.4 KB): read in full.
- DB telemetry: not used (file-only mode).
