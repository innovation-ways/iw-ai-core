# I-00118: Pre-existing red QV gate poisons in-flight items (baseline subtraction covers only 4 gates)

**Type**: Issue
**Severity**: High
**Created**: 2026-05-29
**Reported By**: Operator (diagnosed while investigating CR-00092 stall)
**Status**: Draft

---

## ⛔ Docker is off-limits

Standard policy. Testcontainer fixtures in tests are exempt.

## ⛔ Migrations: agents generate, daemon applies

This item adds **no** migration. It changes pure parsing logic and the
`GATE_PARSERS` map; the `qv_baselines` table is unchanged.

## Description

The F-00061 QV-baseline mechanism is supposed to suppress failures that already
exist on `main` so an in-flight work item is only failed for failures it
introduced. But baseline subtraction is applied only to gates that have a parser
in `GATE_PARSERS` (`lint`, `typecheck`, `unit-tests`, `frontend-tests`). Every
other gate — `assertions`, `format`, `integration-tests`, `diff-coverage`,
`security-secrets`, `check-column-docs` — gets **no** baseline subtraction, so a
failure that was already red on `main` is attributed to the item, produces
findings, burns fix cycles, and ultimately fails the item it did not cause. This
is the condition that surfaced during the CR-00092 stall: `make test-assertions`
was red on `main` (pre-existing tautology violations in two unrelated test
files), which would have failed CR-00092's `assertions` QV gate regardless of the
item's own work.

## Project Context

Read the project's `CLAUDE.md`. F-00061 design: `orch/daemon/qv_baseline.py`
(pure parsers + fingerprint algebra), `orch/daemon/batch_manager.py`
(`_compute_qv_baselines`), `orch/daemon/fix_cycle.py` (`_get_qv_findings`),
`qv_baselines` table.

## Steps to Reproduce

1. Leave a gate red on `main` — e.g. introduce a tautology assertion so
   `make test-assertions` exits non-zero on `main`.
2. Create + execute any work item whose workflow includes the `assertions` QV
   gate (`make test-assertions`).
3. Let the daemon set up the worktree (computes QV baselines) and reach the
   `assertions` gate.

