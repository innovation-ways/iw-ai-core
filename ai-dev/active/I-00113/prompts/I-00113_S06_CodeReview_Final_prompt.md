# I-00113_S06_CodeReview_Final_prompt

**Work Item**: I-00113 -- Re-review StepRun marked PID-dead immediately after fix-cycle commit
**Review Step**: S06 (Global cross-agent final review)
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits
Standard policy.

## ⛔ Migrations: agents generate, daemon applies
No migrations expected.

## Input Files

- `ai-dev/active/I-00113/I-00113_Issue_Design.md` — design document; AC1–AC4 are the contract.
- All four implementation reports: `I-00113_S01_Backend_report.md`, `I-00113_S03_Backend_report.md`, `I-00113_S04_Tests_report.md`, and the two per-agent reviews `I-00113_S02_CodeReview_report.md` and `I-00113_S05_CodeReview_report.md`.
- Full diff vs main: `git diff main...HEAD`.

## Output Files

- `ai-dev/active/I-00113/reports/I-00113_S06_CodeReview_Final_report.md`

## Context

S06 is the global cross-agent review. It does NOT re-do S02 or S05 — those covered their respective sub-scopes. S06 verifies the four ACs end-to-end and that the cross-step contract held (S01's recommendation → S03's fix → S04's coverage).

## Acceptance Criteria Coverage

For each AC in the design doc, write a one-line verdict in the report:

### AC1: Reproduction test exists and proves the bug pre-fix
- Confirm S01 wrote a test that demonstrated the bug.
- Confirm S03 flipped its assertion direction after the fix.
- Read the actual test file; the BUG-OBSERVED → BUG-FIXED flip should be a small focused diff.

### AC2: Bug is fixed
- `uv run pytest tests/unit/daemon/<repro>.py -v --no-cov` must exit 0.
- The fix must address the wrapper-exit-before-agent-registered case specifically — read the production diff and confirm.

### AC3: Regression tests cover every branch of the spawn→monitor lifecycle
- 5 branches mandated (wrapper-exit + healthy agent / wrapper-exit + no agent / agent alive / agent timeout / agent stall).
- Each branch has at least one test with a specific assertion (not shape-only).

### AC4: No false-positive PID-dead — telemetry contract
- The fix must NOT produce a false-positive PID-dead under the grace-window logic — verify the test for the bug case asserts the StepRun stays `running` and `_handle_crashed` was NOT called.
- (The 24-hour telemetry verification is observational and happens post-merge; this review only verifies the test-level contract.)

## Cross-Step Contract Audit

- S01 recommended exactly one fix approach. S03 implemented THAT approach. If they differ, the chain is broken — CRITICAL unless S03's report explicitly documents the deviation with a blocker.
- S04's coverage table directly references the AC3 branches. Missing branch coverage in S04 → CRITICAL.
- Each per-agent review (S02, S05) ended with `verdict: pass` — if either is `fail`, S06 must NOT pass on top of unresolved findings.

## Scope Discipline

- `git diff --name-only main...HEAD` MUST be a subset of: `orch/daemon/fix_cycle.py`, `orch/daemon/step_monitor.py`, `tests/unit/daemon/**`, `tests/integration/daemon/**`, `ai-dev/active/I-00113/**`.
- The implicit-allow paths (`ai-dev/active/I-00113/**`, `ai-dev/archive/I-00113/**`, `ai-dev/work/I-00113/**`) are NOT scope creep — do not flag.
- Any file outside that set is CRITICAL.

## Test Verification (NON-NEGOTIABLE — targeted only; QV gates own full suites)

```bash
uv run pytest tests/unit/daemon/ -v --no-cov
uv run pytest tests/integration/daemon/ -v --no-cov   # ONLY if S04 added integration tests
make lint
make format-check
make type-check
```

Do NOT run `make test-unit` or `make test-integration` here — S11 (unit-tests) and S12 (integration-tests) QV gates own those, and duplicating them inside S06 burns 1800+1800s of fix-cycle budget (I-00073 lesson). A targeted-tests failure, lint/format/typecheck violation, or regression in adjacent daemon tests is CRITICAL — broader regressions are caught by the downstream QV gates.

## Security

- No hardcoded credentials in any added log line.
- No PID values logged in a way that leaks across project boundaries (PIDs are local but make sure logging doesn't include unrelated process info).

## Severity Levels

Standard CRITICAL/HIGH/MEDIUM/LOW. Be strict on cross-step contract violations.

## Result Contract

End with:

```bash
uv run iw step-done I-00113 --step S06 --report ai-dev/active/I-00113/reports/I-00113_S06_CodeReview_Final_report.md
```

(or `step-fail` if the verdict is fail).
