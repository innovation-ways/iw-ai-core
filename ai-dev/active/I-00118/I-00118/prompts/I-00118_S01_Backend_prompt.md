# I-00118_S01_Backend_prompt

**Work Item**: I-00118 -- Pre-existing red QV gate poisons in-flight items
**Step**: S01
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

You MUST NOT execute ANY command that changes Docker container/volume/network
state. Exceptions: testcontainers (pytest fixtures), read-only introspection,
`./ai-core.sh` / `make` targets. Full policy:
`docs/IW_AI_Core_Agent_Constraints.md`.

## ⛔ Migrations: agents generate, daemon applies

This item adds **no** migration. Do not generate or apply one.

## Input Files

- `uv run iw item-status I-00118 --json`
- `ai-dev/active/I-00118/I-00118_Issue_Design.md` (Root Cause + Fix Plan + ACs)
- Source: `orch/daemon/qv_baseline.py` (`GATE_PARSERS`, `parse_*`, `Fingerprint`,
  `FailureEntry`, `subtract`), `orch/daemon/fix_cycle.py` (`_get_qv_findings`,
  ~line 1648), `orch/daemon/batch_manager.py` (`_compute_qv_baselines`, ~line
  1029).
- The scanner whose output you must parse: `scripts/check_test_assertions.py`
  (run `make test-assertions` or read the script to learn the exact line format,
  e.g. `<file>:<line>: <category>: <test_name>: <message>`).

## Output Files

- `ai-dev/active/I-00118/reports/I-00118_S01_Backend_report.md`

## Context

F-00061 baseline subtraction only applies to gates in `GATE_PARSERS`
(`lint`, `typecheck`, `unit-tests`, `frontend-tests`). All other gates fall back
to no-subtraction, so a failure already red on `main` is blamed on the in-flight
item. Read the design's Root Cause Analysis first, then `CLAUDE.md` /
`orch/CLAUDE.md`.

## Requirements

### 1. Add `parse_assertion_scanner(raw_output) -> Fingerprint` in `qv_baseline.py`

- Parse `scripts/check_test_assertions.py` output lines into `FailureEntry`s.
- Key each failure stably and specifically, e.g. `kind="assertion"`,
  `key="<file>::<test_name>"` (NOT including the message text, which can vary).
  Confirm the real output format first and key on the identifying portion.
- Non-matching lines go to `unparseable` (fail-safe, like the other parsers).
- Pure + deterministic (Invariant 6).

### 2. Add `parse_generic_lines(raw_output) -> Fingerprint` in `qv_baseline.py`

- Conservative fallback for gates with no precise parser. Key on the **full
  normalized line**: strip whitespace, drop empty lines. `kind="line"`,
  `key=<stripped line>`. Optionally strip obviously-volatile tokens (timestamps,
  absolute paths, elapsed-time/duration numbers) — keep normalization minimal and
  documented; over-normalizing risks collapsing distinct failures.
- Document the false-suppression risk in the docstring (a new failure whose line
  is byte-identical to a baselined line is suppressed).

### 3. Add a resolver and wire it in

- Add `parser_for_gate(gate_name) -> Callable[[str], Fingerprint]` (or equivalent)
  that returns the precise parser when `gate_name` is known (extend `GATE_PARSERS`
  to include `"assertions": parse_assertion_scanner` **and**
  `"integration-tests": parse_pytest` — `integration-tests` emits pytest output, so
  reuse the existing `parse_pytest` for precise subtraction rather than the fragile
  whole-line generic fallback), else `parse_generic_lines`.
  It MUST never return `None`.
- Update `batch_manager.py:_compute_qv_baselines` and
  `fix_cycle.py:_get_qv_findings` to use `parser_for_gate(...)` instead of
  `GATE_PARSERS.get(...)` + the `if parser is None:` skip/legacy-fallback. Keep
  the legacy path only for the genuine cases it still must handle (no command, no
  base SHA, no baseline row, no latest run) — but NOT for "unknown gate".
- Preserve all existing behavior for the four already-parsed gates.

## Project Conventions

Match `qv_baseline.py`'s pure-function style, `__all__` exports, and the
`FailureEntry`/`Fingerprint` dataclasses. SQLAlchemy 2.0 elsewhere.

## Pre-flight Quality Gates (NON-NEGOTIABLE)

Run and fix, in order: `make format`, `make typecheck`, `make lint`. Record in
`preflight`.

## Test Verification (NON-NEGOTIABLE)

Verify only your changed path with a targeted run, e.g.
`uv run pytest tests/unit/orch/daemon/test_qv_baseline.py -v`. **DO NOT** run
`make test-unit` / `make test-integration` — full suites are the downstream QV
gates' job. Do **not** use `make quality`/`make check` as a completion gate here.

## Subagent Result Contract

```json
{
  "step": "S01",
  "agent": "backend-impl",
  "work_item": "I-00118",
  "completion_status": "complete|partial|blocked",
  "files_changed": ["orch/daemon/qv_baseline.py", "orch/daemon/fix_cycle.py", "orch/daemon/batch_manager.py"],
  "preflight": {"format": "ok|fixed", "typecheck": "ok", "lint": "ok"},
  "tests_passed": true,
  "test_summary": "X passed, 0 failed (targeted)",
  "tdd_red_evidence": "n/a — behavioral tests authored in S03 (Tests)",
  "blockers": [],
  "notes": ""
}
```
