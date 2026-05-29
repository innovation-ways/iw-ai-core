# I-00118_S05_CodeReview_Final_prompt

**Work Item**: I-00118 -- Pre-existing red QV gate poisons in-flight items
**Step**: S05 — Global cross-step review
**Agent**: code-review-final-impl

---

## ⛔ Docker is off-limits

Standard policy (testcontainers + read-only introspection only).

## Input Files

- `uv run iw item-status I-00118 --json`
- `ai-dev/active/I-00118/I-00118_Issue_Design.md`
- All step reports under `ai-dev/active/I-00118/reports/`
- `orch/daemon/qv_baseline.py`, `orch/daemon/fix_cycle.py`,
  `orch/daemon/batch_manager.py`, and the two test files.

## Output Files

- `ai-dev/active/I-00118/reports/I-00118_S05_CodeReview_Final_report.md`

## Mechanical AC verification

- **AC1**: assertions failure present at base → empty delta → suppressed.
- **AC2**: a failure not in baseline → surfaces in the delta.
- **AC3**: both `_compute_qv_baselines` and `_get_qv_findings` use the resolver;
  grep both for any remaining `GATE_PARSERS.get(...)` + `if parser is None` skip
  that would reintroduce the no-baseline path for unknown gates.
- **AC4**: parser/resolver/integration tests present with semantic assertions.

## Cross-step checks

1. Existing four gates' behavior unchanged (precise parsers still used).
2. Legacy no-subtraction path remains ONLY for genuine cases (no command / no base
   SHA / no baseline row / no latest run), never for "unknown gate".
3. Scope discipline: diff = the three daemon files + the two test files
   (+ `ai-dev/**`). Anything else → CRITICAL.
4. Run `make test-unit` AND
   `uv run pytest tests/unit/orch/daemon/test_qv_baseline.py -v`.

If any CRITICAL/HIGH: fail with a reason. Otherwise write the report.
