# CR-00075 Self-Assessment — Process Analysis

**Work Item**: CR-00075 — Security Test Module
**Step**: S12 (SelfAssess)
**Date**: 2026-05-22

---

## Item Analysis: CR-00075

Bottom line: CR-00075 executed cleanly — all 12 steps completed without fix cycles, thrash, or genuine vulnerabilities. The main process concern is that three of the four S01 runs were consumed correcting inherited defects rather than writing new code, suggesting the design-doc for a test-only CR needs stronger discipline on what the agent must NOT inherit from prior attempts.

Steps analyzed: 12   Steps with retries: 0   Total fix-cycles: 0   DB signal: yes

---

## Execution Summary

CR-00075 implemented four security regression test modules (85 tests) under `tests/integration/security/`:

| Module | Tests | Guard covered |
|--------|------:|---------------|
| `test_live_db_write_guard.py` | 11 | I-00041 live-DB write guard (raises `LiveDbConnectionRefusedError`) |
| `test_authz_negative_paths.py` | 18 | Project-scoping authz boundary (4xx, cross-project isolation) |
| `test_doc_render_ssrf_path_traversal.py` | 49 | `DocService._is_ssrf_blocked()`, `validate_links()`, doc-section functions |
| `test_agent_context_env_handling.py` | 7 | `IW_CORE_AGENT_CONTEXT` blocks operator commands + engine creation |

All QV gates passed (S04–S11): lint, assertions, format, typecheck, unit tests, integration tests (2966 passed), diff-coverage, secrets scanning.

**No genuine vulnerabilities found.** No xfailed tests, no SECURITY BLOCKER, no production code edited.

---

## TDD RED Evidence

All four deliberate-break demonstrations were performed and reverted:

1. **Live-DB guard** — `is_live_db_url() → False` patch → 5 tests failed (`DID NOT RAISE`). Reverted.
2. **Doc-render SSRF** — `DocService._is_ssrf_blocked() → False` patch → 26 tests failed. Reverted.
3. **Authz** — removed `project_id` filter → project B's item reachable from project A's URL (assert `200 == 404`). Reverted.
4. **Agent-context** — disabled `IW_CORE_AGENT_CONTEXT` check → 3 tests failed. Reverted.

`grep -rn "DELIBERATE-BREAK" over orch/ dashboard/ tests/` → nothing. `git status` clean after every revert. Confirmed by S02 and S03 independently.

---

## QV Gate Stability

| Gate | Result | Duration |
|------|--------|----------|
| S04 lint | PASS | ~0s |
| S05 assertions | PASS | ~0s |
| S06 format-check | PASS | ~0s |
| S07 typecheck | PASS | ~0s |
| S08 unit-tests | PASS | 5m15s (52.58% coverage, above 50% threshold) |
| S09 integration-tests | PASS | 18m14s (63.63% coverage, above 50% threshold) |
| S10 diff-coverage | PASS | 5m46s (no new lines in diff — test-only CR) |
| S11 security-secrets | PASS | <1s |

S09 passed on first attempt with no fix cycles. The integration-tests gate (S09) did not need any latent failure remediation — the security tests ran cleanly alongside the full suite.

---

## Findings

### [1] Three of four S01 runs corrected inherited defects, not code

Severity: **MED**   Class: process   Frequency: systemic

Evidence:
- `ai-dev/logs/CR-00075_S01_run1.log` — empty (run 1 produced no output, superseded)
- `ai-dev/logs/CR-00075_S01_run2.log` — empty (run 2 superseded)
- `ai-dev/active/CR-00075/reports/CR-00075_S01_Backend_report.md:41` — "corrected two defects inherited from earlier S01 attempts: (1) reverted `tests/assertion_free_baseline.txt` (a prior run had baseline-exempted 17 security tests as no-assert/tautology — defeating the scanner); (2) rewrote `test_authz_negative_paths.py` (prior version used stale chat endpoint paths with a tautological assertion)"

Recommendation: Strengthen the S01 prompt for test-only CRs with a directive: *"Inspect `tests/assertion_free_baseline.txt` against `origin/main` and revert any unintended exemptions before writing new tests. Inspect existing security test files in `tests/integration/security/` for stale paths or tautological assertions before writing replacements."*

Target: `prompts/CR-00075_S01_Backend_prompt.md`

Pros: Eliminates wasted S01 runs on defect correction; agent starts from a clean baseline.
Cons: Requires the design-doc generator to emit this directive for test-only CRs.
If we don't: Future S01 agents repeat the defect-correction loop, burning runs without producing new tests.
Effort: S (~3 bullet additions)

---

### [2] Operator confusion recurs: `test-security-module` vs. scanner targets

Severity: **MED**   Class: convention   Frequency: systemic

Evidence:
- `ai-dev/active/CR-00075/reports/CR-00075_S01_Backend_report.md:55` — "comment block explicitly distinguishes it (asserted pytest tests) from `make security-secrets` (gitleaks) and `make security-sast` (Semgrep/bandit) advisory scanners"
- `ai-dev/active/CR-00075/reports/CR-00075_S02_CodeReview_report.md:94` — "Makefile comment distinguishing from scanners" ✅ — flagged as recurring so it gets surfaced to CLAUDE.md

Recommendation: CR-00075's Makefile comment block is correct, but this confusion has appeared before. Add a brief inline reminder in CLAUDE.md's "Common Commands" table entry for `make test-security-module`: *"(asserted pytest — not the same as `make security-secrets` / `make security-sast` advisory scanners)"*.

Target: `CLAUDE.md`

Pros: High visibility, one-line fix, cheap to implement.
Cons: One additional line in a table that is already long.
If we don't: Operators continue to confuse asserted security tests with advisory scanners; the distinction is important because asserted tests block merge while scanner findings are informational.
Effort: S (~1 line addition)

---

## Security Outcome

No genuine vulnerabilities were discovered during CR-00075's execution. All four security guards passed all assertions on current `main`:

- `is_live_db_url()` correctly refuses the live orch DB URL in both test and agent contexts
- `_is_ssrf_blocked()` blocks all tested internal hosts and `file://` URLs
- `validate_links()` reports internal URLs as `blocked_ssrf` without fetching them
- `IW_CORE_AGENT_CONTEXT=true` blocks `iw migrations apply` and live-DB engine creation

No `xfail`, no `TODO(file-incident)`, no SECURITY BLOCKER, no production fix applied.

---

## What went right

- **Strict scope discipline**: zero production code touched (verified by S02 and S03 independently)
- **Correct TDD demonstrations**: all four modules proven to fail when their guard is removed, reverted cleanly
- **No xfailed tests**: all 85 tests pass without workarounds
- **Baseline file preserved**: the assertion-free baseline was reverted to `origin/main` rather than exempted — the scanner's integrity maintained
- **Skill sync confirmed**: `.claude/skills/` copy byte-identical to master (confirmed by `diff`)
- **S09 integration-tests clean**: no latent security failures surfaced in the full suite run; security modules ran alongside 2966 other tests without interference

---

## Notes on coverage

- `make test-unit` (S08): 52.58% coverage — above the 50% threshold. Unit suite passed.
- `make test-integration` (S09): 63.63% coverage — above the 50% threshold. Integration suite passed.
- `make diff-coverage` (S10): "No lines with coverage information in this diff" — expected for a test-only CR with no production code changes. Gate passed (90% of 0 lines = 0 required).
- The three xfailed tests and three xpassed tests in the integration run are pre-existing (not introduced by CR-00075).