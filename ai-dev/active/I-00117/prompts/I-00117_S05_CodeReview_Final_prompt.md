# I-00117_S05_CodeReview_Final_prompt

**Work Item**: I-00117 -- Daemon silently dead-ends a non-fixable, non-retryable failed step
**Step**: S05 — Global cross-step review
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Standard policy (testcontainers + read-only introspection only).

## Input Files

- `uv run iw item-status I-00117 --json`
- `ai-dev/active/I-00117/I-00117_Issue_Design.md`
- All step reports under `ai-dev/active/I-00117/reports/`
- Source: `orch/daemon/fix_cycle.py`, `orch/daemon/batch_manager.py`,
  `tests/integration/test_recovery_exhausted_escalation.py`

## Output Files

- `ai-dev/active/I-00117/reports/I-00117_S05_CodeReview_Final_report.md`

## Mechanical AC verification

- **AC1**: Drive the logic mentally/in-test — a failed `implementation` step with
  retries exhausted + non-`SPEC_MISMATCH` reason ⇒ `step_recovery_exhausted`
  event + work_item `failed` + batch_item `failed`. Confirm the test asserts all
  three.
- **AC2**: `SPEC_MISMATCH:` still routes to `handle_spec_mismatch_escalation`;
  the two paths are mutually exclusive.
- **AC3**: Reproduction test present, integration-placed, semantic assertions.

## Cross-step checks

1. No remaining silent failure path: grep `batch_manager.py` for any
   failure-handling branch that `return`s without emitting a `DaemonEvent` or
   changing status. The fixed `else` is the only one this CR targets, but flag any
   other you spot (note as a follow-up, do not expand scope).
2. Scope discipline: diff = `orch/daemon/fix_cycle.py`,
   `orch/daemon/batch_manager.py`, `tests/integration/test_recovery_exhausted_escalation.py`
   plus `ai-dev/**`. Anything else → CRITICAL.
3. Run `make test-unit` AND
   `uv run pytest tests/integration/test_recovery_exhausted_escalation.py -v`.

If any CRITICAL/HIGH: fail with a reason. Otherwise write the report.