**Expected**: The pre-existing `assertions` failure is recognized as part of the
baseline (it was red at the worktree's base SHA) and is **subtracted**, so the
item is not failed for it; only failures the item newly introduced should fail
the gate.

**Actual**: `assertions` is not in `GATE_PARSERS`, so `_compute_qv_baselines`
skips capturing a baseline for it ("Unknown gate … skipping baseline") and
`_get_qv_findings` returns early to `_qv_findings_legacy` (no subtraction). The
pre-existing failure is treated as the item's, generating findings and consuming
fix cycles until the item fails.

## Root Cause Analysis

`orch/daemon/qv_baseline.py`:

```python
GATE_PARSERS = {
    "lint": parse_ruff,
    "typecheck": parse_mypy,
    "unit-tests": parse_pytest,
    "frontend-tests": parse_pytest,
}
```

- `orch/daemon/batch_manager.py:_compute_qv_baselines()` — `parser =
  GATE_PARSERS.get(gate)`; `if parser is None: … "skipping baseline"; continue`.
  No baseline row is ever written for unparsed gates.
- `orch/daemon/fix_cycle.py:_get_qv_findings()` — `parser =
  GATE_PARSERS.get(gate_name)`; `if parser is None: return
  _qv_findings_legacy(...)` (no subtraction). When the delta IS computed and is
  empty, it returns `""` and logs `"[F-00061] Suppressed N pre-existing
  failures"` — but only parsed gates ever reach this path.

So the suppression that protects `lint`/`typecheck`/`unit-tests`/`frontend-tests`
from pre-existing `main` failures is structurally unavailable to all other gates.
`assertions` is the concrete gate that poisoned CR-00092's situation; the same
gap applies to `format`, `integration-tests`, `diff-coverage`,
`security-secrets`, and `check-column-docs`.

Note that `integration-tests` is in this list only because it was never
registered, not because its output is unparseable: it emits the same pytest
output `parse_pytest` already handles for `unit-tests`/`frontend-tests`. The fix
therefore registers it precisely (`integration-tests → parse_pytest`) rather than
leaving the slowest, most-expensive gate on the fragile whole-line generic
fallback, where run-to-run-volatile fragments (durations, ordering) would risk a
missed or false suppression.

## Affected Components

| Component | Impact |
|-----------|--------|
| `orch/daemon/qv_baseline.py` | `GATE_PARSERS` omits every text-output gate → no fingerprint for them |
| `orch/daemon/batch_manager.py` (`_compute_qv_baselines`) | Skips baseline capture for unparsed gates |
| `orch/daemon/fix_cycle.py` (`_get_qv_findings`) | Falls back to no-subtraction for unparsed gates |
| In-flight items | Failed/blocked by failures that pre-existed on `main` |

## Fix Plan

### Agents and Execution Order

> **Step-granularity rule**: each implementation step targets one cohesive concern.

| Step | Agent | Scope | Parallel With |
|------|-------|-------|---------------|
| S01 | Backend | In `qv_baseline.py`: add `parse_assertion_scanner` (precise, for the `assertions` gate) and a conservative generic line-keyed fallback parser `parse_generic_lines`. Register `assertions → parse_assertion_scanner` and `integration-tests → parse_pytest` (it emits pytest output) in `GATE_PARSERS`. Add a resolver (e.g. `parser_for_gate(gate)`) returning the precise parser when known, else the generic fallback. Update `_compute_qv_baselines` and `_get_qv_findings` to use the resolver so **every** gate gets baseline capture + subtraction. | — |
| S02 | CodeReview | Review S01 | — |
| S03 | Tests | Parser unit tests + integration test proving a base-red gate is suppressed while a genuinely new failure surfaces | — |
| S04 | CodeReview | Review S03 | — |
| S05 | CodeReview_Final | Global review | — |
| S06..S13 | QV Gates | lint, format, typecheck, assertions, unit-tests, integration-tests, diff-coverage, security-secrets | — |
| S14 | SelfAssess | Self-assessment (project `self_assess=true`) | — |

### Database Changes

- **New tables**: None. **Modified tables**: None. **Migration notes**: None.

### Code Changes

- **Files to modify**: `orch/daemon/qv_baseline.py`, `orch/daemon/fix_cycle.py`,
  `orch/daemon/batch_manager.py`
- **Nature of change**: Add parsers + a gate→parser resolver so F-00061 baseline
  subtraction applies to all gates, not just the original four.

## File Manifest

| File | Type | Purpose |
|------|------|---------|
| `I-00118_Issue_Design.md` | Design | This document |
| `I-00118_Functional.md` | Design | Human-facing summary |
| `workflow-manifest.json` | Manifest | Step definitions |
| `prompts/I-00118_S01_Backend_prompt.md` | Prompt | S01 fix |
| `prompts/I-00118_S02_CodeReview_Backend_prompt.md` | Prompt | Review S01 |
| `prompts/I-00118_S03_Tests_prompt.md` | Prompt | Tests |
| `prompts/I-00118_S04_CodeReview_Tests_prompt.md` | Prompt | Review S03 |
| `prompts/I-00118_S05_CodeReview_Final_prompt.md` | Prompt | Global review |
| `prompts/I-00118_S14_SelfAssess_prompt.md` | Prompt | Self-assessment |

Reports are created during execution in `ai-dev/active/I-00118/reports/`.

## Test to Reproduce

Unit (pure parser) + integration (pipeline). The integration test exercises the
real baseline-capture → subtract path against a testcontainer DB.

```python
def test_assertions_gate_baseline_subtracts_pre_existing_failure():
    """A failure present at the base SHA must be subtracted for the assertions gate.

    FAILS before the fix (assertions has no parser → no subtraction → finding
    surfaces); PASSES after (parser registered → empty delta → suppressed).
    """
    baseline_output = "tests/x_test.py:18: tautology: test_foo: every assert ...\n"
    current_output = baseline_output  # same failure still present, item added nothing
    fp_base = parse_assertion_scanner(baseline_output)
    fp_now = parse_assertion_scanner(current_output)
    delta = subtract(fp_now, fp_base)
    assert delta.failures == ()        # pre-existing failure suppressed
    assert delta.unparseable == ()

def test_assertions_gate_reports_new_failure_not_in_baseline():
    """A NEW tautology (different test) must NOT be suppressed."""
    fp_base = parse_assertion_scanner("tests/a_test.py:1: tautology: test_a: ...\n")
    fp_now = parse_assertion_scanner(
        "tests/a_test.py:1: tautology: test_a: ...\n"
        "tests/b_test.py:9: tautology: test_b: ...\n"
    )
    delta = subtract(fp_now, fp_base)
    assert any("test_b" in f.key for f in delta.failures)
    assert not any("test_a" in f.key for f in delta.failures)
```

## Acceptance Criteria

### AC1: Pre-existing assertions failure is subtracted

```
Given make test-assertions is red at the worktree's base SHA
When  the item's assertions QV gate runs and produces the same failure
Then  baseline subtraction yields an empty delta and the failure is suppressed
      (not attributed to the item)
```

### AC2: New failure still surfaces

```
Given a baseline captured for a gate
When  the gate run contains a failure NOT present in the baseline
Then  that failure appears in the delta and is reported to the fix agent
```

### AC3: All gates get baseline coverage

```
Given any QV gate in a workflow (assertions, format, diff-coverage, security-secrets, …)
When  _compute_qv_baselines runs at worktree setup
Then  a baseline row is captured for it (via precise parser or the generic fallback),
      and _get_qv_findings applies subtraction rather than the legacy no-subtraction path
```

### AC4: Regression tests exist

```
Given the fix is applied
When the test suite runs
Then the parser + subtraction tests pass with semantic assertions
```

## Regression Prevention

- The generic fallback closes the class of bug ("gate without a precise parser =
  zero baseline protection") for all current and future text-output gates.
- A test asserts the resolver never returns `None` for a known gate name,
  preventing silent reintroduction of the no-baseline path.

## Dependencies

- **Depends on**: None
- **Blocks**: None (sibling of I-00117; both surfaced by the CR-00092 stall)

## Impacted Paths

- `orch/daemon/qv_baseline.py`
- `orch/daemon/fix_cycle.py`
- `orch/daemon/batch_manager.py`
- `tests/unit/orch/daemon/test_qv_baseline.py`
- `tests/integration/daemon/test_baseline_qv_pipeline.py`

## TDD Approach

- Reproducing tests: `parse_assertion_scanner` subtraction (above) — fail before
  the parser exists, pass after.
- Unit tests: generic fallback keys identical lines equal; differing lines
  distinct; `parser_for_gate` returns a callable for every gate.
- Integration test: full `_compute_qv_baselines` → gate-fail → `_get_qv_findings`
  suppresses a base-red gate, surfaces a new failure.

## Notes

- **Generic-fallback false-suppression risk**: a brand-new failure whose output
  line is byte-identical to a baselined line would be wrongly suppressed. Mitigate
  by keying on the full normalized (stripped, volatile-token-free) line; for
  line-numbered output (assertion scanner) the file:line:test identity makes
  collisions negligible. Document the conservatism in the parser docstring.
- **Alternative considered (not chosen)**: a coarse pre-flight guard that refuses
  to launch items when `main`'s gates are red. Rejected as too blunt — it blocks
  all work on any red gate, including items that don't touch the affected area.
  The F-00061 extension is per-item and precise.
- `format` (ruff format --check) was intentionally excluded from precise parsing
  in F-00061 because its output shape is incompatible; the generic fallback now
  gives it best-effort baseline coverage.
- `integration-tests` gets the existing `parse_pytest` (it is pytest output), not
  the generic fallback — precise file::test keying avoids the whole-line
  fragility that pytest's volatile duration/ordering fragments would otherwise
  introduce on the slowest gate.
- Keep the fix minimal: do not change the `qv_baselines` schema or the
  fingerprint algebra (`subtract`).
