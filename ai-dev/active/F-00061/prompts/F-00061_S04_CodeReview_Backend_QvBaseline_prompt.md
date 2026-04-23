# F-00061_S04_CodeReview_Backend_QvBaseline_prompt

**Work Item**: F-00061 -- Baseline QV gates to prevent fix-cycle scope expansion
**Step**: S04
**Agent**: code-review-impl
**Reviews**: S03 (Backend — QvBaseline pure module)

---

## ⛔ Docker is off-limits

(Same policy as S01. Read-only `docker ps/inspect/logs` only. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.)

## ⛔ Migrations: agents generate, daemon applies

(No migration work expected in S03. If S03 touched any migration file, flag as CRITICAL out-of-scope.)

## Input Files

- `ai-dev/active/F-00061/F-00061_Feature_Design.md` — **Scope → In Scope**, **Boundary Behavior** (rows 3–5 cover fingerprint normalization), **Invariants 3, 4, 6**, **Notes → Fingerprint schema**
- `ai-dev/active/F-00061/reports/F-00061_S03_Backend_QvBaseline_report.md` — S03's self-report
- `orch/daemon/qv_baseline.py` — new module (review target)
- `orch/config.py` — modified, focus on the `baseline_qv_enabled` wiring
- `orch/CLAUDE.md` + `orch/daemon/CLAUDE.md` — layer rules
- Sample outputs you can capture to spot-check parsers: `uv run ruff check --output-format json .`, `uv run pytest tests/unit -q 2>&1 | tail`, `uv run mypy orch/ 2>&1 | tail`

## Output Files

- `ai-dev/active/F-00061/reports/F-00061_S04_CodeReview_Backend_QvBaseline_report.md`

## Context

S03 implemented the pure core: parsers, fingerprints, subtraction, JSON round-trip, config flag. F-00061's correctness is anchored in this module — if `subtract` has a bug, AC1/AC2 break silently in production. Your review focus is **parser correctness on real tool output** and **algebraic invariants of `subtract`**. Catching regressions here is cheaper than catching them in S08's integration tests.

## Review Checklist

### CRITICAL — must pass

1. **Parsers return stable keys independent of line numbers and error messages** (Boundary Behavior rows 4, 5). Confirm by reading each parser:
   - `parse_ruff`: key contains file + rule code, NOT line number. Pass real ruff JSON AND text samples through it and confirm byte-identity of keys when only line numbers change.
   - `parse_pytest`: key is the pytest nodeid; ignores trailing `- <error message>` text.
   - `parse_mypy`: key is `file::error-code`; ignores line number and message body.
2. **Determinism** (Invariant 6): `Fingerprint.failures` is sorted by `(kind, key)`. Two parses of the same input produce byte-identical `fingerprint_to_jsonable` dicts. Spot-check by running each parser twice in a REPL.
3. **Subtraction invariants**:
   - Identity: `subtract(H, Fingerprint(())) == H` (both failures and unparseable preserved)
   - Full overlap: `subtract(H, H).failures == ()` (unparseable from `current` still surfaces)
   - Stability: `subtract(H, B).failures` preserves `H.failures` order
   - Monotonicity (Invariant 3): `subtract(H, B).failures` is a subset of `H.failures`
4. **JSON round-trip**: `fp == fingerprint_from_jsonable(fingerprint_to_jsonable(fp))` for any Fingerprint the parsers can produce.
5. **No side effects in the module**: grep for `subprocess`, `os.environ` (except in config.py), `db.`, `open()` writes, `Path().write_*`, `logger.*` at module import time. Pure module means pure module.
6. **Unparseable entries always surface** (fail-safe from Boundary Behavior row 3): in `subtract`, `unparseable` from `current` is preserved unchanged (NOT matched against baseline).
7. **Config flag follows `IW_CORE_*` pattern** in `orch/config.py`: parsed with truthy-string normalization, added to `DaemonConfig` with a sensible default (design doc says `True`), no `importlib.reload` calls introduced.
8. **No unintended changes outside `orch/daemon/qv_baseline.py` and `orch/config.py`** — verify with `git diff main..HEAD --name-only`; any other file means S03 overreached and S04 must CRITICAL-fail.

### HIGH — should pass

9. **`GATE_PARSERS` dict covers the gate names that can benefit from subtraction** (lint, typecheck, unit-tests, integration-tests, frontend-tests). **`"format"` MUST BE ABSENT** — `ruff format --check` emits "Would reformat: <file>" which has no rule codes and would route through `parse_ruff` as 100% unparseable, spuriously surfacing every format finding (breaks AC1 for S11). Confirm the comment block in the module explains the omission. Unknown gate → legacy fallthrough in S05, which is correct.
10. **Type hints on every public function**; mypy `--strict` on this module would pass (spot-check with `uv run mypy --strict orch/daemon/qv_baseline.py` — if not strict-clean, it's HIGH not CRITICAL).
11. **Dataclasses are `frozen=True`** (immutability → can be used as dict/set keys; matches Invariant 6's determinism posture).

### MEDIUM_FIXABLE — should fix if noticed

12. Module docstring explains the fingerprint schema and references F-00061.
13. Each parser function has a docstring with a "Representative input:" block showing a short sample.
14. `GATE_PARSERS` constant name is `ALL_CAPS` per convention.

### MEDIUM_SUGGESTION — note but don't block

15. If the parsers accept `Path` objects as well as strings, it would be convenient — but strings are fine.

## Verification Commands (read-only)

- `uv run mypy orch/daemon/qv_baseline.py orch/config.py` — zero errors
- `uv run ruff check orch/daemon/qv_baseline.py orch/config.py` — zero errors on changed lines
- `uv run ruff format --check orch/daemon/qv_baseline.py orch/config.py` — clean
- Ad-hoc parser smoke:
  ```bash
  uv run python -c "
  from orch.daemon.qv_baseline import parse_pytest, subtract, Fingerprint, FailureEntry
  fp1 = parse_pytest('FAILED tests/unit/foo.py::test_a - AssertionError')
  fp2 = parse_pytest('FAILED tests/unit/foo.py::test_a - AssertionError\nFAILED tests/unit/bar.py::test_b - KeyError')
  print('subtract:', subtract(fp2, fp1))
  assert len(subtract(fp2, fp1).failures) == 1
  assert subtract(fp2, fp1).failures[0].key.endswith('test_b')
  print('PASS')
  "
  ```

## Report

Standard CodeReview report format (see `ai-dev/templates/CodeReview_Prompt_Template.md`). Findings table grouped by severity. Overall verdict **pass** only if zero CRITICAL + zero HIGH.

Call `iw step-done` or `iw step-fail` with `--report`.

## Subagent Result Contract

```json
{
  "step": "S04",
  "agent": "code-review-impl",
  "work_item": "F-00061",
  "steps_reviewed": ["S03"],
  "verdict": "pass|fail",
  "findings": [
    {"severity": "CRITICAL|HIGH|MEDIUM_FIXABLE|MEDIUM_SUGGESTION", "file": "path", "line": N, "description": "..."}
  ],
  "mandatory_fix_count": 0,
  "tests_passed": true,
  "test_summary": "mypy clean; ruff clean; subtract smoke passes",
  "notes": ""
}
```
