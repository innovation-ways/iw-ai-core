# F-00061 S03 Backend QvBaseline — Step Report

## What Was Done

Implemented the pure core of F-00061: parsers, fingerprints, and the subtraction algebra in `orch/daemon/qv_baseline.py`, plus the `IW_CORE_BASELINE_QV` kill switch wiring in `orch/config.py`.

## Files Changed

| File | Change |
|------|--------|
| `orch/daemon/qv_baseline.py` | **New** — pure module: `FailureEntry`/`Fingerprint` dataclasses, `parse_ruff`/`parse_pytest`/`parse_mypy` parsers, `GATE_PARSERS` mapping, `fingerprint_to_jsonable`/`fingerprint_from_jsonable` round-trip serialization, `subtract()` algebra |
| `orch/config.py` | **Modified** — added `baseline_qv_enabled: bool = True` to `DaemonConfig`; added `_parse_truthy()` helper; added `IW_CORE_BASELINE_QV` parsing in `load_config()` with same truthy semantics as other flags |

## Module Design

**`FailureEntry`** — frozen dataclass with `kind` and `key` fields. `kind` is one of `"lint" | "test" | "typecheck" | "unknown"`.

**`Fingerprint`** — frozen dataclass with `failures: tuple[FailureEntry, ...]` and `unparseable: tuple[str, ...]`. All public constructors guarantee sorted, deduplicated failures.

**Parsers**:
- `parse_ruff` — detects JSON (`--output-format json`) by leading `{`; parses both JSON array and `{"results": [...]]}` envelope; text mode handles the "concise" and "grouped" output formats (no severity word before rule code). Key: `<filename>::<rule_code>`.
- `parse_pytest` — extracts `FAILED <nodeid> - <msg>` lines; key is the nodeid itself. Skips separator lines (`===`, `FAILED`, `PASSED`). All other non-empty, non-comment lines go to `unparseable`.
- `parse_mypy` — regex: `path:line: error: msg [code]`. Key: `path::<code>` (or `path::error` if no code). Fixed code regex from `[a-z]\d+` to `[a-z][a-z0-9-]*` to handle multi-segment codes like `arg-type`.

**`subtract(current, baseline)`** — returns failures in `current` not in `baseline`; `unparseable` always surfaces (fail-safe). Preserves current ordering (Invariant 4).

**`GATE_PARSERS`** — maps `"lint"`, `"typecheck"`, `"unit-tests"`, `"integration-tests"`, `"frontend-tests"` to their parsers. `"format"` is intentionally absent (incompatible output shape would break AC1 for S11).

## Verification Results

| Check | Result |
|-------|--------|
| `uv run mypy orch/daemon/qv_baseline.py orch/config.py` | ✅ Success: no issues |
| `uv run ruff check orch/daemon/qv_baseline.py orch/config.py` | ✅ All checks passed |
| `uv run ruff format --check orch/daemon/qv_baseline.py orch/config.py` | ✅ 2 files already formatted |
| Parser smoke: `parse_mypy` with real mypy-like output | ✅ Correct codes extracted |
| Parser smoke: `subtract` algebra | ✅ Identity, full-overlap, partial-overlap all correct |
| JSON roundtrip | ✅ `fp == fingerprint_from_jsonable(fingerprint_to_jsonable(fp))` |

## Notes

- The `_RUFF_TEXT_RE` regex was corrected to not expect a severity word before the rule code (ruff's concise/grouped output is `file:line:col: CODE msg`, not `file:line:col: error CODE msg`).
- The mypy code regex was corrected from `[a-z]\d+` to `[a-z][a-z0-9-]*` to handle multi-segment codes like `arg-type`.
- `parse_pytest` correctly returns empty failures for pytest output without `FAILED` lines — these go to `unparseable`. S07's fixture will need proper `FAILED` lines to test the happy path.
- `parse_ruff` text mode requires the `ruff check` output format (not `ruff format --check` which is intentionally excluded).
- No DB calls, no subprocess spawning, no hidden state — fully unit-testable in S07 without testcontainers.
- S05 will wire `compute_baseline` by composing these parsers with the daemon's existing subprocess machinery.