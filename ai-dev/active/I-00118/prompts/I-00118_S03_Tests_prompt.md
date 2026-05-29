# I-00118_S03_Tests_prompt

**Work Item**: I-00118 -- Pre-existing red QV gate poisons in-flight items
**Step**: S03 — Reproduction + regression tests
**Agent**: tests-impl

---

## ⛔ Docker is off-limits

Standard policy. The ONLY allowed docker usage is via `testcontainers` pytest
fixtures. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.

## Input Files

- `ai-dev/active/I-00118/I-00118_Issue_Design.md` (Test to Reproduce + AC1-AC4)
- `ai-dev/active/I-00118/reports/I-00118_S01_Backend_report.md`
- Existing patterns: `tests/unit/orch/daemon/test_qv_baseline.py` (parser unit
  tests), `tests/integration/daemon/test_baseline_qv_pipeline.py` (pipeline),
  `tests/CLAUDE.md`.

## Output Files

- Extend `tests/unit/orch/daemon/test_qv_baseline.py` (parser + resolver tests).
- Extend `tests/integration/daemon/test_baseline_qv_pipeline.py` (or add a focused
  integration test) for the suppress-base-red / surface-new behavior.
- `ai-dev/active/I-00118/reports/I-00118_S03_Tests_report.md`

## Requirements

### 1. Unit: `parse_assertion_scanner` (AC1/AC2)

- A line present in both baseline and current → `subtract` yields empty delta
  (suppressed). Assert `delta.failures == ()` and `delta.unparseable == ()`.
- A NEW assertion failure (different test) present only in current → appears in
  the delta; the pre-existing one does NOT. Assert on the specific `key`/test
  name, not just length.
- Garbage lines → `unparseable` (fail-safe).

### 2. Unit: `parse_generic_lines` + `parser_for_gate` (AC3)

- Identical normalized lines subtract to empty; a differing line surfaces.
- `parser_for_gate("assertions")` is `parse_assertion_scanner`;
  `parser_for_gate("lint")` is `parse_ruff`;
  `parser_for_gate("integration-tests")` is `parse_pytest` (precise, not the
  generic fallback); `parser_for_gate("some-unknown-gate")`
  returns the generic fallback and is **callable** (never `None`).

### 3. Integration (AC1/AC3)

Using the real baseline pipeline against a testcontainer DB (follow
`test_baseline_qv_pipeline.py` + `tests/CLAUDE.md` rules): a gate that is red at
the base SHA, when re-run with the same failure, produces an empty delta and is
suppressed (no finding); a gate run with an additional failure reports only the
new one.

## CRITICAL: Semantic Correctness Over Shape Checking (I003 Lesson)

- BAD: `assert delta.failures` / `assert len(delta.failures) >= 0`
- GOOD: `assert delta.failures == ()` (pre-existing suppressed)
- GOOD: `assert any(f.key.endswith("::test_b") for f in delta.failures)` and
  `assert not any("test_a" in f.key for f in delta.failures)`

## Test Verification (NON-NEGOTIABLE)

Run ONLY the files you changed:
`uv run pytest tests/unit/orch/daemon/test_qv_baseline.py -v` and (if you touched
it) `uv run pytest tests/integration/daemon/test_baseline_qv_pipeline.py -v`.
**DO NOT** run `make test-unit` / `make test-integration` — full suites are the
downstream QV gates' job. Do not report `tests_passed: true` unless your targeted
runs are green. Do not revert source at runtime to "prove RED".

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "tests-impl",
  "work_item": "I-00118",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["tests/unit/orch/daemon/test_qv_baseline.py", "tests/integration/daemon/test_baseline_qv_pipeline.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (targeted)",
  "tdd_red_evidence": "tests/unit/orch/daemon/test_qv_baseline.py::test_assertions_gate_baseline_subtracts_pre_existing_failure — <RED line: parse_assertion_scanner missing / finding surfaced before fix>",
  "blockers": [],
  "notes": ""
}
```
