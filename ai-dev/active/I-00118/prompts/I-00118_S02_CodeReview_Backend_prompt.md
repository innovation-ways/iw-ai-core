# I-00118_S02_CodeReview_Backend_prompt

**Work Item**: I-00118 -- Pre-existing red QV gate poisons in-flight items
**Step**: S02 — Per-agent review of S01
**Agent**: code-review-impl

---

## ⛔ Docker is off-limits

Standard policy (testcontainers + read-only introspection only).

## Input Files

- `uv run iw item-status I-00118 --json`
- `ai-dev/active/I-00118/I-00118_Issue_Design.md`
- `ai-dev/active/I-00118/reports/I-00118_S01_Backend_report.md`
- `orch/daemon/qv_baseline.py`, `orch/daemon/fix_cycle.py`, `orch/daemon/batch_manager.py`

## Output Files

- `ai-dev/active/I-00118/reports/I-00118_S02_CodeReview_Backend_report.md`

## Diff scoping (I-00116)

Restrict your review diff to `scope.allowed_paths` in the manifest.

## Review Bars (CRITICAL → must pass)

1. **`assertions` gate now covered.** `parse_assertion_scanner` exists, keys on a
   stable file/test identity (not message text), routes non-matching lines to
   `unparseable`, and `"assertions"` is registered so it gets baseline capture +
   subtraction.
2. **Generic fallback exists and is the default.** `parser_for_gate` never returns
   `None`; unknown gates resolve to `parse_generic_lines`. Both
   `_compute_qv_baselines` and `_get_qv_findings` use the resolver — there is no
   remaining "unknown gate → skip baseline / legacy no-subtraction" path.
3. **Existing gates unchanged.** `lint`/`typecheck`/`unit-tests`/`frontend-tests`
   still resolve to their precise parsers; behavior preserved.
4. **Legacy fallback retained only where valid** (no command / no base SHA / no
   baseline row / no latest run) — NOT for "unknown gate".
5. **Purity.** New parsers are pure + deterministic; false-suppression risk
   documented in `parse_generic_lines`.
6. **Scope**: only the three daemon files (+ `ai-dev/**`).

If any CRITICAL/HIGH: fail the step with a reason. Otherwise write the report.
