# CR-00062 — S09 Cross-Agent Final Review Fix Report

**Step**: S09 — Apply CRITICAL/HIGH cross-cutting findings from S08
**Agent**: code-review-fix-final-impl
**Completion**: complete
**Date**: 2026-05-19

## Summary

S08 reported **zero CRITICAL, zero HIGH, zero MEDIUM** cross-cutting findings.
Only one **LOW** advisory finding (FF1) was raised, explicitly tagged as
non-blocking ("S09 may or may not address it"; "Advisory only — same pattern
as F-00081"). Per S09's mandate (apply CRITICAL and HIGH only), no code edits
are required.

S09 therefore reduces to a re-verification pass:

1. Re-run preflight gates against the working tree (format / lint / typecheck).
2. Re-run targeted unit tests + the integration test referenced in the step
   instructions.
3. Re-tick AC coverage (all six ACs remain satisfied — nothing in S09 changed
   the diff so the S08 evidence still applies).
4. File FF1 as a follow-up (not addressed in this CR).

## Findings addressed

| ID | Severity | Status | Notes |
|----|----------|--------|-------|
| FF1 | LOW | deferred | `_VALID_CLI_TOOLS` is not referenced by any dispatch site. Existing pattern (explicit `raise ValueError` per dispatch helper) matches F-00081's pattern and is acceptable. Filed as follow-up; out of S09 scope (which is CRITICAL/HIGH only). |

No CRITICAL or HIGH findings existed to fix.

## Files changed

Only the report file itself:

- `ai-dev/active/CR-00062/reports/CR-00062_S09_CodeReviewFixFinal_report.md` (new)

No source files were modified in S09. (The full set of working-tree changes
from S01..S07 is unchanged — `git diff HEAD --name-only` returns the same
set S08 reviewed.)

## Re-verification results

### Preflight gates

| Gate | Command | Result |
|------|---------|--------|
| Format | `make format` | ok — `776 files already formatted` |
| Lint | `make lint` | ok — `All checks passed!` (ruff + check_templates.py) |
| Typecheck | `make typecheck` | ok — `Success: no issues found in 257 source files` |

### Migration-check

Not re-run in S09. S09 did not touch `orch/db/migrations/versions/6d78323d0954_add_pi_runtime_options.py`
or `orch/db/models.py`. S02 reported `3 passed in 9.09s` (round-trip + create_all
parity + head-from-empty) and S08 confirmed S07's diff did not touch the
migration. `make migration-check` will run again at S13 as the final gate.

### Targeted unit subset (S08's set, re-run)

```
$ uv run pytest tests/unit/test_pi_runtime_dispatch.py \
                tests/unit/test_sync_agents_pi.py \
                tests/unit/test_project_registry_allowlist.py \
                tests/unit/test_batch_manager.py \
                tests/unit/test_doc_job_poller.py --no-cov
collected 96 items
============================== 96 passed in 0.42s ==============================
```

### Integration test (named in step instructions)

```
$ uv run pytest tests/integration/test_pi_dispatch_end_to_end.py --no-cov
collected 6 items
============================== 6 passed in 6.04s ===============================
```

Total: **102 passed, 0 failed**.

## Acceptance Criteria re-tick

S08 marked all six ACs as **satisfied** at the cross-agent-review boundary.
S09 made no code changes, so the evidence chain still holds. Re-stating for
the record:

| AC | Status | Notes |
|----|--------|-------|
| AC1 — pi dispatches end-to-end through 8 sites | satisfied | 19 dispatch unit tests + 6 integration tests still green; positional argv assertions intact. |
| AC2 — catalogue rows resolve + surface in dashboard | satisfied | Migration round-trip pinned by S02, unchanged by S07/S09; dashboard router unchanged but verified generic in S08. |
| AC3 — agents/pi/ created, synced, reported | satisfied | 30/30 master files present, `pi_agents_synced` counter threaded end-to-end, CLI prints `Pi agents: N` line. |
| AC4 — allowlist enforcement | satisfied | `_VALID_CLI_TOOLS = {"opencode", "claude", "pi"}`; 7 allowlist tests green. FF1 is a future-drift hint, not a present gap. |
| AC5 — column comments updated; default unchanged | satisfied | Migration sets new comment text on both `step_runs.cli_tool` and `batches.cli_tool`; `server_default='opencode'` preserved. |
| AC6 — all QV gates pass | satisfied at S09 boundary | format/lint/typecheck re-run green; targeted pytest 102/102 green. Final confirmation via S10..S13. |

## Notes / Observations

- **FF1 deferral rationale.** S08 explicitly says: *"FF1 is advisory only — does
  not block S09 or merge"* and *"the existing explicit-raise pattern (same as
  F-00081's) is acceptable as-is."* Adding `assert cli_tool in _VALID_CLI_TOOLS`
  to one dispatch helper would be a defensible safety-net change, but doing so
  would require either (a) editing multiple dispatch sites for consistency, or
  (b) picking one site arbitrarily — both of which are out of scope for S09's
  "CRITICAL/HIGH only" mandate. Filing as a follow-up keeps the discussion in
  one place.
- **No scope amendment needed.** S09 made zero code changes. No `scope.allowed_paths`
  expansion is required.
- **No new `<!-- TODO(CR-00062-followup): -->` markers** were added in any source
  file. The FF1 follow-up lives in this report.
- **Cache warmth check.** Re-ran the same 96-test subset S08 ran (against the
  exact same working-tree contents) — identical green result, identical
  collected-count. No drift between S08 and S09.

## Result Contract

```json
{
  "step": "S09",
  "agent": "code-review-fix-final-impl",
  "work_item": "CR-00062",
  "completion_status": "complete",
  "files_changed": [
    "ai-dev/active/CR-00062/reports/CR-00062_S09_CodeReviewFixFinal_report.md"
  ],
  "preflight": {
    "format": "ok",
    "typecheck": "ok",
    "lint": "ok"
  },
  "tests_passed": true,
  "test_summary": "102 passed (96 targeted unit + 6 integration)",
  "tdd_red_evidence": "n/a — non-behavioural verification pass; no code edits",
  "findings_addressed": [
    {"id": "FF1", "severity": "LOW", "status": "deferred", "notes": "Advisory only per S08 — explicit-raise pattern is acceptable and matches F-00081. Out of S09's CRITICAL/HIGH-only mandate. Filed as follow-up."}
  ],
  "ac_coverage": {
    "AC1": "satisfied",
    "AC2": "satisfied",
    "AC3": "satisfied",
    "AC4": "satisfied",
    "AC5": "satisfied",
    "AC6": "satisfied"
  },
  "blockers": [],
  "notes": "S08 reported zero CRITICAL/HIGH/MEDIUM findings — no code edits were required in S09. Re-ran preflight gates (format, lint, typecheck — all green), targeted unit subset (96/96 green), and the integration test (6/6 green). FF1 deferred to follow-up per S08's explicit guidance. Migration-check not re-run because S09 touched neither migrations nor models; the S02 round-trip evidence still holds and S13 will run the final make migration-check."
}
```
