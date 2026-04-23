# F-00061_S03_Backend_QvBaseline_prompt

**Work Item**: F-00061 -- Baseline QV gates to prevent fix-cycle scope expansion
**Step**: S03
**Agent**: backend-impl

---

## ⛔ Docker is off-limits

(Same policy as S01. NEVER `docker compose up/down/restart`, `docker kill`, `docker rm`, `docker volume rm`. Read-only `docker ps/inspect/logs` is OK. Full policy: `docs/IW_AI_Core_Agent_Constraints.md`.)

## ⛔ Migrations: agents generate, daemon applies

(You will NOT touch migrations in this step. S01 owns the migration file; if you discover a schema gap, record it as a blocker — do NOT create or modify migrations here. NEVER run `alembic upgrade|downgrade|stamp` against port 5433.)

## Input Files

- `ai-dev/active/F-00061/F-00061_Feature_Design.md` — particularly **Description**, **Scope**, **Acceptance Criteria AC1/AC2/AC5/AC6/AC7**, **Boundary Behavior** (every row is a test case in S07; your module's behaviour must satisfy them), **Notes → Fingerprint schema**
- `ai-dev/active/F-00061/reports/F-00061_S01_Database_report.md` — for the migration revision id the new model is committed under
- `orch/db/models.py` — the new `QvBaseline` class (S01); you only READ it here, the DB wiring happens in S05
- `orch/config.py` — existing `DaemonConfig` dataclass and `_require`/`load_config` pattern (lines ~27–115)
- `orch/CLAUDE.md` — layer conventions
- `orch/daemon/CLAUDE.md` (if present) — daemon-specific patterns
- Representative gate output samples to design your parsers against:
  - Ruff: `uv run ruff check --output-format json .` (capture a small sample from a branch with known violations)
  - Pytest: `uv run pytest tests/unit/... -q 2>&1` (the `FAILED` lines + `short test summary info` block)
  - Mypy: `uv run mypy orch/ 2>&1` (the `file:line: error: ... [error-code]` lines)

## Output Files

- New: `orch/daemon/qv_baseline.py` — pure module (no DB calls, no long-lived state)
- Modified: `orch/config.py` — add `IW_CORE_BASELINE_QV` parsing + `baseline_qv_enabled: bool` on `DaemonConfig`
- `ai-dev/active/F-00061/reports/F-00061_S03_Backend_QvBaseline_report.md` — step report

**Explicitly out of scope for this step:**
- `orch/daemon/batch_manager.py` (hook wiring — S05)
- `orch/daemon/fix_cycle.py` (subtraction integration — S05)
- Any test file (S07)

## Context

You are implementing the PURE core of F-00061: parsers, fingerprints, and the subtraction algebra. Keeping this module side-effect-free (no DB, no daemon state) lets S07 exhaustively unit-test it without testcontainers and lets S05 wire the plumbing without reinventing the logic. The integration into the daemon's control flow is S05's job — your job is to produce correct, deterministic building blocks.

## Requirements

### 1. Module layout: `orch/daemon/qv_baseline.py`

Public surface (everything else MUST be private `_name`):

```python
@dataclass(frozen=True)
class FailureEntry:
    """One canonical failure identifier from a QV gate."""
    kind: str      # "lint" | "test" | "typecheck" | "unknown"
    key: str       # Stable identifier (e.g. "<file>::<rule>" for ruff, pytest nodeid, mypy "<file>:<code>")

@dataclass(frozen=True)
class Fingerprint:
    """Canonical failure set from a QV gate."""
    failures: tuple[FailureEntry, ...]   # Always sorted by (kind, key)
    unparseable: tuple[str, ...] = ()    # Raw lines the parser could not classify; see Boundary Behavior row 3

def parse_ruff(raw_output: str) -> Fingerprint: ...
def parse_pytest(raw_output: str) -> Fingerprint: ...
def parse_mypy(raw_output: str) -> Fingerprint: ...

GATE_PARSERS: Mapping[str, Callable[[str], Fingerprint]] = {
    "lint": parse_ruff,
    "typecheck": parse_mypy,
    "unit-tests": parse_pytest,
    "integration-tests": parse_pytest,
    "frontend-tests": parse_pytest,  # best-effort; if pytest-incompatible, returns Fingerprint(unparseable=(raw,))
}
# NOTE: "format" (ruff format --check) is intentionally absent. Its output shape
# ("Would reformat: <file>") differs completely from `ruff check` and would route
# every finding into `unparseable`, which always surfaces — breaking AC1 for S11.
# Unknown gates fall through to legacy behaviour in S05's subtraction path, which
# is the correct semantics: the format gate is all-or-nothing against a fully-
# formatted codebase, so pre-existing format drift is typically zero anyway.

def fingerprint_to_jsonable(fp: Fingerprint) -> dict: ...
def fingerprint_from_jsonable(data: dict) -> Fingerprint: ...

def subtract(current: Fingerprint, baseline: Fingerprint) -> Fingerprint:
    """Return a new Fingerprint containing every failure in `current` that is NOT in `baseline`.
    Preserves the order from `current` (important for Invariant 4 — stable fix-cycle prompt output).
    """
```

### 2. Parser implementation details

- **`parse_ruff`**: Handles `ruff check` output ONLY (NOT `ruff format --check`, which has a different shape and is deliberately excluded from `GATE_PARSERS`). Accept BOTH Ruff's JSON output (`--output-format json`) and its default text output. Key for each violation: `"<relative_file>::<rule_code>"` (no line number — see Boundary Behavior row 4).
- **`parse_pytest`**: Extract each `FAILED tests/path/test_mod.py::TestClass::test_name - ...` line's nodeid. Key: the nodeid itself. Ignore the trailing error message (Boundary Behavior row 5). If pytest output contains only a summary line and no explicit `FAILED ...` lines (e.g. xdist worker crash), treat the whole section as unparseable.
- **`parse_mypy`**: Lines of the form `path/file.py:42: error: Message [error-code]`. Key: `"<file>::<error_code>"` (NOT including line number or message — so drift in code doesn't spuriously invalidate).
- **Determinism** (Invariant 6): The output `Fingerprint.failures` tuple MUST be sorted by `(kind, key)`. Two calls on the same input produce byte-identical `fingerprint_to_jsonable(...)` dicts.
- **Unparseable handling** (Boundary Behavior row 3): If a line in the failure section doesn't match the expected regex, drop it into `Fingerprint.unparseable`. `subtract` treats `unparseable` entries as never-matching — they ALWAYS surface in the delta (fail-safe: if we can't classify it, assume it's a new problem).

### 3. `subtract(current, baseline)` algebra

Implementation skeleton:

```python
def subtract(current: Fingerprint, baseline: Fingerprint) -> Fingerprint:
    baseline_keys = frozenset((f.kind, f.key) for f in baseline.failures)
    kept = tuple(f for f in current.failures if (f.kind, f.key) not in baseline_keys)
    # Unparseable entries always surface
    return Fingerprint(failures=kept, unparseable=current.unparseable)
```

Invariants that MUST hold (will be verified in S07 and S06 review):
- `subtract(H, Fingerprint(()))` returns `H` (identity)
- `subtract(H, H).failures == ()` (but `unparseable` is preserved from `current`)
- `subtract(H, B).failures` is a prefix-subset of `H.failures` in the original order (stability)

### 4. JSON serialization

`fingerprint_to_jsonable` and `fingerprint_from_jsonable` MUST round-trip: `fp == fingerprint_from_jsonable(fingerprint_to_jsonable(fp))` for any `Fingerprint`. Chosen schema (matches the `fingerprint` JSONB default from S01):

```json
{
  "failures": [{"kind": "test", "key": "tests/unit/foo.py::test_bar"}, ...],
  "unparseable": ["raw line 1", "raw line 2"]
}
```

### 5. Config wiring in `orch/config.py`

Follow the existing `IW_CORE_*` style (see `load_config()` lines ~89–110):
- Add `baseline_qv_enabled: bool = True` to `DaemonConfig` (default ON so the feature rolls out active; AC5 lets operators flip it)
- In `load_config()`, parse `os.environ.get("IW_CORE_BASELINE_QV", "true")` with the same truthy semantics used elsewhere in the file (normalize to lowercase and compare against `{"1", "true", "yes", "on"}`)
- Do NOT use `importlib.reload(orch.config)` anywhere (tests use `monkeypatch.setenv`)

### 6. Tests deferred to S07

Do NOT write tests in this step. Your module should be written in a style that makes S07's unit tests trivial (pure functions, no hidden globals, no subprocess spawning from within the module — `compute_baseline` is S05's job, not yours). Note: `compute_baseline` as a function that launches subprocesses is intentionally NOT in this module's surface; S05 owns that by composing your parsers with the daemon's existing subprocess machinery.

## Project Conventions

Follow `orch/CLAUDE.md`. Key rules for this step:
- Module-level imports at top, no `from X import Y` inside functions unless cyclic-import-avoidance demands it
- Type hints on every public function; mypy must pass on this module
- No global mutable state — all functions are pure

## TDD Requirement

S07 owns the test suite — but your module must be designed for testability:
- Pure functions, no hidden side effects
- No reliance on the daemon's subprocess-run helpers in this module
- Representative output samples used in design should be copy-pasteable into S07's fixture files

If writing a quick REPL scratchpad helps you sanity-check a parser, run it ad-hoc via `uv run python -c "..."` — but delete the scratchpad before committing.

## Test Verification (NON-NEGOTIABLE)

Before reporting complete:
1. `uv run mypy orch/daemon/qv_baseline.py orch/config.py` — zero errors
2. `uv run ruff check orch/daemon/qv_baseline.py orch/config.py` — zero errors on changed lines (pre-existing errors OK; do NOT touch them — scope gate will block drive-by fixes)
3. `uv run ruff format --check orch/daemon/qv_baseline.py orch/config.py` — clean
4. A quick ad-hoc smoke on each parser via `uv run python -c "from orch.daemon.qv_baseline import parse_ruff; print(parse_ruff(open('/tmp/ruff_sample.txt').read()))"` — it returns a sensible `Fingerprint`

## Subagent Result Contract

```json
{
  "step": "S03",
  "agent": "backend-impl",
  "work_item": "F-00061",
  "completion_status": "complete|partial|blocked",
  "files_changed": [
    "orch/daemon/qv_baseline.py",
    "orch/config.py"
  ],
  "tests_passed": true,
  "test_summary": "mypy clean; ruff clean; ruff-format clean; parser smoke tests pass",
  "blockers": [],
  "notes": ""
}
```
