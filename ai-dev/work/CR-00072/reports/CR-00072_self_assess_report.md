### CR-00072 Self-Assessment — S12

**Work item**: CR-00072 — Contract / No-5xx Route Sweep + schemathesis Fuzzing
**Step**: S12 (self-assess-impl)
**Date**: 2026-05-22
**DB signal**: yes (DB:UP throughout execution)

---

## Bottom line

CR-00072 executed cleanly — 11 of 12 steps passed on the first run with no
thrashing, no tool failures, and no scope discipline issues. The only fix cycle
(S11 security-secrets, one pass) was a legitimate gitleaks false positive on an
RFC 6761 reserved domain (`example.local`) in `.env`, not a harness bug. The
new contract test layer is well-designed and the `contract_fuzz` marker
exclusion held correctly. No process improvements are warranted.

---

## Execution summary

| Step | Agent | Status | Fix cycles | Notes |
|------|-------|--------|------------|-------|
| S01  | backend-impl   | completed | 0 | All tests written, deliberate-break TDD demonstrated |
| S02  | code-review-impl | completed | 0 | All ACs verified, scope clean |
| S03  | code-review-final-impl | completed | 0 | Unit + integration suites green |
| S04  | qv-gate (lint)         | completed | 0 | |
| S05  | qv-gate (assertions)   | completed | 0 | |
| S06  | qv-gate (format)       | completed | 0 | |
| S07  | qv-gate (typecheck)    | completed | 0 | |
| S08  | qv-gate (unit-tests)   | completed | 0 | |
| S09  | qv-gate (integration-tests) | completed | 0 | Route sweep ran here; no latent failures surfaced |
| S10  | qv-gate (diff-coverage)| completed | 0 | |
| S11  | qv-gate (security-secrets) | completed | 1 | gitleaks false positive on `example.local` — fix cycle resolved it |
| S12  | self-assess-impl | in_progress | 0 | |

**Steps analyzed**: 12   **Steps with retries**: 0   **Total fix-cycles**: 1   **DB signal**: yes

---

## No findings promoted

No finding appeared in ≥2 steps, and no finding was HIGH-severity in a single
step. The item ran cleanly.

---

## Notable observations (informational — no action required)

### TDD RED evidence — S01 recorded deliberate-break demonstrations correctly

Both new test files demonstrated they could fail:
- **Route sweep**: a throwaway `GET /__cr72_selfcheck__` handler raising
  `RuntimeError` was registered on the test app; the sweep picked it up and
  the parametrized case failed (`assert 500 < 500`). Throwaway route removed.
- **schemathesis**: a throwaway `GET /__cr72_jsonfuzz__` route raising
  `RuntimeError` was added; schemathesis reported `not_a_server_error` violation.
  Throwaway route removed.
- `git diff origin/main -- dashboard/ orch/` is empty — no throwaway route
  remains, and no production code was touched. ✅ Confirmed in S02 and S03.

### `EXPECTED_5XX` allowlist — small, correctly scoped

- **Route sweep `EXPECTED_5XX`**: 1 entry (`GET /project/{project_id}/docs/{doc_id}/pdf`
  → 500, `docs_pdf()` unhandled `PermissionError` on optional cache write).
- **schemathesis `KNOWN_CONTRACT_5XX`**: 2 entries (keep-alive slot endpoints
  → BIGINT-overflow on out-of-range `slot_id` path param).
- All three are genuine pre-existing handler bugs, not harness artefacts. Each
  carries a `TODO(file-incident)` placeholder. The operator should file three
  Incidents on `main` post-merge — see the S01 report's "Operator follow-up"
  section.
- The allowlist is small (1 + 2 = 3) relative to the 123 GET/HEAD routes swept.
  The route table is not substantially more broken than expected.

### `contract_fuzz` marker exclusion — held first time

The `contract_fuzz` marker was registered in `pyproject.toml` (already present)
and excluded from the default `addopts -m '... and not contract_fuzz'`. S02
independently verified the exclusion via `--collect-only`: 2 tests deselected on
default collection. No `diff-coverage` or `unit-tests` QV gate accidentally
collected the fuzzer. ✅

### S09 (integration-tests) — no latent failure burn-in

S09 ran `make test-integration` (1143s), which collected the new route sweep
automatically (it lives under `tests/dashboard/`). It passed on the first run
— no latent route failures burned extra cycles. This is the expected outcome:
the route sweep was written by the same agent that owned the implementation, so
harness artefacts (seed data gaps, unresolved parameter patterns) were caught
before the QV gate. A future CR where a different agent writes the sweep against
an evolving route table may see S09 fix cycles — that is when the latent-failure
burn-in pattern becomes relevant.

### S11 fix cycle — gitleaks false positive on `example.local`

- **Run 1 (S11_run1.log)**: gitleaks exit=2, `WRN leaks found: 1`. Root cause:
  `.env` contains `e2e_user: dev@example.local` (placeholder string used in
  browser E2E tests). gitleaks matched `iw-internal-email` (detected
  `dev@example.local`) and `iw-internal-fqdn` (detected `example.local`) — both
  false positives on RFC 6761 reserved domains.
- **Fix cycle (S11_fix1.log)**: agent added `local` to the existing
  `(?i)example\.(com|org|net|invalid|local)` regex in `.gitleaks.toml`. Minimal,
  correct fix.
- **Run 4 (S11_run4.log)**: exit=0, `no leaks found`. ✅

The `.gitleaks.toml` `regexes` section already had `example\.(com|org|net|invalid)`
but had not included the `.local` TLD variant. The agent correctly identified the
gap and extended the existing pattern. This is a single-occurrence false positive
from a pre-existing gap in the allowlist — informational only, no process change
needed.

---

## Coverage notes

- S01_run1.log: 0 bytes — agent did not log to the run log; S01_run4.log
  contains the summary. The actual agent execution log is in the worktree's
  per-step log (not available from the orchestrator perspective in this
  environment). All evidence is drawn from the step-summary log files in
  `ai-dev/logs/`.
- S02, S03: small summary logs (1.9 KB, 2 KB) — full summaries present.
- S08 (unit-tests): 414 KB — used `tail -500` sampling; no errors found.
- S09 (integration-tests): 431 KB — used `tail -500` sampling; coverage report
  tail confirmed pass.
- S10 (diff-coverage): 86 KB — tail confirmed pass.
- S11 fix log: 807 bytes — fix summary present.